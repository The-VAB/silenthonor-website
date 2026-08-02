//! `/api/auth/*` -- login, me, logout.
//!
//! Faithful port of backend/routers/auth.py: same cookies (`access_token`,
//! `refresh_token`), same JSON response shapes, same status codes. Brute-force
//! lockout and the register/refresh/password-reset routes are tracked for the
//! auth-hardening follow-up (see docs/RUST_BACKEND.md).

use axum::extract::State;
use axum::http::header::SET_COOKIE;
use axum::http::{HeaderMap, HeaderValue};
use axum::response::{IntoResponse, Response};
use axum::Json;
use bson::oid::ObjectId;
use bson::{doc, Document};
use serde::Deserialize;
use serde_json::{json, Value};

use sh_core::auth::{
    create_access_token, create_refresh_token, hash_password, verify_password, verify_token,
};
use sh_core::models::User;
use sh_core::{AppError, AppResult};

use super::{clear_cookie, cookie_value, set_cookie};
use crate::state::AppState;

const ACCESS_MAX_AGE: i64 = 3600; // 1 hour
const REFRESH_MAX_AGE: i64 = 2_592_000; // 30 days

#[derive(Debug, Deserialize)]
pub struct LoginRequest {
    pub email: String,
    #[serde(default)]
    pub password: String,
}

pub async fn login(
    State(state): State<AppState>,
    Json(body): Json<LoginRequest>,
) -> AppResult<Response> {
    let email = body.email.trim().to_lowercase();
    if email.is_empty() || body.password.is_empty() {
        return Err(AppError::BadRequest(
            "Email and password are required".to_string(),
        ));
    }

    let users = state.db.collection::<User>("users");
    let user = users
        .find_one(doc! { "email": email.as_str() })
        .await?
        .ok_or(AppError::AuthFailed)?;

    if !verify_password(&body.password, &user.password_hash) {
        return Err(AppError::AuthFailed);
    }
    if user.is_deactivated() {
        return Err(AppError::Forbidden(
            "This account has been deactivated. Please contact Silent Honor Foundation for assistance."
                .to_string(),
        ));
    }

    let id = user.id.map(|o| o.to_hex()).unwrap_or_default();
    let access = create_access_token(&state.config.jwt_secret, &id, &email)?;
    let refresh = create_refresh_token(&state.config.jwt_secret, &id)?;

    let profile = user.to_profile(&id);
    let resp = Json(profile).into_response();
    Ok(with_auth_cookies(
        resp,
        &access,
        &refresh,
        state.config.cookie_secure,
    ))
}

/// Signup payload. Mirrors backend/server.py `RegisterRequest`; every field past
/// the four required ones is optional (the signup form only sends a subset).
#[derive(Debug, Deserialize)]
pub struct RegisterRequest {
    pub email: String,
    #[serde(default)]
    pub password: String,
    #[serde(default)]
    pub first_name: String,
    #[serde(default)]
    pub last_name: String,
    #[serde(default)]
    pub phone: Option<String>,
    #[serde(default)]
    pub state: Option<String>,
    #[serde(default)]
    pub branch: Option<String>,
    #[serde(default)]
    pub service_status: Option<String>,
    #[serde(default)]
    pub years_of_service: Option<String>,
    #[serde(default)]
    pub separation_year: Option<String>,
    #[serde(default)]
    pub dob: Option<String>,
    #[serde(default)]
    pub how_heard: Option<String>,
    #[serde(default)]
    pub challenges: Option<Vec<String>>,
    #[serde(default)]
    pub notes: Option<String>,
    #[serde(default)]
    pub consent_contact: Option<bool>,
}

/// `POST /api/auth/register` -- port of backend/server.py `register`.
///
/// Creates a LIVE member account (so signup immediately reaches the dashboard),
/// marked `verified=false` / `dd214_status="pending"` -- i.e. awaiting admin
/// provisioning. (Phase 2: auto-provision via DD-214 OCR.) Sets the same auth
/// cookies as login and returns the user profile.
pub async fn register(
    State(state): State<AppState>,
    Json(body): Json<RegisterRequest>,
) -> AppResult<Response> {
    let email = body.email.trim().to_lowercase();
    let first_name = body.first_name.trim().to_string();
    let last_name = body.last_name.trim().to_string();

    if email.is_empty() || body.password.is_empty() || first_name.is_empty() || last_name.is_empty()
    {
        return Err(AppError::BadRequest(
            "Email, password, first name and last name are required".to_string(),
        ));
    }
    if body.password.len() < 8 {
        return Err(AppError::BadRequest(
            "Password must be at least 8 characters".to_string(),
        ));
    }

    let users = state.db.collection::<Document>("users");
    if users
        .find_one(doc! { "email": email.as_str() })
        .await?
        .is_some()
    {
        return Err(AppError::BadRequest("Email already registered".to_string()));
    }

    let password_hash = hash_password(&body.password)?;
    let now = bson::DateTime::now();
    let challenges =
        bson::to_bson(&body.challenges.clone().unwrap_or_default()).unwrap_or(bson::Bson::Array(vec![]));

    // Insert as a raw document so every field the Python backend stores (phone,
    // state, notes, ...) is preserved even though the typed `User` reads a subset.
    let user_doc = doc! {
        "email": email.as_str(),
        "password_hash": password_hash.as_str(),
        "auth_provider": "password",
        "first_name": first_name.as_str(),
        "last_name": last_name.as_str(),
        "dob": opt_str(&body.dob),
        "phone": opt_str(&body.phone),
        "state": opt_str(&body.state),
        "branch": opt_str(&body.branch),
        "service_status": opt_str(&body.service_status),
        "years_of_service": opt_str(&body.years_of_service),
        "separation_year": opt_str(&body.separation_year),
        "how_heard": opt_str(&body.how_heard),
        "challenges": challenges,
        "notes": opt_str(&body.notes),
        "consent_contact": body.consent_contact.unwrap_or(false),
        "role": "member",
        "verified": false,
        "dd214_file": bson::Bson::Null,
        "dd214_status": "pending",
        "pipeline_stage": "applied",
        "created_at": now,
    };

    let inserted = users.insert_one(user_doc).await?;
    let id = inserted
        .inserted_id
        .as_object_id()
        .map(|o| o.to_hex())
        .unwrap_or_default();

    let access = create_access_token(&state.config.jwt_secret, &id, &email)?;
    let refresh = create_refresh_token(&state.config.jwt_secret, &id)?;

    // Fire the same two signup emails the Python backend sends, non-blocking
    // (mirrors asyncio.create_task): welcome to the member + admin notification.
    let na = |o: &Option<String>| {
        o.clone()
            .filter(|s| !s.is_empty())
            .unwrap_or_else(|| "N/A".to_string())
    };
    let challenges_display = match &body.challenges {
        Some(v) if !v.is_empty() => v.join(", "),
        _ => "Not specified".to_string(),
    };
    // AWAIT the sends: a Lambda freezes its execution environment the moment the
    // handler returns, so fire-and-forget (which the always-warm App Runner
    // backend uses) would leave the mail unsent. send_* swallow their own errors,
    // so a mail failure never fails signup. Both sends run concurrently.
    let (phone, branch) = (na(&body.phone), na(&body.branch));
    let (svc, st) = (na(&body.service_status), na(&body.state));
    tokio::join!(
        sh_core::email::send_welcome_email(&email, &first_name),
        sh_core::email::send_new_membership_notification(
            &first_name, &last_name, &email, &phone, &branch, &svc, &st, &challenges_display,
        ),
    );

    let profile = json!({
        "id": id,
        "_id": id,
        "email": email,
        "first_name": first_name,
        "last_name": last_name,
        "role": "member",
        "roles": ["member"],
        "verified": false,
        "pipeline_stage": "applied",
        "dd214_status": "pending",
        "dd214_file": Value::Null,
        "branch": body.branch,
        "service_status": body.service_status,
        "created_at": now.timestamp_millis(),
    });

    let resp = Json(profile).into_response();
    Ok(with_auth_cookies(
        resp,
        &access,
        &refresh,
        state.config.cookie_secure,
    ))
}

fn opt_str(v: &Option<String>) -> bson::Bson {
    match v {
        Some(s) if !s.is_empty() => bson::Bson::String(s.clone()),
        _ => bson::Bson::Null,
    }
}

pub async fn me(State(state): State<AppState>, headers: HeaderMap) -> AppResult<Json<Value>> {
    let token = cookie_value(&headers, "access_token").ok_or(AppError::Unauthorized)?;
    let claims =
        verify_token(&state.config.jwt_secret, &token).map_err(|_| AppError::Unauthorized)?;

    // Reject blacklisted (logged-out) tokens.
    let blacklisted = state
        .db
        .collection::<Document>("token_blacklist")
        .find_one(doc! { "token": token.as_str() })
        .await?
        .is_some();
    if blacklisted {
        return Err(AppError::Unauthorized);
    }

    let oid = ObjectId::parse_str(&claims.sub).map_err(|_| AppError::Unauthorized)?;
    let user = state
        .db
        .collection::<User>("users")
        .find_one(doc! { "_id": oid })
        .await?
        .ok_or(AppError::Unauthorized)?;

    Ok(Json(user.to_profile(&claims.sub)))
}

pub async fn logout(State(state): State<AppState>, headers: HeaderMap) -> AppResult<Response> {
    if let Some(token) = cookie_value(&headers, "access_token") {
        if let Ok(claims) = verify_token(&state.config.jwt_secret, &token) {
            let expires = bson::DateTime::from_millis((claims.exp as i64) * 1000);
            let _ = state
                .db
                .collection::<Document>("token_blacklist")
                .insert_one(doc! {
                    "token": token.as_str(),
                    "user_id": claims.sub.as_str(),
                    "expires_at": expires,
                })
                .await;
        }
    }

    let mut resp = Json(json!({ "message": "Logged out successfully" })).into_response();
    let secure = state.config.cookie_secure;
    append_cookie(&mut resp, &clear_cookie("access_token", secure));
    append_cookie(&mut resp, &clear_cookie("refresh_token", secure));
    Ok(resp)
}

// ── POST /api/auth/refresh -- mint a new access token from the refresh cookie ──
pub async fn refresh(State(state): State<AppState>, headers: HeaderMap) -> AppResult<Response> {
    let token = cookie_value(&headers, "refresh_token").ok_or(AppError::Unauthorized)?;
    let claims =
        verify_token(&state.config.jwt_secret, &token).map_err(|_| AppError::Unauthorized)?;
    if claims.token_type != "refresh" {
        return Err(AppError::Unauthorized);
    }
    let oid = ObjectId::parse_str(&claims.sub).map_err(|_| AppError::Unauthorized)?;
    let user = state
        .db
        .collection::<User>("users")
        .find_one(doc! { "_id": oid })
        .await?
        .ok_or(AppError::Unauthorized)?;
    let id = user.id.map(|o| o.to_hex()).unwrap_or(claims.sub);
    let access = create_access_token(&state.config.jwt_secret, &id, &user.email)?;

    let mut resp = Json(json!({ "message": "Token refreshed" })).into_response();
    append_cookie(
        &mut resp,
        &set_cookie("access_token", &access, ACCESS_MAX_AGE, state.config.cookie_secure),
    );
    Ok(resp)
}

#[derive(Debug, Deserialize)]
pub struct ForgotPasswordRequest {
    pub email: String,
}

// ── POST /api/auth/forgot-password -- always 200 (no email enumeration) ───────
pub async fn forgot_password(
    State(state): State<AppState>,
    Json(body): Json<ForgotPasswordRequest>,
) -> AppResult<Json<Value>> {
    let email = body.email.trim().to_lowercase();
    if let Some(user) = state
        .db
        .collection::<User>("users")
        .find_one(doc! { "email": email.as_str() })
        .await?
    {
        let token = gen_reset_token();
        let expires = bson::DateTime::from_millis(bson::DateTime::now().timestamp_millis() + 3_600_000);
        let _ = state
            .db
            .collection::<Document>("password_reset_tokens")
            .insert_one(doc! {
                "token": token.as_str(),
                "user_id": user.id,
                "email": email.as_str(),
                "expires_at": expires,
                "used": false,
            })
            .await;
        let first_name = user.first_name.clone().unwrap_or_else(|| "Member".to_string());
        // Awaited (Lambda freezes on return); send_* swallow their own errors.
        sh_core::email::send_password_reset_email(&email, &first_name, &token).await;
    }
    Ok(Json(json!({
        "message": "If an account exists with this email, a reset link has been sent."
    })))
}

#[derive(Debug, Deserialize)]
pub struct ResetPasswordRequest {
    pub token: String,
    #[serde(default)]
    pub new_password: String,
}

// ── POST /api/auth/reset-password -- consume a one-time token, set new password ─
pub async fn reset_password(
    State(state): State<AppState>,
    Json(body): Json<ResetPasswordRequest>,
) -> AppResult<Json<Value>> {
    if body.new_password.len() < 8 {
        return Err(AppError::BadRequest(
            "Password must be at least 8 characters".to_string(),
        ));
    }
    let tokens = state.db.collection::<Document>("password_reset_tokens");
    let reset_doc = tokens
        .find_one(doc! {
            "token": body.token.as_str(),
            "used": false,
            "expires_at": { "$gt": bson::DateTime::now() },
        })
        .await?
        .ok_or_else(|| AppError::BadRequest("Invalid or expired reset token".to_string()))?;

    let new_hash = hash_password(&body.new_password)?;
    if let Ok(uid) = reset_doc.get_object_id("user_id") {
        state
            .db
            .collection::<Document>("users")
            .update_one(
                doc! { "_id": uid },
                doc! { "$set": { "password_hash": new_hash.as_str() } },
            )
            .await?;
    }
    if let Ok(tid) = reset_doc.get_object_id("_id") {
        tokens
            .update_one(doc! { "_id": tid }, doc! { "$set": { "used": true } })
            .await?;
    }
    Ok(Json(json!({ "message": "Password reset successfully" })))
}

#[derive(Debug, Deserialize)]
pub struct ChangePasswordRequest {
    #[serde(default)]
    pub current_password: String,
    #[serde(default)]
    pub new_password: String,
}

// ── POST /api/auth/change-password -- authenticated password change ───────────
pub async fn change_password(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(body): Json<ChangePasswordRequest>,
) -> AppResult<Json<Value>> {
    let (id, user) = super::authenticate(&state, &headers).await?;
    if !verify_password(&body.current_password, &user.password_hash) {
        return Err(AppError::BadRequest("Current password is incorrect".to_string()));
    }
    if body.new_password.len() < 8 {
        return Err(AppError::BadRequest(
            "Password must be at least 8 characters".to_string(),
        ));
    }
    let oid = ObjectId::parse_str(&id).map_err(|_| AppError::Unauthorized)?;
    let new_hash = hash_password(&body.new_password)?;
    state
        .db
        .collection::<Document>("users")
        .update_one(
            doc! { "_id": oid },
            doc! { "$set": { "password_hash": new_hash.as_str() } },
        )
        .await?;
    Ok(Json(json!({ "message": "Password changed successfully" })))
}

/// URL-safe one-time reset token (hex of 32 random bytes; Python used token_urlsafe(32)).
fn gen_reset_token() -> String {
    let mut buf = [0u8; 32];
    getrandom::getrandom(&mut buf).expect("system RNG");
    buf.iter().map(|b| format!("{b:02x}")).collect()
}

fn with_auth_cookies(mut resp: Response, access: &str, refresh: &str, secure: bool) -> Response {
    append_cookie(
        &mut resp,
        &set_cookie("access_token", access, ACCESS_MAX_AGE, secure),
    );
    append_cookie(
        &mut resp,
        &set_cookie("refresh_token", refresh, REFRESH_MAX_AGE, secure),
    );
    resp
}

fn append_cookie(resp: &mut Response, value: &str) {
    if let Ok(v) = HeaderValue::from_str(value) {
        resp.headers_mut().append(SET_COOKIE, v);
    }
}

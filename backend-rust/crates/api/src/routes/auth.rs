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

use sh_core::auth::{create_access_token, create_refresh_token, verify_password, verify_token};
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

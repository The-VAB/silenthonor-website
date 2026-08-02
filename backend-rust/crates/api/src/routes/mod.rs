//! HTTP routing + small cookie helpers shared by handlers.

pub mod admin;
pub mod auth;
pub mod content;
pub mod health;
pub mod major_finance;
pub mod members;

use axum::extract::Request;
use axum::http::{HeaderMap, Method, StatusCode};
use axum::middleware::{self, Next};
use axum::response::{IntoResponse, Response};
use axum::routing::{get, post, put};
use axum::Router;
use serde_json::Value;

use bson::oid::ObjectId;
use bson::{doc, Document};
use sh_core::auth::verify_token;
use sh_core::models::User;
use sh_core::{AppError, AppResult};

use crate::state::AppState;

/// Build the full application router. Paths mirror the current FastAPI service
/// exactly so the frontend can be pointed at either backend.
pub fn router(state: AppState) -> Router {
    Router::new()
        .route("/health", get(health::health))
        .route("/api/health", get(health::health))
        .route("/api/auth/register", post(auth::register))
        .route("/api/auth/login", post(auth::login))
        .route("/api/auth/me", get(auth::me))
        .route("/api/auth/logout", post(auth::logout))
        .route("/api/auth/refresh", post(auth::refresh))
        .route("/api/auth/forgot-password", post(auth::forgot_password))
        .route("/api/auth/reset-password", post(auth::reset_password))
        .route("/api/auth/change-password", post(auth::change_password))
        .route("/api/contact", post(content::contact))
        .route("/api/admin/stats", get(admin::stats))
        .route("/api/admin/members", get(admin::members))
        .route("/api/admin/members/:member_id/verify", post(admin::verify_member))
        .route(
            "/api/admin/courses",
            get(admin::list_courses).post(admin::create_course),
        )
        .route(
            "/api/admin/courses/:course_id",
            put(admin::update_course).delete(admin::delete_course),
        )
        .route("/api/admin/contacts", get(admin::list_contacts))
        .route(
            "/api/admin/contacts/:contact_id",
            put(admin::update_contact).delete(admin::delete_contact),
        )
        .route("/api/admin/dd214/:filename", get(admin::download_dd214))
        // DD-214 upload -- registered under every path the frontend/backend use.
        .route("/api/upload/dd214", post(members::upload_dd214))
        .route("/api/member/upload/dd214", post(members::upload_dd214))
        .route("/api/member/dd214", post(members::upload_dd214))
        .route(
            "/api/member/profile",
            get(members::get_profile).put(members::update_profile),
        )
        .route("/api/member/counselor", get(members::counselor))
        .route("/api/member/dashboard", get(members::dashboard))
        .route("/api/member/courses", get(members::courses))
        .route(
            "/api/member/courses/:course_id/progress",
            post(members::update_progress),
        )
        .route(
            "/api/member/financial-intake",
            get(members::get_financial_intake).post(members::save_financial_intake),
        )
        .route(
            "/api/member/major-finance/status",
            get(major_finance::status),
        )
        .route("/api/member/major-finance", post(major_finance::chat))
        .layer(middleware::from_fn(preflight_ok))
        .with_state(state)
}

/// CORS preflight handler. The API Gateway `ANY /{proxy+}` route forwards OPTIONS
/// to the Lambda, so axum would 405 it (handlers declare no OPTIONS) and a browser
/// preflight would fail. Short-circuit every OPTIONS with 204; API Gateway's
/// cors_configuration attaches the Access-Control-* headers to the response.
async fn preflight_ok(req: Request, next: Next) -> Response {
    if req.method() == Method::OPTIONS {
        return StatusCode::NO_CONTENT.into_response();
    }
    next.run(req).await
}

/// Read a single cookie value out of the request `Cookie` header.
pub fn cookie_value(headers: &HeaderMap, name: &str) -> Option<String> {
    let raw = headers.get(http::header::COOKIE)?.to_str().ok()?;
    let prefix = format!("{name}=");
    raw.split(';')
        .map(str::trim)
        .find_map(|part| part.strip_prefix(&prefix).map(|v| v.to_string()))
}

/// A `Set-Cookie` value matching the current backend's auth cookies
/// (HttpOnly, SameSite=None so the cross-origin frontend can send it with
/// `credentials: "include"`; Secure in prod).
pub fn set_cookie(name: &str, value: &str, max_age: i64, secure: bool) -> String {
    let secure = if secure { "; Secure" } else { "" };
    format!("{name}={value}; HttpOnly{secure}; SameSite=None; Path=/; Max-Age={max_age}")
}

pub fn clear_cookie(name: &str, secure: bool) -> String {
    let secure = if secure { "; Secure" } else { "" };
    format!("{name}=; HttpOnly{secure}; SameSite=None; Path=/; Max-Age=0")
}

/// Authenticate a request from its `access_token` cookie: verify the JWT, reject
/// blacklisted (logged-out) tokens, and load the user. Returns the user id (hex)
/// and the full user record. Every protected handler starts with this.
pub async fn authenticate(state: &AppState, headers: &HeaderMap) -> AppResult<(String, User)> {
    let token = cookie_value(headers, "access_token").ok_or(AppError::Unauthorized)?;
    let claims =
        verify_token(&state.config.jwt_secret, &token).map_err(|_| AppError::Unauthorized)?;

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
    Ok((claims.sub, user))
}

/// Authenticate + require the `admin` role (matches get_current_admin). Roles are
/// read from the `roles` array if present, else the single `role` field.
pub async fn authenticate_admin(state: &AppState, headers: &HeaderMap) -> AppResult<(String, User)> {
    let (id, user) = authenticate(state, headers).await?;
    if !user.effective_roles().iter().any(|r| r == "admin") {
        return Err(AppError::Forbidden("Admin access required".to_string()));
    }
    Ok((id, user))
}

/// Best-effort audit-log write (mirrors log_audit_event -> db.audit_log). Never
/// fails the request.
pub async fn log_audit(
    state: &AppState,
    action: &str,
    entity_type: &str,
    entity_id: Option<&str>,
    user_email: Option<&str>,
) {
    let _ = state
        .db
        .collection::<Document>("audit_log")
        .insert_one(doc! {
            "action": action,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "user_email": user_email,
            "details": {},
            "timestamp": bson::DateTime::now(),
        })
        .await;
}

/// Serialize a BSON datetime as an ISO-8601 string (or JSON null), matching the
/// Python backend's `.isoformat()`.
pub fn iso(dt: Option<bson::DateTime>) -> Value {
    match dt.and_then(|d| d.try_to_rfc3339_string().ok()) {
        Some(s) => Value::String(s),
        None => Value::Null,
    }
}

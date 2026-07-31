//! HTTP routing + small cookie helpers shared by handlers.

pub mod auth;
pub mod health;
pub mod members;

use axum::http::HeaderMap;
use axum::routing::{get, post};
use axum::Router;

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
        .route("/api/auth/login", post(auth::login))
        .route("/api/auth/me", get(auth::me))
        .route("/api/auth/logout", post(auth::logout))
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
        .with_state(state)
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

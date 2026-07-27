//! HTTP routing + small cookie helpers shared by handlers.

pub mod auth;
pub mod health;

use axum::http::HeaderMap;
use axum::routing::{get, post};
use axum::Router;

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

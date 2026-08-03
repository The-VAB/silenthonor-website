//! Single application error type that renders to the same JSON shape the current
//! FastAPI backend uses (`{ "detail": "..." }`), so the existing frontend keeps
//! working unchanged during the migration.

use axum::http::StatusCode;
use axum::response::{IntoResponse, Response};
use axum::Json;
use serde_json::json;

pub type AppResult<T> = Result<T, AppError>;

#[derive(Debug, thiserror::Error)]
pub enum AppError {
    #[error("unauthorized")]
    Unauthorized,
    /// Wrong email/password on login -- distinct message from a missing session.
    #[error("invalid credentials")]
    AuthFailed,
    #[error("forbidden: {0}")]
    Forbidden(String),
    #[error("not found")]
    NotFound,
    #[error("bad request: {0}")]
    BadRequest(String),
    #[error("conflict: {0}")]
    Conflict(String),
    /// A feature isn't configured (e.g. Google sign-in with no client id). 503.
    #[error("service unavailable: {0}")]
    ServiceUnavailable(String),
    /// Anything unexpected. The detail is logged, never returned to the client.
    #[error(transparent)]
    Internal(#[from] anyhow::Error),
}

impl AppError {
    fn parts(&self) -> (StatusCode, String) {
        match self {
            AppError::Unauthorized => (StatusCode::UNAUTHORIZED, "Not authenticated".to_string()),
            AppError::AuthFailed => (
                StatusCode::UNAUTHORIZED,
                "Invalid email or password".to_string(),
            ),
            AppError::Forbidden(m) => (StatusCode::FORBIDDEN, m.clone()),
            AppError::NotFound => (StatusCode::NOT_FOUND, "Not found".to_string()),
            AppError::BadRequest(m) => (StatusCode::BAD_REQUEST, m.clone()),
            AppError::Conflict(m) => (StatusCode::CONFLICT, m.clone()),
            AppError::ServiceUnavailable(m) => (StatusCode::SERVICE_UNAVAILABLE, m.clone()),
            AppError::Internal(e) => {
                tracing::error!(error = ?e, "internal error");
                (
                    StatusCode::INTERNAL_SERVER_ERROR,
                    "Internal server error".to_string(),
                )
            }
        }
    }
}

impl IntoResponse for AppError {
    fn into_response(self) -> Response {
        let (status, detail) = self.parts();
        (status, Json(json!({ "detail": detail }))).into_response()
    }
}

/// Convenience: turn a MongoDB error into an `Internal` app error.
impl From<mongodb::error::Error> for AppError {
    fn from(e: mongodb::error::Error) -> Self {
        AppError::Internal(e.into())
    }
}

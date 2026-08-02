//! Public content endpoints. Port of routers/content.py (the pieces the static
//! site uses). Currently: POST /api/contact.

use axum::extract::State;
use axum::Json;
use bson::{doc, Bson, Document};
use serde::Deserialize;
use serde_json::{json, Value};

use crate::state::AppState;
use sh_core::{AppError, AppResult};

#[derive(Debug, Deserialize)]
pub struct ContactRequest {
    #[serde(default)]
    pub first_name: String,
    #[serde(default)]
    pub last_name: String,
    pub email: String,
    #[serde(default)]
    pub branch: Option<String>,
    #[serde(default)]
    pub status: Option<String>,
    #[serde(default)]
    pub topic: Option<String>,
    #[serde(default)]
    pub message: String,
}

fn opt(v: &Option<String>) -> Bson {
    match v {
        Some(s) if !s.is_empty() => Bson::String(s.clone()),
        _ => Bson::Null,
    }
}

/// POST /api/contact -- store a contact-form submission. Public. Mirrors the
/// Python handler's document shape exactly.
pub async fn contact(
    State(state): State<AppState>,
    Json(body): Json<ContactRequest>,
) -> AppResult<Json<Value>> {
    if body.first_name.trim().is_empty()
        || body.last_name.trim().is_empty()
        || body.email.trim().is_empty()
        || body.message.trim().is_empty()
    {
        return Err(AppError::BadRequest(
            "first_name, last_name, email and message are required".to_string(),
        ));
    }
    let contact_doc = doc! {
        "first_name": body.first_name.trim(),
        "last_name": body.last_name.trim(),
        "email": body.email.trim().to_lowercase(),
        "branch": opt(&body.branch),
        "status": opt(&body.status),
        "topic": opt(&body.topic),
        "message": body.message.as_str(),
        "created_at": bson::DateTime::now(),
        "responded": false,
    };
    state
        .db
        .collection::<Document>("contacts")
        .insert_one(contact_doc)
        .await?;
    Ok(Json(json!({
        "message": "Message received. We'll be in touch within 2-3 business days."
    })))
}

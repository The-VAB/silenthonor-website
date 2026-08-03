//! Public content endpoints. Port of routers/content.py (the pieces the static
//! site uses). Currently: POST /api/contact.

use axum::extract::State;
use axum::Json;
use bson::{doc, Bson, Document};
use serde::Deserialize;
use serde_json::{json, Value};

use super::{ddate, dstr_or, hex_id};
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

/// GET /api/announcements -- PUBLIC. Active, non-expired announcements, newest first.
pub async fn announcements(State(state): State<AppState>) -> AppResult<Json<Value>> {
    let mut cur = state
        .db
        .collection::<Document>("announcements")
        .find(doc! {
            "active": true,
            "$or": [ { "expires_at": Bson::Null }, { "expires_at": { "$gt": bson::DateTime::now() } } ],
        })
        .sort(doc! { "created_at": -1 })
        .limit(20)
        .await?;
    let mut out: Vec<Value> = Vec::new();
    while cur.advance().await? {
        let a = cur.deserialize_current()?;
        out.push(json!({
            "id": hex_id(&a),
            "title": dstr_or(&a, "title", ""),
            "content": dstr_or(&a, "content", ""),
            "type": dstr_or(&a, "type", "info"),
            "created_at": ddate(&a, "created_at"),
        }));
    }
    Ok(Json(json!(out)))
}

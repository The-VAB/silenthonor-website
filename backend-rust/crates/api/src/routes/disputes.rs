//! Disputes (`/api/disputes`, member scope). Port of routers/disputes.py.
//! Collection `disputes`, scoped `{ user_id: <auth user> }`. Create/update/delete
//! write the audit log.

use axum::extract::{Path, State};
use axum::http::HeaderMap;
use axum::Json;
use bson::oid::ObjectId;
use bson::{doc, Bson, Document};
use serde_json::{json, Value};

use super::{authenticate, body_bson, body_str, ddate, draw, dstr_or, hex_id, log_audit, parse_iso};
use crate::state::AppState;
use sh_core::{AppError, AppResult};

fn uid(id: &str) -> AppResult<ObjectId> {
    ObjectId::parse_str(id).map_err(|_| AppError::Unauthorized)
}

// GET /api/disputes
pub async fn list(State(state): State<AppState>, headers: HeaderMap) -> AppResult<Json<Value>> {
    let (id, _) = authenticate(&state, &headers).await?;
    let oid = uid(&id)?;
    let mut cur = state
        .db
        .collection::<Document>("disputes")
        .find(doc! { "user_id": oid })
        .sort(doc! { "created_at": -1 })
        .limit(100)
        .await?;
    let mut out: Vec<Value> = Vec::new();
    while cur.advance().await? {
        let d = cur.deserialize_current()?;
        out.push(json!({
            "id": hex_id(&d),
            "bureau": dstr_or(&d, "bureau", ""),
            "account_name": dstr_or(&d, "account_name", ""),
            "account_number": dstr_or(&d, "account_number", ""),
            "dispute_reason": dstr_or(&d, "dispute_reason", ""),
            "status": dstr_or(&d, "status", "pending"),
            "date_sent": ddate(&d, "date_sent"),
            "date_response": ddate(&d, "date_response"),
            "response_outcome": draw(&d, "response_outcome"),
            "tracking_number": draw(&d, "tracking_number"),
            "notes": dstr_or(&d, "notes", ""),
            "created_at": ddate(&d, "created_at"),
        }));
    }
    Ok(Json(json!(out)))
}

// POST /api/disputes
pub async fn create(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(body): Json<Value>,
) -> AppResult<Json<Value>> {
    let (id, user) = authenticate(&state, &headers).await?;
    let oid = uid(&id)?;
    let d = doc! {
        "user_id": oid,
        "bureau": body_str(&body, "bureau", ""),
        "account_name": body_str(&body, "account_name", ""),
        "account_number": body_str(&body, "account_number", ""),
        "dispute_reason": body_str(&body, "dispute_reason", ""),
        "status": body_str(&body, "status", "draft"),
        "date_sent": Bson::Null,
        "date_response": Bson::Null,
        "response_outcome": Bson::Null,
        "tracking_number": body_bson(&body, "tracking_number"),
        "notes": body_str(&body, "notes", ""),
        "created_at": bson::DateTime::now(),
    };
    let res = state.db.collection::<Document>("disputes").insert_one(d).await?;
    let iid = res.inserted_id.as_object_id().map(|o| o.to_hex()).unwrap_or_default();
    log_audit(&state, "dispute_created", "dispute", Some(&iid), Some(user.email.as_str())).await;
    Ok(Json(json!({ "id": iid, "message": "Dispute created" })))
}

// PUT /api/disputes/{dispute_id}
pub async fn update(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(dispute_id): Path<String>,
    Json(body): Json<Value>,
) -> AppResult<Json<Value>> {
    let (id, user) = authenticate(&state, &headers).await?;
    let oid = uid(&id)?;
    let did = ObjectId::parse_str(&dispute_id).map_err(|_| AppError::NotFound)?;
    let disputes = state.db.collection::<Document>("disputes");
    if disputes
        .find_one(doc! { "_id": did, "user_id": oid })
        .await?
        .is_none()
    {
        return Err(AppError::NotFound);
    }
    let mut set = Document::new();
    for k in [
        "bureau",
        "account_name",
        "account_number",
        "dispute_reason",
        "status",
        "tracking_number",
        "notes",
        "response_outcome",
    ] {
        if body.get(k).is_some() {
            set.insert(k, body_bson(&body, k));
        }
    }
    for k in ["date_sent", "date_response"] {
        if let Some(v) = body.get(k) {
            if !v.is_null() {
                if let Some(dt) = parse_iso(Some(v)) {
                    set.insert(k, dt);
                }
            }
        }
    }
    set.insert("updated_at", bson::DateTime::now());
    disputes
        .update_one(doc! { "_id": did }, doc! { "$set": set })
        .await?;
    log_audit(&state, "dispute_updated", "dispute", Some(&dispute_id), Some(user.email.as_str())).await;
    Ok(Json(json!({ "message": "Dispute updated" })))
}

// DELETE /api/disputes/{dispute_id}
pub async fn delete(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(dispute_id): Path<String>,
) -> AppResult<Json<Value>> {
    let (id, user) = authenticate(&state, &headers).await?;
    let oid = uid(&id)?;
    let did = ObjectId::parse_str(&dispute_id).map_err(|_| AppError::NotFound)?;
    let res = state
        .db
        .collection::<Document>("disputes")
        .delete_one(doc! { "_id": did, "user_id": oid })
        .await?;
    if res.deleted_count == 0 {
        return Err(AppError::NotFound);
    }
    log_audit(&state, "dispute_deleted", "dispute", Some(&dispute_id), Some(user.email.as_str())).await;
    Ok(Json(json!({ "message": "Dispute deleted" })))
}

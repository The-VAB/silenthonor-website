//! Knowledge base (`/api/knowledge` member read + `/api/admin/knowledge/*`
//! management). Port of routers/knowledge.py. Collection `knowledge_base`.
//!
//! `visibility` is the server-enforced wall between the two AI assistants: the
//! member-facing list can ONLY ever return published + member_visible entries.

use axum::extract::{Path, Query, State};
use axum::http::HeaderMap;
use axum::Json;
use bson::oid::ObjectId;
use bson::{doc, Bson, Document};
use serde::Deserialize;
use serde_json::{json, Value};
use std::collections::HashMap;

use super::{authenticate, authenticate_admin, ddate, dstr, dstr_or, hex_id};
use crate::state::AppState;
use sh_core::models::User;
use sh_core::{AppError, AppResult};

const EDITOR_ROLES: [&str; 3] = ["admin", "staff", "counselor"];

/// Authenticate + require an editor role (admin/staff/counselor).
async fn require_kb_editor(state: &AppState, headers: &HeaderMap) -> AppResult<User> {
    let (_, user) = authenticate(state, headers).await?;
    if !user.effective_roles().iter().any(|r| EDITOR_ROLES.contains(&r.as_str())) {
        return Err(AppError::Forbidden(
            "Not authorized to manage the knowledge base".to_string(),
        ));
    }
    Ok(user)
}

fn tags_of(d: &Document) -> Value {
    match d.get_array("tags") {
        Ok(a) => Value::Array(a.iter().filter_map(|b| b.as_str().map(|s| json!(s))).collect()),
        Err(_) => json!([]),
    }
}

/// Member-facing serialization by default; `internal` adds management fields.
fn serialize(d: &Document, internal: bool) -> Value {
    let mut o = json!({
        "id": hex_id(d),
        "title": dstr_or(d, "title", ""),
        "body": dstr_or(d, "body", ""),
        "category": dstr(d, "category"),
        "tags": tags_of(d),
    });
    if internal {
        o["visibility"] = dstr_or(d, "visibility", "staff_only");
        o["status"] = dstr_or(d, "status", "draft");
        // version defaults to 1 when absent (dint returns 0 for absent).
        o["version"] = json!(if d.contains_key("version") { super::dint(d, "version") } else { 1 });
        o["created_by"] = dstr(d, "created_by");
        o["updated_by"] = dstr(d, "updated_by");
        o["created_at"] = ddate(d, "created_at");
        o["updated_at"] = ddate(d, "updated_at");
    }
    o
}

fn regex_or(q: &str) -> Bson {
    Bson::Array(vec![
        Bson::Document(doc! { "title": { "$regex": q, "$options": "i" } }),
        Bson::Document(doc! { "body": { "$regex": q, "$options": "i" } }),
    ])
}

// ── GET /api/knowledge -- member-facing (published + member_visible only) ──────
pub async fn list_member_knowledge(
    State(state): State<AppState>,
    headers: HeaderMap,
    Query(qs): Query<HashMap<String, String>>,
) -> AppResult<Json<Value>> {
    authenticate(&state, &headers).await?;
    let mut query = doc! { "status": "published", "visibility": "member_visible" };
    if let Some(c) = qs.get("category").filter(|s| !s.is_empty()) {
        query.insert("category", c.as_str());
    }
    if let Some(q) = qs.get("q").filter(|s| !s.is_empty()) {
        query.insert("$or", regex_or(q));
    }
    let mut cur = state
        .db
        .collection::<Document>("knowledge_base")
        .find(query)
        .sort(doc! { "title": 1 })
        .limit(500)
        .await?;
    let mut out: Vec<Value> = Vec::new();
    while cur.advance().await? {
        out.push(serialize(&cur.deserialize_current()?, false));
    }
    Ok(Json(json!(out)))
}

// ── GET /api/admin/knowledge -- full management list ──────────────────────────
pub async fn list_all(
    State(state): State<AppState>,
    headers: HeaderMap,
    Query(qs): Query<HashMap<String, String>>,
) -> AppResult<Json<Value>> {
    require_kb_editor(&state, &headers).await?;
    let mut query = Document::new();
    for f in ["visibility", "status", "category"] {
        if let Some(v) = qs.get(f).filter(|s| !s.is_empty()) {
            query.insert(f, v.as_str());
        }
    }
    if let Some(q) = qs.get("q").filter(|s| !s.is_empty()) {
        query.insert("$or", regex_or(q));
    }
    let mut cur = state
        .db
        .collection::<Document>("knowledge_base")
        .find(query)
        .sort(doc! { "updated_at": -1 })
        .limit(1000)
        .await?;
    let mut out: Vec<Value> = Vec::new();
    while cur.advance().await? {
        out.push(serialize(&cur.deserialize_current()?, true));
    }
    Ok(Json(json!(out)))
}

// ── GET /api/admin/knowledge/{entry_id} ───────────────────────────────────────
pub async fn get_entry(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(entry_id): Path<String>,
) -> AppResult<Json<Value>> {
    require_kb_editor(&state, &headers).await?;
    let oid = ObjectId::parse_str(&entry_id).map_err(|_| AppError::NotFound)?;
    let e = state
        .db
        .collection::<Document>("knowledge_base")
        .find_one(doc! { "_id": oid })
        .await?
        .ok_or(AppError::NotFound)?;
    Ok(Json(serialize(&e, true)))
}

#[derive(Debug, Deserialize)]
pub struct KnowledgeCreate {
    #[serde(default)]
    pub title: String,
    #[serde(default)]
    pub body: String,
    #[serde(default)]
    pub category: Option<String>,
    #[serde(default)]
    pub tags: Vec<String>,
    #[serde(default = "staff_only")]
    pub visibility: String,
    #[serde(default = "draft")]
    pub status: String,
}
fn staff_only() -> String {
    "staff_only".to_string()
}
fn draft() -> String {
    "draft".to_string()
}

// ── POST /api/admin/knowledge ─────────────────────────────────────────────────
pub async fn create_entry(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(body): Json<KnowledgeCreate>,
) -> AppResult<Json<Value>> {
    let editor = require_kb_editor(&state, &headers).await?;
    let now = bson::DateTime::now();
    let tags: Vec<Bson> = body.tags.iter().map(|t| Bson::String(t.clone())).collect();
    let doc = doc! {
        "title": body.title.as_str(),
        "body": body.body.as_str(),
        "category": match &body.category { Some(c) => Bson::String(c.clone()), None => Bson::Null },
        "tags": tags,
        "visibility": body.visibility.as_str(),
        "status": body.status.as_str(),
        "version": 1_i64,
        "created_by": editor.email.as_str(),
        "updated_by": editor.email.as_str(),
        "created_at": now,
        "updated_at": now,
    };
    let res = state
        .db
        .collection::<Document>("knowledge_base")
        .insert_one(&doc)
        .await?;
    let mut stored = doc;
    stored.insert("_id", res.inserted_id);
    Ok(Json(serialize(&stored, true)))
}

#[derive(Debug, Deserialize)]
pub struct KnowledgeUpdate {
    pub title: Option<String>,
    pub body: Option<String>,
    pub category: Option<String>,
    pub tags: Option<Vec<String>>,
    pub visibility: Option<String>,
    pub status: Option<String>,
}

// ── PUT /api/admin/knowledge/{entry_id} ───────────────────────────────────────
pub async fn update_entry(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(entry_id): Path<String>,
    Json(body): Json<KnowledgeUpdate>,
) -> AppResult<Json<Value>> {
    let editor = require_kb_editor(&state, &headers).await?;
    let oid = ObjectId::parse_str(&entry_id).map_err(|_| AppError::NotFound)?;
    let col = state.db.collection::<Document>("knowledge_base");
    let entry = col.find_one(doc! { "_id": oid }).await?.ok_or(AppError::NotFound)?;

    let mut updates = Document::new();
    if let Some(v) = &body.title {
        updates.insert("title", v.as_str());
    }
    if let Some(v) = &body.body {
        updates.insert("body", v.as_str());
    }
    if let Some(v) = &body.category {
        updates.insert("category", v.as_str());
    }
    if let Some(v) = &body.tags {
        updates.insert("tags", v.iter().map(|t| Bson::String(t.clone())).collect::<Vec<_>>());
    }
    if let Some(v) = &body.visibility {
        updates.insert("visibility", v.as_str());
    }
    if let Some(v) = &body.status {
        updates.insert("status", v.as_str());
    }
    if updates.is_empty() {
        return Ok(Json(serialize(&entry, true)));
    }
    // Python: entry.get("version", 1) + 1.
    let version = if entry.contains_key("version") {
        super::dint(&entry, "version") + 1
    } else {
        2
    };
    updates.insert("updated_by", editor.email.as_str());
    updates.insert("updated_at", bson::DateTime::now());
    updates.insert("version", version);
    col.update_one(doc! { "_id": oid }, doc! { "$set": updates }).await?;
    let entry = col.find_one(doc! { "_id": oid }).await?.ok_or(AppError::NotFound)?;
    Ok(Json(serialize(&entry, true)))
}

async fn set_status(
    state: &AppState,
    headers: &HeaderMap,
    entry_id: &str,
    status: &str,
    msg: &str,
) -> AppResult<Json<Value>> {
    let editor = require_kb_editor(state, headers).await?;
    let oid = ObjectId::parse_str(entry_id).map_err(|_| AppError::NotFound)?;
    let res = state
        .db
        .collection::<Document>("knowledge_base")
        .update_one(
            doc! { "_id": oid },
            doc! { "$set": {
                "status": status,
                "updated_by": editor.email.as_str(),
                "updated_at": bson::DateTime::now(),
            }},
        )
        .await?;
    if res.matched_count == 0 {
        return Err(AppError::NotFound);
    }
    Ok(Json(json!({ "message": msg })))
}

// ── POST /api/admin/knowledge/{entry_id}/publish ──────────────────────────────
pub async fn publish_entry(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(entry_id): Path<String>,
) -> AppResult<Json<Value>> {
    set_status(&state, &headers, &entry_id, "published", "Entry published").await
}

// ── POST /api/admin/knowledge/{entry_id}/retire ───────────────────────────────
pub async fn retire_entry(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(entry_id): Path<String>,
) -> AppResult<Json<Value>> {
    set_status(&state, &headers, &entry_id, "retired", "Entry retired").await
}

// ── DELETE /api/admin/knowledge/{entry_id} -- admin only ──────────────────────
pub async fn delete_entry(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(entry_id): Path<String>,
) -> AppResult<Json<Value>> {
    authenticate_admin(&state, &headers).await?;
    let oid = ObjectId::parse_str(&entry_id).map_err(|_| AppError::NotFound)?;
    let res = state
        .db
        .collection::<Document>("knowledge_base")
        .delete_one(doc! { "_id": oid })
        .await?;
    if res.deleted_count == 0 {
        return Err(AppError::NotFound);
    }
    Ok(Json(json!({ "message": "Entry deleted" })))
}

//! Messaging (`/api/messages/*`). Port of routers/messages.py. Collection
//! `messages`. Conversation grouping / admin listing are done in Rust rather
//! than a Mongo aggregation (same result, clearer).

use std::collections::{HashMap, HashSet};

use axum::extract::{Path, Query, State};
use axum::http::HeaderMap;
use axum::Json;
use bson::oid::ObjectId;
use bson::{doc, Document};
use serde::Deserialize;
use serde_json::{json, Value};

use super::{authenticate, authenticate_admin, dbool, ddate, dstr_or, hex_field, hex_id, iso};
use crate::state::AppState;
use sh_core::{AppError, AppResult};

fn uid(id: &str) -> AppResult<ObjectId> {
    ObjectId::parse_str(id).map_err(|_| AppError::Unauthorized)
}

fn full_name(d: &Document) -> String {
    format!(
        "{} {}",
        d.get_str("first_name").unwrap_or(""),
        d.get_str("last_name").unwrap_or("")
    )
    .trim()
    .to_string()
}

fn titlecase(s: &str) -> String {
    s.split(' ')
        .map(|w| {
            let mut c = w.chars();
            match c.next() {
                Some(f) => f.to_uppercase().collect::<String>() + c.as_str(),
                None => String::new(),
            }
        })
        .collect::<Vec<_>>()
        .join(" ")
}

#[derive(Debug, Deserialize)]
pub struct ConvQuery {
    #[serde(default)]
    pub conversation_id: Option<String>,
}

// GET /api/messages[?conversation_id=]
pub async fn list(
    State(state): State<AppState>,
    headers: HeaderMap,
    Query(q): Query<ConvQuery>,
) -> AppResult<Json<Value>> {
    let (id, _) = authenticate(&state, &headers).await?;
    let oid = uid(&id)?;
    let filter = match q.conversation_id.as_deref().and_then(|s| ObjectId::parse_str(s).ok()) {
        Some(other) => doc! { "$or": [
            { "from_user_id": oid, "to_user_id": other },
            { "from_user_id": other, "to_user_id": oid },
        ]},
        None => doc! { "$or": [ { "from_user_id": oid }, { "to_user_id": oid } ] },
    };
    let mut cur = state
        .db
        .collection::<Document>("messages")
        .find(filter)
        .sort(doc! { "created_at": 1 })
        .limit(500)
        .await?;
    let mut out: Vec<Value> = Vec::new();
    while cur.advance().await? {
        let m = cur.deserialize_current()?;
        out.push(json!({
            "id": hex_id(&m),
            "from_user_id": hex_field(&m, "from_user_id"),
            "to_user_id": hex_field(&m, "to_user_id"),
            "content": dstr_or(&m, "content", ""),
            "read": dbool(&m, "read"),
            "created_at": ddate(&m, "created_at"),
        }));
    }
    Ok(Json(json!(out)))
}

// POST /api/messages
pub async fn send(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(body): Json<Value>,
) -> AppResult<Json<Value>> {
    let (id, _) = authenticate(&state, &headers).await?;
    let oid = uid(&id)?;
    let to_str = body.get("to_user_id").and_then(|v| v.as_str()).unwrap_or("");
    let content = body
        .get("content")
        .and_then(|v| v.as_str())
        .unwrap_or("")
        .trim()
        .to_string();
    if to_str.is_empty() || content.is_empty() {
        return Err(AppError::BadRequest("Recipient and content required".to_string()));
    }
    let to_oid = ObjectId::parse_str(to_str).map_err(|_| AppError::NotFound)?;
    if state
        .db
        .collection::<Document>("users")
        .find_one(doc! { "_id": to_oid })
        .await?
        .is_none()
    {
        return Err(AppError::NotFound);
    }
    let now = bson::DateTime::now();
    let res = state
        .db
        .collection::<Document>("messages")
        .insert_one(doc! {
            "from_user_id": oid,
            "to_user_id": to_oid,
            "content": content.as_str(),
            "read": false,
            "created_at": now,
        })
        .await?;
    let iid = res.inserted_id.as_object_id().map(|o| o.to_hex()).unwrap_or_default();
    Ok(Json(json!({ "id": iid, "message": "Message sent", "created_at": iso(Some(now)) })))
}

// GET /api/messages/conversations
pub async fn conversations(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> AppResult<Json<Value>> {
    let (id, _) = authenticate(&state, &headers).await?;
    let oid = uid(&id)?;
    let messages = state.db.collection::<Document>("messages");
    let mut cur = messages
        .find(doc! { "$or": [ { "from_user_id": oid }, { "to_user_id": oid } ] })
        .sort(doc! { "created_at": -1 })
        .limit(1000)
        .await?;

    let mut order: Vec<ObjectId> = Vec::new();
    let mut last: HashMap<ObjectId, (Value, Value)> = HashMap::new();
    let mut unread: HashMap<ObjectId, i64> = HashMap::new();
    while cur.advance().await? {
        let m = cur.deserialize_current()?;
        let from = m.get_object_id("from_user_id").ok();
        let to = m.get_object_id("to_user_id").ok();
        let other = if from == Some(oid) { to } else { from };
        let Some(other) = other else { continue };
        if !last.contains_key(&other) {
            order.push(other);
            last.insert(other, (dstr_or(&m, "content", ""), ddate(&m, "created_at")));
        }
        if to == Some(oid) && !m.get_bool("read").unwrap_or(false) {
            *unread.entry(other).or_insert(0) += 1;
        }
    }

    let users = state.db.collection::<Document>("users");
    let mut out: Vec<Value> = Vec::new();
    for other in order {
        let Some(p) = users.find_one(doc! { "_id": other }).await? else {
            continue;
        };
        let mut name = full_name(&p);
        if name.is_empty() {
            name = p.get_str("email").unwrap_or("").to_string();
        }
        let role = p.get_str("role").unwrap_or("member").to_string();
        let title = match p.get_str("title") {
            Ok(t) if !t.is_empty() => t.to_string(),
            _ => titlecase(&role.replace('_', " ")),
        };
        let (lm, lt) = last.get(&other).cloned().unwrap_or((json!(""), Value::Null));
        out.push(json!({
            "id": other.to_hex(),
            "name": name,
            "title": title,
            "role": role,
            "last_message": lm,
            "last_time": lt,
            "unread": unread.get(&other).copied().unwrap_or(0),
        }));
    }
    Ok(Json(json!(out)))
}

// GET /api/messages/unread
pub async fn unread(State(state): State<AppState>, headers: HeaderMap) -> AppResult<Json<Value>> {
    let (id, _) = authenticate(&state, &headers).await?;
    let oid = uid(&id)?;
    let n = state
        .db
        .collection::<Document>("messages")
        .count_documents(doc! { "to_user_id": oid, "read": false })
        .await?;
    Ok(Json(json!({ "unread": n })))
}

// PUT /api/messages/{message_id}/read
pub async fn mark_read(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(message_id): Path<String>,
) -> AppResult<Json<Value>> {
    let (id, _) = authenticate(&state, &headers).await?;
    let oid = uid(&id)?;
    let mid = ObjectId::parse_str(&message_id).map_err(|_| AppError::NotFound)?;
    state
        .db
        .collection::<Document>("messages")
        .update_one(doc! { "_id": mid, "to_user_id": oid }, doc! { "$set": { "read": true } })
        .await?;
    Ok(Json(json!({ "message": "Marked as read" })))
}

// PUT /api/messages/conversation/{user_id}/read
pub async fn mark_conversation_read(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(user_id): Path<String>,
) -> AppResult<Json<Value>> {
    let (id, _) = authenticate(&state, &headers).await?;
    let oid = uid(&id)?;
    let other = ObjectId::parse_str(&user_id).map_err(|_| AppError::NotFound)?;
    state
        .db
        .collection::<Document>("messages")
        .update_many(
            doc! { "from_user_id": other, "to_user_id": oid, "read": false },
            doc! { "$set": { "read": true } },
        )
        .await?;
    Ok(Json(json!({ "message": "Conversation marked as read" })))
}

// GET /api/messages/admin/all  (admin only)
pub async fn admin_all(State(state): State<AppState>, headers: HeaderMap) -> AppResult<Json<Value>> {
    authenticate_admin(&state, &headers).await?;
    let messages = state.db.collection::<Document>("messages");
    let mut cur = messages
        .find(doc! {})
        .sort(doc! { "created_at": -1 })
        .limit(500)
        .await?;
    let mut msgs: Vec<Document> = Vec::new();
    let mut ids: HashSet<ObjectId> = HashSet::new();
    while cur.advance().await? {
        let m = cur.deserialize_current()?;
        if let Ok(f) = m.get_object_id("from_user_id") {
            ids.insert(f);
        }
        if let Ok(t) = m.get_object_id("to_user_id") {
            ids.insert(t);
        }
        msgs.push(m);
    }

    let mut umap: HashMap<ObjectId, (String, String)> = HashMap::new();
    let id_vec: Vec<ObjectId> = ids.into_iter().collect();
    if !id_vec.is_empty() {
        let mut ucur = state
            .db
            .collection::<Document>("users")
            .find(doc! { "_id": { "$in": id_vec } })
            .await?;
        while ucur.advance().await? {
            let u = ucur.deserialize_current()?;
            if let Ok(id) = u.get_object_id("_id") {
                umap.insert(id, (full_name(&u), u.get_str("email").unwrap_or("").to_string()));
            }
        }
    }
    let mkuser = |oid: Option<ObjectId>| -> Value {
        match oid.and_then(|o| umap.get(&o).map(|x| (o, x))) {
            Some((o, (name, email))) => json!({ "id": o.to_hex(), "name": name, "email": email }),
            None => json!({ "id": null, "name": "", "email": "" }),
        }
    };
    let out: Vec<Value> = msgs
        .iter()
        .map(|m| {
            json!({
                "id": hex_id(m),
                "from_user": mkuser(m.get_object_id("from_user_id").ok()),
                "to_user": mkuser(m.get_object_id("to_user_id").ok()),
                "content": dstr_or(m, "content", ""),
                "read": dbool(m, "read"),
                "created_at": ddate(m, "created_at"),
            })
        })
        .collect();
    Ok(Json(json!(out)))
}

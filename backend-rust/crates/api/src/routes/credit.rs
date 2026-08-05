//! Credit scores (`/api/credit/*`). Port of routers/credit.py. Collection
//! `credit_scores`, scoped to `{ user_id: <auth user> }`.

use axum::extract::{Path, State};
use axum::http::HeaderMap;
use axum::Json;
use bson::oid::ObjectId;
use bson::{doc, Document};
use serde_json::{json, Value};

use super::{authenticate, body_bson, body_str, ddate, draw, dstr_or, hex_id, parse_iso, parse_iso_or_now};
use crate::state::AppState;
use sh_core::{AppError, AppResult};

fn uid(id: &str) -> AppResult<ObjectId> {
    ObjectId::parse_str(id).map_err(|_| AppError::Unauthorized)
}

fn num(d: &Document, k: &str) -> Value {
    draw(d, k)
}

// GET /api/credit/history
pub async fn history(State(state): State<AppState>, headers: HeaderMap) -> AppResult<Json<Value>> {
    let (id, _) = authenticate(&state, &headers).await?;
    let oid = uid(&id)?;
    let mut cur = state
        .db
        .collection::<Document>("credit_scores")
        .find(doc! { "user_id": oid })
        .sort(doc! { "date": -1 })
        .limit(100)
        .await?;
    let mut out: Vec<Value> = Vec::new();
    while cur.advance().await? {
        let d = cur.deserialize_current()?;
        out.push(json!({
            "id": hex_id(&d),
            "date": ddate(&d, "date"),
            "equifax": num(&d, "equifax"),
            "experian": num(&d, "experian"),
            "transunion": num(&d, "transunion"),
            "source": dstr_or(&d, "source", "manual"),
            "notes": dstr_or(&d, "notes", ""),
        }));
    }
    Ok(Json(json!(out)))
}

// GET /api/credit/latest
pub async fn latest(State(state): State<AppState>, headers: HeaderMap) -> AppResult<Json<Value>> {
    let (id, _) = authenticate(&state, &headers).await?;
    let oid = uid(&id)?;
    let mut cur = state
        .db
        .collection::<Document>("credit_scores")
        .find(doc! { "user_id": oid })
        .sort(doc! { "date": -1 })
        .limit(1)
        .await?;
    if cur.advance().await? {
        let d = cur.deserialize_current()?;
        Ok(Json(json!({
            "id": hex_id(&d),
            "date": ddate(&d, "date"),
            "equifax": num(&d, "equifax"),
            "experian": num(&d, "experian"),
            "transunion": num(&d, "transunion"),
        })))
    } else {
        Ok(Json(json!({ "equifax": null, "experian": null, "transunion": null })))
    }
}

// POST /api/credit/score
pub async fn create_score(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(body): Json<Value>,
) -> AppResult<Json<Value>> {
    let (id, _) = authenticate(&state, &headers).await?;
    let oid = uid(&id)?;
    let score_date = parse_iso_or_now(body.get("date"));
    let d = doc! {
        "user_id": oid,
        "date": score_date,
        "equifax": body_bson(&body, "equifax"),
        "experian": body_bson(&body, "experian"),
        "transunion": body_bson(&body, "transunion"),
        "source": body_str(&body, "source", "manual"),
        "notes": body_str(&body, "notes", ""),
        "created_at": bson::DateTime::now(),
    };
    let res = state
        .db
        .collection::<Document>("credit_scores")
        .insert_one(d)
        .await?;
    let iid = res.inserted_id.as_object_id().map(|o| o.to_hex()).unwrap_or_default();
    Ok(Json(json!({ "id": iid, "message": "Credit score recorded" })))
}

// PUT /api/credit/{score_id}
pub async fn update_score(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(score_id): Path<String>,
    Json(body): Json<Value>,
) -> AppResult<Json<Value>> {
    let (id, _) = authenticate(&state, &headers).await?;
    let oid = uid(&id)?;
    let sid = ObjectId::parse_str(&score_id).map_err(|_| AppError::NotFound)?;
    let scores = state.db.collection::<Document>("credit_scores");
    if scores
        .find_one(doc! { "_id": sid, "user_id": oid })
        .await?
        .is_none()
    {
        return Err(AppError::NotFound);
    }
    let mut set = Document::new();
    for k in ["equifax", "experian", "transunion"] {
        if body.get(k).is_some() {
            set.insert(k, body_bson(&body, k));
        }
    }
    for k in ["source", "notes"] {
        if let Some(v) = body.get(k).and_then(|v| v.as_str()) {
            set.insert(k, v);
        }
    }
    // credit PUT swallows a bad date (only sets it when parseable)
    if let Some(dt) = parse_iso(body.get("date")) {
        set.insert("date", dt);
    }
    set.insert("updated_at", bson::DateTime::now());
    scores.update_one(doc! { "_id": sid }, doc! { "$set": set }).await?;
    Ok(Json(json!({ "message": "Score updated" })))
}

// DELETE /api/credit/{score_id}
pub async fn delete_score(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(score_id): Path<String>,
) -> AppResult<Json<Value>> {
    let (id, _) = authenticate(&state, &headers).await?;
    let oid = uid(&id)?;
    let sid = ObjectId::parse_str(&score_id).map_err(|_| AppError::NotFound)?;
    let res = state
        .db
        .collection::<Document>("credit_scores")
        .delete_one(doc! { "_id": sid, "user_id": oid })
        .await?;
    if res.deleted_count == 0 {
        return Err(AppError::NotFound);
    }
    Ok(Json(json!({ "message": "Score deleted" })))
}

// GET /api/credit/stats
pub async fn stats(State(state): State<AppState>, headers: HeaderMap) -> AppResult<Json<Value>> {
    let (id, _) = authenticate(&state, &headers).await?;
    let oid = uid(&id)?;
    let mut cur = state
        .db
        .collection::<Document>("credit_scores")
        .find(doc! { "user_id": oid })
        .sort(doc! { "date": -1 })
        .limit(24)
        .await?;
    let mut docs: Vec<Document> = Vec::new();
    while cur.advance().await? {
        docs.push(cur.deserialize_current()?);
    }
    if docs.is_empty() {
        return Ok(Json(json!({
            "current": { "equifax": null, "experian": null, "transunion": null },
            "change_30_days": { "equifax": null, "experian": null, "transunion": null },
            "average": { "equifax": null, "experian": null, "transunion": null },
        })));
    }
    let bureau_i64 = |d: &Document, k: &str| -> Option<i64> {
        match d.get(k) {
            Some(bson::Bson::Int32(i)) => Some(*i as i64),
            Some(bson::Bson::Int64(i)) => Some(*i),
            Some(bson::Bson::Double(f)) => Some(*f as i64),
            _ => None,
        }
    };
    let current = &docs[0];
    let avg = |k: &str| -> Value {
        let vals: Vec<i64> = docs.iter().filter_map(|d| bureau_i64(d, k)).collect();
        if vals.is_empty() {
            Value::Null
        } else {
            json!((vals.iter().sum::<i64>() as f64 / vals.len() as f64).round() as i64)
        }
    };
    // change_30_days: the Python computes an "old score" only on the 31st of a
    // month (buggy day>30 guard), so in practice it is null. Mirror that: null.
    Ok(Json(json!({
        "current": {
            "equifax": num(current, "equifax"),
            "experian": num(current, "experian"),
            "transunion": num(current, "transunion"),
            "date": ddate(current, "date"),
        },
        "change_30_days": { "equifax": null, "experian": null, "transunion": null },
        "average": { "equifax": avg("equifax"), "experian": avg("experian"), "transunion": avg("transunion") },
    })))
}

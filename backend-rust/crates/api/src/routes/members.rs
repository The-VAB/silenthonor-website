//! `/api/member/*` -- profile, counselor, dashboard, courses, course progress.
//!
//! Faithful port of backend/routers/members.py (read + progress endpoints).
//! The DD-214 upload (POST /api/member/dd214) is intentionally deferred to its
//! own PR: it needs S3 + AES-256 encryption and multipart handling.

use std::collections::HashMap;

use axum::extract::{Path, State};
use axum::http::HeaderMap;
use axum::Json;
use bson::oid::ObjectId;
use bson::{doc, Bson, Document};
use serde_json::{json, Value};

use sh_core::{AppError, AppResult};

use super::authenticate;
use crate::state::AppState;

/// Read an integer-ish BSON value (stored as Int32, Int64, or Double) as i64.
fn bson_i64(v: Option<&Bson>) -> Option<i64> {
    match v {
        Some(Bson::Int32(i)) => Some(*i as i64),
        Some(Bson::Int64(i)) => Some(*i),
        Some(Bson::Double(f)) => Some(*f as i64),
        _ => None,
    }
}

// GET /api/member/profile
pub async fn get_profile(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> AppResult<Json<Value>> {
    let (uid, user) = authenticate(&state, &headers).await?;
    Ok(Json(user.to_profile(&uid)))
}

// PUT /api/member/profile
pub async fn update_profile(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(body): Json<Value>,
) -> AppResult<Json<Value>> {
    let (uid, _user) = authenticate(&state, &headers).await?;

    let allowed = [
        "first_name",
        "last_name",
        "phone",
        "state",
        "email_preferences",
    ];
    let mut set = Document::new();
    if let Some(obj) = body.as_object() {
        for key in allowed {
            if let Some(v) = obj.get(key) {
                if let Ok(b) = bson::to_bson(v) {
                    set.insert(key, b);
                }
            }
        }
    }

    if !set.is_empty() {
        let oid = ObjectId::parse_str(&uid).map_err(|_| AppError::Unauthorized)?;
        state
            .db
            .collection::<Document>("users")
            .update_one(doc! { "_id": oid }, doc! { "$set": set })
            .await?;
    }
    Ok(Json(json!({ "message": "Profile updated successfully" })))
}

// GET /api/member/counselor
pub async fn counselor(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> AppResult<Json<Value>> {
    let (_uid, user) = authenticate(&state, &headers).await?;

    let counselor_id = match user.assigned_counselor_id.as_deref() {
        Some(c) if !c.is_empty() => c.to_string(),
        _ => {
            return Ok(Json(
                json!({ "id": null, "name": null, "message": "No counselor assigned yet" }),
            ))
        }
    };

    let coid = match ObjectId::parse_str(&counselor_id) {
        Ok(o) => o,
        Err(_) => {
            return Ok(Json(
                json!({ "id": null, "name": null, "message": "Counselor not found" }),
            ))
        }
    };

    let counselor = state
        .db
        .collection::<Document>("users")
        .find_one(doc! { "_id": coid })
        .await?;
    let Some(c) = counselor else {
        return Ok(Json(
            json!({ "id": null, "name": null, "message": "Counselor not found" }),
        ));
    };

    let first = c.get_str("first_name").unwrap_or("");
    let last = c.get_str("last_name").unwrap_or("");
    let specialties: Vec<String> = c
        .get_array("specialties")
        .map(|a| {
            a.iter()
                .filter_map(|b| b.as_str().map(str::to_string))
                .collect()
        })
        .unwrap_or_default();

    Ok(Json(json!({
        "id": coid.to_hex(),
        "name": format!("{first} {last}").trim(),
        "email": c.get_str("email").ok(),
        "title": c.get_str("title").unwrap_or("Certified Financial Counselor"),
        "bio": c.get_str("bio").unwrap_or(""),
        "specialties": specialties,
        "calendly_url": c.get_str("calendly_url").ok(),
    })))
}

// GET /api/member/dashboard
pub async fn dashboard(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> AppResult<Json<Value>> {
    let (uid, user) = authenticate(&state, &headers).await?;
    let oid = ObjectId::parse_str(&uid).map_err(|_| AppError::Unauthorized)?;

    let latest_credit = state
        .db
        .collection::<Document>("credit_scores")
        .find_one(doc! { "user_id": oid })
        .sort(doc! { "date": -1 })
        .await?;
    let (equifax, experian, transunion, date) = match &latest_credit {
        Some(d) => (
            bson_i64(d.get("equifax")),
            bson_i64(d.get("experian")),
            bson_i64(d.get("transunion")),
            d.get_datetime("date").ok().map(|dt| dt.timestamp_millis()),
        ),
        None => (None, None, None, None),
    };

    let disputes = state.db.collection::<Document>("disputes");
    let disputes_total = disputes.count_documents(doc! { "user_id": oid }).await?;
    let disputes_pending = disputes
        .count_documents(doc! { "user_id": oid, "status": { "$in": ["pending", "sent"] } })
        .await?;

    let unread = state
        .db
        .collection::<Document>("messages")
        .count_documents(doc! { "to_user_id": oid, "read": false })
        .await?;

    let mut in_progress = 0i64;
    let mut completed = 0i64;
    let mut cursor = state
        .db
        .collection::<Document>("course_progress")
        .find(doc! { "user_id": oid })
        .await?;
    while cursor.advance().await? {
        let d = cursor.deserialize_current()?;
        let pct = bson_i64(d.get("percent_complete")).unwrap_or(0);
        if pct > 0 && pct < 100 {
            in_progress += 1;
        } else if pct >= 100 {
            completed += 1;
        }
    }

    let counselor_assigned = user
        .assigned_counselor_id
        .as_ref()
        .map(|s| !s.is_empty())
        .unwrap_or(false);

    Ok(Json(json!({
        "credit_scores": { "equifax": equifax, "experian": experian, "transunion": transunion, "date": date },
        "disputes": { "total": disputes_total, "pending": disputes_pending },
        "messages": { "unread": unread },
        "courses": { "in_progress": in_progress, "completed": completed },
        "counselor_assigned": counselor_assigned,
        "pipeline_stage": user.pipeline_stage.clone().unwrap_or_else(|| "applied".to_string()),
        "dd214_status": user.dd214_status.clone().unwrap_or_else(|| "pending".to_string()),
    })))
}

// GET /api/member/courses
pub async fn courses(State(state): State<AppState>, headers: HeaderMap) -> AppResult<Json<Value>> {
    let (uid, user) = authenticate(&state, &headers).await?;
    if !user.verified {
        return Err(AppError::Forbidden(
            "Your account must be verified to access courses.".to_string(),
        ));
    }
    let oid = ObjectId::parse_str(&uid).map_err(|_| AppError::Unauthorized)?;

    // Map course_id -> completed lesson count (stored as an int or an array).
    let mut progress: HashMap<String, i64> = HashMap::new();
    let mut pc = state
        .db
        .collection::<Document>("course_progress")
        .find(doc! { "user_id": oid })
        .await?;
    while pc.advance().await? {
        let d = pc.deserialize_current()?;
        let cid = match d.get("course_id") {
            Some(Bson::String(s)) => s.clone(),
            Some(Bson::ObjectId(o)) => o.to_hex(),
            _ => continue,
        };
        let done = match d.get("completed_lessons") {
            Some(Bson::Int32(i)) => *i as i64,
            Some(Bson::Int64(i)) => *i,
            Some(Bson::Array(a)) => a.len() as i64,
            _ => 0,
        };
        progress.insert(cid, done);
    }

    let lessons = state.db.collection::<Document>("lessons");
    let mut out: Vec<Value> = Vec::new();
    let mut cursor = state
        .db
        .collection::<Document>("courses")
        .find(doc! { "status": { "$in": ["live", "published", "coming_soon"] } })
        .sort(doc! { "created_at": 1 })
        .await?;
    while cursor.advance().await? {
        let c = cursor.deserialize_current()?;
        let cid = c
            .get_object_id("_id")
            .map(|o| o.to_hex())
            .unwrap_or_default();
        let total = lessons
            .count_documents(doc! { "course_id": cid.as_str() })
            .await? as i64;
        let done = *progress.get(&cid).unwrap_or(&0);
        let pct = if total > 0 {
            ((done as f64 / total as f64) * 100.0).round() as i64
        } else {
            0
        };
        out.push(json!({
            "id": cid,
            "title": c.get_str("title").unwrap_or(""),
            "total_lessons": total,
            "status": c.get_str("status").unwrap_or("draft"),
            "completed_lessons": done,
            "progress": pct,
        }));
    }

    Ok(Json(json!(out)))
}

// POST /api/member/courses/{course_id}/progress
pub async fn update_progress(
    State(state): State<AppState>,
    Path(course_id): Path<String>,
    headers: HeaderMap,
    Json(body): Json<Value>,
) -> AppResult<Json<Value>> {
    let (uid, user) = authenticate(&state, &headers).await?;
    if !user.verified {
        return Err(AppError::Forbidden(
            "Your account must be verified to access courses.".to_string(),
        ));
    }
    let oid = ObjectId::parse_str(&uid).map_err(|_| AppError::Unauthorized)?;

    let completed = body
        .get("completed_lessons")
        .and_then(|v| v.as_i64())
        .unwrap_or(0);

    state
        .db
        .collection::<Document>("course_progress")
        .update_one(
            doc! { "user_id": oid, "course_id": course_id.as_str() },
            doc! { "$set": { "completed_lessons": completed, "updated_at": bson::DateTime::now() } },
        )
        .upsert(true)
        .await?;

    Ok(Json(json!({ "message": "Progress updated" })))
}

// GET /api/member/financial-intake
// Returns the member's saved financial profile (income/expenses/debts/savings/
// goals), or an empty object if they have not filled it in yet.
pub async fn get_financial_intake(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> AppResult<Json<Value>> {
    let (uid, _user) = authenticate(&state, &headers).await?;
    let oid = ObjectId::parse_str(&uid).map_err(|_| AppError::Unauthorized)?;

    let found = state
        .db
        .collection::<Document>("financial_intake")
        .find_one(doc! { "member_id": oid })
        .await?;

    match found {
        Some(mut d) => {
            d.remove("_id");
            d.remove("member_id");
            d.remove("updated_at");
            Ok(Json(serde_json::to_value(&d).unwrap_or_else(|_| json!({}))))
        }
        None => Ok(Json(json!({}))),
    }
}

// POST /api/member/financial-intake
// The member submits their own financial profile (from the My Plan intake).
// Stored per member and available to their assigned counselor.
pub async fn save_financial_intake(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(body): Json<Value>,
) -> AppResult<Json<Value>> {
    let (uid, _user) = authenticate(&state, &headers).await?;
    let oid = ObjectId::parse_str(&uid).map_err(|_| AppError::Unauthorized)?;

    let mut fields = bson::to_document(&body)
        .map_err(|_| AppError::BadRequest("Invalid financial profile".to_string()))?;
    fields.insert("member_id", oid);
    fields.insert("updated_at", bson::DateTime::now());

    state
        .db
        .collection::<Document>("financial_intake")
        .update_one(doc! { "member_id": oid }, doc! { "$set": fields })
        .upsert(true)
        .await?;

    Ok(Json(json!({ "message": "Financial profile saved" })))
}

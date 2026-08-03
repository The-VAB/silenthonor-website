//! Member course catalog (`/api/courses/*`). Port of routers/courses.py (member
//! reads). Collections `courses`, `lessons`, `course_progress`.
//! NOTE: `lessons.course_id` / `course_progress.course_id` are stored as STRINGS.

use axum::extract::{Path, State};
use axum::http::HeaderMap;
use axum::Json;
use bson::oid::ObjectId;
use bson::{doc, Document};
use serde_json::{json, Value};

use super::{authenticate, ddate, dint, draw, dstr_or, hex_id};
use crate::state::AppState;
use sh_core::{AppError, AppResult};

fn uid(id: &str) -> AppResult<ObjectId> {
    ObjectId::parse_str(id).map_err(|_| AppError::Unauthorized)
}

// GET /api/courses/progress
pub async fn progress(State(state): State<AppState>, headers: HeaderMap) -> AppResult<Json<Value>> {
    let (id, _) = authenticate(&state, &headers).await?;
    let oid = uid(&id)?;
    let mut cur = state
        .db
        .collection::<Document>("course_progress")
        .find(doc! { "user_id": oid })
        .limit(100)
        .await?;
    let mut out: Vec<Value> = Vec::new();
    while cur.advance().await? {
        let p = cur.deserialize_current()?;
        out.push(json!({
            "course_id": p.get_str("course_id").unwrap_or("").to_string(),
            "completed_lessons": if p.contains_key("completed_lessons") {
                draw(&p, "completed_lessons")
            } else {
                json!([])
            },
            "percent_complete": dint(&p, "percent_complete"),
            "last_accessed": ddate(&p, "updated_at"),
        }));
    }
    Ok(Json(json!(out)))
}

// GET /api/courses/{course_id}
pub async fn detail(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(course_id): Path<String>,
) -> AppResult<Json<Value>> {
    let (id, _) = authenticate(&state, &headers).await?;
    let oid = uid(&id)?;

    // Guard exactly like Python: only look up when the id is a 24-char hex.
    let course = if course_id.len() == 24 {
        match ObjectId::parse_str(&course_id) {
            Ok(cid) => {
                state
                    .db
                    .collection::<Document>("courses")
                    .find_one(doc! { "_id": cid })
                    .await?
            }
            Err(_) => None,
        }
    } else {
        None
    };
    let Some(c) = course else {
        return Err(AppError::NotFound);
    };

    // completed lesson ids from this member's progress
    let progress = state
        .db
        .collection::<Document>("course_progress")
        .find_one(doc! { "user_id": oid, "course_id": course_id.as_str() })
        .await?;
    let completed: Vec<String> = progress
        .as_ref()
        .and_then(|p| p.get_array("completed_lessons").ok())
        .map(|arr| arr.iter().filter_map(|b| b.as_str().map(String::from)).collect())
        .unwrap_or_default();

    let mut lcur = state
        .db
        .collection::<Document>("lessons")
        .find(doc! { "course_id": course_id.as_str() })
        .sort(doc! { "order": 1 })
        .limit(100)
        .await?;
    let mut lessons: Vec<Value> = Vec::new();
    while lcur.advance().await? {
        let l = lcur.deserialize_current()?;
        let lid = hex_id(&l);
        lessons.push(json!({
            "id": lid,
            "title": dstr_or(&l, "title", ""),
            "content": dstr_or(&l, "content", ""),
            "duration": dstr_or(&l, "duration", "10 min"),
            "video_url": draw(&l, "video_url"),
            "order": dint(&l, "order"),
            "completed": completed.contains(&lid),
        }));
    }

    Ok(Json(json!({
        "id": hex_id(&c),
        "title": dstr_or(&c, "title", ""),
        "description": dstr_or(&c, "description", ""),
        "category": draw(&c, "category"),
        "thumbnail": draw(&c, "thumbnail"),
        "lessons": lessons,
    })))
}

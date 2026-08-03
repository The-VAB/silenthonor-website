//! Member course catalog (`/api/courses/*`). Port of routers/courses.py (member
//! reads). Collections `courses`, `lessons`, `course_progress`.
//! NOTE: `lessons.course_id` / `course_progress.course_id` are stored as STRINGS.

use axum::extract::{Path, State};
use axum::http::HeaderMap;
use axum::Json;
use bson::oid::ObjectId;
use bson::{doc, Bson, Document};
use serde::Deserialize;
use serde_json::{json, Value};

use super::{authenticate, authenticate_admin, ddate, dint, draw, dstr_or, hex_id};
use crate::state::AppState;
use sh_core::{AppError, AppResult};

fn uid(id: &str) -> AppResult<ObjectId> {
    ObjectId::parse_str(id).map_err(|_| AppError::Unauthorized)
}

/// Optional string body field -> BSON string, or Null when absent/empty-key.
fn ostr(body: &Value, k: &str) -> Bson {
    match body.get(k) {
        Some(Value::String(s)) => Bson::String(s.clone()),
        Some(v) if !v.is_null() => bson::to_bson(v).unwrap_or(Bson::Null),
        _ => Bson::Null,
    }
}
/// Optional owned string -> BSON string or Null.
fn oopt(v: &Option<String>) -> Bson {
    match v {
        Some(s) => Bson::String(s.clone()),
        None => Bson::Null,
    }
}
/// Integer body field (Int32/Int64/Double/string) -> i64 with default.
fn oint(body: &Value, k: &str, default: i64) -> i64 {
    body.get(k).and_then(|v| v.as_i64()).unwrap_or(default)
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

// ═══════════════════════════════════════════════════════════════════════════
// ADMIN: MODULES  (module_id / course_id are stored as STRINGS)
// ═══════════════════════════════════════════════════════════════════════════

// GET /api/admin/courses/{course_id}/modules
pub async fn get_modules(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(course_id): Path<String>,
) -> AppResult<Json<Value>> {
    authenticate_admin(&state, &headers).await?;
    let lessons = state.db.collection::<Document>("lessons");
    let mut cur = state
        .db
        .collection::<Document>("modules")
        .find(doc! { "course_id": course_id.as_str() })
        .sort(doc! { "order": 1 })
        .limit(100)
        .await?;
    let mut out: Vec<Value> = Vec::new();
    while cur.advance().await? {
        let m = cur.deserialize_current()?;
        let mid = hex_id(&m);
        let lesson_count = lessons
            .count_documents(doc! { "module_id": mid.as_str() })
            .await?;
        out.push(json!({
            "id": mid,
            "title": dstr_or(&m, "title", ""),
            "description": dstr_or(&m, "description", ""),
            "order": dint(&m, "order"),
            "lesson_count": lesson_count,
        }));
    }
    Ok(Json(json!(out)))
}

// POST /api/admin/courses/{course_id}/modules
pub async fn create_module(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(course_id): Path<String>,
    Json(body): Json<Value>,
) -> AppResult<Json<Value>> {
    authenticate_admin(&state, &headers).await?;
    let coid = ObjectId::parse_str(&course_id).map_err(|_| AppError::NotFound)?;
    if state
        .db
        .collection::<Document>("courses")
        .find_one(doc! { "_id": coid })
        .await?
        .is_none()
    {
        return Err(AppError::NotFound);
    }
    let res = state
        .db
        .collection::<Document>("modules")
        .insert_one(doc! {
            "course_id": course_id.as_str(),
            "title": super::body_str(&body, "title", "New Module"),
            "description": super::body_str(&body, "description", ""),
            "order": oint(&body, "order", 0),
            "created_at": bson::DateTime::now(),
        })
        .await?;
    let id = res.inserted_id.as_object_id().map(|o| o.to_hex()).unwrap_or_default();
    Ok(Json(json!({ "id": id, "message": "Module created" })))
}

// PUT /api/admin/modules/{module_id}
pub async fn update_module(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(module_id): Path<String>,
    Json(body): Json<Value>,
) -> AppResult<Json<Value>> {
    authenticate_admin(&state, &headers).await?;
    let oid = ObjectId::parse_str(&module_id).map_err(|_| AppError::NotFound)?;
    let mut set = Document::new();
    for f in ["title", "description", "order"] {
        if let Some(v) = body.get(f) {
            set.insert(f, bson::to_bson(v).unwrap_or(Bson::Null));
        }
    }
    set.insert("updated_at", bson::DateTime::now());
    let res = state
        .db
        .collection::<Document>("modules")
        .update_one(doc! { "_id": oid }, doc! { "$set": set })
        .await?;
    if res.matched_count == 0 {
        return Err(AppError::NotFound);
    }
    Ok(Json(json!({ "message": "Module updated" })))
}

// DELETE /api/admin/modules/{module_id}
pub async fn delete_module(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(module_id): Path<String>,
) -> AppResult<Json<Value>> {
    authenticate_admin(&state, &headers).await?;
    let oid = ObjectId::parse_str(&module_id).map_err(|_| AppError::NotFound)?;
    state
        .db
        .collection::<Document>("modules")
        .delete_one(doc! { "_id": oid })
        .await?;
    state
        .db
        .collection::<Document>("lessons")
        .delete_many(doc! { "module_id": module_id.as_str() })
        .await?;
    Ok(Json(json!({ "message": "Module and its lessons deleted" })))
}

// GET /api/admin/modules/{module_id}/lessons
pub async fn get_module_lessons(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(module_id): Path<String>,
) -> AppResult<Json<Value>> {
    authenticate_admin(&state, &headers).await?;
    let mut cur = state
        .db
        .collection::<Document>("lessons")
        .find(doc! { "module_id": module_id.as_str() })
        .sort(doc! { "order": 1 })
        .limit(100)
        .await?;
    let mut out: Vec<Value> = Vec::new();
    while cur.advance().await? {
        let l = cur.deserialize_current()?;
        out.push(json!({
            "id": hex_id(&l),
            "title": dstr_or(&l, "title", ""),
            "content": dstr_or(&l, "content", ""),
            "lesson_type": dstr_or(&l, "lesson_type", "text"),
            "order": dint(&l, "order"),
            "video_url": draw(&l, "video_url"),
            "resource_url": draw(&l, "resource_url"),
            "duration": draw(&l, "duration"),
        }));
    }
    Ok(Json(json!(out)))
}

// POST /api/admin/modules/{module_id}/lessons
pub async fn create_module_lesson(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(module_id): Path<String>,
    Json(body): Json<Value>,
) -> AppResult<Json<Value>> {
    authenticate_admin(&state, &headers).await?;
    let moid = ObjectId::parse_str(&module_id).map_err(|_| AppError::NotFound)?;
    let module = state
        .db
        .collection::<Document>("modules")
        .find_one(doc! { "_id": moid })
        .await?
        .ok_or(AppError::NotFound)?;
    let course_id = module.get_str("course_id").unwrap_or("").to_string();
    let res = state
        .db
        .collection::<Document>("lessons")
        .insert_one(doc! {
            "course_id": course_id.as_str(),
            "module_id": module_id.as_str(),
            "title": super::body_str(&body, "title", "New Lesson"),
            "content": super::body_str(&body, "content", ""),
            "lesson_type": super::body_str(&body, "lesson_type", "text"),
            "order": oint(&body, "order", 0),
            "video_url": ostr(&body, "video_url"),
            "resource_url": ostr(&body, "resource_url"),
            "duration": ostr(&body, "duration"),
            "created_at": bson::DateTime::now(),
        })
        .await?;
    let id = res.inserted_id.as_object_id().map(|o| o.to_hex()).unwrap_or_default();
    Ok(Json(json!({ "id": id, "message": "Lesson created" })))
}

// PUT /api/admin/modules/{module_id}/lessons/{lesson_id}
pub async fn update_module_lesson(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path((module_id, lesson_id)): Path<(String, String)>,
    Json(body): Json<Value>,
) -> AppResult<Json<Value>> {
    authenticate_admin(&state, &headers).await?;
    let loid = ObjectId::parse_str(&lesson_id).map_err(|_| AppError::NotFound)?;
    let mut set = Document::new();
    for f in ["title", "content", "lesson_type", "order", "video_url", "resource_url", "duration"] {
        if let Some(v) = body.get(f) {
            set.insert(f, bson::to_bson(v).unwrap_or(Bson::Null));
        }
    }
    set.insert("updated_at", bson::DateTime::now());
    let res = state
        .db
        .collection::<Document>("lessons")
        .update_one(
            doc! { "_id": loid, "module_id": module_id.as_str() },
            doc! { "$set": set },
        )
        .await?;
    if res.matched_count == 0 {
        return Err(AppError::NotFound);
    }
    Ok(Json(json!({ "message": "Lesson updated" })))
}

#[derive(Debug, Deserialize)]
pub struct LessonRequest {
    #[serde(default)]
    pub course_id: String,
    #[serde(default)]
    pub title: String,
    #[serde(default)]
    pub content: String,
    #[serde(default)]
    pub order: i64,
    #[serde(default)]
    pub video_url: Option<String>,
    #[serde(default)]
    pub duration: Option<String>,
}

// POST /api/admin/lessons
pub async fn create_lesson(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(body): Json<LessonRequest>,
) -> AppResult<Json<Value>> {
    authenticate_admin(&state, &headers).await?;
    let res = state
        .db
        .collection::<Document>("lessons")
        .insert_one(doc! {
            "course_id": body.course_id.as_str(),
            "title": body.title.as_str(),
            "content": body.content.as_str(),
            "order": body.order,
            "video_url": oopt(&body.video_url),
            "duration": oopt(&body.duration),
            "created_at": bson::DateTime::now(),
        })
        .await?;
    let id = res.inserted_id.as_object_id().map(|o| o.to_hex()).unwrap_or_default();
    Ok(Json(json!({ "id": id, "message": "Lesson created successfully" })))
}

// PUT /api/admin/lessons/{lesson_id}
pub async fn update_lesson(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(lesson_id): Path<String>,
    Json(body): Json<LessonRequest>,
) -> AppResult<Json<Value>> {
    authenticate_admin(&state, &headers).await?;
    let oid = ObjectId::parse_str(&lesson_id).map_err(|_| AppError::NotFound)?;
    state
        .db
        .collection::<Document>("lessons")
        .update_one(
            doc! { "_id": oid },
            doc! { "$set": {
                "title": body.title.as_str(),
                "content": body.content.as_str(),
                "order": body.order,
                "video_url": oopt(&body.video_url),
                "duration": oopt(&body.duration),
                "updated_at": bson::DateTime::now(),
            }},
        )
        .await?;
    Ok(Json(json!({ "message": "Lesson updated successfully" })))
}

// DELETE /api/admin/lessons/{lesson_id}
pub async fn delete_lesson(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(lesson_id): Path<String>,
) -> AppResult<Json<Value>> {
    authenticate_admin(&state, &headers).await?;
    let oid = ObjectId::parse_str(&lesson_id).map_err(|_| AppError::NotFound)?;
    state
        .db
        .collection::<Document>("lessons")
        .delete_one(doc! { "_id": oid })
        .await?;
    Ok(Json(json!({ "message": "Lesson deleted" })))
}

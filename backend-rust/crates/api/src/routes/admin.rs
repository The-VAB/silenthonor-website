//! Admin console endpoints (`/api/admin/*`). Faithful port of routers/admin.py
//! plus the admin course endpoints from routers/courses.py. Every handler
//! requires the `admin` role. DD-214 review/download is deferred with the upload
//! (needs S3); see members.rs.

use axum::extract::{Path, State};
use axum::http::HeaderMap;
use axum::response::Redirect;
use axum::Json;
use bson::oid::ObjectId;
use bson::{doc, Bson, Document};
use serde::Deserialize;
use serde_json::{json, Value};

use super::{authenticate_admin, iso, log_audit};
use crate::state::AppState;
use sh_core::{AppError, AppResult};

const PIPELINE_STAGES: [&str; 9] = [
    "applied",
    "dd214_pending",
    "dd214_review",
    "approved",
    "counselor_assigned",
    "intake_complete",
    "active",
    "graduated",
    "inactive",
];

// ── small BSON->JSON accessors (all null/absent-safe) ─────────────────────────
fn s(d: &Document, k: &str) -> Value {
    match d.get_str(k) {
        Ok(v) => Value::String(v.to_string()),
        Err(_) => Value::Null,
    }
}
fn s_or(d: &Document, k: &str, default: &str) -> Value {
    Value::String(d.get_str(k).unwrap_or(default).to_string())
}
fn b(d: &Document, k: &str) -> Value {
    Value::Bool(d.get_bool(k).unwrap_or(false))
}
fn dt(d: &Document, k: &str) -> Value {
    iso(d.get_datetime(k).ok().copied())
}
fn oid_hex(d: &Document) -> String {
    d.get_object_id("_id").map(|o| o.to_hex()).unwrap_or_default()
}
fn opt(v: &Option<String>) -> Bson {
    match v {
        Some(x) if !x.is_empty() => Bson::String(x.clone()),
        _ => Bson::Null,
    }
}
fn parse_oid(id: &str, what: &str) -> AppResult<ObjectId> {
    ObjectId::parse_str(id).map_err(|_| AppError::BadRequest(format!("Invalid {what} id")))
}

// ── GET /api/admin/stats ──────────────────────────────────────────────────────
pub async fn stats(State(state): State<AppState>, headers: HeaderMap) -> AppResult<Json<Value>> {
    authenticate_admin(&state, &headers).await?;
    let users = state.db.collection::<Document>("users");
    let total_members = users.count_documents(doc! { "role": "member" }).await?;
    let verified_members = users
        .count_documents(doc! { "role": "member", "verified": true })
        .await?;
    let pending_verification = users
        .count_documents(doc! { "role": "member", "dd214_status": "pending_review" })
        .await?;
    let total_contacts = state
        .db
        .collection::<Document>("contacts")
        .count_documents(doc! {})
        .await?;
    let total_courses = state
        .db
        .collection::<Document>("courses")
        .count_documents(doc! {})
        .await?;
    let total_counselors = users.count_documents(doc! { "role": "counselor" }).await?;
    let total_staff = users.count_documents(doc! { "role": "staff" }).await?;

    let mut pipeline = serde_json::Map::new();
    for stage in PIPELINE_STAGES {
        let c = users
            .count_documents(doc! { "role": "member", "pipeline_stage": stage })
            .await?;
        pipeline.insert(stage.to_string(), json!(c));
    }

    Ok(Json(json!({
        "total_members": total_members,
        "verified_members": verified_members,
        "pending_verification": pending_verification,
        "total_contacts": total_contacts,
        "total_courses": total_courses,
        "total_counselors": total_counselors,
        "total_staff": total_staff,
        "pipeline": pipeline,
    })))
}

// ── GET /api/admin/members ────────────────────────────────────────────────────
pub async fn members(State(state): State<AppState>, headers: HeaderMap) -> AppResult<Json<Value>> {
    authenticate_admin(&state, &headers).await?;
    let mut cursor = state
        .db
        .collection::<Document>("users")
        .find(doc! { "role": "member" })
        .sort(doc! { "created_at": -1 })
        .limit(1000)
        .await?;
    let mut out: Vec<Value> = Vec::new();
    while cursor.advance().await? {
        let d = cursor.deserialize_current()?;
        let has_counselor = d
            .get_str("assigned_counselor_id")
            .map(|v| !v.is_empty())
            .unwrap_or(false);
        out.push(json!({
            "id": oid_hex(&d),
            "email": s(&d, "email"),
            "first_name": s_or(&d, "first_name", ""),
            "last_name": s_or(&d, "last_name", ""),
            "branch": s(&d, "branch"),
            "service_status": s(&d, "service_status"),
            "verified": b(&d, "verified"),
            "dd214_status": s_or(&d, "dd214_status", "pending"),
            "dd214_file": s(&d, "dd214_file"),
            "pipeline_stage": s_or(&d, "pipeline_stage", "applied"),
            "has_counselor": has_counselor,
            "created_at": dt(&d, "created_at"),
        }));
    }
    Ok(Json(json!(out)))
}

#[derive(Debug, Deserialize)]
pub struct VerifyBody {
    #[serde(default = "verified_default")]
    pub status: String,
    #[serde(default)]
    pub notes: String,
}
fn verified_default() -> String {
    "verified".to_string()
}

// ── POST /api/admin/members/{member_id}/verify ────────────────────────────────
pub async fn verify_member(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(member_id): Path<String>,
    Json(body): Json<VerifyBody>,
) -> AppResult<Json<Value>> {
    let (_, admin) = authenticate_admin(&state, &headers).await?;
    let oid = parse_oid(&member_id, "member")?;
    let users = state.db.collection::<Document>("users");
    let member = users
        .find_one(doc! { "_id": oid })
        .await?
        .ok_or(AppError::NotFound)?;

    let verified = body.status == "verified";
    let mut set = doc! {
        "verified": verified,
        "dd214_status": body.status.as_str(),
        "verification_notes": body.notes.as_str(),
        "verified_at": if verified { Bson::DateTime(bson::DateTime::now()) } else { Bson::Null },
    };
    if body.status == "verified" {
        set.insert("pipeline_stage", "approved");
    } else if body.status == "rejected" {
        set.insert("pipeline_stage", "dd214_review");
    }
    users
        .update_one(doc! { "_id": oid }, doc! { "$set": set })
        .await?;

    log_audit(&state, "dd214_reviewed", "user", Some(&member_id), Some(admin.email.as_str())).await;

    if verified {
        if let Ok(email) = member.get_str("email") {
            let fname = member.get_str("first_name").unwrap_or("Member").to_string();
            sh_core::email::send_dd214_approved_email(email, &fname).await;
        }
    }
    Ok(Json(json!({
        "message": format!("Member verification status updated to {}", body.status)
    })))
}

#[derive(Debug, Deserialize)]
pub struct CourseRequest {
    #[serde(default)]
    pub title: String,
    #[serde(default)]
    pub description: String,
    #[serde(default = "draft_default")]
    pub status: String,
    #[serde(default)]
    pub category: Option<String>,
    #[serde(default)]
    pub thumbnail: Option<String>,
}
fn draft_default() -> String {
    "draft".to_string()
}

// ── GET /api/admin/courses ────────────────────────────────────────────────────
pub async fn list_courses(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> AppResult<Json<Value>> {
    authenticate_admin(&state, &headers).await?;
    let lessons = state.db.collection::<Document>("lessons");
    let mut cursor = state
        .db
        .collection::<Document>("courses")
        .find(doc! {})
        .sort(doc! { "created_at": -1 })
        .limit(100)
        .await?;
    let mut out: Vec<Value> = Vec::new();
    while cursor.advance().await? {
        let d = cursor.deserialize_current()?;
        let id = oid_hex(&d);
        let lesson_count = lessons
            .count_documents(doc! { "course_id": id.as_str() })
            .await?;
        out.push(json!({
            "id": id,
            "title": s(&d, "title"),
            "description": s(&d, "description"),
            "status": s_or(&d, "status", "draft"),
            "total_lessons": lesson_count,
            "category": s(&d, "category"),
            "thumbnail": s(&d, "thumbnail"),
            "created_at": dt(&d, "created_at"),
        }));
    }
    Ok(Json(json!(out)))
}

// ── POST /api/admin/courses ───────────────────────────────────────────────────
pub async fn create_course(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(body): Json<CourseRequest>,
) -> AppResult<Json<Value>> {
    let (_, admin) = authenticate_admin(&state, &headers).await?;
    let now = bson::DateTime::now();
    let res = state
        .db
        .collection::<Document>("courses")
        .insert_one(doc! {
            "title": body.title.as_str(),
            "description": body.description.as_str(),
            "status": body.status.as_str(),
            "category": opt(&body.category),
            "thumbnail": opt(&body.thumbnail),
            "created_at": now,
            "updated_at": now,
        })
        .await?;
    let id = res
        .inserted_id
        .as_object_id()
        .map(|o| o.to_hex())
        .unwrap_or_default();
    log_audit(&state, "course_created", "course", Some(&id), Some(admin.email.as_str())).await;
    Ok(Json(json!({ "id": id, "message": "Course created successfully" })))
}

// ── PUT /api/admin/courses/{course_id} ────────────────────────────────────────
pub async fn update_course(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(course_id): Path<String>,
    Json(body): Json<CourseRequest>,
) -> AppResult<Json<Value>> {
    let (_, admin) = authenticate_admin(&state, &headers).await?;
    let oid = parse_oid(&course_id, "course")?;
    state
        .db
        .collection::<Document>("courses")
        .update_one(
            doc! { "_id": oid },
            doc! { "$set": {
                "title": body.title.as_str(),
                "description": body.description.as_str(),
                "status": body.status.as_str(),
                "category": opt(&body.category),
                "thumbnail": opt(&body.thumbnail),
                "updated_at": bson::DateTime::now(),
            }},
        )
        .await?;
    log_audit(&state, "course_updated", "course", Some(&course_id), Some(admin.email.as_str())).await;
    Ok(Json(json!({ "message": "Course updated successfully" })))
}

// ── DELETE /api/admin/courses/{course_id} ─────────────────────────────────────
pub async fn delete_course(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(course_id): Path<String>,
) -> AppResult<Json<Value>> {
    let (_, admin) = authenticate_admin(&state, &headers).await?;
    let oid = parse_oid(&course_id, "course")?;
    state
        .db
        .collection::<Document>("courses")
        .delete_one(doc! { "_id": oid })
        .await?;
    state
        .db
        .collection::<Document>("lessons")
        .delete_many(doc! { "course_id": course_id.as_str() })
        .await?;
    log_audit(&state, "course_deleted", "course", Some(&course_id), Some(admin.email.as_str())).await;
    Ok(Json(json!({ "message": "Course and lessons deleted" })))
}

// ── GET /api/admin/contacts ───────────────────────────────────────────────────
pub async fn list_contacts(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> AppResult<Json<Value>> {
    authenticate_admin(&state, &headers).await?;
    let mut cursor = state
        .db
        .collection::<Document>("contacts")
        .find(doc! {})
        .sort(doc! { "created_at": -1 })
        .limit(500)
        .await?;
    let mut out: Vec<Value> = Vec::new();
    while cursor.advance().await? {
        let d = cursor.deserialize_current()?;
        out.push(json!({
            "id": oid_hex(&d),
            "first_name": s(&d, "first_name"),
            "last_name": s(&d, "last_name"),
            "email": s(&d, "email"),
            "topic": s(&d, "topic"),
            "message": s(&d, "message"),
            "created_at": dt(&d, "created_at"),
            "responded": b(&d, "responded"),
        }));
    }
    Ok(Json(json!(out)))
}

#[derive(Debug, Deserialize)]
pub struct RespondedBody {
    #[serde(default = "yes")]
    pub responded: bool,
}
fn yes() -> bool {
    true
}

// ── PUT /api/admin/contacts/{contact_id} ──────────────────────────────────────
pub async fn update_contact(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(contact_id): Path<String>,
    Json(body): Json<RespondedBody>,
) -> AppResult<Json<Value>> {
    authenticate_admin(&state, &headers).await?;
    let oid = parse_oid(&contact_id, "contact")?;
    state
        .db
        .collection::<Document>("contacts")
        .update_one(
            doc! { "_id": oid },
            doc! { "$set": { "responded": body.responded } },
        )
        .await?;
    Ok(Json(json!({ "message": "Contact updated" })))
}

// ── DELETE /api/admin/contacts/{contact_id} ───────────────────────────────────
pub async fn delete_contact(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(contact_id): Path<String>,
) -> AppResult<Json<Value>> {
    authenticate_admin(&state, &headers).await?;
    let oid = parse_oid(&contact_id, "contact")?;
    state
        .db
        .collection::<Document>("contacts")
        .delete_one(doc! { "_id": oid })
        .await?;
    Ok(Json(json!({ "message": "Contact deleted" })))
}

// ── GET /api/admin/dd214/{filename} -- redirect to a presigned S3 URL ─────────
pub async fn download_dd214(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(filename): Path<String>,
) -> AppResult<Redirect> {
    authenticate_admin(&state, &headers).await?;
    let key = format!("{}{filename}", sh_core::storage::DD214_PREFIX);
    let url = sh_core::storage::presign_get(&key, 3600)
        .await
        .map_err(AppError::Internal)?;
    Ok(Redirect::temporary(&url))
}

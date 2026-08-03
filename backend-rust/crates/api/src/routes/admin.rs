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
use chrono::{Datelike, Duration as ChronoDuration, TimeZone, Utc};
use serde::Deserialize;
use serde_json::{json, Value};

use super::{authenticate_admin, full_name, iso, log_audit, sanitize};
use crate::state::AppState;
use sh_core::auth::hash_password;
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

// Credit-repair + financial-counseling pipeline stages (analytics distributions).
const CR_STAGES: [&str; 8] = [
    "cr_waitlist", "cr_consultation", "cr_documents", "cr_dispute_1", "cr_dispute_2",
    "cr_dispute_3", "cr_monitoring", "cr_complete",
];
const FC_STAGES: [&str; 6] = [
    "fc_waitlist", "fc_consultation", "fc_documents", "fc_gameplan", "fc_working", "fc_complete",
];

/// N random bytes rendered as lowercase hex. Used for one-time invite tokens and
/// temporary staff passwords (Python uses secrets.token_urlsafe; the exact
/// encoding is irrelevant since both write and read stay inside this service).
fn rand_hex(n: usize) -> String {
    let mut buf = vec![0u8; n];
    getrandom::getrandom(&mut buf).ok();
    buf.iter().map(|b| format!("{b:02x}")).collect()
}

/// Aggregate `$sum` count (Int32/Int64/Double) from a grouped document.
fn cnt(d: &Document, k: &str) -> i64 {
    match d.get(k) {
        Some(Bson::Int32(i)) => *i as i64,
        Some(Bson::Int64(i)) => *i,
        Some(Bson::Double(f)) => *f as i64,
        _ => 0,
    }
}

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

// ── GET /api/admin/analytics -- dashboard charts ──────────────────────────────
pub async fn analytics(State(state): State<AppState>, headers: HeaderMap) -> AppResult<Json<Value>> {
    authenticate_admin(&state, &headers).await?;
    let users = state.db.collection::<Document>("users");
    let courses = state.db.collection::<Document>("courses");

    let total_members = users.count_documents(doc! { "role": "member" }).await?;
    let verified_members = users
        .count_documents(doc! { "role": "member", "verified": true })
        .await?;
    let pending_dd214 = users
        .count_documents(doc! { "role": "member", "dd214_status": "pending_review" })
        .await?;
    let total_counselors = users
        .count_documents(doc! { "role": "counselor", "active": true })
        .await?;
    let active_courses = courses.count_documents(doc! { "status": "published" }).await?;

    let now = bson::DateTime::now().to_chrono();
    let month_start = Utc.with_ymd_and_hms(now.year(), now.month(), 1, 0, 0, 0).unwrap();
    let new_this_month = users
        .count_documents(doc! { "role": "member", "created_at": { "$gte": bson::DateTime::from_chrono(month_start) } })
        .await?;

    // Members by month (last 6). Mirrors the Python 30-day-step + first-of-month.
    let mut monthly: Vec<Value> = Vec::new();
    for i in (0i64..=5).rev() {
        let base = now - ChronoDuration::days(30 * i);
        let ms = Utc.with_ymd_and_hms(base.year(), base.month(), 1, 0, 0, 0).unwrap();
        let (ny, nm) = if base.month() == 12 {
            (base.year() + 1, 1)
        } else {
            (base.year(), base.month() + 1)
        };
        let me = Utc.with_ymd_and_hms(ny, nm, 1, 0, 0, 0).unwrap();
        let count = users
            .count_documents(doc! { "role": "member", "created_at": {
                "$gte": bson::DateTime::from_chrono(ms),
                "$lt": bson::DateTime::from_chrono(me),
            }})
            .await?;
        monthly.push(json!({ "month": ms.format("%b %Y").to_string(), "count": count }));
    }

    // Branch breakdown via aggregation.
    let mut branches = serde_json::Map::new();
    let mut agg = users
        .aggregate(vec![
            doc! { "$match": { "role": "member" } },
            doc! { "$group": { "_id": "$branch", "count": { "$sum": 1 } } },
        ])
        .await?;
    while agg.advance().await? {
        let d = agg.deserialize_current()?;
        let key = match d.get("_id") {
            Some(Bson::String(v)) if !v.is_empty() => v.clone(),
            _ => "Not Specified".to_string(),
        };
        branches.insert(key, json!(cnt(&d, "count")));
    }

    let dist = |field: &'static str, stages: &[&str]| {
        let users = users.clone();
        let stages: Vec<String> = stages.iter().map(|s| s.to_string()).collect();
        async move {
            let mut m = serde_json::Map::new();
            for s in stages {
                let c = users
                    .count_documents(doc! { "role": "member", field: s.as_str() })
                    .await?;
                m.insert(s, json!(c));
            }
            Ok::<_, AppError>(m)
        }
    };

    let pipeline = dist("pipeline_stage", &PIPELINE_STAGES).await?;
    let cr = dist("credit_repair_stage", &CR_STAGES).await?;
    let fc = dist("financial_counseling_stage", &FC_STAGES).await?;
    let dd214 = dist(
        "dd214_status",
        &["pending", "pending_review", "approved", "rejected", "manual_approved"],
    )
    .await?;

    Ok(Json(json!({
        "kpis": {
            "total_members": total_members,
            "verified_members": verified_members,
            "pending_dd214": pending_dd214,
            "total_counselors": total_counselors,
            "active_courses": active_courses,
            "new_this_month": new_this_month,
        },
        "monthly_members": monthly,
        "branches": Value::Object(branches),
        "pipeline": Value::Object(pipeline),
        "dd214": Value::Object(dd214),
        "cr_pipeline": Value::Object(cr),
        "fc_pipeline": Value::Object(fc),
    })))
}

// ── GET /api/admin/audit-log ──────────────────────────────────────────────────
pub async fn audit_log(State(state): State<AppState>, headers: HeaderMap) -> AppResult<Json<Value>> {
    authenticate_admin(&state, &headers).await?;
    let mut cursor = state
        .db
        .collection::<Document>("audit_log")
        .find(doc! {})
        .sort(doc! { "timestamp": -1 })
        .limit(500)
        .await?;
    let mut out: Vec<Value> = Vec::new();
    while cursor.advance().await? {
        let d = cursor.deserialize_current()?;
        let details = d.get("details").cloned().map(sanitize).unwrap_or_else(|| json!({}));
        out.push(json!({
            "id": oid_hex(&d),
            "action": s(&d, "action"),
            "entity_type": s(&d, "entity_type"),
            "entity_id": s(&d, "entity_id"),
            "user_email": s(&d, "user_email"),
            "details": details,
            "ip_address": s(&d, "ip_address"),
            "timestamp": dt(&d, "timestamp"),
        }));
    }
    Ok(Json(json!(out)))
}

/// Resolve a name-or-string ObjectId reference (a field may be stored as either).
fn as_oid(b: Option<&Bson>) -> Option<ObjectId> {
    match b {
        Some(Bson::ObjectId(o)) => Some(*o),
        Some(Bson::String(s)) if !s.is_empty() => ObjectId::parse_str(s).ok(),
        _ => None,
    }
}

// ── GET /api/admin/members/{member_id} -- full raw member doc + counselor ──────
pub async fn member_detail(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(member_id): Path<String>,
) -> AppResult<Json<Value>> {
    authenticate_admin(&state, &headers).await?;
    let oid = ObjectId::parse_str(&member_id).map_err(|_| AppError::NotFound)?;
    let users = state.db.collection::<Document>("users");
    let member = users
        .find_one(doc! { "_id": oid })
        .await?
        .ok_or(AppError::NotFound)?;

    let mut obj = match sanitize(Bson::Document(member.clone())) {
        Value::Object(m) => m,
        _ => serde_json::Map::new(),
    };
    obj.remove("password_hash");

    if let Some(coid) = as_oid(member.get("assigned_counselor_id")) {
        if let Some(c) = users.find_one(doc! { "_id": coid }).await? {
            obj.insert(
                "counselor".to_string(),
                json!({
                    "id": coid.to_hex(),
                    "name": full_name(&c),
                    "email": c.get_str("email").ok(),
                }),
            );
        }
    }
    Ok(Json(Value::Object(obj)))
}

// ── GET /api/admin/members/{member_id}/full -- profile + courses/disputes/notes ─
pub async fn member_full(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(member_id): Path<String>,
) -> AppResult<Json<Value>> {
    authenticate_admin(&state, &headers).await?;
    let oid = ObjectId::parse_str(&member_id)
        .map_err(|_| AppError::BadRequest(format!("Invalid member ID format: {member_id}")))?;
    let users = state.db.collection::<Document>("users");
    let member = users
        .find_one(doc! { "_id": oid })
        .await?
        .ok_or_else(|| AppError::NotFound)?;

    // Enrolled courses with progress.
    let courses_col = state.db.collection::<Document>("courses");
    let mut pcur = state
        .db
        .collection::<Document>("course_progress")
        .find(doc! { "user_id": oid })
        .limit(50)
        .await?;
    let mut courses: Vec<Value> = Vec::new();
    while pcur.advance().await? {
        let p = pcur.deserialize_current()?;
        let cid = p.get_str("course_id").unwrap_or("").to_string();
        if cid.len() == 24 {
            if let Ok(coid) = ObjectId::parse_str(&cid) {
                if let Some(course) = courses_col.find_one(doc! { "_id": coid }).await? {
                    courses.push(json!({
                        "id": oid_hex(&course),
                        "title": s_or(&course, "title", ""),
                        "percent_complete": super::dint(&p, "percent_complete"),
                        "last_accessed": dt(&p, "updated_at"),
                    }));
                }
            }
        }
    }

    // Disputes.
    let mut dcur = state
        .db
        .collection::<Document>("disputes")
        .find(doc! { "user_id": oid })
        .sort(doc! { "created_at": -1 })
        .limit(50)
        .await?;
    let mut disputes: Vec<Value> = Vec::new();
    while dcur.advance().await? {
        let d = dcur.deserialize_current()?;
        disputes.push(json!({
            "id": oid_hex(&d),
            "bureau": s(&d, "bureau"),
            "account": s(&d, "account"),
            "status": s(&d, "status"),
            "round": super::draw(&d, "round"),
            "created_at": dt(&d, "created_at"),
        }));
    }

    // Intake notes.
    let mut ncur = state
        .db
        .collection::<Document>("intake_notes")
        .find(doc! { "member_id": oid })
        .sort(doc! { "created_at": -1 })
        .limit(50)
        .await?;
    let mut notes: Vec<Value> = Vec::new();
    while ncur.advance().await? {
        let n = ncur.deserialize_current()?;
        notes.push(json!({
            "id": oid_hex(&n),
            "content": s_or(&n, "content", ""),
            "author": s_or(&n, "author", ""),
            "created_at": dt(&n, "created_at"),
        }));
    }

    let counselor_oid = as_oid(member.get("assigned_counselor_id"));
    let counselor_name = match counselor_oid {
        Some(coid) => users.find_one(doc! { "_id": coid }).await?.map(|c| full_name(&c)),
        None => None,
    };
    let acid_out = match member.get("assigned_counselor_id") {
        Some(Bson::ObjectId(o)) => json!(o.to_hex()),
        Some(Bson::String(v)) if !v.is_empty() => json!(v),
        _ => Value::Null,
    };

    Ok(Json(json!({
        "id": oid_hex(&member),
        "email": s_or(&member, "email", ""),
        "first_name": s_or(&member, "first_name", ""),
        "last_name": s_or(&member, "last_name", ""),
        "phone": s_or(&member, "phone", ""),
        "state": s_or(&member, "state", ""),
        "dob": s_or(&member, "dob", ""),
        "branch": s_or(&member, "branch", ""),
        "service_status": s_or(&member, "service_status", ""),
        "years_of_service": super::draw(&member, "years_of_service"),
        "separation_year": super::draw(&member, "separation_year"),
        "challenges": s_or(&member, "challenges", ""),
        "how_heard": s_or(&member, "how_heard", ""),
        "notes": s_or(&member, "notes", ""),
        "role": s_or(&member, "role", "member"),
        "verified": b(&member, "verified"),
        "dd214_status": s_or(&member, "dd214_status", "pending"),
        "dd214_file": s(&member, "dd214_file"),
        "dd214_approved_by": s(&member, "dd214_approved_by"),
        "dd214_approved_at": dt(&member, "dd214_approved_at"),
        "pipeline_stage": s_or(&member, "pipeline_stage", "applied"),
        "cr_stage": s(&member, "credit_repair_stage"),
        "fc_stage": s(&member, "financial_counseling_stage"),
        "assigned_counselor_id": acid_out,
        "assigned_counselor_name": counselor_name,
        "admin_notes": s_or(&member, "admin_notes", ""),
        "created_at": dt(&member, "created_at"),
        "courses": courses,
        "disputes": disputes,
        "notes_history": notes,
    })))
}

// ── GET /api/admin/members/{member_id}/notes ──────────────────────────────────
pub async fn get_member_notes(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(member_id): Path<String>,
) -> AppResult<Json<Value>> {
    authenticate_admin(&state, &headers).await?;
    let oid = ObjectId::parse_str(&member_id).map_err(|_| AppError::NotFound)?;
    let mut cursor = state
        .db
        .collection::<Document>("intake_notes")
        .find(doc! { "member_id": oid })
        .sort(doc! { "created_at": -1 })
        .limit(100)
        .await?;
    let mut out: Vec<Value> = Vec::new();
    while cursor.advance().await? {
        let n = cursor.deserialize_current()?;
        out.push(json!({
            "id": oid_hex(&n),
            "content": s_or(&n, "content", ""),
            "note_type": s_or(&n, "note_type", "general"),
            "created_by": s_or(&n, "created_by_name", "Admin"),
            "created_at": dt(&n, "created_at"),
        }));
    }
    Ok(Json(json!(out)))
}

#[derive(Debug, Deserialize)]
pub struct NoteBody {
    #[serde(default)]
    pub content: String,
    #[serde(default = "general")]
    pub note_type: String,
}
fn general() -> String {
    "general".to_string()
}

// ── POST /api/admin/members/{member_id}/notes ─────────────────────────────────
pub async fn add_member_note(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(member_id): Path<String>,
    Json(body): Json<NoteBody>,
) -> AppResult<Json<Value>> {
    let (admin_id, admin) = authenticate_admin(&state, &headers).await?;
    let moid = ObjectId::parse_str(&member_id).map_err(|_| AppError::NotFound)?;
    let admin_oid = ObjectId::parse_str(&admin_id).map_err(|_| AppError::Unauthorized)?;
    let name = {
        let n = full_name_of(&admin);
        if n.is_empty() { "Admin".to_string() } else { n }
    };
    let res = state
        .db
        .collection::<Document>("intake_notes")
        .insert_one(doc! {
            "member_id": moid,
            "content": body.content.as_str(),
            "note_type": body.note_type.as_str(),
            "created_by": admin_oid,
            "created_by_name": name.as_str(),
            "created_at": bson::DateTime::now(),
        })
        .await?;
    let id = res.inserted_id.as_object_id().map(|o| o.to_hex()).unwrap_or_default();
    Ok(Json(json!({ "id": id, "message": "Note added" })))
}

#[derive(Debug, Deserialize)]
pub struct PasswordBody {
    #[serde(default)]
    pub password: String,
}

// ── PUT /api/admin/members/{member_id}/password ───────────────────────────────
pub async fn set_member_password(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(member_id): Path<String>,
    Json(body): Json<PasswordBody>,
) -> AppResult<Json<Value>> {
    let (_, admin) = authenticate_admin(&state, &headers).await?;
    let new_password = body.password.trim();
    if new_password.len() < 6 {
        return Err(AppError::BadRequest(
            "Password must be at least 6 characters".to_string(),
        ));
    }
    let oid = ObjectId::parse_str(&member_id).map_err(|_| AppError::NotFound)?;
    let users = state.db.collection::<Document>("users");
    if users.find_one(doc! { "_id": oid }).await?.is_none() {
        return Err(AppError::NotFound);
    }
    let hash = hash_password(new_password).map_err(AppError::Internal)?;
    users
        .update_one(
            doc! { "_id": oid },
            doc! { "$set": { "password_hash": hash.as_str(), "updated_at": bson::DateTime::now() } },
        )
        .await?;
    log_audit(&state, "ADMIN_SET_PASSWORD", "user", Some(&member_id), Some(admin.email.as_str())).await;
    Ok(Json(json!({ "message": "Password updated" })))
}

#[derive(Debug, Deserialize)]
pub struct ApproveDd214Body {
    #[serde(default)]
    pub notes: String,
}

// ── POST /api/admin/members/{member_id}/approve-dd214 ─────────────────────────
pub async fn approve_dd214(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(member_id): Path<String>,
    Json(body): Json<ApproveDd214Body>,
) -> AppResult<Json<Value>> {
    let (_, admin) = authenticate_admin(&state, &headers).await?;
    let oid = ObjectId::parse_str(&member_id).map_err(|_| AppError::NotFound)?;
    let users = state.db.collection::<Document>("users");
    let member = users
        .find_one(doc! { "_id": oid })
        .await?
        .ok_or(AppError::NotFound)?;
    let now = bson::DateTime::now();
    users
        .update_one(
            doc! { "_id": oid },
            doc! { "$set": {
                "dd214_status": "manual_approved",
                "dd214_approved_by": admin.email.as_str(),
                "dd214_approved_at": now,
                "dd214_approval_notes": body.notes.as_str(),
                "verified": true,
                "updated_at": now,
            }},
        )
        .await?;
    log_audit(&state, "DD214_MANUAL_APPROVED", "user", Some(&member_id), Some(admin.email.as_str())).await;
    if let Ok(email) = member.get_str("email") {
        let fname = member.get_str("first_name").unwrap_or("Member").to_string();
        sh_core::email::send_dd214_approved_email(email, &fname).await;
    }
    Ok(Json(json!({ "message": "DD-214 manually approved, member verified" })))
}

// ── PATCH /api/admin/members/{member_id}/archive ──────────────────────────────
pub async fn archive_member(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(member_id): Path<String>,
) -> AppResult<Json<Value>> {
    let (_, admin) = authenticate_admin(&state, &headers).await?;
    let oid = ObjectId::parse_str(&member_id).map_err(|_| AppError::NotFound)?;
    let users = state.db.collection::<Document>("users");
    let member = users
        .find_one(doc! { "_id": oid, "role": "member" })
        .await?
        .ok_or(AppError::NotFound)?;
    let now = bson::DateTime::now();
    users
        .update_one(
            doc! { "_id": oid },
            doc! { "$set": {
                "pipeline_stage": "inactive",
                "is_active": false,
                "archived_at": now,
                "archived_by": admin.email.as_str(),
                "updated_at": now,
            }},
        )
        .await?;
    log_audit(&state, "MEMBER_ARCHIVED", "user", Some(&member_id), Some(admin.email.as_str())).await;
    let fname = member.get_str("first_name").unwrap_or("Member");
    Ok(Json(json!({ "message": format!("{fname} has been archived") })))
}

// ── GET /api/admin/staff/{staff_id}/full -- profile + clients + activity ───────
pub async fn staff_full(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(staff_id): Path<String>,
) -> AppResult<Json<Value>> {
    authenticate_admin(&state, &headers).await?;
    let oid = ObjectId::parse_str(&staff_id)
        .map_err(|_| AppError::BadRequest("Invalid staff ID".to_string()))?;
    let users = state.db.collection::<Document>("users");
    let staff = users
        .find_one(doc! { "_id": oid, "role": { "$in": ["staff", "admin", "counselor"] } })
        .await?
        .ok_or(AppError::NotFound)?;

    let mut result = json!({
        "id": oid_hex(&staff),
        "email": s_or(&staff, "email", ""),
        "first_name": s_or(&staff, "first_name", ""),
        "last_name": s_or(&staff, "last_name", ""),
        "role": s_or(&staff, "role", ""),
        "title": s_or(&staff, "title", ""),
        "bio": s_or(&staff, "bio", ""),
        "specialties": arr(&staff, "specialties"),
        "credentials": s_or(&staff, "credentials", ""),
        "calendly_url": s(&staff, "calendly_url"),
        "active": Value::Bool(staff.get_bool("active").unwrap_or(true)),
        "created_at": dt(&staff, "created_at"),
        "last_active": dt(&staff, "last_active"),
    });

    if staff.get_str("role").unwrap_or("") == "counselor" {
        let intake = state.db.collection::<Document>("intake_notes");
        let disputes = state.db.collection::<Document>("disputes");

        let mut ccur = users
            .find(doc! { "assigned_counselor_id": oid })
            .sort(doc! { "created_at": -1 })
            .limit(200)
            .await?;
        let mut clients: Vec<Value> = Vec::new();
        while ccur.advance().await? {
            let c = ccur.deserialize_current()?;
            let cid = c.get_object_id("_id").ok();
            let notes_count = match cid {
                Some(cid) => intake
                    .count_documents(doc! { "member_id": cid, "created_by": oid })
                    .await?,
                None => 0,
            };
            let disputes_count = match cid {
                Some(cid) => disputes.count_documents(doc! { "user_id": cid }).await?,
                None => 0,
            };
            clients.push(json!({
                "id": oid_hex(&c),
                "name": full_name(&c),
                "email": s_or(&c, "email", ""),
                "pipeline_stage": s_or(&c, "pipeline_stage", "applied"),
                "cr_stage": s(&c, "credit_repair_stage"),
                "fc_stage": s(&c, "financial_counseling_stage"),
                "notes_count": notes_count,
                "disputes_count": disputes_count,
                "created_at": dt(&c, "created_at"),
            }));
        }
        result["clients"] = json!(clients);

        let mut acur = intake
            .find(doc! { "created_by": oid })
            .sort(doc! { "created_at": -1 })
            .limit(20)
            .await?;
        let mut activity: Vec<Value> = Vec::new();
        while acur.advance().await? {
            let n = acur.deserialize_current()?;
            let member_name = match as_oid(n.get("member_id")) {
                Some(mid) => users
                    .find_one(doc! { "_id": mid })
                    .await?
                    .map(|m| full_name(&m))
                    .unwrap_or_else(|| "Unknown".to_string()),
                None => "Unknown".to_string(),
            };
            let member_id = match n.get("member_id") {
                Some(Bson::ObjectId(o)) => o.to_hex(),
                Some(Bson::String(v)) => v.clone(),
                _ => String::new(),
            };
            activity.push(json!({
                "type": "note",
                "member_id": member_id,
                "member_name": member_name,
                "content": s_or(&n, "content", ""),
                "created_at": dt(&n, "created_at"),
            }));
        }
        result["recent_activity"] = json!(activity);
    }

    Ok(Json(result))
}

// ── POST /api/admin/staff/{staff_id}/invite -- portal password-setup email ─────
pub async fn staff_invite(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(staff_id): Path<String>,
) -> AppResult<Json<Value>> {
    let (_, admin) = authenticate_admin(&state, &headers).await?;
    let oid = ObjectId::parse_str(&staff_id)
        .map_err(|_| AppError::BadRequest("Invalid staff ID".to_string()))?;
    let users = state.db.collection::<Document>("users");
    let staff = users
        .find_one(doc! { "_id": oid, "role": { "$in": ["counselor", "staff", "admin"] } })
        .await?
        .ok_or(AppError::NotFound)?;

    let email = staff.get_str("email").unwrap_or("").to_string();
    let token = rand_hex(32);
    let now = bson::DateTime::now();
    let expires = bson::DateTime::from_millis(now.timestamp_millis() + 24 * 3_600_000);
    state
        .db
        .collection::<Document>("password_reset_tokens")
        .insert_one(doc! {
            "token": token.as_str(),
            "user_id": oid,
            "email": email.as_str(),
            "created_at": now,
            "expires_at": expires,
            "used": false,
        })
        .await?;

    let first_name = staff
        .get_str("first_name")
        .ok()
        .filter(|s| !s.is_empty())
        .unwrap_or(if email.is_empty() { "there" } else { email.as_str() })
        .to_string();
    let role = staff.get_str("role").unwrap_or("counselor").to_string();
    let sent = sh_core::email::send_staff_invite_email(&email, &first_name, &role, &token).await;
    if !sent {
        return Err(AppError::Internal(anyhow::anyhow!(
            "Failed to send invite email. Check email service configuration."
        )));
    }
    log_audit(&state, "STAFF_INVITE_SENT", "user", Some(&staff_id), Some(admin.email.as_str())).await;
    Ok(Json(json!({ "message": format!("Invite sent to {email}") })))
}

/// "first_name last_name" of a `User`, trimmed.
fn full_name_of(u: &sh_core::models::User) -> String {
    format!(
        "{} {}",
        u.first_name.clone().unwrap_or_default(),
        u.last_name.clone().unwrap_or_default()
    )
    .trim()
    .to_string()
}

/// Array field -> JSON array (relaxed passthrough), or empty array when absent.
fn arr(d: &Document, k: &str) -> Value {
    match d.get_array(k) {
        Ok(a) => Value::Array(a.iter().cloned().map(sanitize).collect()),
        Err(_) => json!([]),
    }
}

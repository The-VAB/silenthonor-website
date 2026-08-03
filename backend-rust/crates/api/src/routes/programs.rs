//! Programs + applications (`/api/member/programs`, `/api/member/apply/*`).
//! Port of routers/programs.py. Collections `program_applications`, `users`.

use axum::extract::{Path, Query, State};
use axum::http::HeaderMap;
use axum::Json;
use bson::oid::ObjectId;
use bson::{doc, Bson, Document};
use serde_json::{json, Value};
use std::collections::HashMap;

use super::{
    authenticate, authenticate_admin, body_bson, body_str, ddate, dstr, dstr_or, full_name, hex_id,
    log_audit, sanitize,
};
use crate::state::AppState;
use sh_core::models::User;
use sh_core::{AppError, AppResult};

// Pipeline stage lists (mirror routers/programs.py).
const ONBOARDING_STAGES: [&str; 7] = [
    "applied", "dd214_pending", "dd214_review", "approved", "active", "inactive", "graduated",
];
const CREDIT_REPAIR_STAGES: [&str; 8] = [
    "cr_waitlist", "cr_consultation", "cr_documents", "cr_dispute_1", "cr_dispute_2", "cr_dispute_3",
    "cr_monitoring", "cr_complete",
];
const FINANCIAL_COUNSELING_STAGES: [&str; 6] = [
    "fc_waitlist", "fc_consultation", "fc_documents", "fc_gameplan", "fc_working", "fc_complete",
];

fn uid(id: &str) -> AppResult<ObjectId> {
    ObjectId::parse_str(id).map_err(|_| AppError::Unauthorized)
}

const CR_KEYS: &[&str] = &[
    "experian_score", "equifax_score", "transunion_score", "total_debt", "monthly_income",
    "recent_bankruptcy", "bankruptcy_chapter", "bankruptcy_year", "outstanding_collections",
    "negative_items_count", "primary_credit_issues", "worked_with_credit_repair_before",
    "credit_repair_goals", "target_timeline", "credit_reports_uploaded", "additional_notes",
];
const FC_KEYS: &[&str] = &[
    "primary_challenges", "monthly_income", "monthly_expenses", "total_debt", "debt_types",
    "has_written_budget", "has_emergency_fund", "emergency_fund_months",
    "worked_with_counselor_before", "top_financial_goals", "areas_need_help", "additional_notes",
];

// GET /api/member/programs
pub async fn list_programs(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> AppResult<Json<Value>> {
    let (id, _) = authenticate(&state, &headers).await?;
    let oid = uid(&id)?;
    let mut cur = state
        .db
        .collection::<Document>("program_applications")
        .find(doc! { "member_id": oid })
        .sort(doc! { "applied_at": -1 })
        .limit(10)
        .await?;
    let users = state.db.collection::<Document>("users");
    let mut cr: Option<Value> = None;
    let mut fc: Option<Value> = None;
    while cur.advance().await? {
        let a = cur.deserialize_current()?;
        let pt = a.get_str("program_type").unwrap_or("").to_string();
        let slot = match pt.as_str() {
            "credit_repair" => &mut cr,
            "financial_counseling" => &mut fc,
            _ => continue,
        };
        if slot.is_none() {
            let counselor = match a.get_object_id("counselor_id").ok() {
                Some(cid) => match users.find_one(doc! { "_id": cid }).await? {
                    Some(c) => json!({ "id": cid.to_hex(), "name": full_name(&c) }),
                    None => Value::Null,
                },
                None => Value::Null,
            };
            *slot = Some(json!({
                "id": hex_id(&a),
                "status": dstr_or(&a, "status", "pending"),
                "applied_at": ddate(&a, "applied_at"),
                "counselor": counselor,
            }));
        }
    }
    let userdoc = users.find_one(doc! { "_id": oid }).await?;
    let stage = |field: &str| -> Value {
        userdoc
            .as_ref()
            .and_then(|u| u.get_str(field).ok())
            .map(|s| json!(s))
            .unwrap_or(Value::Null)
    };
    Ok(Json(json!({
        "credit_repair": cr.unwrap_or(Value::Null),
        "financial_counseling": fc.unwrap_or(Value::Null),
        "credit_repair_stage": stage("credit_repair_stage"),
        "financial_counseling_stage": stage("financial_counseling_stage"),
    })))
}

#[allow(clippy::too_many_arguments)]
async fn apply(
    state: AppState,
    headers: HeaderMap,
    body: Value,
    program_type: &str,
    data_keys: &[&str],
    stage_field: &str,
    waitlist_stage: &str,
    admin_subject: &str,
    program_label: &str,
    dup_msg: &str,
    success_msg: &str,
) -> AppResult<Json<Value>> {
    let (id, user): (String, User) = authenticate(&state, &headers).await?;
    let oid = uid(&id)?;
    let users = state.db.collection::<Document>("users");

    let member = users.find_one(doc! { "_id": oid }).await?;
    let verified = member.as_ref().map(|m| m.get_bool("verified").unwrap_or(false)).unwrap_or(false);
    if !verified {
        return Err(AppError::Forbidden(
            "You must be a verified member to apply for programs".to_string(),
        ));
    }
    let apps = state.db.collection::<Document>("program_applications");
    if apps
        .find_one(doc! {
            "member_id": oid,
            "program_type": program_type,
            "status": { "$in": ["pending", "approved"] },
        })
        .await?
        .is_some()
    {
        return Err(AppError::BadRequest(dup_msg.to_string()));
    }

    let mut app_data = Document::new();
    for k in data_keys {
        app_data.insert(*k, body_bson(&body, k));
    }
    let member_name = format!(
        "{} {}",
        user.first_name.clone().unwrap_or_default(),
        user.last_name.clone().unwrap_or_default()
    )
    .trim()
    .to_string();
    let now = bson::DateTime::now();
    let res = apps
        .insert_one(doc! {
            "member_id": oid,
            "member_email": user.email.as_str(),
            "member_name": member_name.as_str(),
            "program_type": program_type,
            "status": "pending",
            "applied_at": now,
            "reviewed_at": Bson::Null,
            "reviewed_by": Bson::Null,
            "counselor_id": Bson::Null,
            "application_data": app_data,
            "notes": "",
        })
        .await?;
    let iid = res.inserted_id.as_object_id().map(|o| o.to_hex()).unwrap_or_default();

    users
        .update_one(doc! { "_id": oid }, doc! { "$set": { stage_field: waitlist_stage } })
        .await?;
    log_audit(
        &state,
        "PROGRAM_APPLICATION_SUBMITTED",
        "program_application",
        Some(&iid),
        Some(user.email.as_str()),
    )
    .await;
    sh_core::email::send_admin_notification(
        admin_subject,
        &format!("{member_name} ({}) has applied for the {program_label} program.", user.email),
    )
    .await;
    Ok(Json(json!({ "id": iid, "message": success_msg })))
}

// POST /api/member/apply/credit-repair
pub async fn apply_credit_repair(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(body): Json<Value>,
) -> AppResult<Json<Value>> {
    apply(
        state,
        headers,
        body,
        "credit_repair",
        CR_KEYS,
        "credit_repair_stage",
        "cr_waitlist",
        "New Credit Repair Application",
        "Credit Repair",
        "You already have a pending or approved credit repair application",
        "Credit repair application submitted successfully",
    )
    .await
}

// POST /api/member/apply/financial-counseling
pub async fn apply_financial_counseling(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(body): Json<Value>,
) -> AppResult<Json<Value>> {
    apply(
        state,
        headers,
        body,
        "financial_counseling",
        FC_KEYS,
        "financial_counseling_stage",
        "fc_waitlist",
        "New Financial Counseling Application",
        "Financial Counseling",
        "You already have a pending or approved financial counseling application",
        "Financial counseling application submitted successfully",
    )
    .await
}

// ═══════════════════════════════════════════════════════════════════════════
// ADMIN: ANNOUNCEMENTS
// ═══════════════════════════════════════════════════════════════════════════

// GET /api/admin/announcements
pub async fn list_announcements(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> AppResult<Json<Value>> {
    authenticate_admin(&state, &headers).await?;
    let mut cur = state
        .db
        .collection::<Document>("announcements")
        .find(doc! {})
        .sort(doc! { "created_at": -1 })
        .limit(100)
        .await?;
    let mut out: Vec<Value> = Vec::new();
    while cur.advance().await? {
        let a = cur.deserialize_current()?;
        out.push(json!({
            "id": hex_id(&a),
            "title": dstr_or(&a, "title", ""),
            "content": dstr_or(&a, "content", ""),
            "type": dstr_or(&a, "type", "info"),
            "active": Value::Bool(a.get_bool("active").unwrap_or(true)),
            "expires_at": ddate(&a, "expires_at"),
            "created_by_name": dstr_or(&a, "created_by_name", "Admin"),
            "created_at": ddate(&a, "created_at"),
        }));
    }
    Ok(Json(json!(out)))
}

// POST /api/admin/announcements
pub async fn create_announcement(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(body): Json<Value>,
) -> AppResult<Json<Value>> {
    let (admin_id, admin) = authenticate_admin(&state, &headers).await?;
    let admin_oid = ObjectId::parse_str(&admin_id).map_err(|_| AppError::Unauthorized)?;
    let now = bson::DateTime::now();
    let created_by_name = format!(
        "{} {}",
        admin.first_name.clone().unwrap_or_default(),
        admin.last_name.clone().unwrap_or_default()
    )
    .trim()
    .to_string();
    let expires = match super::parse_iso(body.get("expires_at")) {
        Some(d) => Bson::DateTime(d),
        None => Bson::Null,
    };
    let res = state
        .db
        .collection::<Document>("announcements")
        .insert_one(doc! {
            "title": body_str(&body, "title", ""),
            "content": body_str(&body, "content", ""),
            "type": body_str(&body, "type", "info"),
            "active": body.get("active").and_then(|v| v.as_bool()).unwrap_or(true),
            "expires_at": expires,
            "created_by": admin_oid,
            "created_by_name": created_by_name.as_str(),
            "created_at": now,
        })
        .await?;
    let id = res.inserted_id.as_object_id().map(|o| o.to_hex()).unwrap_or_default();
    log_audit(&state, "ANNOUNCEMENT_CREATED", "announcement", Some(&id), Some(admin.email.as_str())).await;
    Ok(Json(json!({ "id": id, "message": "Announcement created" })))
}

// PUT /api/admin/announcements/{announcement_id}
pub async fn update_announcement(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(announcement_id): Path<String>,
    Json(body): Json<Value>,
) -> AppResult<Json<Value>> {
    let (_, admin) = authenticate_admin(&state, &headers).await?;
    let oid = ObjectId::parse_str(&announcement_id).map_err(|_| AppError::NotFound)?;
    let mut set = Document::new();
    for f in ["title", "content", "type", "active"] {
        if let Some(v) = body.get(f) {
            set.insert(f, bson::to_bson(v).unwrap_or(Bson::Null));
        }
    }
    if let Some(exp) = body.get("expires_at") {
        let truthy = match exp {
            Value::Null => false,
            Value::String(s) => !s.is_empty(),
            Value::Bool(b) => *b,
            _ => true,
        };
        if !truthy {
            set.insert("expires_at", Bson::Null);
        } else if let Some(d) = super::parse_iso(Some(exp)) {
            set.insert("expires_at", d);
        }
    }
    set.insert("updated_at", bson::DateTime::now());
    state
        .db
        .collection::<Document>("announcements")
        .update_one(doc! { "_id": oid }, doc! { "$set": set })
        .await?;
    log_audit(&state, "ANNOUNCEMENT_UPDATED", "announcement", Some(&announcement_id), Some(admin.email.as_str())).await;
    Ok(Json(json!({ "message": "Announcement updated" })))
}

// DELETE /api/admin/announcements/{announcement_id}
pub async fn delete_announcement(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(announcement_id): Path<String>,
) -> AppResult<Json<Value>> {
    let (_, admin) = authenticate_admin(&state, &headers).await?;
    let oid = ObjectId::parse_str(&announcement_id).map_err(|_| AppError::NotFound)?;
    state
        .db
        .collection::<Document>("announcements")
        .delete_one(doc! { "_id": oid })
        .await?;
    log_audit(&state, "ANNOUNCEMENT_DELETED", "announcement", Some(&announcement_id), Some(admin.email.as_str())).await;
    Ok(Json(json!({ "message": "Announcement deleted" })))
}

// ═══════════════════════════════════════════════════════════════════════════
// ADMIN: PROGRAM APPLICATIONS
// ═══════════════════════════════════════════════════════════════════════════

// GET /api/admin/applications?program_type=&status=
pub async fn list_applications(
    State(state): State<AppState>,
    headers: HeaderMap,
    Query(q): Query<HashMap<String, String>>,
) -> AppResult<Json<Value>> {
    authenticate_admin(&state, &headers).await?;
    let mut filter = Document::new();
    if let Some(pt) = q.get("program_type").filter(|s| !s.is_empty()) {
        filter.insert("program_type", pt.as_str());
    }
    if let Some(st) = q.get("status").filter(|s| !s.is_empty()) {
        filter.insert("status", st.as_str());
    }
    let users = state.db.collection::<Document>("users");
    let mut cur = state
        .db
        .collection::<Document>("program_applications")
        .find(filter)
        .sort(doc! { "applied_at": -1 })
        .limit(500)
        .await?;
    let mut out: Vec<Value> = Vec::new();
    while cur.advance().await? {
        let a = cur.deserialize_current()?;
        let counselor_name = match a.get_object_id("counselor_id").ok() {
            Some(cid) => users.find_one(doc! { "_id": cid }).await?.map(|c| full_name(&c)),
            None => None,
        };
        out.push(json!({
            "id": hex_id(&a),
            "member_id": a.get_object_id("member_id").map(|o| o.to_hex()).unwrap_or_default(),
            "member_email": dstr(&a, "member_email"),
            "member_name": dstr(&a, "member_name"),
            "program_type": dstr(&a, "program_type"),
            "status": dstr(&a, "status"),
            "applied_at": ddate(&a, "applied_at"),
            "reviewed_at": ddate(&a, "reviewed_at"),
            "counselor_name": counselor_name,
        }));
    }
    Ok(Json(json!(out)))
}

// GET /api/admin/applications/{application_id}
pub async fn application_detail(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(application_id): Path<String>,
) -> AppResult<Json<Value>> {
    authenticate_admin(&state, &headers).await?;
    let oid = ObjectId::parse_str(&application_id).map_err(|_| AppError::NotFound)?;
    let users = state.db.collection::<Document>("users");
    let a = state
        .db
        .collection::<Document>("program_applications")
        .find_one(doc! { "_id": oid })
        .await?
        .ok_or(AppError::NotFound)?;

    let counselor = match a.get_object_id("counselor_id").ok() {
        Some(cid) => users.find_one(doc! { "_id": cid }).await?.map(|c| {
            json!({ "id": cid.to_hex(), "name": full_name(&c), "email": c.get_str("email").ok() })
        }),
        None => None,
    };
    let reviewed_by = match a.get_object_id("reviewed_by").ok() {
        Some(rid) => users.find_one(doc! { "_id": rid }).await?.map(|r| full_name(&r)),
        None => None,
    };
    let application_data = a.get("application_data").cloned().map(sanitize).unwrap_or_else(|| json!({}));

    Ok(Json(json!({
        "id": hex_id(&a),
        "member_id": a.get_object_id("member_id").map(|o| o.to_hex()).unwrap_or_default(),
        "member_email": dstr(&a, "member_email"),
        "member_name": dstr(&a, "member_name"),
        "program_type": dstr(&a, "program_type"),
        "status": dstr(&a, "status"),
        "applied_at": ddate(&a, "applied_at"),
        "reviewed_at": ddate(&a, "reviewed_at"),
        "reviewed_by": reviewed_by,
        "counselor": counselor,
        "application_data": application_data,
        "notes": dstr_or(&a, "notes", ""),
    })))
}

// PUT /api/admin/applications/{application_id}/approve
pub async fn approve_application(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(application_id): Path<String>,
    Json(body): Json<Value>,
) -> AppResult<Json<Value>> {
    let (admin_id, admin) = authenticate_admin(&state, &headers).await?;
    let admin_oid = ObjectId::parse_str(&admin_id).map_err(|_| AppError::Unauthorized)?;
    let apps = state.db.collection::<Document>("program_applications");
    let users = state.db.collection::<Document>("users");
    let aoid = ObjectId::parse_str(&application_id).map_err(|_| AppError::NotFound)?;
    let app = apps
        .find_one(doc! { "_id": aoid })
        .await?
        .ok_or(AppError::NotFound)?;

    let counselor_id = body.get("counselor_id").and_then(|v| v.as_str()).filter(|s| !s.is_empty());
    let coid = counselor_id.and_then(|c| ObjectId::parse_str(c).ok());
    let now = bson::DateTime::now();
    let notes = body
        .get("notes")
        .and_then(|v| v.as_str())
        .map(|s| s.to_string())
        .unwrap_or_else(|| app.get_str("notes").unwrap_or("").to_string());

    let mut app_update = doc! {
        "status": "approved",
        "reviewed_at": now,
        "reviewed_by": admin_oid,
        "notes": notes.as_str(),
    };
    if let Some(c) = coid {
        app_update.insert("counselor_id", c);
    }
    apps.update_one(doc! { "_id": aoid }, doc! { "$set": app_update }).await?;

    let program_type = app.get_str("program_type").unwrap_or("").to_string();
    let member_id = app.get_object_id("member_id").ok();
    let mut mset = Document::new();
    if let Some(c) = coid {
        mset.insert("assigned_counselor_id", c);
    }
    if program_type == "credit_repair" {
        mset.insert("credit_repair_stage", "cr_consultation");
    } else if program_type == "financial_counseling" {
        mset.insert("financial_counseling_stage", "fc_consultation");
    }
    if let Some(mid) = member_id {
        if !mset.is_empty() {
            users.update_one(doc! { "_id": mid }, doc! { "$set": mset }).await?;
        }
    }

    // Emails (awaited -- Lambda freezes on return).
    let member = match member_id {
        Some(mid) => users.find_one(doc! { "_id": mid }).await?,
        None => None,
    };
    let counselor = match coid {
        Some(c) => users.find_one(doc! { "_id": c }).await?,
        None => None,
    };
    if let Some(m) = &member {
        if let Ok(email) = m.get_str("email") {
            let fname = m.get_str("first_name").unwrap_or("Member");
            let program_label = if program_type == "credit_repair" {
                "Credit Repair"
            } else {
                "Financial Counseling"
            };
            let counselor_name = counselor.as_ref().map(|c| full_name(c));
            sh_core::email::send_program_approved_email(
                email,
                fname,
                program_label,
                counselor.is_some(),
                counselor_name.as_deref(),
            )
            .await;
            if let Some(cn) = &counselor_name {
                sh_core::email::send_counselor_assigned_email(email, fname, cn).await;
            }
        }
    }

    log_audit(&state, "PROGRAM_APPLICATION_APPROVED", "program_application", Some(&application_id), Some(admin.email.as_str())).await;
    Ok(Json(json!({ "message": "Application approved and counselor assigned" })))
}

// PUT /api/admin/applications/{application_id}/reject
pub async fn reject_application(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(application_id): Path<String>,
    Json(body): Json<Value>,
) -> AppResult<Json<Value>> {
    let (admin_id, admin) = authenticate_admin(&state, &headers).await?;
    let admin_oid = ObjectId::parse_str(&admin_id).map_err(|_| AppError::Unauthorized)?;
    let apps = state.db.collection::<Document>("program_applications");
    let users = state.db.collection::<Document>("users");
    let aoid = ObjectId::parse_str(&application_id).map_err(|_| AppError::NotFound)?;
    let app = apps
        .find_one(doc! { "_id": aoid })
        .await?
        .ok_or(AppError::NotFound)?;

    let reason = body.get("reason").and_then(|v| v.as_str()).unwrap_or("").to_string();
    apps.update_one(
        doc! { "_id": aoid },
        doc! { "$set": {
            "status": "rejected",
            "reviewed_at": bson::DateTime::now(),
            "reviewed_by": admin_oid,
            "notes": reason.as_str(),
        }},
    )
    .await?;

    let program_type = app.get_str("program_type").unwrap_or("").to_string();
    let member_id = app.get_object_id("member_id").ok();
    if let Some(mid) = member_id {
        if program_type == "credit_repair" {
            users.update_one(doc! { "_id": mid }, doc! { "$unset": { "credit_repair_stage": "" } }).await?;
        } else if program_type == "financial_counseling" {
            users.update_one(doc! { "_id": mid }, doc! { "$unset": { "financial_counseling_stage": "" } }).await?;
        }
    }

    let member = match member_id {
        Some(mid) => users.find_one(doc! { "_id": mid }).await?,
        None => None,
    };
    if let Some(m) = &member {
        if let Ok(email) = m.get_str("email") {
            let fname = m.get_str("first_name").unwrap_or("Member");
            let program_name = if program_type == "credit_repair" {
                "Credit Repair"
            } else {
                "Financial Counseling"
            };
            sh_core::email::send_program_rejected_email(email, fname, program_name, &reason).await;
        }
    }

    log_audit(&state, "PROGRAM_APPLICATION_REJECTED", "program_application", Some(&application_id), Some(admin.email.as_str())).await;
    Ok(Json(json!({ "message": "Application rejected" })))
}

// ═══════════════════════════════════════════════════════════════════════════
// ADMIN: PIPELINE + STAGE
// ═══════════════════════════════════════════════════════════════════════════

// GET /api/admin/pipeline
pub async fn admin_pipeline(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> AppResult<Json<Value>> {
    authenticate_admin(&state, &headers).await?;

    let init = |stages: &[&str]| -> serde_json::Map<String, Value> {
        stages.iter().map(|s| (s.to_string(), json!([]))).collect()
    };
    let mut onboarding = init(&ONBOARDING_STAGES);
    let mut credit_repair = init(&CREDIT_REPAIR_STAGES);
    let mut financial_counseling = init(&FINANCIAL_COUNSELING_STAGES);

    let mut cur = state
        .db
        .collection::<Document>("users")
        .find(doc! { "role": "member" })
        .limit(1000)
        .await?;
    while cur.advance().await? {
        let m = cur.deserialize_current()?;
        let has_counselor = match m.get("assigned_counselor_id") {
            Some(Bson::ObjectId(_)) => true,
            Some(Bson::String(s)) => !s.is_empty(),
            _ => false,
        };
        let md = json!({
            "id": hex_id(&m),
            "name": full_name(&m),
            "email": dstr(&m, "email"),
            "branch": dstr(&m, "branch"),
            "has_counselor": has_counselor,
            "created_at": ddate(&m, "created_at"),
            "updated_at": ddate(&m, "updated_at"),
        });
        let push = |map: &mut serde_json::Map<String, Value>, key: &str| {
            if let Some(Value::Array(a)) = map.get_mut(key) {
                a.push(md.clone());
            }
        };
        push(&mut onboarding, m.get_str("pipeline_stage").unwrap_or("applied"));
        if let Ok(cr) = m.get_str("credit_repair_stage") {
            push(&mut credit_repair, cr);
        }
        if let Ok(fc) = m.get_str("financial_counseling_stage") {
            push(&mut financial_counseling, fc);
        }
    }

    Ok(Json(json!({
        "onboarding": Value::Object(onboarding),
        "credit_repair": Value::Object(credit_repair),
        "financial_counseling": Value::Object(financial_counseling),
    })))
}

// PUT /api/admin/members/{member_id}/stage
pub async fn set_member_stage(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(member_id): Path<String>,
    Json(body): Json<Value>,
) -> AppResult<Json<Value>> {
    let (_, admin) = authenticate_admin(&state, &headers).await?;
    let pipeline_type = body_str(&body, "pipeline_type", "onboarding").to_string();
    let new_stage = body.get("stage").and_then(|v| v.as_str()).unwrap_or("").to_string();

    let field = match pipeline_type.as_str() {
        "onboarding" => {
            if !ONBOARDING_STAGES.contains(&new_stage.as_str()) {
                return Err(AppError::BadRequest(format!(
                    "Invalid onboarding stage. Must be one of: [{}]",
                    ONBOARDING_STAGES.join(", ")
                )));
            }
            "pipeline_stage"
        }
        "credit_repair" => {
            if !CREDIT_REPAIR_STAGES.contains(&new_stage.as_str()) {
                return Err(AppError::BadRequest(format!(
                    "Invalid credit repair stage. Must be one of: [{}]",
                    CREDIT_REPAIR_STAGES.join(", ")
                )));
            }
            "credit_repair_stage"
        }
        "financial_counseling" => {
            if !FINANCIAL_COUNSELING_STAGES.contains(&new_stage.as_str()) {
                return Err(AppError::BadRequest(format!(
                    "Invalid financial counseling stage. Must be one of: [{}]",
                    FINANCIAL_COUNSELING_STAGES.join(", ")
                )));
            }
            "financial_counseling_stage"
        }
        _ => {
            return Err(AppError::BadRequest(
                "Invalid pipeline_type. Must be: onboarding, credit_repair, or financial_counseling"
                    .to_string(),
            ))
        }
    };

    let oid = ObjectId::parse_str(&member_id).map_err(|_| AppError::NotFound)?;
    state
        .db
        .collection::<Document>("users")
        .update_one(
            doc! { "_id": oid },
            doc! { "$set": { field: new_stage.as_str(), "updated_at": bson::DateTime::now() } },
        )
        .await?;
    log_audit(&state, "member_stage_changed", "user", Some(&member_id), Some(admin.email.as_str())).await;
    Ok(Json(json!({
        "message": format!("Member {pipeline_type} stage updated to {new_stage}")
    })))
}

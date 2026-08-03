//! Programs + applications (`/api/member/programs`, `/api/member/apply/*`).
//! Port of routers/programs.py. Collections `program_applications`, `users`.

use axum::extract::State;
use axum::http::HeaderMap;
use axum::Json;
use bson::oid::ObjectId;
use bson::{doc, Bson, Document};
use serde_json::{json, Value};

use super::{authenticate, body_bson, ddate, dstr_or, full_name, hex_id, log_audit};
use crate::state::AppState;
use sh_core::models::User;
use sh_core::{AppError, AppResult};

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

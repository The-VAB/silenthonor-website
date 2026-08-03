//! Financial-counseling tools (`/api/counselor/members/{id}/fc/*`). Port of
//! routers/financial_counseling.py. One upserted `fc_data` document per member.
//! Access: counselor assigned to the member, or any admin.

use axum::extract::{Path, State};
use axum::http::HeaderMap;
use axum::Json;
use bson::oid::ObjectId;
use bson::{doc, Bson, Document};
use serde_json::{json, Value};

use super::{authenticate_counselor, sanitize};
use crate::state::AppState;
use sh_core::models::User;
use sh_core::{AppError, AppResult};

fn coid(id: &str) -> AppResult<ObjectId> {
    ObjectId::parse_str(id).map_err(|_| AppError::Unauthorized)
}

fn gen_id() -> String {
    let mut b = [0u8; 16];
    getrandom::getrandom(&mut b).ok();
    b.iter().map(|x| format!("{x:02x}")).collect()
}

fn body_doc(body: &Value) -> Document {
    bson::to_document(body).unwrap_or_default()
}

/// _verify_access: member exists + assigned to this counselor (admins bypass).
async fn fc_access(state: &AppState, member_id: &str, user: &User, c: ObjectId) -> AppResult<ObjectId> {
    let moid = ObjectId::parse_str(member_id).map_err(|_| AppError::BadRequest("Invalid member ID".to_string()))?;
    let member = state
        .db
        .collection::<Document>("users")
        .find_one(doc! { "_id": moid, "role": "member" })
        .await?
        .ok_or(AppError::NotFound)?;
    let is_admin = user.effective_roles().iter().any(|r| r == "admin");
    if !is_admin && member.get_object_id("assigned_counselor_id").ok() != Some(c) {
        return Err(AppError::Forbidden("Not assigned to this member".to_string()));
    }
    Ok(moid)
}

async fn upsert(state: &AppState, moid: ObjectId, update: Document) -> AppResult<()> {
    state
        .db
        .collection::<Document>("fc_data")
        .update_one(doc! { "member_id": moid }, update)
        .upsert(true)
        .await?;
    Ok(())
}

// GET /fc
pub async fn get_fc(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(member_id): Path<String>,
) -> AppResult<Json<Value>> {
    let (id, user) = authenticate_counselor(&state, &headers).await?;
    let c = coid(&id)?;
    let moid = fc_access(&state, &member_id, &user, c).await?;
    match state.db.collection::<Document>("fc_data").find_one(doc! { "member_id": moid }).await? {
        Some(d) => Ok(Json(sanitize(Bson::Document(d)))),
        None => Ok(Json(json!({}))),
    }
}

// PUT /fc/intake
pub async fn intake(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(member_id): Path<String>,
    Json(body): Json<Value>,
) -> AppResult<Json<Value>> {
    let (id, user) = authenticate_counselor(&state, &headers).await?;
    let c = coid(&id)?;
    let moid = fc_access(&state, &member_id, &user, c).await?;
    let now = bson::DateTime::now();
    let mut b = body_doc(&body);
    b.insert("completed", true);
    b.insert("completed_at", now);
    upsert(&state, moid, doc! { "$set": { "intake": b, "updated_at": now } }).await?;
    Ok(Json(json!({ "message": "Intake saved" })))
}

// POST /fc/budgets  (append-only, versioned)
pub async fn add_budget(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(member_id): Path<String>,
    Json(body): Json<Value>,
) -> AppResult<Json<Value>> {
    let (id, user) = authenticate_counselor(&state, &headers).await?;
    let c = coid(&id)?;
    let moid = fc_access(&state, &member_id, &user, c).await?;
    let existing = state.db.collection::<Document>("fc_data").find_one(doc! { "member_id": moid }).await?;
    let version = existing
        .as_ref()
        .and_then(|d| d.get_array("budgets").ok())
        .map(|a| a.len())
        .unwrap_or(0) as i64
        + 1;
    let now = bson::DateTime::now();
    let bid = gen_id();
    let mut b = body_doc(&body);
    b.insert("id", bid.as_str());
    b.insert("version", version);
    b.insert("created_at", now);
    upsert(&state, moid, doc! { "$push": { "budgets": b }, "$set": { "updated_at": now } }).await?;
    Ok(Json(json!({ "id": bid, "version": version })))
}

// PUT /fc/debt-plan
pub async fn debt_plan(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(member_id): Path<String>,
    Json(body): Json<Value>,
) -> AppResult<Json<Value>> {
    set_field(state, headers, member_id, body, "debt_plan", "Debt plan saved").await
}

// POST /fc/goals
pub async fn add_goal(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(member_id): Path<String>,
    Json(body): Json<Value>,
) -> AppResult<Json<Value>> {
    let (id, user) = authenticate_counselor(&state, &headers).await?;
    let c = coid(&id)?;
    let moid = fc_access(&state, &member_id, &user, c).await?;
    let now = bson::DateTime::now();
    let gid = gen_id();
    let mut b = body_doc(&body);
    b.insert("id", gid.as_str());
    b.insert("status", "active");
    b.insert("created_at", now);
    upsert(&state, moid, doc! { "$push": { "goals": b }, "$set": { "updated_at": now } }).await?;
    Ok(Json(json!({ "id": gid })))
}

// PATCH /fc/goals/{goal_id}  (positional array filter)
pub async fn update_goal(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path((member_id, goal_id)): Path<(String, String)>,
    Json(body): Json<Value>,
) -> AppResult<Json<Value>> {
    let (id, user) = authenticate_counselor(&state, &headers).await?;
    let c = coid(&id)?;
    let moid = fc_access(&state, &member_id, &user, c).await?;
    let now = bson::DateTime::now();
    let mut set = Document::new();
    if let Some(obj) = body.as_object() {
        for (k, v) in obj {
            set.insert(format!("goals.$[elem].{k}"), bson::to_bson(v).unwrap_or(Bson::Null));
        }
    }
    set.insert("updated_at", now);
    let res = state
        .db
        .collection::<Document>("fc_data")
        .update_one(doc! { "member_id": moid }, doc! { "$set": set })
        .array_filters(vec![doc! { "elem.id": goal_id.as_str() }])
        .await?;
    if res.matched_count == 0 {
        return Err(AppError::NotFound);
    }
    Ok(Json(json!({ "message": "Goal updated" })))
}

// DELETE /fc/goals/{goal_id}
pub async fn delete_goal(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path((member_id, goal_id)): Path<(String, String)>,
) -> AppResult<Json<Value>> {
    let (id, user) = authenticate_counselor(&state, &headers).await?;
    let c = coid(&id)?;
    let moid = fc_access(&state, &member_id, &user, c).await?;
    let now = bson::DateTime::now();
    upsert(
        &state,
        moid,
        doc! { "$pull": { "goals": { "id": goal_id.as_str() } }, "$set": { "updated_at": now } },
    )
    .await?;
    Ok(Json(json!({ "message": "Goal deleted" })))
}

// POST /fc/session-notes  (append-only)
pub async fn add_session_note(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(member_id): Path<String>,
    Json(body): Json<Value>,
) -> AppResult<Json<Value>> {
    let (id, user) = authenticate_counselor(&state, &headers).await?;
    let c = coid(&id)?;
    let moid = fc_access(&state, &member_id, &user, c).await?;
    let now = bson::DateTime::now();
    let sid = gen_id();
    let cname = {
        let n = format!(
            "{} {}",
            user.first_name.clone().unwrap_or_default(),
            user.last_name.clone().unwrap_or_default()
        )
        .trim()
        .to_string();
        if n.is_empty() { "Counselor".to_string() } else { n }
    };
    let mut b = body_doc(&body);
    b.insert("id", sid.as_str());
    b.insert("created_at", now);
    b.insert("created_by", cname.as_str());
    upsert(&state, moid, doc! { "$push": { "session_notes": b }, "$set": { "updated_at": now } }).await?;
    Ok(Json(json!({ "id": sid })))
}

// PUT /fc/housing | /retirement | /tax-ref | /fraud-checklist
pub async fn housing(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(member_id): Path<String>,
    Json(body): Json<Value>,
) -> AppResult<Json<Value>> {
    set_field(state, headers, member_id, body, "housing", "Housing data saved").await
}
pub async fn retirement(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(member_id): Path<String>,
    Json(body): Json<Value>,
) -> AppResult<Json<Value>> {
    set_field(state, headers, member_id, body, "retirement", "Retirement data saved").await
}
pub async fn tax_ref(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(member_id): Path<String>,
    Json(body): Json<Value>,
) -> AppResult<Json<Value>> {
    set_field(state, headers, member_id, body, "tax_ref", "Tax reference saved").await
}
pub async fn fraud_checklist(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(member_id): Path<String>,
    Json(body): Json<Value>,
) -> AppResult<Json<Value>> {
    set_field(state, headers, member_id, body, "fraud_checklist", "Fraud checklist saved").await
}

// POST /fc/referrals  (append-only)
pub async fn add_referral(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(member_id): Path<String>,
    Json(body): Json<Value>,
) -> AppResult<Json<Value>> {
    let (id, user) = authenticate_counselor(&state, &headers).await?;
    let c = coid(&id)?;
    let moid = fc_access(&state, &member_id, &user, c).await?;
    let now = bson::DateTime::now();
    let rid = gen_id();
    let cname = {
        let n = format!(
            "{} {}",
            user.first_name.clone().unwrap_or_default(),
            user.last_name.clone().unwrap_or_default()
        )
        .trim()
        .to_string();
        if n.is_empty() { "Counselor".to_string() } else { n }
    };
    let mut b = body_doc(&body);
    b.insert("id", rid.as_str());
    b.insert("logged_at", now);
    b.insert("logged_by", cname.as_str());
    upsert(&state, moid, doc! { "$push": { "referrals_used": b }, "$set": { "updated_at": now } }).await?;
    Ok(Json(json!({ "id": rid })))
}

/// Shared helper for the PUT tools that store body-as-field + updated_at.
async fn set_field(
    state: AppState,
    headers: HeaderMap,
    member_id: String,
    body: Value,
    field: &str,
    msg: &str,
) -> AppResult<Json<Value>> {
    let (id, user) = authenticate_counselor(&state, &headers).await?;
    let c = coid(&id)?;
    let moid = fc_access(&state, &member_id, &user, c).await?;
    let now = bson::DateTime::now();
    let mut b = body_doc(&body);
    b.insert("updated_at", now);
    upsert(&state, moid, doc! { "$set": { field: b, "updated_at": now } }).await?;
    Ok(Json(json!({ "message": msg })))
}

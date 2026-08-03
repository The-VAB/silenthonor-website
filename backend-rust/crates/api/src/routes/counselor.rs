//! Counselor portal (`/api/counselor/*`). Port of routers/counselor.py. Every
//! handler requires the `counselor` or `admin` role (admins may act on any
//! member). The FC tools live in fc.rs.

use axum::extract::{Multipart, Path, State};
use axum::http::HeaderMap;
use axum::Json;
use bson::oid::ObjectId;
use bson::{doc, Bson, Document};
use serde_json::{json, Value};

use super::{
    assigned_member, authenticate, authenticate_counselor, body_bson, body_str, ddate, dint, draw,
    dstr_or, full_name, hex_id, parse_iso, parse_iso_or_now,
};
use crate::state::AppState;
use sh_core::{AppError, AppResult};

const BUREAUS: [&str; 3] = ["equifax", "experian", "transunion"];
const ACCOUNT_TYPES: [&str; 6] = ["revolving", "installment", "collection", "mortgage", "auto", "other"];
const ACCOUNT_STATUSES: [&str; 3] = ["open", "closed", "collection"];
const DISPUTE_STATUSES: [&str; 5] = ["draft", "pending", "sent", "responded", "closed"];
const GAME_PLAN_ACTIONS: [&str; 6] = [
    "dispute", "goodwill", "no_action", "debt_validation", "pay_for_delete", "cross_bureau_dispute",
];

fn coid(id: &str) -> AppResult<ObjectId> {
    ObjectId::parse_str(id).map_err(|_| AppError::Unauthorized)
}
fn bureau_label(b: &str) -> String {
    if b == "transunion" {
        "TransUnion".to_string()
    } else {
        let mut c = b.chars();
        c.next()
            .map(|f| f.to_uppercase().collect::<String>() + c.as_str())
            .unwrap_or_default()
    }
}

// ── GET /api/counselor/stats ──────────────────────────────────────────────────
pub async fn stats(State(state): State<AppState>, headers: HeaderMap) -> AppResult<Json<Value>> {
    let (id, _) = authenticate_counselor(&state, &headers).await?;
    let c = coid(&id)?;
    let users = state.db.collection::<Document>("users");
    let cdoc = users.find_one(doc! { "_id": c }).await?;
    let max_caseload = cdoc.as_ref().map(|u| dint(u, "max_caseload")).filter(|&n| n > 0).unwrap_or(12);
    let assigned = users
        .count_documents(doc! { "assigned_counselor_id": c, "role": "member" })
        .await? as i64;
    let waitlist = users
        .count_documents(doc! {
            "role": "member",
            "$and": [
                { "$or": [ { "assigned_counselor_id": { "$exists": false } }, { "assigned_counselor_id": Bson::Null } ] },
                { "$or": [ { "credit_repair_stage": "cr_waitlist" }, { "financial_counseling_stage": "fc_waitlist" } ] },
            ],
        })
        .await? as i64;
    let tasks_due = state
        .db
        .collection::<Document>("tasks")
        .count_documents(doc! { "counselor_id": c, "completed": false, "due_date": { "$lte": bson::DateTime::now() } })
        .await? as i64;
    let unread = state
        .db
        .collection::<Document>("messages")
        .count_documents(doc! { "to_user_id": c, "read": false })
        .await? as i64;
    Ok(Json(json!({
        "assigned_members": assigned,
        "max_caseload": max_caseload,
        "open_slots": (max_caseload - assigned).max(0),
        "waitlist_count": waitlist,
        "tasks_due": tasks_due,
        "unread_messages": unread,
        "recent_activity": [],
    })))
}

// ── GET /api/counselor/caseload ───────────────────────────────────────────────
pub async fn caseload(State(state): State<AppState>, headers: HeaderMap) -> AppResult<Json<Value>> {
    let (id, _) = authenticate_counselor(&state, &headers).await?;
    let c = coid(&id)?;
    let mut cur = state
        .db
        .collection::<Document>("users")
        .find(doc! { "assigned_counselor_id": c })
        .limit(200)
        .await?;
    let mut members: Vec<Document> = Vec::new();
    while cur.advance().await? {
        members.push(cur.deserialize_current()?);
    }
    let member_ids: Vec<ObjectId> = members.iter().filter_map(|m| m.get_object_id("_id").ok()).collect();

    // unread-by-sender + overdue-tasks-by-member, computed in Rust
    let mut unread: std::collections::HashMap<ObjectId, bool> = std::collections::HashMap::new();
    if !member_ids.is_empty() {
        let mut mc = state
            .db
            .collection::<Document>("messages")
            .find(doc! { "to_user_id": c, "from_user_id": { "$in": member_ids.clone() }, "read": false })
            .await?;
        while mc.advance().await? {
            if let Ok(f) = mc.deserialize_current()?.get_object_id("from_user_id") {
                unread.insert(f, true);
            }
        }
    }
    let mut overdue: std::collections::HashMap<ObjectId, bool> = std::collections::HashMap::new();
    let mut tc = state
        .db
        .collection::<Document>("tasks")
        .find(doc! { "counselor_id": c, "completed": false, "due_date": { "$lt": bson::DateTime::now() } })
        .await?;
    while tc.advance().await? {
        if let Ok(m) = tc.deserialize_current()?.get_object_id("member_id") {
            overdue.insert(m, true);
        }
    }

    let mut out: Vec<Value> = members
        .iter()
        .map(|m| {
            let mid = m.get_object_id("_id").ok();
            let last = if m.contains_key("last_activity_date") {
                ddate(m, "last_activity_date")
            } else {
                ddate(m, "created_at")
            };
            json!({
                "id": hex_id(m),
                "name": full_name(m),
                "email": dstr_or(m, "email", ""),
                "branch": draw(m, "branch"),
                "program_track": dstr_or(m, "program_track", "onboarding"),
                "cr_stage": draw(m, "credit_repair_stage"),
                "fc_stage": draw(m, "financial_counseling_stage"),
                "last_activity": last,
                "flags": {
                    "unread_message": mid.map(|x| unread.contains_key(&x)).unwrap_or(false),
                    "overdue_task": mid.map(|x| overdue.contains_key(&x)).unwrap_or(false),
                    "new_document": false,
                },
            })
        })
        .collect();
    out.sort_by(|a, b| {
        b["last_activity"].as_str().unwrap_or("").cmp(a["last_activity"].as_str().unwrap_or(""))
    });
    Ok(Json(json!(out)))
}

// ── GET /api/counselor/members ────────────────────────────────────────────────
pub async fn members(State(state): State<AppState>, headers: HeaderMap) -> AppResult<Json<Value>> {
    let (id, _) = authenticate_counselor(&state, &headers).await?;
    let c = coid(&id)?;
    let mut cur = state
        .db
        .collection::<Document>("users")
        .find(doc! { "assigned_counselor_id": c })
        .sort(doc! { "created_at": -1 })
        .limit(100)
        .await?;
    let mut out: Vec<Value> = Vec::new();
    while cur.advance().await? {
        let m = cur.deserialize_current()?;
        out.push(json!({
            "id": hex_id(&m),
            "email": dstr_or(&m, "email", ""),
            "name": full_name(&m),
            "branch": draw(&m, "branch"),
            "pipeline_stage": dstr_or(&m, "pipeline_stage", "active"),
            "created_at": ddate(&m, "created_at"),
        }));
    }
    Ok(Json(json!(out)))
}

// ── GET /api/counselor/members/{member_id} ────────────────────────────────────
pub async fn member_detail(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(member_id): Path<String>,
) -> AppResult<Json<Value>> {
    let (id, _) = authenticate_counselor(&state, &headers).await?;
    let c = coid(&id)?;
    let mut member = assigned_member(&state, &member_id, c).await?;
    member.remove("password_hash");
    let moid = member.get_object_id("_id").map_err(|_| AppError::NotFound)?;

    let mut scores = Vec::new();
    let mut sc = state.db.collection::<Document>("credit_scores")
        .find(doc! { "user_id": moid }).sort(doc! { "date": -1 }).limit(10).await?;
    while sc.advance().await? {
        let d = sc.deserialize_current()?;
        scores.push(json!({ "id": hex_id(&d), "date": ddate(&d, "date"),
            "equifax": draw(&d, "equifax"), "experian": draw(&d, "experian"), "transunion": draw(&d, "transunion") }));
    }
    let mut disputes = Vec::new();
    let mut dc = state.db.collection::<Document>("disputes")
        .find(doc! { "user_id": moid }).sort(doc! { "created_at": -1 }).limit(50).await?;
    while dc.advance().await? {
        let d = dc.deserialize_current()?;
        disputes.push(json!({ "id": hex_id(&d), "bureau": dstr_or(&d,"bureau",""),
            "account_name": dstr_or(&d,"account_name",""), "status": dstr_or(&d,"status","draft"),
            "created_at": ddate(&d,"created_at") }));
    }
    let mut notes = Vec::new();
    let mut nc = state.db.collection::<Document>("intake_notes")
        .find(doc! { "member_id": moid }).sort(doc! { "created_at": -1 }).limit(50).await?;
    while nc.advance().await? {
        let d = nc.deserialize_current()?;
        notes.push(json!({ "id": hex_id(&d), "content": dstr_or(&d,"content",""),
            "note_type": dstr_or(&d,"note_type","counselor"),
            "created_by": dstr_or(&d,"created_by_name",""), "created_at": ddate(&d,"created_at") }));
    }
    // sanitize member doc to plain JSON (ObjectId->hex, datetime->ISO)
    let member_json = super::sanitize(Bson::Document(member));
    Ok(Json(json!({ "member": member_json, "credit_scores": scores, "disputes": disputes, "notes": notes })))
}

// ── PATCH /api/counselor/members/{member_id}/program-track ────────────────────
pub async fn program_track(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(member_id): Path<String>,
    Json(body): Json<Value>,
) -> AppResult<Json<Value>> {
    let (id, _) = authenticate_counselor(&state, &headers).await?;
    let c = coid(&id)?;
    let track = body_str(&body, "program_track", "").to_string();
    if !["onboarding", "credit_repair", "financial_counseling"].contains(&track.as_str()) {
        return Err(AppError::BadRequest("Invalid program track".to_string()));
    }
    let member = assigned_member(&state, &member_id, c).await?;
    let moid = member.get_object_id("_id").map_err(|_| AppError::NotFound)?;
    let now = bson::DateTime::now();
    let mut set = doc! { "program_track": track.as_str(), "last_activity_date": now, "updated_at": now };
    if track == "credit_repair" && member.get_str("credit_repair_stage").unwrap_or("").is_empty() {
        set.insert("credit_repair_stage", "cr_waitlist");
    }
    if track == "financial_counseling" && member.get_str("financial_counseling_stage").unwrap_or("").is_empty() {
        set.insert("financial_counseling_stage", "fc_waitlist");
    }
    state.db.collection::<Document>("users").update_one(doc! { "_id": moid }, doc! { "$set": set }).await?;
    Ok(Json(json!({ "message": "Program track updated", "program_track": track })))
}

// ── POST /api/counselor/members/{member_id}/notes ─────────────────────────────
pub async fn add_note(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(member_id): Path<String>,
    Json(body): Json<Value>,
) -> AppResult<Json<Value>> {
    let (id, user) = authenticate_counselor(&state, &headers).await?;
    let c = coid(&id)?;
    let member = assigned_member(&state, &member_id, c).await?;
    let moid = member.get_object_id("_id").map_err(|_| AppError::NotFound)?;
    let cname = format!(
        "{} {}",
        user.first_name.clone().unwrap_or_default(),
        user.last_name.clone().unwrap_or_default()
    )
    .trim()
    .to_string();
    let now = bson::DateTime::now();
    let res = state.db.collection::<Document>("intake_notes").insert_one(doc! {
        "member_id": moid, "content": body_str(&body, "content", ""),
        "note_type": body_str(&body, "note_type", "counselor"),
        "created_by": c, "created_by_name": cname.as_str(), "created_at": now,
    }).await?;
    state.db.collection::<Document>("users").update_one(doc! { "_id": moid }, doc! { "$set": { "last_activity_date": now } }).await?;
    let iid = res.inserted_id.as_object_id().map(|o| o.to_hex()).unwrap_or_default();
    Ok(Json(json!({ "id": iid, "message": "Note added" })))
}

// ── GET/POST /api/counselor/members/{member_id}/credit-scores ─────────────────
pub async fn get_credit_scores(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(member_id): Path<String>,
) -> AppResult<Json<Value>> {
    let (id, _) = authenticate_counselor(&state, &headers).await?;
    let c = coid(&id)?;
    let member = assigned_member(&state, &member_id, c).await?;
    let moid = member.get_object_id("_id").map_err(|_| AppError::NotFound)?;
    let mut cur = state.db.collection::<Document>("credit_scores")
        .find(doc! { "$or": [ { "user_id": moid }, { "member_id": moid } ] }).limit(200).await?;
    let mut history: Vec<(String, Value)> = Vec::new(); // (date_iso_sort_key, entry)
    while cur.advance().await? {
        let d = cur.deserialize_current()?;
        let date_val = if d.contains_key("date_pulled") { ddate(&d, "date_pulled") } else { ddate(&d, "created_at") };
        let sort_key = date_val.as_str().unwrap_or("").to_string();
        if let Ok(b) = d.get_str("bureau") {
            history.push((sort_key.clone(), json!({ "id": hex_id(&d), "bureau": b, "score": draw(&d, "score"), "date_pulled": date_val })));
        } else {
            for b in BUREAUS {
                if d.get(b).map(|v| v != &Bson::Null).unwrap_or(false) {
                    history.push((sort_key.clone(), json!({ "id": format!("{}_{}", hex_id(&d), b), "bureau": b, "score": draw(&d, b), "date_pulled": date_val.clone() })));
                }
            }
        }
    }
    history.sort_by(|a, b| b.0.cmp(&a.0));
    let mut latest = serde_json::Map::new();
    for (_, e) in &history {
        if let Some(bureau) = e.get("bureau").and_then(|v| v.as_str()) {
            latest.entry(bureau.to_string()).or_insert_with(|| json!({ "score": e.get("score"), "date": e.get("date_pulled") }));
        }
    }
    let hist: Vec<Value> = history.into_iter().map(|(_, e)| e).collect();
    Ok(Json(json!({ "latest": latest, "history": hist })))
}

pub async fn add_credit_score(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(member_id): Path<String>,
    Json(body): Json<Value>,
) -> AppResult<Json<Value>> {
    let (id, _) = authenticate_counselor(&state, &headers).await?;
    let c = coid(&id)?;
    let member = assigned_member(&state, &member_id, c).await?;
    let moid = member.get_object_id("_id").map_err(|_| AppError::NotFound)?;
    let bureau = body_str(&body, "bureau", "");
    if !BUREAUS.contains(&bureau) {
        return Err(AppError::BadRequest("Invalid bureau".to_string()));
    }
    let score = body.get("score").and_then(|v| v.as_i64()).ok_or_else(|| AppError::BadRequest("score must be a number".to_string()))?;
    if !(300..=850).contains(&score) {
        return Err(AppError::BadRequest("score must be between 300 and 850".to_string()));
    }
    let date_pulled = parse_iso_or_now(body.get("date_pulled"));
    let now = bson::DateTime::now();
    state.db.collection::<Document>("credit_scores").insert_one(doc! {
        "member_id": moid, "bureau": bureau, "score": score, "date_pulled": date_pulled, "created_at": now,
    }).await?;
    state.db.collection::<Document>("users").update_one(doc! { "_id": moid }, doc! { "$set": { "last_activity_date": now } }).await?;
    Ok(Json(json!({ "message": "Credit score added" })))
}

// ── Game plan (credit accounts + rules engine) ────────────────────────────────
fn compute_game_plan(a: &Document) -> (&'static str, &'static str, &'static str) {
    let status = a.get_str("account_status").unwrap_or("open");
    let atype = a.get_str("account_type").unwrap_or("revolving");
    let has_late = a.get_bool("has_late_payments").unwrap_or(false);
    let cross = a.get_bool("cross_bureau_inaccuracy").unwrap_or(false);
    let days_since = a.get_datetime("late_payment_date").ok().map(|d| {
        ((bson::DateTime::now().timestamp_millis() - d.timestamp_millis()) / 86_400_000).max(0)
    });
    if cross {
        return ("cross_bureau_dispute", "This account reports different data across bureaus, which is a strong basis for a cross-bureau dispute.", "high");
    }
    if atype == "collection" || status == "collection" {
        return ("debt_validation", "As a collection account, the first step is to demand debt validation from the collector.", "high");
    }
    if status == "closed" {
        return ("dispute", "This account is closed; dispute any inaccurate reporting with the bureaus.", "medium");
    }
    if has_late {
        match days_since {
            Some(d) if d < 180 => return ("goodwill", "The late payment is recent (within 6 months); a goodwill letter to the creditor is the best first move.", "medium"),
            _ => return ("no_action", "The late payment is older than 6 months and will age off naturally; no action recommended.", "low"),
        }
    }
    ("pay_for_delete", "No negative items detected on this account; a pay-for-delete or maintenance approach is appropriate.", "low")
}

pub async fn game_plan(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(member_id): Path<String>,
) -> AppResult<Json<Value>> {
    let (id, _) = authenticate_counselor(&state, &headers).await?;
    let c = coid(&id)?;
    let member = assigned_member(&state, &member_id, c).await?;
    let moid = member.get_object_id("_id").map_err(|_| AppError::NotFound)?;
    let mut cur = state.db.collection::<Document>("credit_accounts")
        .find(doc! { "member_id": moid }).sort(doc! { "added_at": 1 }).limit(200).await?;
    let mut out: Vec<Value> = Vec::new();
    while cur.advance().await? {
        let a = cur.deserialize_current()?;
        let (rec, rationale, priority) = compute_game_plan(&a);
        let ovr = a.get_str("counselor_action_override").ok().filter(|s| !s.is_empty());
        let valid = ovr.filter(|o| GAME_PLAN_ACTIONS.contains(o));
        let final_action = valid.unwrap_or(rec).to_string();
        let is_overridden = valid.map(|o| o != rec).unwrap_or(false);
        let late = a.get_datetime("late_payment_date").ok().and_then(|d| d.try_to_rfc3339_string().ok()).map(|s| s.chars().take(10).collect::<String>());
        out.push(json!({
            "id": hex_id(&a),
            "creditor_name": dstr_or(&a, "creditor_name", ""),
            "account_type": dstr_or(&a, "account_type", "revolving"),
            "account_status": dstr_or(&a, "account_status", "open"),
            "bureaus": if a.contains_key("bureaus") { draw(&a, "bureaus") } else { json!([]) },
            "balance": draw(&a, "balance"),
            "has_late_payments": a.get_bool("has_late_payments").unwrap_or(false),
            "late_payment_date": late.map(Value::String).unwrap_or(Value::Null),
            "cross_bureau_inaccuracy": a.get_bool("cross_bureau_inaccuracy").unwrap_or(false),
            "counselor_action_override": draw(&a, "counselor_action_override"),
            "notes": dstr_or(&a, "notes", ""),
            "recommended_action": rec,
            "rationale": rationale,
            "priority": priority,
            "final_action": final_action,
            "is_overridden": is_overridden,
        }));
    }
    Ok(Json(json!(out)))
}

fn filtered_bureaus(body: &Value) -> Vec<String> {
    body.get("bureaus")
        .and_then(|v| v.as_array())
        .map(|arr| {
            arr.iter()
                .filter_map(|x| x.as_str())
                .filter(|b| BUREAUS.contains(b))
                .map(String::from)
                .collect()
        })
        .unwrap_or_default()
}
fn opt_float(body: &Value, k: &str) -> Bson {
    match body.get(k).and_then(|v| v.as_f64()) {
        Some(f) => Bson::Double(f),
        None => Bson::Null,
    }
}

pub async fn add_credit_account(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(member_id): Path<String>,
    Json(body): Json<Value>,
) -> AppResult<Json<Value>> {
    let (id, _) = authenticate_counselor(&state, &headers).await?;
    let c = coid(&id)?;
    let member = assigned_member(&state, &member_id, c).await?;
    let moid = member.get_object_id("_id").map_err(|_| AppError::NotFound)?;
    let creditor = body_str(&body, "creditor_name", "").trim().to_string();
    if creditor.is_empty() {
        return Err(AppError::BadRequest("creditor_name is required".to_string()));
    }
    let atype = body_str(&body, "account_type", "revolving");
    if !ACCOUNT_TYPES.contains(&atype) {
        return Err(AppError::BadRequest("Invalid account_type".to_string()));
    }
    let astatus = body_str(&body, "account_status", "open");
    if !ACCOUNT_STATUSES.contains(&astatus) {
        return Err(AppError::BadRequest("Invalid account_status".to_string()));
    }
    let now = bson::DateTime::now();
    state.db.collection::<Document>("credit_accounts").insert_one(doc! {
        "member_id": moid, "counselor_id": c, "creditor_name": creditor.as_str(),
        "account_type": atype, "account_status": astatus,
        "bureaus": filtered_bureaus(&body),
        "balance": opt_float(&body, "balance"),
        "has_late_payments": body.get("has_late_payments").and_then(|v| v.as_bool()).unwrap_or(false),
        "late_payment_date": parse_iso(body.get("late_payment_date")).map(Bson::DateTime).unwrap_or(Bson::Null),
        "cross_bureau_inaccuracy": body.get("cross_bureau_inaccuracy").and_then(|v| v.as_bool()).unwrap_or(false),
        "counselor_action_override": Bson::Null,
        "notes": body_str(&body, "notes", ""),
        "added_at": now,
    }).await?;
    state.db.collection::<Document>("users").update_one(doc! { "_id": moid }, doc! { "$set": { "last_activity_date": now } }).await?;
    Ok(Json(json!({ "message": "Account added" })))
}

async fn account_owned(state: &AppState, account_id: &str, c: ObjectId) -> AppResult<(ObjectId, Document)> {
    let aid = ObjectId::parse_str(account_id).map_err(|_| AppError::BadRequest("Invalid account ID".to_string()))?;
    let acc = state.db.collection::<Document>("credit_accounts").find_one(doc! { "_id": aid }).await?.ok_or(AppError::NotFound)?;
    let moid = acc.get_object_id("member_id").map_err(|_| AppError::NotFound)?;
    if state.db.collection::<Document>("users").find_one(doc! { "_id": moid, "assigned_counselor_id": c }).await?.is_none() {
        return Err(AppError::Forbidden("Not authorized to update this account".to_string()));
    }
    Ok((aid, acc))
}

pub async fn update_credit_account(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(account_id): Path<String>,
    Json(body): Json<Value>,
) -> AppResult<Json<Value>> {
    let (id, _) = authenticate_counselor(&state, &headers).await?;
    let c = coid(&id)?;
    let (aid, _) = account_owned(&state, &account_id, c).await?;
    let mut set = Document::new();
    for k in ["creditor_name", "account_type", "account_status", "notes"] {
        if let Some(v) = body.get(k).and_then(|v| v.as_str()) {
            set.insert(k, v);
        }
    }
    if body.get("counselor_action_override").is_some() {
        let ovr = body.get("counselor_action_override").and_then(|v| v.as_str()).filter(|s| !s.is_empty());
        set.insert("counselor_action_override", ovr.map(Bson::from).unwrap_or(Bson::Null));
    }
    if body.get("bureaus").is_some() {
        set.insert("bureaus", filtered_bureaus(&body));
    }
    for k in ["has_late_payments", "cross_bureau_inaccuracy"] {
        if let Some(b) = body.get(k).and_then(|v| v.as_bool()) {
            set.insert(k, b);
        }
    }
    if body.get("balance").is_some() {
        set.insert("balance", opt_float(&body, "balance"));
    }
    if body.get("late_payment_date").is_some() {
        set.insert("late_payment_date", parse_iso(body.get("late_payment_date")).map(Bson::DateTime).unwrap_or(Bson::Null));
    }
    if !set.is_empty() {
        set.insert("updated_at", bson::DateTime::now());
        state.db.collection::<Document>("credit_accounts").update_one(doc! { "_id": aid }, doc! { "$set": set }).await?;
    }
    Ok(Json(json!({ "message": "Account updated" })))
}

pub async fn delete_credit_account(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(account_id): Path<String>,
) -> AppResult<Json<Value>> {
    let (id, _) = authenticate_counselor(&state, &headers).await?;
    let c = coid(&id)?;
    let (aid, _) = account_owned(&state, &account_id, c).await?;
    state.db.collection::<Document>("credit_accounts").delete_one(doc! { "_id": aid }).await?;
    Ok(Json(json!({ "message": "Account deleted" })))
}

// ── Disputes (counselor view) ─────────────────────────────────────────────────
pub async fn get_disputes(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(member_id): Path<String>,
) -> AppResult<Json<Value>> {
    let (id, _) = authenticate_counselor(&state, &headers).await?;
    let c = coid(&id)?;
    let member = assigned_member(&state, &member_id, c).await?;
    let moid = member.get_object_id("_id").map_err(|_| AppError::NotFound)?;
    let mut cur = state.db.collection::<Document>("disputes")
        .find(doc! { "user_id": moid }).sort(doc! { "created_at": -1 }).limit(100).await?;
    let mut out = Vec::new();
    while cur.advance().await? {
        let d = cur.deserialize_current()?;
        out.push(json!({
            "id": hex_id(&d), "bureau": dstr_or(&d,"bureau",""), "account_name": dstr_or(&d,"account_name",""),
            "account_number": dstr_or(&d,"account_number",""), "dispute_reason": dstr_or(&d,"dispute_reason",""),
            "status": dstr_or(&d,"status","draft"), "date_sent": ddate(&d,"date_sent"), "date_response": ddate(&d,"date_response"),
            "response_outcome": draw(&d,"response_outcome"), "tracking_number": draw(&d,"tracking_number"),
            "notes": dstr_or(&d,"notes",""), "created_at": ddate(&d,"created_at"),
        }));
    }
    Ok(Json(json!(out)))
}

pub async fn create_dispute(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(member_id): Path<String>,
    Json(body): Json<Value>,
) -> AppResult<Json<Value>> {
    let (id, _) = authenticate_counselor(&state, &headers).await?;
    let c = coid(&id)?;
    let member = assigned_member(&state, &member_id, c).await?;
    let moid = member.get_object_id("_id").map_err(|_| AppError::NotFound)?;
    let bureau = body_str(&body, "bureau", "");
    if !BUREAUS.contains(&bureau) {
        return Err(AppError::BadRequest("Invalid bureau".to_string()));
    }
    let account_name = body_str(&body, "account_name", "");
    if account_name.trim().is_empty() {
        return Err(AppError::BadRequest("account_name is required".to_string()));
    }
    let now = bson::DateTime::now();
    let dres = state.db.collection::<Document>("disputes").insert_one(doc! {
        "user_id": moid, "bureau": bureau, "account_name": account_name,
        "account_number": body_str(&body, "account_number", ""), "dispute_reason": body_str(&body, "dispute_reason", ""),
        "status": "draft", "date_sent": Bson::Null, "date_response": Bson::Null, "response_outcome": Bson::Null,
        "tracking_number": Bson::Null, "notes": body_str(&body, "notes", ""), "created_by_counselor": c, "created_at": now,
    }).await?;
    // auto follow-up task, +7 days
    let due = bson::DateTime::from_millis(now.timestamp_millis() + 7 * 86_400_000);
    state.db.collection::<Document>("tasks").insert_one(doc! {
        "counselor_id": c, "member_id": moid,
        "title": format!("Send certified dispute letter — {account_name} @ {}", bureau_label(bureau)),
        "task_type": "dispute_letter", "dispute_id": dres.inserted_id.clone(),
        "due_date": due, "completed": false, "completed_at": Bson::Null, "created_at": now,
    }).await?;
    state.db.collection::<Document>("users").update_one(doc! { "_id": moid }, doc! { "$set": { "last_activity_date": now } }).await?;
    Ok(Json(json!({ "message": "Dispute created" })))
}

async fn dispute_owned(state: &AppState, dispute_id: &str, c: ObjectId) -> AppResult<(ObjectId, Document)> {
    let did = ObjectId::parse_str(dispute_id).map_err(|_| AppError::BadRequest("Invalid dispute ID".to_string()))?;
    let d = state.db.collection::<Document>("disputes").find_one(doc! { "_id": did }).await?.ok_or(AppError::NotFound)?;
    let moid = d.get_object_id("user_id").map_err(|_| AppError::NotFound)?;
    if state.db.collection::<Document>("users").find_one(doc! { "_id": moid, "assigned_counselor_id": c }).await?.is_none() {
        return Err(AppError::Forbidden("Not authorized to update this dispute".to_string()));
    }
    Ok((did, d))
}

pub async fn update_dispute(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(dispute_id): Path<String>,
    Json(body): Json<Value>,
) -> AppResult<Json<Value>> {
    let (id, _) = authenticate_counselor(&state, &headers).await?;
    let c = coid(&id)?;
    let (did, existing) = dispute_owned(&state, &dispute_id, c).await?;
    let new_status = body.get("status").and_then(|v| v.as_str());
    if let Some(s) = new_status {
        if !DISPUTE_STATUSES.contains(&s) {
            return Err(AppError::BadRequest("Invalid status".to_string()));
        }
    }
    // hard rule: marking sent requires a tracking number (new or existing)
    if new_status == Some("sent") {
        let incoming = body.get("tracking_number").and_then(|v| v.as_str()).filter(|s| !s.is_empty());
        let existing_tn = existing.get_str("tracking_number").ok().filter(|s| !s.is_empty());
        if incoming.is_none() && existing_tn.is_none() {
            return Err(AppError::BadRequest("A certified mail tracking number is required before marking as Sent".to_string()));
        }
    }
    let mut set = Document::new();
    for k in ["bureau", "account_name", "account_number", "dispute_reason", "status", "tracking_number", "notes", "response_outcome"] {
        if body.get(k).is_some() {
            set.insert(k, body_bson(&body, k));
        }
    }
    for k in ["date_sent", "date_response"] {
        if let Some(dt) = parse_iso(body.get(k)) {
            set.insert(k, dt);
        }
    }
    if new_status == Some("sent") && existing.get_datetime("date_sent").is_err() && !set.contains_key("date_sent") {
        set.insert("date_sent", bson::DateTime::now());
    }
    let now = bson::DateTime::now();
    set.insert("updated_at", now);
    state.db.collection::<Document>("disputes").update_one(doc! { "_id": did }, doc! { "$set": set }).await?;
    if let Ok(moid) = existing.get_object_id("user_id") {
        state.db.collection::<Document>("users").update_one(doc! { "_id": moid }, doc! { "$set": { "last_activity_date": now } }).await?;
        if matches!(new_status, Some("sent") | Some("responded")) {
            if let Some(m) = state.db.collection::<Document>("users").find_one(doc! { "_id": moid }).await? {
                if let Ok(email) = m.get_str("email") {
                    let fname = m.get_str("first_name").unwrap_or("Member").to_string();
                    let acct = existing.get_str("account_name").unwrap_or("Account").to_string();
                    let bureau = existing.get_str("bureau").unwrap_or("Bureau").to_string();
                    sh_core::email::send_dispute_update_email(email, &fname, &acct, &bureau, new_status.unwrap()).await;
                }
            }
        }
    }
    Ok(Json(json!({ "message": "Dispute updated" })))
}

pub async fn delete_dispute(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(dispute_id): Path<String>,
) -> AppResult<Json<Value>> {
    let (id, _) = authenticate_counselor(&state, &headers).await?;
    let c = coid(&id)?;
    let (did, _) = dispute_owned(&state, &dispute_id, c).await?;
    state.db.collection::<Document>("disputes").delete_one(doc! { "_id": did }).await?;
    Ok(Json(json!({ "message": "Dispute deleted" })))
}

// ── Documents (S3) ────────────────────────────────────────────────────────────
const ALLOWED_DOC_TYPES: [&str; 6] = [
    "application/pdf", "image/jpeg", "image/jpg", "image/png",
    "application/msword", "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
];
const DOC_CATEGORIES: [&str; 7] = [
    "dd214", "credit_report", "dispute_letter", "goodwill_letter", "validation_letter", "correspondence", "other",
];

pub async fn get_documents(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(member_id): Path<String>,
) -> AppResult<Json<Value>> {
    let (id, _) = authenticate_counselor(&state, &headers).await?;
    let c = coid(&id)?;
    let member = assigned_member(&state, &member_id, c).await?;
    let moid = member.get_object_id("_id").map_err(|_| AppError::NotFound)?;
    let mut out: Vec<Value> = Vec::new();
    if let Ok(f) = member.get_str("dd214_file") {
        if !f.is_empty() {
            let url = sh_core::storage::presign_get(&format!("dd214/{f}"), 3600).await.unwrap_or_default();
            out.push(json!({
                "id": format!("dd214-{member_id}"), "display_name": "DD-214", "category": "dd214",
                "storage_type": dstr_or(&member, "dd214_storage_type", "local"),
                "uploaded_at": ddate(&member, "dd214_uploaded_at"), "uploaded_by": Value::Null,
                "download_url": url, "is_system": true, "dd214_status": dstr_or(&member, "dd214_status", "pending"),
            }));
        }
    }
    let mut cur = state.db.collection::<Document>("documents")
        .find(doc! { "member_id": moid }).sort(doc! { "uploaded_at": -1 }).limit(200).await?;
    while cur.advance().await? {
        let d = cur.deserialize_current()?;
        let key = d.get_str("storage_key").unwrap_or("");
        let url = if key.is_empty() { String::new() } else { sh_core::storage::presign_get(key, 3600).await.unwrap_or_default() };
        out.push(json!({
            "id": hex_id(&d), "display_name": dstr_or(&d, "display_name", ""), "category": dstr_or(&d, "category", "other"),
            "storage_type": dstr_or(&d, "storage_type", "local"), "file_size": dint(&d, "file_size"),
            "uploaded_at": ddate(&d, "uploaded_at"), "uploaded_by": dstr_or(&d, "uploaded_by_name", ""),
            "download_url": url, "is_system": false,
        }));
    }
    Ok(Json(json!(out)))
}

pub async fn upload_document(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(member_id): Path<String>,
    mut multipart: Multipart,
) -> AppResult<Json<Value>> {
    let (id, user) = authenticate_counselor(&state, &headers).await?;
    let c = coid(&id)?;
    let member = assigned_member(&state, &member_id, c).await?;
    let moid = member.get_object_id("_id").map_err(|_| AppError::NotFound)?;

    let mut bytes: Option<Vec<u8>> = None;
    let mut original = String::new();
    let mut content_type = String::new();
    let mut category = String::new();
    let mut display_name = String::new();
    while let Some(field) = multipart.next_field().await.map_err(|_| AppError::BadRequest("Malformed upload".to_string()))? {
        match field.name() {
            Some("file") => {
                original = field.file_name().unwrap_or("document").to_string();
                content_type = field.content_type().unwrap_or("").to_string();
                bytes = Some(field.bytes().await.map_err(|_| AppError::BadRequest("Could not read file".to_string()))?.to_vec());
            }
            Some("category") => category = field.text().await.unwrap_or_default(),
            Some("display_name") => display_name = field.text().await.unwrap_or_default(),
            _ => {}
        }
    }
    if !DOC_CATEGORIES.contains(&category.as_str()) {
        return Err(AppError::BadRequest("Invalid category".to_string()));
    }
    if !ALLOWED_DOC_TYPES.contains(&content_type.as_str()) {
        return Err(AppError::BadRequest("Invalid file type".to_string()));
    }
    let data = bytes.ok_or_else(|| AppError::BadRequest("No file provided".to_string()))?;
    if data.len() > 20 * 1024 * 1024 {
        return Err(AppError::BadRequest("File too large. Maximum 20MB.".to_string()));
    }
    let ext = original.rsplit('.').next().filter(|e| !e.is_empty() && e.len() <= 5).unwrap_or("bin").to_lowercase();
    let file_size = data.len() as i64;
    let mut rand = [0u8; 16];
    getrandom::getrandom(&mut rand).ok();
    let stored = format!("{member_id}_{}.{ext}", rand.iter().map(|b| format!("{b:02x}")).collect::<String>());
    let key = format!("documents/{stored}");
    sh_core::storage::put_object(&key, data).await.map_err(AppError::Internal)?;

    let cname = format!("{} {}", user.first_name.clone().unwrap_or_default(), user.last_name.clone().unwrap_or_default()).trim().to_string();
    let doc_name = if display_name.trim().is_empty() { original.clone() } else { display_name.trim().to_string() };
    let now = bson::DateTime::now();
    state.db.collection::<Document>("documents").insert_one(doc! {
        "member_id": moid, "display_name": doc_name.as_str(), "category": category.as_str(),
        "storage_key": key.as_str(), "storage_type": "s3", "file_size": file_size,
        "original_filename": original.as_str(), "uploaded_at": now, "uploaded_by": c, "uploaded_by_name": cname.as_str(),
    }).await?;
    state.db.collection::<Document>("users").update_one(doc! { "_id": moid }, doc! { "$set": { "last_activity_date": now } }).await?;
    Ok(Json(json!({ "message": "Document uploaded successfully", "display_name": doc_name })))
}

pub async fn delete_document(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(doc_id): Path<String>,
) -> AppResult<Json<Value>> {
    let (id, _) = authenticate_counselor(&state, &headers).await?;
    let c = coid(&id)?;
    let did = ObjectId::parse_str(&doc_id).map_err(|_| AppError::BadRequest("Invalid document ID".to_string()))?;
    let docs = state.db.collection::<Document>("documents");
    let d = docs.find_one(doc! { "_id": did }).await?.ok_or(AppError::NotFound)?;
    let moid = d.get_object_id("member_id").map_err(|_| AppError::NotFound)?;
    if state.db.collection::<Document>("users").find_one(doc! { "_id": moid, "assigned_counselor_id": c }).await?.is_none() {
        return Err(AppError::Forbidden("Not authorized to delete this document".to_string()));
    }
    docs.delete_one(doc! { "_id": did }).await?;
    Ok(Json(json!({ "message": "Document deleted" })))
}

// ── Tasks ─────────────────────────────────────────────────────────────────────
pub async fn get_tasks(State(state): State<AppState>, headers: HeaderMap) -> AppResult<Json<Value>> {
    let (id, _) = authenticate_counselor(&state, &headers).await?;
    let c = coid(&id)?;
    let mut cur = state.db.collection::<Document>("tasks")
        .find(doc! { "counselor_id": c }).sort(doc! { "due_date": 1 }).limit(500).await?;
    let mut tasks: Vec<Document> = Vec::new();
    let mut mids: Vec<ObjectId> = Vec::new();
    while cur.advance().await? {
        let t = cur.deserialize_current()?;
        if let Ok(m) = t.get_object_id("member_id") {
            mids.push(m);
        }
        tasks.push(t);
    }
    let mut names: std::collections::HashMap<ObjectId, String> = std::collections::HashMap::new();
    if !mids.is_empty() {
        let mut uc = state.db.collection::<Document>("users").find(doc! { "_id": { "$in": mids } }).await?;
        while uc.advance().await? {
            let u = uc.deserialize_current()?;
            if let Ok(mid) = u.get_object_id("_id") {
                names.insert(mid, full_name(&u));
            }
        }
    }
    let now = bson::DateTime::now().timestamp_millis();
    let out: Vec<Value> = tasks.iter().map(|t| {
        let completed = t.get_bool("completed").unwrap_or(false);
        let due_ms = t.get_datetime("due_date").ok().map(|d| d.timestamp_millis());
        let overdue = !completed && due_ms.map(|d| d < now).unwrap_or(false);
        let mname = t.get_object_id("member_id").ok().and_then(|m| names.get(&m).cloned()).unwrap_or_else(|| "Unknown".to_string());
        json!({
            "id": hex_id(t), "title": dstr_or(t, "title", ""), "task_type": dstr_or(t, "task_type", "custom"),
            "member_id": t.get_object_id("member_id").ok().map(|m| m.to_hex()), "member_name": mname,
            "dispute_id": t.get_object_id("dispute_id").ok().map(|d| d.to_hex()),
            "due_date": ddate(t, "due_date"), "completed": completed, "completed_at": ddate(t, "completed_at"),
            "overdue": overdue, "created_at": ddate(t, "created_at"),
        })
    }).collect();
    Ok(Json(json!(out)))
}

pub async fn create_task(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(body): Json<Value>,
) -> AppResult<Json<Value>> {
    let (id, _) = authenticate_counselor(&state, &headers).await?;
    let c = coid(&id)?;
    let member_id = body_str(&body, "member_id", "");
    let moid = ObjectId::parse_str(member_id).map_err(|_| AppError::BadRequest("Invalid member_id".to_string()))?;
    if state.db.collection::<Document>("users").find_one(doc! { "_id": moid, "assigned_counselor_id": c }).await?.is_none() {
        return Err(AppError::NotFound);
    }
    let title = body_str(&body, "title", "").trim().to_string();
    if title.is_empty() {
        return Err(AppError::BadRequest("title is required".to_string()));
    }
    let due = parse_iso_or_now(body.get("due_date"));
    state.db.collection::<Document>("tasks").insert_one(doc! {
        "counselor_id": c, "member_id": moid, "title": title.as_str(), "task_type": "custom",
        "dispute_id": Bson::Null, "due_date": due, "completed": false, "completed_at": Bson::Null, "created_at": bson::DateTime::now(),
    }).await?;
    Ok(Json(json!({ "message": "Task created" })))
}

pub async fn complete_task(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(task_id): Path<String>,
    Json(body): Json<Value>,
) -> AppResult<Json<Value>> {
    let (id, _) = authenticate_counselor(&state, &headers).await?;
    let c = coid(&id)?;
    let tid = ObjectId::parse_str(&task_id).map_err(|_| AppError::BadRequest("Invalid task ID".to_string()))?;
    let tasks = state.db.collection::<Document>("tasks");
    if tasks.find_one(doc! { "_id": tid, "counselor_id": c }).await?.is_none() {
        return Err(AppError::NotFound);
    }
    let completed = body.get("completed").and_then(|v| v.as_bool()).unwrap_or(true);
    let completed_at = if completed { Bson::DateTime(bson::DateTime::now()) } else { Bson::Null };
    tasks.update_one(doc! { "_id": tid }, doc! { "$set": { "completed": completed, "completed_at": completed_at } }).await?;
    Ok(Json(json!({ "message": "Task updated", "completed": completed })))
}

pub async fn delete_task(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(task_id): Path<String>,
) -> AppResult<Json<Value>> {
    let (id, _) = authenticate_counselor(&state, &headers).await?;
    let c = coid(&id)?;
    let tid = ObjectId::parse_str(&task_id).map_err(|_| AppError::BadRequest("Invalid task ID".to_string()))?;
    let res = state.db.collection::<Document>("tasks").delete_one(doc! { "_id": tid, "counselor_id": c }).await?;
    if res.deleted_count == 0 {
        return Err(AppError::NotFound);
    }
    Ok(Json(json!({ "message": "Task deleted" })))
}

// ── Waitlist ──────────────────────────────────────────────────────────────────
pub async fn waitlist(State(state): State<AppState>, headers: HeaderMap) -> AppResult<Json<Value>> {
    let (id, _) = authenticate_counselor(&state, &headers).await?;
    let c = coid(&id)?;
    let users = state.db.collection::<Document>("users");
    let cdoc = users.find_one(doc! { "_id": c }).await?;
    let max_caseload = cdoc.as_ref().map(|u| dint(u, "max_caseload")).filter(|&n| n > 0).unwrap_or(12);
    let current = users.count_documents(doc! { "assigned_counselor_id": c, "role": "member" }).await? as i64;
    let mut cur = users.find(doc! {
        "role": "member",
        "$and": [
            { "$or": [ { "assigned_counselor_id": { "$exists": false } }, { "assigned_counselor_id": Bson::Null } ] },
            { "$or": [ { "credit_repair_stage": "cr_waitlist" }, { "financial_counseling_stage": "fc_waitlist" } ] },
        ],
    }).sort(doc! { "created_at": 1 }).limit(500).await?;
    let mut list = Vec::new();
    while cur.advance().await? {
        let m = cur.deserialize_current()?;
        let has_cr = m.get_str("credit_repair_stage").map(|s| s == "cr_waitlist").unwrap_or(false);
        let has_fc = m.get_str("financial_counseling_stage").map(|s| s == "fc_waitlist").unwrap_or(false);
        let program = if has_cr && has_fc { "Credit Repair & Financial Counseling" } else if has_cr { "Credit Repair" } else { "Financial Counseling" };
        list.push(json!({
            "id": hex_id(&m), "name": full_name(&m), "email": dstr_or(&m,"email",""),
            "branch": draw(&m,"branch"), "state": draw(&m,"state"),
            "program": program, "has_cr": has_cr, "has_fc": has_fc, "created_at": ddate(&m,"created_at"),
        }));
    }
    Ok(Json(json!({
        "capacity": { "current": current, "max": max_caseload, "available": (max_caseload - current).max(0) },
        "members": list,
    })))
}

pub async fn claim_waitlist(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(member_id): Path<String>,
) -> AppResult<Json<Value>> {
    let (id, user) = authenticate_counselor(&state, &headers).await?;
    let c = coid(&id)?;
    let users = state.db.collection::<Document>("users");
    let current = users.count_documents(doc! { "assigned_counselor_id": c, "role": "member" }).await? as i64;
    let cdoc = users.find_one(doc! { "_id": c }).await?;
    let max_caseload = cdoc.as_ref().map(|u| dint(u, "max_caseload")).filter(|&n| n > 0).unwrap_or(12);
    if current >= max_caseload {
        return Err(AppError::BadRequest(format!("You are at your maximum caseload ({max_caseload} members)")));
    }
    let moid = ObjectId::parse_str(&member_id).map_err(|_| AppError::NotFound)?;
    let member = users.find_one(doc! { "_id": moid, "role": "member" }).await?.ok_or(AppError::NotFound)?;
    if member.get_object_id("assigned_counselor_id").is_ok() {
        return Err(AppError::Conflict("This member was just claimed by another counselor".to_string()));
    }
    let track = if member.get_str("credit_repair_stage").map(|s| s == "cr_waitlist").unwrap_or(false) {
        "credit_repair"
    } else if member.get_str("financial_counseling_stage").map(|s| s == "fc_waitlist").unwrap_or(false) {
        "financial_counseling"
    } else {
        member.get_str("program_track").unwrap_or("onboarding")
    };
    let now = bson::DateTime::now();
    users.update_one(doc! { "_id": moid }, doc! { "$set": {
        "assigned_counselor_id": c, "pipeline_stage": "counselor_assigned", "program_track": track, "last_activity_date": now,
    }}).await?;
    let first = member.get_str("first_name").unwrap_or("Member").to_string();
    if let Ok(email) = member.get_str("email") {
        let cname = format!("{} {}", user.first_name.clone().unwrap_or_default(), user.last_name.clone().unwrap_or_default()).trim().to_string();
        sh_core::email::send_counselor_assigned_email(email, &first, &cname).await;
    }
    Ok(Json(json!({ "message": format!("{first} added to your caseload") })))
}

// ── GET /api/member/counselor  (also /api/counselor/assigned) ─────────────────
pub async fn my_counselor(State(state): State<AppState>, headers: HeaderMap) -> AppResult<Json<Value>> {
    let (_, user) = authenticate(&state, &headers).await?;
    let cid = match user.assigned_counselor_id.as_deref().and_then(|s| ObjectId::parse_str(s).ok()) {
        Some(c) => c,
        None => return Ok(Json(json!({ "id": null, "name": null, "message": "No counselor assigned yet" }))),
    };
    match state.db.collection::<Document>("users").find_one(doc! { "_id": cid }).await? {
        Some(c) => Ok(Json(json!({
            "id": c.get_object_id("_id").map(|o| o.to_hex()).unwrap_or_default(),
            "name": full_name(&c), "email": dstr_or(&c, "email", ""),
            "title": dstr_or(&c, "title", "Certified Financial Counselor"),
            "bio": dstr_or(&c, "bio", ""), "specialties": draw(&c, "specialties"), "calendly_url": draw(&c, "calendly_url"),
        }))),
        None => Ok(Json(json!({ "id": null, "name": null, "message": "No counselor assigned yet" }))),
    }
}

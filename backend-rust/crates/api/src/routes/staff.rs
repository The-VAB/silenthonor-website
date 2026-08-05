//! Staff management (`/api/admin/staff/*`). Port of routers/staff.py. Staff,
//! admins and counselors are all `users` documents with the matching `role`.

use axum::extract::{Path, State};
use axum::http::HeaderMap;
use axum::Json;
use bson::oid::ObjectId;
use bson::{doc, Bson, Document};
use serde::Deserialize;
use serde_json::{json, Value};

use super::{authenticate_admin, ddate, dstr, dstr_or, full_name, hex_id, iso, log_audit};
use crate::state::AppState;
use sh_core::auth::hash_password;
use sh_core::{AppError, AppResult};

const STAFF_ROLES: [&str; 3] = ["staff", "admin", "counselor"];

fn rand_hex(n: usize) -> String {
    let mut buf = vec![0u8; n];
    getrandom::getrandom(&mut buf).ok();
    buf.iter().map(|b| format!("{b:02x}")).collect()
}

fn arr(d: &Document, k: &str) -> Value {
    match d.get_array(k) {
        Ok(a) => Value::Array(a.iter().cloned().map(super::sanitize).collect()),
        Err(_) => json!([]),
    }
}

// ── GET /api/admin/staff ──────────────────────────────────────────────────────
pub async fn get_staff(State(state): State<AppState>, headers: HeaderMap) -> AppResult<Json<Value>> {
    authenticate_admin(&state, &headers).await?;
    let users = state.db.collection::<Document>("users");
    let mut cur = users
        .find(doc! { "role": { "$in": ["staff", "admin", "counselor"] } })
        .limit(100)
        .await?;
    let mut out: Vec<Value> = Vec::new();
    while cur.advance().await? {
        let s = cur.deserialize_current()?;
        let client_count = if s.get_str("role").unwrap_or("") == "counselor" {
            if let Ok(sid) = s.get_object_id("_id") {
                users.count_documents(doc! { "assigned_counselor_id": sid }).await?
            } else {
                0
            }
        } else {
            0
        };
        out.push(json!({
            "id": hex_id(&s),
            "email": dstr(&s, "email"),
            "first_name": dstr_or(&s, "first_name", ""),
            "last_name": dstr_or(&s, "last_name", ""),
            "name": full_name(&s),
            "role": dstr(&s, "role"),
            "title": dstr_or(&s, "title", ""),
            "bio": dstr_or(&s, "bio", ""),
            "specialties": arr(&s, "specialties"),
            "permissions": arr(&s, "permissions"),
            "active": Value::Bool(s.get_bool("active").unwrap_or(true)),
            "client_count": client_count,
            "calendly_url": dstr_or(&s, "calendly_url", ""),
            "created_at": ddate(&s, "created_at"),
            "last_active": ddate(&s, "last_active"),
        }));
    }
    Ok(Json(json!(out)))
}

#[derive(Debug, Deserialize)]
pub struct StaffRequest {
    pub email: String,
    #[serde(default)]
    pub first_name: String,
    #[serde(default)]
    pub last_name: String,
    #[serde(default = "staff_role")]
    pub role: String,
    #[serde(default)]
    pub title: Option<String>,
    #[serde(default)]
    pub bio: Option<String>,
    #[serde(default)]
    pub specialties: Vec<String>,
    #[serde(default)]
    pub credentials: Option<String>,
    #[serde(default)]
    pub permissions: Vec<String>,
    #[serde(default)]
    pub calendly_url: Option<String>,
}
fn staff_role() -> String {
    "staff".to_string()
}

// ── POST /api/admin/staff ─────────────────────────────────────────────────────
pub async fn create_staff(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(body): Json<StaffRequest>,
) -> AppResult<Json<Value>> {
    let (_, admin) = authenticate_admin(&state, &headers).await?;
    if !STAFF_ROLES.contains(&body.role.as_str()) {
        return Err(AppError::BadRequest(
            "Role must be one of: [staff, admin, counselor]".to_string(),
        ));
    }
    let email = body.email.to_lowercase();
    let users = state.db.collection::<Document>("users");
    if users.find_one(doc! { "email": email.as_str() }).await?.is_some() {
        return Err(AppError::BadRequest("Email already registered".to_string()));
    }

    let temp_password = rand_hex(12);
    let hash = hash_password(&temp_password).map_err(AppError::Internal)?;
    let now = bson::DateTime::now();
    let specialties: Vec<Bson> = body.specialties.iter().map(|s| Bson::String(s.clone())).collect();
    let permissions: Vec<Bson> = body.permissions.iter().map(|s| Bson::String(s.clone())).collect();

    let res = users
        .insert_one(doc! {
            "email": email.as_str(),
            "password_hash": hash.as_str(),
            "first_name": body.first_name.as_str(),
            "last_name": body.last_name.as_str(),
            "role": body.role.as_str(),
            "roles": [body.role.as_str()],
            "title": body.title.clone().unwrap_or_default(),
            "bio": body.bio.clone().unwrap_or_default(),
            "specialties": specialties,
            "credentials": body.credentials.clone().unwrap_or_default(),
            "calendly_url": match &body.calendly_url { Some(u) => Bson::String(u.clone()), None => Bson::Null },
            "permissions": permissions,
            "active": true,
            "created_at": now,
        })
        .await?;
    let id = res.inserted_id.as_object_id().map(|o| o.to_hex()).unwrap_or_default();

    log_audit(&state, "staff_created", "user", Some(&id), Some(admin.email.as_str())).await;
    // Awaited (Lambda freezes background tasks on return).
    sh_core::email::send_staff_welcome_email(&email, &body.first_name, &body.role, &temp_password).await;

    Ok(Json(json!({
        "id": id,
        "email": body.email,
        "first_name": body.first_name,
        "last_name": body.last_name,
        "name": format!("{} {}", body.first_name, body.last_name).trim(),
        "role": body.role,
        "active": true,
        "created_at": iso(Some(now)),
    })))
}

// ── PUT /api/admin/staff/{staff_id} ───────────────────────────────────────────
pub async fn update_staff(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(staff_id): Path<String>,
    Json(body): Json<Value>,
) -> AppResult<Json<Value>> {
    let (_, admin) = authenticate_admin(&state, &headers).await?;
    let oid = ObjectId::parse_str(&staff_id).map_err(|_| AppError::NotFound)?;

    const ALLOWED: [&str; 11] = [
        "first_name", "last_name", "email", "role", "title", "active", "bio", "specialties",
        "calendly_url", "credentials", "max_caseload",
    ];
    let mut set = Document::new();
    if let Some(obj) = body.as_object() {
        for (k, v) in obj {
            if ALLOWED.contains(&k.as_str()) {
                set.insert(k, bson::to_bson(v).unwrap_or(Bson::Null));
            }
        }
    }
    if let Some(role) = set.get_str("role").ok() {
        if !STAFF_ROLES.contains(&role) {
            return Err(AppError::BadRequest(
                "Role must be one of: [staff, admin, counselor]".to_string(),
            ));
        }
    }
    if set.is_empty() {
        return Err(AppError::BadRequest("No valid fields to update".to_string()));
    }
    set.insert("updated_at", bson::DateTime::now());
    let res = state
        .db
        .collection::<Document>("users")
        .update_one(
            doc! { "_id": oid, "role": { "$in": ["staff", "admin", "counselor"] } },
            doc! { "$set": set },
        )
        .await?;
    if res.matched_count == 0 {
        return Err(AppError::NotFound);
    }
    log_audit(&state, "staff_updated", "user", Some(&staff_id), Some(admin.email.as_str())).await;
    Ok(Json(json!({ "message": "Staff member updated" })))
}

// ── GET /api/admin/staff/counselors ───────────────────────────────────────────
pub async fn get_counselors(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> AppResult<Json<Value>> {
    authenticate_admin(&state, &headers).await?;
    let users = state.db.collection::<Document>("users");
    let mut cur = users
        .find(doc! { "role": "counselor", "active": true })
        .limit(100)
        .await?;
    let mut out: Vec<Value> = Vec::new();
    while cur.advance().await? {
        let c = cur.deserialize_current()?;
        let client_count = match c.get_object_id("_id") {
            Ok(cid) => users.count_documents(doc! { "assigned_counselor_id": cid }).await?,
            Err(_) => 0,
        };
        out.push(json!({
            "id": hex_id(&c),
            "name": full_name(&c),
            "email": dstr(&c, "email"),
            "specialties": arr(&c, "specialties"),
            "client_count": client_count,
        }));
    }
    Ok(Json(json!(out)))
}

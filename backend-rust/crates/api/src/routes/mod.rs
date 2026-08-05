//! HTTP routing + small cookie helpers shared by handlers.

pub mod admin;
pub mod assistant;
pub mod auth;
pub mod content;
pub mod counselor;
pub mod courses;
pub mod credit;
pub mod disputes;
pub mod fc;
pub mod health;
pub mod knowledge;
pub mod major_finance;
pub mod members;
pub mod messages;
pub mod programs;
pub mod staff;

use axum::extract::Request;
use axum::http::{HeaderMap, Method, StatusCode};
use axum::middleware::{self, Next};
use axum::response::{IntoResponse, Response};
use axum::routing::{delete, get, patch, post, put};
use axum::Router;
use serde_json::Value;

use bson::oid::ObjectId;
use bson::{doc, Document};
use sh_core::auth::verify_token;
use sh_core::models::User;
use sh_core::{AppError, AppResult};

use crate::state::AppState;

/// Build the full application router. Paths mirror the current FastAPI service
/// exactly so the frontend can be pointed at either backend.
pub fn router(state: AppState) -> Router {
    Router::new()
        .route("/health", get(health::health))
        .route("/api/health", get(health::health))
        .route("/api/auth/register", post(auth::register))
        .route("/api/auth/login", post(auth::login))
        .route("/api/auth/me", get(auth::me))
        .route("/api/auth/logout", post(auth::logout))
        .route("/api/auth/refresh", post(auth::refresh))
        .route("/api/auth/forgot-password", post(auth::forgot_password))
        .route("/api/auth/reset-password", post(auth::reset_password))
        .route("/api/auth/change-password", post(auth::change_password))
        .route("/api/auth/google/config", get(auth::google_config))
        .route("/api/auth/google", post(auth::google_login))
        .route("/api/contact", post(content::contact))
        .route("/api/admin/stats", get(admin::stats))
        .route("/api/admin/members", get(admin::members))
        .route("/api/admin/members/:member_id/verify", post(admin::verify_member))
        .route(
            "/api/admin/courses",
            get(admin::list_courses).post(admin::create_course),
        )
        .route(
            "/api/admin/courses/:course_id",
            put(admin::update_course).delete(admin::delete_course),
        )
        .route("/api/admin/contacts", get(admin::list_contacts))
        .route(
            "/api/admin/contacts/:contact_id",
            put(admin::update_contact).delete(admin::delete_contact),
        )
        .route("/api/admin/dd214/:filename", get(admin::download_dd214))
        // ── admin console: analytics / pipeline / audit ──
        .route("/api/admin/analytics", get(admin::analytics))
        .route("/api/admin/audit-log", get(admin::audit_log))
        .route("/api/admin/pipeline", get(programs::admin_pipeline))
        // ── admin console: member operations ──
        .route("/api/admin/members/:member_id", get(admin::member_detail))
        .route("/api/admin/members/:member_id/full", get(admin::member_full))
        .route(
            "/api/admin/members/:member_id/notes",
            get(admin::get_member_notes).post(admin::add_member_note),
        )
        .route("/api/admin/members/:member_id/password", put(admin::set_member_password))
        .route("/api/admin/members/:member_id/stage", put(programs::set_member_stage))
        .route("/api/admin/members/:member_id/archive", patch(admin::archive_member))
        .route("/api/admin/members/:member_id/approve-dd214", post(admin::approve_dd214))
        // ── admin console: announcements ──
        .route(
            "/api/admin/announcements",
            get(programs::list_announcements).post(programs::create_announcement),
        )
        .route(
            "/api/admin/announcements/:announcement_id",
            put(programs::update_announcement).delete(programs::delete_announcement),
        )
        // ── admin console: program applications ──
        .route("/api/admin/applications", get(programs::list_applications))
        .route("/api/admin/applications/:application_id", get(programs::application_detail))
        .route(
            "/api/admin/applications/:application_id/approve",
            put(programs::approve_application),
        )
        .route(
            "/api/admin/applications/:application_id/reject",
            put(programs::reject_application),
        )
        // ── admin console: LMS modules + lessons ──
        .route(
            "/api/admin/courses/:course_id/modules",
            get(courses::get_modules).post(courses::create_module),
        )
        .route(
            "/api/admin/modules/:module_id",
            put(courses::update_module).delete(courses::delete_module),
        )
        .route(
            "/api/admin/modules/:module_id/lessons",
            get(courses::get_module_lessons).post(courses::create_module_lesson),
        )
        .route(
            "/api/admin/modules/:module_id/lessons/:lesson_id",
            put(courses::update_module_lesson),
        )
        .route("/api/admin/lessons", post(courses::create_lesson))
        .route(
            "/api/admin/lessons/:lesson_id",
            put(courses::update_lesson).delete(courses::delete_lesson),
        )
        // ── knowledge base (member read + admin management) ──
        .route("/api/knowledge", get(knowledge::list_member_knowledge))
        .route(
            "/api/admin/knowledge",
            get(knowledge::list_all).post(knowledge::create_entry),
        )
        .route(
            "/api/admin/knowledge/:entry_id",
            get(knowledge::get_entry).put(knowledge::update_entry).delete(knowledge::delete_entry),
        )
        .route("/api/admin/knowledge/:entry_id/publish", post(knowledge::publish_entry))
        .route("/api/admin/knowledge/:entry_id/retire", post(knowledge::retire_entry))
        // ── admin console: staff management ──
        .route(
            "/api/admin/staff",
            get(staff::get_staff).post(staff::create_staff),
        )
        .route("/api/admin/staff/counselors", get(staff::get_counselors))
        .route("/api/admin/staff/:staff_id", put(staff::update_staff))
        .route("/api/admin/staff/:staff_id/full", get(admin::staff_full))
        .route("/api/admin/staff/:staff_id/invite", post(admin::staff_invite))
        // DD-214 upload -- registered under every path the frontend/backend use.
        .route("/api/upload/dd214", post(members::upload_dd214))
        .route("/api/member/upload/dd214", post(members::upload_dd214))
        .route("/api/member/dd214", post(members::upload_dd214))
        // ── member-facing: credit / disputes / messages / programs / courses ──
        .route("/api/credit/history", get(credit::history))
        .route("/api/credit/latest", get(credit::latest))
        .route("/api/credit/stats", get(credit::stats))
        .route("/api/credit/score", post(credit::create_score))
        .route(
            "/api/credit/:score_id",
            put(credit::update_score).delete(credit::delete_score),
        )
        .route("/api/disputes", get(disputes::list).post(disputes::create))
        .route(
            "/api/disputes/:dispute_id",
            put(disputes::update).delete(disputes::delete),
        )
        .route("/api/messages", get(messages::list).post(messages::send))
        .route("/api/messages/conversations", get(messages::conversations))
        .route("/api/messages/unread", get(messages::unread))
        .route("/api/messages/admin/all", get(messages::admin_all))
        .route("/api/messages/:message_id/read", put(messages::mark_read))
        .route(
            "/api/messages/conversation/:user_id/read",
            put(messages::mark_conversation_read),
        )
        .route("/api/member/programs", get(programs::list_programs))
        .route("/api/member/apply/credit-repair", post(programs::apply_credit_repair))
        .route(
            "/api/member/apply/financial-counseling",
            post(programs::apply_financial_counseling),
        )
        .route("/api/announcements", get(content::announcements))
        .route("/api/courses/progress", get(courses::progress))
        .route("/api/courses/:course_id", get(courses::detail))
        // ── counselor portal ──
        .route("/api/counselor/stats", get(counselor::stats))
        .route("/api/counselor/caseload", get(counselor::caseload))
        .route("/api/counselor/members", get(counselor::members))
        .route("/api/counselor/members/:member_id", get(counselor::member_detail))
        .route(
            "/api/counselor/members/:member_id/program-track",
            patch(counselor::program_track),
        )
        .route("/api/counselor/members/:member_id/notes", post(counselor::add_note))
        .route(
            "/api/counselor/members/:member_id/credit-scores",
            get(counselor::get_credit_scores).post(counselor::add_credit_score),
        )
        .route("/api/counselor/members/:member_id/game-plan", get(counselor::game_plan))
        .route(
            "/api/counselor/members/:member_id/credit-accounts",
            post(counselor::add_credit_account),
        )
        .route(
            "/api/counselor/credit-accounts/:account_id",
            patch(counselor::update_credit_account).delete(counselor::delete_credit_account),
        )
        .route(
            "/api/counselor/members/:member_id/disputes",
            get(counselor::get_disputes).post(counselor::create_dispute),
        )
        .route(
            "/api/counselor/disputes/:dispute_id",
            patch(counselor::update_dispute).delete(counselor::delete_dispute),
        )
        .route(
            "/api/counselor/members/:member_id/documents",
            get(counselor::get_documents).post(counselor::upload_document),
        )
        .route("/api/counselor/documents/:doc_id", delete(counselor::delete_document))
        .route(
            "/api/counselor/tasks",
            get(counselor::get_tasks).post(counselor::create_task),
        )
        .route("/api/counselor/tasks/:task_id/complete", patch(counselor::complete_task))
        .route("/api/counselor/tasks/:task_id", delete(counselor::delete_task))
        .route("/api/counselor/waitlist", get(counselor::waitlist))
        .route("/api/counselor/waitlist/:member_id/claim", post(counselor::claim_waitlist))
        // NOTE: GET /api/member/counselor is already served by members::counselor.
        .route("/api/counselor/assigned", get(counselor::my_counselor))
        // ── financial-counseling tools (fc/*) ──
        .route("/api/counselor/members/:member_id/fc", get(fc::get_fc))
        .route("/api/counselor/members/:member_id/fc/intake", put(fc::intake))
        .route("/api/counselor/members/:member_id/fc/budgets", post(fc::add_budget))
        .route("/api/counselor/members/:member_id/fc/debt-plan", put(fc::debt_plan))
        .route("/api/counselor/members/:member_id/fc/goals", post(fc::add_goal))
        .route(
            "/api/counselor/members/:member_id/fc/goals/:goal_id",
            patch(fc::update_goal).delete(fc::delete_goal),
        )
        .route(
            "/api/counselor/members/:member_id/fc/session-notes",
            post(fc::add_session_note),
        )
        .route("/api/counselor/members/:member_id/fc/housing", put(fc::housing))
        .route("/api/counselor/members/:member_id/fc/retirement", put(fc::retirement))
        .route("/api/counselor/members/:member_id/fc/tax-ref", put(fc::tax_ref))
        .route(
            "/api/counselor/members/:member_id/fc/fraud-checklist",
            put(fc::fraud_checklist),
        )
        .route("/api/counselor/members/:member_id/fc/referrals", post(fc::add_referral))
        .route(
            "/api/member/profile",
            get(members::get_profile).put(members::update_profile),
        )
        .route("/api/member/counselor", get(members::counselor))
        .route("/api/member/dashboard", get(members::dashboard))
        .route("/api/member/courses", get(members::courses))
        .route(
            "/api/member/courses/:course_id/progress",
            post(members::update_progress),
        )
        .route(
            "/api/member/financial-intake",
            get(members::get_financial_intake).post(members::save_financial_intake),
        )
        .route(
            "/api/member/major-finance/status",
            get(major_finance::status),
        )
        .route("/api/member/major-finance", post(major_finance::chat))
        .route(
            "/api/admin/assistant/status",
            get(assistant::status),
        )
        .route("/api/admin/assistant", post(assistant::chat))
        .layer(middleware::from_fn(preflight_ok))
        .with_state(state)
}

/// CORS preflight handler. The API Gateway `ANY /{proxy+}` route forwards OPTIONS
/// to the Lambda, so axum would 405 it (handlers declare no OPTIONS) and a browser
/// preflight would fail. Short-circuit every OPTIONS with 204; API Gateway's
/// cors_configuration attaches the Access-Control-* headers to the response.
async fn preflight_ok(req: Request, next: Next) -> Response {
    if req.method() == Method::OPTIONS {
        return StatusCode::NO_CONTENT.into_response();
    }
    next.run(req).await
}

/// Read a single cookie value out of the request `Cookie` header.
pub fn cookie_value(headers: &HeaderMap, name: &str) -> Option<String> {
    let raw = headers.get(http::header::COOKIE)?.to_str().ok()?;
    let prefix = format!("{name}=");
    raw.split(';')
        .map(str::trim)
        .find_map(|part| part.strip_prefix(&prefix).map(|v| v.to_string()))
}

/// A `Set-Cookie` value matching the current backend's auth cookies
/// (HttpOnly, SameSite=None so the cross-origin frontend can send it with
/// `credentials: "include"`; Secure in prod).
pub fn set_cookie(name: &str, value: &str, max_age: i64, secure: bool) -> String {
    let secure = if secure { "; Secure" } else { "" };
    format!("{name}={value}; HttpOnly{secure}; SameSite=None; Path=/; Max-Age={max_age}")
}

pub fn clear_cookie(name: &str, secure: bool) -> String {
    let secure = if secure { "; Secure" } else { "" };
    format!("{name}=; HttpOnly{secure}; SameSite=None; Path=/; Max-Age=0")
}

/// Authenticate a request from its `access_token` cookie: verify the JWT, reject
/// blacklisted (logged-out) tokens, and load the user. Returns the user id (hex)
/// and the full user record. Every protected handler starts with this.
pub async fn authenticate(state: &AppState, headers: &HeaderMap) -> AppResult<(String, User)> {
    let token = cookie_value(headers, "access_token").ok_or(AppError::Unauthorized)?;
    let claims =
        verify_token(&state.config.jwt_secret, &token).map_err(|_| AppError::Unauthorized)?;

    let blacklisted = state
        .db
        .collection::<Document>("token_blacklist")
        .find_one(doc! { "token": token.as_str() })
        .await?
        .is_some();
    if blacklisted {
        return Err(AppError::Unauthorized);
    }

    let oid = ObjectId::parse_str(&claims.sub).map_err(|_| AppError::Unauthorized)?;
    let user = state
        .db
        .collection::<User>("users")
        .find_one(doc! { "_id": oid })
        .await?
        .ok_or(AppError::Unauthorized)?;
    Ok((claims.sub, user))
}

/// Authenticate + require the `admin` role (matches get_current_admin). Roles are
/// read from the `roles` array if present, else the single `role` field.
pub async fn authenticate_admin(state: &AppState, headers: &HeaderMap) -> AppResult<(String, User)> {
    let (id, user) = authenticate(state, headers).await?;
    if !user.effective_roles().iter().any(|r| r == "admin") {
        return Err(AppError::Forbidden("Admin access required".to_string()));
    }
    Ok((id, user))
}

/// Authenticate + require the `counselor` OR `admin` role (get_current_counselor).
pub async fn authenticate_counselor(
    state: &AppState,
    headers: &HeaderMap,
) -> AppResult<(String, User)> {
    let (id, user) = authenticate(state, headers).await?;
    if !user
        .effective_roles()
        .iter()
        .any(|r| r == "counselor" || r == "admin")
    {
        return Err(AppError::Forbidden("Counselor access required".to_string()));
    }
    Ok((id, user))
}

/// Load a member that is assigned to `counselor_oid`, else 404. Mirrors the
/// repeated `{_id, assigned_counselor_id}` guard.
pub async fn assigned_member(
    state: &AppState,
    member_id: &str,
    counselor_oid: ObjectId,
) -> AppResult<Document> {
    let moid = ObjectId::parse_str(member_id).map_err(|_| AppError::NotFound)?;
    state
        .db
        .collection::<Document>("users")
        .find_one(doc! { "_id": moid, "assigned_counselor_id": counselor_oid })
        .await?
        .ok_or(AppError::NotFound)
}

/// Best-effort audit-log write (mirrors log_audit_event -> db.audit_log). Never
/// fails the request.
pub async fn log_audit(
    state: &AppState,
    action: &str,
    entity_type: &str,
    entity_id: Option<&str>,
    user_email: Option<&str>,
) {
    let _ = state
        .db
        .collection::<Document>("audit_log")
        .insert_one(doc! {
            "action": action,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "user_email": user_email,
            "details": {},
            "timestamp": bson::DateTime::now(),
        })
        .await;
}

/// Serialize a BSON datetime as an ISO-8601 string (or JSON null), matching the
/// Python backend's `.isoformat()`.
pub fn iso(dt: Option<bson::DateTime>) -> Value {
    match dt.and_then(|d| d.try_to_rfc3339_string().ok()) {
        Some(s) => Value::String(s),
        None => Value::Null,
    }
}

// ── BSON Document -> JSON field accessors (null/absent-safe) ──────────────────
/// `_id` as a 24-char hex string.
pub fn hex_id(d: &Document) -> String {
    d.get_object_id("_id").map(|o| o.to_hex()).unwrap_or_default()
}
/// A named ObjectId field as hex, or None.
pub fn hex_field(d: &Document, k: &str) -> Option<String> {
    d.get_object_id(k).ok().map(|o| o.to_hex())
}
/// String field -> JSON string, else null.
pub fn dstr(d: &Document, k: &str) -> Value {
    match d.get_str(k) {
        Ok(v) => Value::String(v.to_string()),
        Err(_) => Value::Null,
    }
}
/// String field -> JSON string with a default when missing.
pub fn dstr_or(d: &Document, k: &str, default: &str) -> Value {
    Value::String(d.get_str(k).unwrap_or(default).to_string())
}
/// Bool field -> JSON bool (default false).
pub fn dbool(d: &Document, k: &str) -> Value {
    Value::Bool(d.get_bool(k).unwrap_or(false))
}
/// Datetime field -> ISO-8601 string or null.
pub fn ddate(d: &Document, k: &str) -> Value {
    iso(d.get_datetime(k).ok().copied())
}
/// Integer-ish field -> i64 (default 0), accepting Int32/Int64/Double.
pub fn dint(d: &Document, k: &str) -> i64 {
    match d.get(k) {
        Some(bson::Bson::Int32(i)) => *i as i64,
        Some(bson::Bson::Int64(i)) => *i,
        Some(bson::Bson::Double(f)) => *f as i64,
        _ => 0,
    }
}
/// Recursively convert a BSON value to plain JSON, matching the Python
/// `_sanitize`: ObjectId -> hex string, datetime -> ISO-8601 string, and
/// documents/arrays recursed. Avoids the `{"$oid"}` / `{"$date"}` wrappers that
/// relaxed extended-JSON would produce.
pub fn sanitize(b: bson::Bson) -> Value {
    use bson::Bson;
    match b {
        Bson::ObjectId(o) => Value::String(o.to_hex()),
        Bson::DateTime(d) => d.try_to_rfc3339_string().map(Value::String).unwrap_or(Value::Null),
        Bson::Document(doc) => {
            Value::Object(doc.into_iter().map(|(k, v)| (k, sanitize(v))).collect())
        }
        Bson::Array(arr) => Value::Array(arr.into_iter().map(sanitize).collect()),
        Bson::String(s) => Value::String(s),
        Bson::Boolean(x) => Value::Bool(x),
        Bson::Int32(i) => Value::from(i),
        Bson::Int64(i) => Value::from(i),
        Bson::Double(f) => Value::from(f),
        Bson::Null => Value::Null,
        other => other.into_relaxed_extjson(),
    }
}

/// "first_name last_name" (trimmed).
pub fn full_name(d: &Document) -> String {
    format!(
        "{} {}",
        d.get_str("first_name").unwrap_or(""),
        d.get_str("last_name").unwrap_or("")
    )
    .trim()
    .to_string()
}
/// Raw passthrough of any field as relaxed-JSON (ints stay numbers, etc.); null if absent.
pub fn draw(d: &Document, k: &str) -> Value {
    d.get(k)
        .cloned()
        .map(|b| b.into_relaxed_extjson())
        .unwrap_or(Value::Null)
}

// ── request-body (raw JSON) helpers, matching Python's `await request.json()` ─
/// A JSON body field as BSON for storage (Null if absent); numbers stay numeric.
pub fn body_bson(body: &Value, k: &str) -> bson::Bson {
    match body.get(k) {
        Some(v) => bson::to_bson(v).unwrap_or(bson::Bson::Null),
        None => bson::Bson::Null,
    }
}
/// A JSON body field as &str with a default.
pub fn body_str<'a>(body: &'a Value, k: &str, default: &'a str) -> &'a str {
    body.get(k).and_then(|v| v.as_str()).unwrap_or(default)
}
/// Parse an ISO-8601 string value -> BSON datetime; None if absent/blank/unparseable.
pub fn parse_iso(v: Option<&Value>) -> Option<bson::DateTime> {
    let s = v.and_then(|x| x.as_str())?.trim();
    if s.is_empty() {
        return None;
    }
    let s = s.replace('Z', "+00:00");
    if let Ok(dt) = bson::DateTime::parse_rfc3339_str(&s) {
        return Some(dt);
    }
    bson::DateTime::parse_rfc3339_str(format!("{s}T00:00:00+00:00")).ok()
}
/// parse_iso but defaults to now() when absent/unparseable.
pub fn parse_iso_or_now(v: Option<&Value>) -> bson::DateTime {
    parse_iso(v).unwrap_or_else(bson::DateTime::now)
}

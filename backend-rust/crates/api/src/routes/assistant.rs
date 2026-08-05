//! `/api/admin/assistant/*` -- the admin-facing operations assistant.
//!
//! DORMANT BY DEFAULT. The chat endpoint returns "not available" unless the
//! ADMIN_ASSISTANT_ENABLED env flag is "true" AND an Anthropic API key is
//! configured (env for dev, Secrets Manager for prod). Reuses the same
//! Anthropic Messages API contract as major_finance.rs. Admin-gated.
//!
//! This is a thin relay, deliberately holding no write power of its own:
//!  - Tier 1 (advisor): drafts member messages / announcements / knowledge.
//!  - Tier 2 (operator): the console may attach a CONTEXT block (analytics, a
//!    member record, the pipeline) which is injected into the prompt so the
//!    assistant can answer operational questions from real data.
//!  - Tier 3 (actions): the model PROPOSES a write as a machine-readable
//!    `sh-action` block; the console renders it as a confirm button and calls
//!    the existing /api/admin/* endpoint on click. The backend never writes.

use axum::extract::State;
use axum::http::HeaderMap;
use axum::Json;
use bson::{doc, Document};
use serde::Deserialize;
use serde_json::{json, Value};

use sh_core::{AppError, AppResult};

use super::{authenticate_admin, hex_id, log_audit};
use crate::state::AppState;

const ADMIN_SYSTEM: &str = "You are the Silent Honor Assistant, an operations copilot for the ADMIN staff of Silent Honor Foundation, a veterans nonprofit. You help administrators run the platform efficiently. Your audience is trusted staff, not members.\n\
\n\
You help with three things:\n\
1. DRAFTING — write member messages, program announcements, and knowledge-base articles in the foundation's warm, plain-spoken, veteran-respecting voice. Return the draft clearly so the admin can copy or insert it.\n\
2. ANSWERING WITH DATA — you have read-only tools to look up live data yourself: `program_stats` (member counts + pipeline breakdown), `search_members` (filter by name/branch/stage/dd214_status), and `dd214_queue` (who's awaiting DD-214 review). Call them instead of guessing whenever a question needs current numbers or specific members. The console may also attach a CONTEXT block (analytics or a specific member) — use it too. Never invent members, numbers, or records; if a tool returns nothing, say so.\n\
3. PROPOSING ACTIONS — if the admin asks you to DO something that changes data (message a member, move a member's pipeline stage, publish an announcement), do NOT claim you did it. Propose it for the admin to confirm by emitting exactly one fenced code block labeled sh-action containing a single JSON object, followed by a one-line plain summary. The console turns your proposal into a confirm button; nothing happens until the admin clicks it.\n\
\n\
Action block format (at most one per reply, only when a write is actually requested):\n\
```sh-action\n\
{\"type\":\"send_message\",\"member_id\":\"<id>\",\"body\":\"<message text>\",\"label\":\"Send this message to <name>\"}\n\
```\n\
Supported types: \"send_message\" {member_id, body}; \"set_stage\" {member_id, pipeline_type, stage}; \"create_announcement\" {title, content, kind}. Use only ids/values present in the provided context; if you lack the id, ask for it instead of proposing the action.\n\
\n\
Style: concise, professional, warm. Never fabricate data. Never put Social Security numbers, full account numbers, or passwords in a draft. You are handling real people's records — be accurate and careful.";

fn enabled() -> bool {
    std::env::var("ADMIN_ASSISTANT_ENABLED")
        .map(|v| v.trim().eq_ignore_ascii_case("true"))
        .unwrap_or(false)
}

// GET /api/admin/assistant/status
// The console calls this to decide whether to show the Assistant section.
pub async fn status(State(state): State<AppState>, headers: HeaderMap) -> AppResult<Json<Value>> {
    authenticate_admin(&state, &headers).await?;
    Ok(Json(
        json!({ "assistant": "Silent Honor Assistant", "enabled": enabled() }),
    ))
}

#[derive(Debug, Deserialize)]
pub struct ChatTurn {
    pub role: String,
    pub content: String,
}

#[derive(Debug, Deserialize)]
pub struct ChatRequest {
    #[serde(default)]
    pub message: String,
    #[serde(default)]
    pub history: Vec<ChatTurn>,
    /// Optional snapshot the console attaches for data-grounded answers.
    #[serde(default)]
    pub context: Option<Value>,
}

// POST /api/admin/assistant
pub async fn chat(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(body): Json<ChatRequest>,
) -> AppResult<Json<Value>> {
    let (_id, user) = authenticate_admin(&state, &headers).await?;

    if !enabled() {
        return Err(AppError::Forbidden(
            "The assistant is not enabled yet.".to_string(),
        ));
    }

    let message = body.message.trim();
    if message.is_empty() {
        return Err(AppError::BadRequest("Message is required".to_string()));
    }

    // Bedrock model id / inference-profile id (env-driven; no API key needed).
    let model = std::env::var("ADMIN_ASSISTANT_MODEL")
        .or_else(|_| std::env::var("BEDROCK_MODEL_ID"))
        .or_else(|_| std::env::var("MAJOR_FINANCE_MODEL"))
        .unwrap_or_else(|_| "us.anthropic.claude-3-5-sonnet-20241022-v2:0".to_string());

    // Inject the admin-provided context snapshot (if any) into the system prompt.
    let system = match &body.context {
        Some(ctx) if !ctx.is_null() => format!(
            "{ADMIN_SYSTEM}\n\nCURRENT CONTEXT (JSON provided by the console; may be partial; treat as ground truth and do not invent data beyond it):\n{}",
            serde_json::to_string(ctx).unwrap_or_default()
        ),
        _ => ADMIN_SYSTEM.to_string(),
    };

    let mut messages: Vec<Value> = body
        .history
        .iter()
        .filter(|t| t.role == "user" || t.role == "assistant")
        .map(|t| json!({ "role": t.role, "content": t.content }))
        .collect();
    messages.push(json!({ "role": "user", "content": message }));

    // Tool-use loop: the model may call read-only data tools; we execute them and
    // feed results back until it returns a final text answer (bounded rounds).
    let tools = tool_defs();
    let mut convo = messages;
    let mut reply = String::new();
    for _round in 0..4 {
        let data = sh_core::bedrock::invoke_claude_tools(&model, &system, convo.clone(), tools.clone(), 1500)
            .await
            .map_err(AppError::Internal)?;
        let stop = data.get("stop_reason").and_then(|s| s.as_str()).unwrap_or("");
        let content = data
            .get("content")
            .and_then(|c| c.as_array())
            .cloned()
            .unwrap_or_default();

        if stop == "tool_use" {
            // Record the assistant's tool-call turn, then run each tool.
            convo.push(json!({ "role": "assistant", "content": content.clone() }));
            let mut results: Vec<Value> = Vec::new();
            for block in &content {
                if block.get("type").and_then(|t| t.as_str()) == Some("tool_use") {
                    let tname = block.get("name").and_then(|n| n.as_str()).unwrap_or("");
                    let tid = block.get("id").and_then(|i| i.as_str()).unwrap_or("");
                    let tinput = block.get("input").cloned().unwrap_or_else(|| json!({}));
                    let result = run_tool(&state, tname, &tinput).await;
                    results.push(json!({ "type": "tool_result", "tool_use_id": tid, "content": result }));
                }
            }
            convo.push(json!({ "role": "user", "content": results }));
            continue;
        }

        reply = content
            .iter()
            .find(|b| b.get("type").and_then(|t| t.as_str()) == Some("text"))
            .and_then(|b| b.get("text"))
            .and_then(|t| t.as_str())
            .unwrap_or("")
            .to_string();
        break;
    }
    if reply.is_empty() {
        reply = "Sorry, I couldn't complete that request.".to_string();
    }

    log_audit(
        &state,
        "assistant_query",
        "assistant",
        None,
        Some(&user.email),
    )
    .await;

    Ok(Json(json!({ "reply": reply })))
}

/// Read-only tools the assistant may call to look up live data. Strictly
/// read-only — writes always go through the Tier-3 propose/confirm flow.
fn tool_defs() -> Value {
    json!([
        {
            "name": "program_stats",
            "description": "Member counts: total, verified, DD-214 pending, and a breakdown by pipeline stage. Use for 'how many' / distribution / program-health questions.",
            "input_schema": { "type": "object", "properties": {} }
        },
        {
            "name": "search_members",
            "description": "Search members. All filters optional: query (name/email substring), branch, stage (pipeline_stage), dd214_status, limit (default 15, max 50). Returns id, name, email, branch, pipeline_stage, dd214_status, verified.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": { "type": "string" },
                    "branch": { "type": "string" },
                    "stage": { "type": "string" },
                    "dd214_status": { "type": "string" },
                    "limit": { "type": "integer" }
                }
            }
        },
        {
            "name": "dd214_queue",
            "description": "List members whose DD-214 is awaiting review (dd214_status = pending_review).",
            "input_schema": { "type": "object", "properties": {} }
        }
    ])
}

/// Execute a read-only tool and return its result as a JSON string.
async fn run_tool(state: &AppState, name: &str, input: &Value) -> String {
    let users = state.db.collection::<Document>("users");
    let full_name = |d: &Document| -> String {
        format!(
            "{} {}",
            d.get_str("first_name").unwrap_or(""),
            d.get_str("last_name").unwrap_or("")
        )
        .trim()
        .to_string()
    };

    match name {
        "program_stats" => {
            let total = users.count_documents(doc! { "role": "member" }).await.unwrap_or(0);
            let verified = users
                .count_documents(doc! { "role": "member", "verified": true })
                .await
                .unwrap_or(0);
            let pending_dd214 = users
                .count_documents(doc! { "role": "member", "dd214_status": "pending_review" })
                .await
                .unwrap_or(0);
            let mut by_stage = serde_json::Map::new();
            for s in [
                "applied", "dd214_pending", "dd214_review", "approved", "active", "inactive",
                "graduated",
            ] {
                let c = users
                    .count_documents(doc! { "role": "member", "pipeline_stage": s })
                    .await
                    .unwrap_or(0);
                by_stage.insert(s.to_string(), json!(c));
            }
            json!({ "total_members": total, "verified": verified, "pending_dd214": pending_dd214, "by_stage": by_stage }).to_string()
        }
        "search_members" => {
            let mut q = doc! { "role": "member" };
            for key in ["branch", "dd214_status"] {
                if let Some(v) = input.get(key).and_then(|v| v.as_str()) {
                    if !v.is_empty() {
                        q.insert(key, v.to_string());
                    }
                }
            }
            if let Some(v) = input.get("stage").and_then(|v| v.as_str()) {
                if !v.is_empty() {
                    q.insert("pipeline_stage", v.to_string());
                }
            }
            let limit = input.get("limit").and_then(|v| v.as_i64()).unwrap_or(15).clamp(1, 50);
            let text = input.get("query").and_then(|v| v.as_str()).unwrap_or("").to_lowercase();

            let mut cursor = match users.find(q).sort(doc! { "created_at": -1 }).limit(200).await {
                Ok(c) => c,
                Err(e) => return json!({ "error": e.to_string() }).to_string(),
            };
            let mut out: Vec<Value> = Vec::new();
            while cursor.advance().await.unwrap_or(false) {
                let d = match cursor.deserialize_current() {
                    Ok(d) => d,
                    Err(_) => continue,
                };
                if !text.is_empty() {
                    let hay = format!(
                        "{} {}",
                        full_name(&d),
                        d.get_str("email").unwrap_or("")
                    )
                    .to_lowercase();
                    if !hay.contains(&text) {
                        continue;
                    }
                }
                out.push(json!({
                    "id": hex_id(&d),
                    "name": full_name(&d),
                    "email": d.get_str("email").unwrap_or(""),
                    "branch": d.get_str("branch").unwrap_or(""),
                    "pipeline_stage": d.get_str("pipeline_stage").unwrap_or("applied"),
                    "dd214_status": d.get_str("dd214_status").unwrap_or("pending"),
                    "verified": d.get_bool("verified").unwrap_or(false),
                }));
                if out.len() as i64 >= limit {
                    break;
                }
            }
            json!({ "members": out, "count": out.len() }).to_string()
        }
        "dd214_queue" => {
            let mut cursor = match users
                .find(doc! { "role": "member", "dd214_status": "pending_review" })
                .limit(50)
                .await
            {
                Ok(c) => c,
                Err(e) => return json!({ "error": e.to_string() }).to_string(),
            };
            let mut out: Vec<Value> = Vec::new();
            while cursor.advance().await.unwrap_or(false) {
                let d = match cursor.deserialize_current() {
                    Ok(d) => d,
                    Err(_) => continue,
                };
                out.push(json!({
                    "id": hex_id(&d),
                    "name": full_name(&d),
                    "branch": d.get_str("branch").unwrap_or(""),
                }));
            }
            json!({ "pending_dd214": out, "count": out.len() }).to_string()
        }
        _ => json!({ "error": format!("unknown tool: {name}") }).to_string(),
    }
}

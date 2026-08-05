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
use serde::Deserialize;
use serde_json::{json, Value};

use sh_core::{AppError, AppResult};

use super::{authenticate_admin, log_audit};
use crate::state::AppState;

const ADMIN_SYSTEM: &str = "You are the Silent Honor Assistant, an operations copilot for the ADMIN staff of Silent Honor Foundation, a veterans nonprofit. You help administrators run the platform efficiently. Your audience is trusted staff, not members.\n\
\n\
You help with three things:\n\
1. DRAFTING — write member messages, program announcements, and knowledge-base articles in the foundation's warm, plain-spoken, veteran-respecting voice. Return the draft clearly so the admin can copy or insert it.\n\
2. ANSWERING WITH DATA — when the console provides a CONTEXT block (JSON of analytics, the pipeline, or a specific member), use ONLY that data to answer operational questions (e.g. how many members await DD-214 review, how the pipeline is distributed, a summary of a member's case). If the data you need is not in the context, say what you'd need rather than guessing. Never invent members, numbers, or records.\n\
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

    let api_key = resolve_anthropic_key().await.map_err(AppError::Internal)?;
    let model = std::env::var("ADMIN_ASSISTANT_MODEL")
        .or_else(|_| std::env::var("MAJOR_FINANCE_MODEL"))
        .unwrap_or_else(|_| "claude-opus-5".to_string());

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

    let payload = json!({
        "model": model,
        "max_tokens": 1500,
        "system": system,
        "messages": messages,
    });

    let resp = reqwest::Client::new()
        .post("https://api.anthropic.com/v1/messages")
        .header("x-api-key", api_key)
        .header("anthropic-version", "2023-06-01")
        .header("content-type", "application/json")
        .json(&payload)
        .send()
        .await
        .map_err(|e| AppError::Internal(anyhow::anyhow!("Anthropic request failed: {e}")))?;

    if !resp.status().is_success() {
        let code = resp.status();
        let detail = resp.text().await.unwrap_or_default();
        tracing::error!("Anthropic API error {code}: {detail}");
        return Err(AppError::Internal(anyhow::anyhow!(
            "Anthropic API error {code}"
        )));
    }

    let data: Value = resp
        .json()
        .await
        .map_err(|e| AppError::Internal(anyhow::anyhow!("Anthropic response parse failed: {e}")))?;

    let reply = data
        .get("content")
        .and_then(|c| c.as_array())
        .and_then(|blocks| {
            blocks
                .iter()
                .find(|b| b.get("type").and_then(|t| t.as_str()) == Some("text"))
        })
        .and_then(|b| b.get("text"))
        .and_then(|t| t.as_str())
        .unwrap_or("Sorry, I couldn't answer that right now.")
        .to_string();

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

/// Anthropic API key: direct env for local dev, else the Secrets Manager name
/// set by Terraform. Never hard-coded.
async fn resolve_anthropic_key() -> anyhow::Result<String> {
    if let Ok(k) = std::env::var("ANTHROPIC_API_KEY") {
        if !k.is_empty() {
            return Ok(k);
        }
    }
    if let Ok(name) = std::env::var("ANTHROPIC_API_KEY_SECRET_NAME") {
        if !name.is_empty() {
            return sh_core::secrets::get_secret(&name).await;
        }
    }
    anyhow::bail!("The assistant is enabled but no Anthropic API key is configured")
}

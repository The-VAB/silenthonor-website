//! `/api/member/major-finance/*` -- the member-facing AI assistant.
//!
//! DORMANT BY DEFAULT. The chat endpoint returns "not available" unless the
//! MAJOR_FINANCE_ENABLED env flag is "true" AND an Anthropic API key is
//! configured (env for dev, Secrets Manager for prod). The status endpoint
//! reports that flag so the frontend hides the tab until it is on. Do not flip
//! the flag until the conditions in docs/MAJOR_FINANCE.md are met.
//!
//! Rust has no official Anthropic SDK, so this calls the Messages API over raw
//! HTTPS (reqwest) -- the documented cURL contract. No secret is in code: the
//! API key comes from env (dev) or Secrets Manager via the Lambda IAM role.

use axum::extract::State;
use axum::http::HeaderMap;
use axum::Json;
use serde::Deserialize;
use serde_json::{json, Value};

use sh_core::{AppError, AppResult};

use super::authenticate;
use crate::state::AppState;

/// Major Finance guardrails: general education only, defer specifics to the
/// counselor, never a promise about a member's credit, never collect secrets.
const MF_SYSTEM: &str = "You are Major Finance, a friendly financial educator for Silent Honor Foundation, a veterans nonprofit. \
You give general financial education only. You never give personalized financial, legal, or tax advice, and you never make a promise or prediction about a specific member's credit score or outcome. \
Keep answers short, warm, and plain-spoken; the audience is veterans and their families, so avoid jargon. \
For anything specific to the member's own situation (their accounts, their disputes, their plan), tell them to message their counselor, who has their full picture. \
Never ask for or repeat Social Security numbers, full account numbers, or passwords. \
If a question is outside personal finance, credit, budgeting, saving, or debt, gently steer back or suggest they contact the foundation.";

fn enabled() -> bool {
    std::env::var("MAJOR_FINANCE_ENABLED")
        .map(|v| v.trim().eq_ignore_ascii_case("true"))
        .unwrap_or(false)
}

// GET /api/member/major-finance/status
// The frontend calls this to decide whether to show the Major Finance tab.
pub async fn status(State(state): State<AppState>, headers: HeaderMap) -> AppResult<Json<Value>> {
    authenticate(&state, &headers).await?;
    Ok(Json(json!({ "assistant": "Major Finance", "enabled": enabled() })))
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
}

// POST /api/member/major-finance
pub async fn chat(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(body): Json<ChatRequest>,
) -> AppResult<Json<Value>> {
    authenticate(&state, &headers).await?;

    if !enabled() {
        return Err(AppError::Forbidden(
            "Major Finance is not available yet.".to_string(),
        ));
    }

    let message = body.message.trim();
    if message.is_empty() {
        return Err(AppError::BadRequest("Message is required".to_string()));
    }

    let api_key = resolve_anthropic_key().await.map_err(AppError::Internal)?;
    let model =
        std::env::var("MAJOR_FINANCE_MODEL").unwrap_or_else(|_| "claude-opus-5".to_string());

    // Rebuild the conversation for the Messages API (only user/assistant turns).
    let mut messages: Vec<Value> = body
        .history
        .iter()
        .filter(|t| t.role == "user" || t.role == "assistant")
        .map(|t| json!({ "role": t.role, "content": t.content }))
        .collect();
    messages.push(json!({ "role": "user", "content": message }));

    let payload = json!({
        "model": model,
        "max_tokens": 1024,
        "system": MF_SYSTEM,
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

    // Refusals come back as stop_reason "refusal" -- give a safe fallback line.
    if data.get("stop_reason").and_then(|s| s.as_str()) == Some("refusal") {
        return Ok(Json(json!({
            "reply": "I can't help with that one. For anything about your own situation, message your counselor -- they have the full picture."
        })));
    }

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
        .unwrap_or("Sorry, I couldn't answer that right now. Please message your counselor.")
        .to_string();

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
    anyhow::bail!("Major Finance is enabled but no Anthropic API key is configured");
}

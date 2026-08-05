//! Amazon Bedrock (Claude) access.
//!
//! No API key: the Lambda's IAM role authenticates (needs `bedrock:InvokeModel`).
//! We use the InvokeModel API with Claude's native (Anthropic Messages) request
//! body, so the request/response shape is identical to calling Anthropic directly
//! — only the transport and auth change. The model id (a Bedrock foundation-model
//! id or cross-region inference-profile id) is supplied by the caller from env.

use anyhow::{Context, Result};
use aws_sdk_bedrockruntime::primitives::Blob;
use aws_sdk_bedrockruntime::Client;
use once_cell::sync::OnceCell;
use serde_json::{json, Value};

static CLIENT: OnceCell<Client> = OnceCell::new();

async fn client() -> &'static Client {
    if let Some(c) = CLIENT.get() {
        return c;
    }
    let cfg = aws_config::load_defaults(aws_config::BehaviorVersion::latest()).await;
    let _ = CLIENT.set(Client::new(&cfg));
    CLIENT.get().expect("bedrock client initialized")
}

/// Invoke a Claude model on Bedrock with the Anthropic Messages format.
/// `messages` is a list of `{ "role": ..., "content": ... }` values. Returns the
/// parsed model response body (same shape as the Anthropic Messages API).
pub async fn invoke_claude(
    model_id: &str,
    system: &str,
    messages: Vec<Value>,
    max_tokens: u32,
) -> Result<Value> {
    let payload = json!({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "system": system,
        "messages": messages,
    });
    let bytes = serde_json::to_vec(&payload).context("serialize Bedrock request")?;

    let out = client()
        .await
        .invoke_model()
        .model_id(model_id)
        .content_type("application/json")
        .accept("application/json")
        .body(Blob::new(bytes))
        .send()
        .await
        .with_context(|| format!("Bedrock InvokeModel ({model_id})"))?;

    serde_json::from_slice(out.body().as_ref()).context("parse Bedrock response body")
}

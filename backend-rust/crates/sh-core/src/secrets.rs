//! AWS Secrets Manager access.
//!
//! No secret value is ever compiled into this binary. At cold start the Lambda's
//! IAM role is used to fetch named secrets (the names come from environment
//! variables set by Terraform -- see infra/aws/lambda-api.tf). Fetched values are
//! cached for the life of the warm container.

use anyhow::{Context, Result};
use aws_sdk_secretsmanager::Client;
use once_cell::sync::OnceCell;
use std::collections::HashMap;
use std::sync::Mutex;

static CLIENT: OnceCell<Client> = OnceCell::new();
static CACHE: OnceCell<Mutex<HashMap<String, String>>> = OnceCell::new();

async fn client() -> &'static Client {
    if let Some(c) = CLIENT.get() {
        return c;
    }
    let cfg = aws_config::load_defaults(aws_config::BehaviorVersion::latest()).await;
    let client = Client::new(&cfg);
    // Ignore the race: whoever wins, we return the stored client.
    let _ = CLIENT.set(client);
    CLIENT.get().expect("secrets client initialized")
}

/// Fetch a secret string by name/ARN, caching it for the warm container.
pub async fn get_secret(name: &str) -> Result<String> {
    let cache = CACHE.get_or_init(|| Mutex::new(HashMap::new()));
    if let Some(v) = cache.lock().expect("secrets cache lock").get(name) {
        return Ok(v.clone());
    }

    let out = client()
        .await
        .get_secret_value()
        .secret_id(name)
        .send()
        .await
        .with_context(|| format!("GetSecretValue for {name}"))?;

    let value = out
        .secret_string()
        .context("secret has no string value")?
        .to_string();

    cache
        .lock()
        .expect("secrets cache lock")
        .insert(name.to_string(), value.clone());
    Ok(value)
}

//! Silent Honor API -- single binary that runs as an AWS Lambda (behind API
//! Gateway HTTP API) in production, or as a plain axum server locally.
//!
//! Startup (cold start): load config (secrets from Secrets Manager) -> connect to
//! DocumentDB -> build the router. The DB handle and config are reused across warm
//! invocations via `AppState`.

mod routes;
mod state;

use std::sync::Arc;

use lambda_http::{run, Error};
use sh_core::{db, Config};

use crate::state::AppState;

#[tokio::main]
async fn main() -> Result<(), Error> {
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| tracing_subscriber::EnvFilter::new("info")),
        )
        .without_time()
        .init();

    let config = Config::load()
        .await
        .map_err(|e| Error::from(format!("config load failed: {e}")))?;
    let database = db::connect(&config.mongodb_uri, &config.db_name)
        .await
        .map_err(|e| Error::from(format!("db connect failed: {e}")))?;

    let state = AppState {
        db: database,
        config: Arc::new(config),
    };
    let app = routes::router(state);

    if std::env::var("AWS_LAMBDA_RUNTIME_API").is_ok() {
        // Inside Lambda: bridge API Gateway events to the axum app.
        run(app).await
    } else {
        // Local development server.
        let addr = std::env::var("BIND_ADDR").unwrap_or_else(|_| "0.0.0.0:8000".to_string());
        tracing::info!("local dev server listening on http://{addr}");
        let listener = tokio::net::TcpListener::bind(&addr).await?;
        axum::serve(listener, app).await?;
        Ok(())
    }
}

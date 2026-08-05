//! Liveness / readiness probes. `/health` is a bare liveness check; `/api/health`
//! additionally pings the database.

use axum::extract::State;
use axum::Json;
use serde_json::{json, Value};

use crate::state::AppState;

pub async fn health(State(state): State<AppState>) -> Json<Value> {
    // Best-effort DB ping; never fail the probe hard, just report status.
    let db_ok = state.db.run_command(bson::doc! { "ping": 1 }).await.is_ok();
    Json(json!({
        "status": "ok",
        "service": "silenthonor-rust-api",
        "db": if db_ok { "up" } else { "down" },
    }))
}

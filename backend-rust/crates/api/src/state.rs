//! Shared, cheaply-clonable state handed to every route handler.

use std::sync::Arc;

use mongodb::Database;
use sh_core::Config;

#[derive(Clone)]
pub struct AppState {
    pub db: Database,
    pub config: Arc<Config>,
}

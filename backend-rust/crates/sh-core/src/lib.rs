//! Shared library for the Silent Honor Rust/Lambda backend.
//!
//! Everything cross-cutting -- config, secrets, DB access, domain models, auth,
//! and the HTTP error type -- lives here so each route handler in the `api`
//! crate stays small.

pub mod auth;
pub mod config;
pub mod db;
pub mod error;
pub mod models;
pub mod secrets;

pub use config::Config;
pub use error::{AppError, AppResult};

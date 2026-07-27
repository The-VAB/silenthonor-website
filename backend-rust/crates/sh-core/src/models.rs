//! Domain models. Field names and the `_id` handling mirror the documents the
//! existing Python backend already writes to DocumentDB, so both services read
//! the same data during the migration.

use serde::{Deserialize, Serialize};
use serde_json::{json, Value};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct User {
    #[serde(rename = "_id", skip_serializing_if = "Option::is_none")]
    pub id: Option<bson::oid::ObjectId>,
    pub email: String,
    #[serde(default)]
    pub password_hash: String,
    #[serde(default)]
    pub first_name: Option<String>,
    #[serde(default)]
    pub last_name: Option<String>,
    #[serde(default)]
    pub role: Option<String>,
    #[serde(default)]
    pub roles: Option<Vec<String>>,
    #[serde(default)]
    pub verified: bool,
    /// The Python backend historically wrote both `active` and `is_active`;
    /// login treats `is_active == false` as deactivated.
    #[serde(default)]
    pub is_active: Option<bool>,
    #[serde(default)]
    pub active: Option<bool>,
    #[serde(default)]
    pub pipeline_stage: Option<String>,
    #[serde(default)]
    pub dd214_status: Option<String>,
    #[serde(default)]
    pub dd214_file: Option<String>,
    #[serde(default)]
    pub branch: Option<String>,
    #[serde(default)]
    pub service_status: Option<String>,
    #[serde(default)]
    pub created_at: Option<bson::DateTime>,
}

impl User {
    /// Effective role list: explicit `roles`, else `[role]`, else `["member"]`.
    pub fn effective_roles(&self) -> Vec<String> {
        if let Some(r) = &self.roles {
            if !r.is_empty() {
                return r.clone();
            }
        }
        vec![self.role.clone().unwrap_or_else(|| "member".to_string())]
    }

    pub fn is_deactivated(&self) -> bool {
        self.is_active == Some(false) || self.active == Some(false)
    }

    /// Public profile returned by `/api/auth/login` and `/api/auth/me`.
    /// Never includes `password_hash`. Shape matches what the frontend reads.
    pub fn to_profile(&self, id: &str) -> Value {
        let role = self.role.clone().unwrap_or_else(|| "member".to_string());
        json!({
            "id": id,
            "_id": id,
            "email": self.email,
            "first_name": self.first_name.clone().unwrap_or_default(),
            "last_name": self.last_name.clone().unwrap_or_default(),
            "role": role,
            "roles": self.effective_roles(),
            "verified": self.verified,
            "pipeline_stage": self.pipeline_stage.clone().unwrap_or_else(|| "applied".to_string()),
            "dd214_status": self.dd214_status,
            "dd214_file": self.dd214_file,
            "branch": self.branch,
            "service_status": self.service_status,
            // Epoch milliseconds -- `new Date(ms)` on the frontend handles this
            // exactly like the previous ISO string, and timestamp_millis() is a
            // core bson::DateTime method (no version risk).
            "created_at": self.created_at.map(|d| d.timestamp_millis()),
        })
    }
}

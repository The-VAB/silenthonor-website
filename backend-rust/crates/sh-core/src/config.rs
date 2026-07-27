//! Runtime configuration.
//!
//! Resolution order for each secret value:
//!   1. A direct environment variable (used for LOCAL DEV only, e.g. `JWT_SECRET`).
//!   2. Otherwise the name in the `*_SECRET_NAME` env var is looked up in AWS
//!      Secrets Manager (production -- see infra/aws/lambda-api.tf).
//!
//! This keeps real secrets out of both the code and the Lambda's plaintext env.

use anyhow::{bail, Result};

#[derive(Clone)]
pub struct Config {
    pub jwt_secret: String,
    pub mongodb_uri: String,
    pub db_name: String,
    /// `Secure` flag on auth cookies. True in prod (HTTPS); set COOKIE_SECURE=false
    /// for plain-HTTP local dev.
    pub cookie_secure: bool,
}

impl Config {
    pub async fn load() -> Result<Self> {
        let jwt_secret = resolve("JWT_SECRET", "JWT_SECRET_NAME").await?;
        let mut mongodb_uri = resolve("MONGODB_URI", "MONGODB_URI_SECRET_NAME").await?;

        // The DocumentDB URI stored in Secrets Manager was written for App Runner
        // (`tlsCAFile=/app/rds-global-bundle.pem`). In Lambda the CA bundle ships
        // inside the package at a different path, so DOCDB_CA_PATH (set by
        // Terraform) rewrites the `tlsCAFile` value without duplicating the secret.
        if let Ok(ca) = std::env::var("DOCDB_CA_PATH") {
            if !ca.is_empty() {
                mongodb_uri = override_ca_file(&mongodb_uri, &ca);
            }
        }
        let db_name = std::env::var("MONGODB_DB")
            .or_else(|_| std::env::var("DB_NAME"))
            .unwrap_or_else(|_| "silenthonor".to_string());
        let cookie_secure = std::env::var("COOKIE_SECURE")
            .map(|v| v.to_lowercase() != "false")
            .unwrap_or(true);

        Ok(Self {
            jwt_secret,
            mongodb_uri,
            db_name,
            cookie_secure,
        })
    }
}

async fn resolve(direct_env: &str, secret_name_env: &str) -> Result<String> {
    if let Ok(v) = std::env::var(direct_env) {
        if !v.is_empty() {
            return Ok(v);
        }
    }
    if let Ok(name) = std::env::var(secret_name_env) {
        if !name.is_empty() {
            return crate::secrets::get_secret(&name).await;
        }
    }
    bail!("missing config: set {direct_env} (dev) or {secret_name_env} (prod)");
}

/// Replace the `tlsCAFile=...` value in a Mongo connection string (or append it
/// if absent), leaving every other option untouched.
fn override_ca_file(uri: &str, ca_path: &str) -> String {
    const KEY: &str = "tlsCAFile=";
    if let Some(start) = uri.find(KEY) {
        let val_start = start + KEY.len();
        let rel_end = uri[val_start..].find('&');
        let end = rel_end.map(|i| val_start + i).unwrap_or(uri.len());
        format!("{}{}{}{}", &uri[..start], KEY, ca_path, &uri[end..])
    } else {
        let sep = if uri.contains('?') { '&' } else { '?' };
        format!("{uri}{sep}{KEY}{ca_path}")
    }
}

#[cfg(test)]
mod tests {
    use super::override_ca_file;

    #[test]
    fn rewrites_existing_ca_file_in_the_middle() {
        let uri = "mongodb://u:p@host:27017/?tls=true&tlsCAFile=/app/rds.pem&replicaSet=rs0";
        let out = override_ca_file(uri, "/var/task/global-bundle.pem");
        assert_eq!(
            out,
            "mongodb://u:p@host:27017/?tls=true&tlsCAFile=/var/task/global-bundle.pem&replicaSet=rs0"
        );
    }

    #[test]
    fn rewrites_existing_ca_file_at_end() {
        let uri = "mongodb://host/?tls=true&tlsCAFile=/app/rds.pem";
        let out = override_ca_file(uri, "/tmp/ca.pem");
        assert_eq!(out, "mongodb://host/?tls=true&tlsCAFile=/tmp/ca.pem");
    }

    #[test]
    fn appends_when_absent() {
        assert_eq!(
            override_ca_file("mongodb://host/?tls=true", "/tmp/ca.pem"),
            "mongodb://host/?tls=true&tlsCAFile=/tmp/ca.pem"
        );
        assert_eq!(
            override_ca_file("mongodb://host/", "/tmp/ca.pem"),
            "mongodb://host/?tlsCAFile=/tmp/ca.pem"
        );
    }
}

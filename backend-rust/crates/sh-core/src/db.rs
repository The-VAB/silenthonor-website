//! MongoDB / Amazon DocumentDB connection.
//!
//! The `mongodb` driver reads TLS options straight from the connection string,
//! including `tls=true` and `tlsCAFile=...`. The DocumentDB URI stored in Secrets
//! Manager already carries those parameters; the CA bundle
//! (`global-bundle.pem`) must exist at the path the URI points to inside the
//! Lambda package (see docs/RUST_BACKEND.md -> "TLS / CA bundle").
//!
//! The returned `Database` handle holds an internal connection pool and is cheap
//! to clone, so it is created once per cold start and reused across warm
//! invocations via the shared `AppState`.

use anyhow::{Context, Result};
use mongodb::{Client, Database};

pub async fn connect(uri: &str, db_name: &str) -> Result<Database> {
    let client = Client::with_uri_str(uri)
        .await
        .context("connecting to MongoDB/DocumentDB")?;
    Ok(client.database(db_name))
}

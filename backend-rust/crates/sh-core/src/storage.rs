//! DD-214 / document storage on S3 -- port of utils/storage.py's S3 path.
//!
//! Objects live under the `dd214/` prefix in the private uploads bucket (env
//! `S3_BUCKET`), encrypted with SSE-KMS when `S3_KMS_KEY_ID` is set (else SSE-S3),
//! matching the Python backend. Reads are handed out as short-lived presigned
//! GET URLs. Requires s3:PutObject/GetObject on the bucket + kms perms on the key
//! (see infra/aws/lambda-api.tf).

use std::time::Duration;

use anyhow::{anyhow, Result};
use aws_config::BehaviorVersion;
use aws_sdk_s3::presigning::PresigningConfig;
use aws_sdk_s3::primitives::ByteStream;
use aws_sdk_s3::types::ServerSideEncryption;
use aws_sdk_s3::Client;

pub const DD214_PREFIX: &str = "dd214/";

fn bucket() -> Result<String> {
    std::env::var("S3_BUCKET")
        .ok()
        .filter(|s| !s.is_empty())
        .ok_or_else(|| anyhow!("S3_BUCKET not configured"))
}

async fn client() -> Client {
    let cfg = aws_config::defaults(BehaviorVersion::latest()).load().await;
    Client::new(&cfg)
}

/// Put an object with server-side encryption (SSE-KMS if S3_KMS_KEY_ID is set,
/// else SSE-S3 AES256). `key` should already include the `dd214/` prefix.
pub async fn put_object(key: &str, body: Vec<u8>) -> Result<()> {
    let bucket = bucket()?;
    let mut req = client()
        .await
        .put_object()
        .bucket(bucket)
        .key(key)
        .body(ByteStream::from(body));

    match std::env::var("S3_KMS_KEY_ID") {
        Ok(kms) if !kms.is_empty() => {
            req = req
                .server_side_encryption(ServerSideEncryption::AwsKms)
                .ssekms_key_id(kms);
        }
        _ => {
            req = req.server_side_encryption(ServerSideEncryption::Aes256);
        }
    }
    req.send().await?;
    Ok(())
}

/// Presigned GET URL for an object (default 1h), matching get_dd214_url.
pub async fn presign_get(key: &str, expires_secs: u64) -> Result<String> {
    let bucket = bucket()?;
    let presigned = client()
        .await
        .get_object()
        .bucket(bucket)
        .key(key)
        .presigned(PresigningConfig::expires_in(Duration::from_secs(expires_secs))?)
        .await?;
    Ok(presigned.uri().to_string())
}

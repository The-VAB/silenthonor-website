//! JWT + password primitives. Deliberately identical in shape to the current
//! Python implementation (HS256, claims `sub`/`email`/`exp`/`type`, bcrypt) so
//! tokens and password hashes are interchangeable between the two services
//! during the migration.

use anyhow::Result;
use jsonwebtoken::{decode, encode, Algorithm, DecodingKey, EncodingKey, Header, Validation};
use serde::{Deserialize, Serialize};
use time::{Duration, OffsetDateTime};

const ACCESS_TTL_MINUTES: i64 = 60;
const REFRESH_TTL_DAYS: i64 = 30;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Claims {
    pub sub: String,
    #[serde(default)]
    pub email: String,
    pub exp: usize,
    #[serde(rename = "type", default)]
    pub token_type: String,
}

pub fn create_access_token(secret: &str, user_id: &str, email: &str) -> Result<String> {
    let exp = (OffsetDateTime::now_utc() + Duration::minutes(ACCESS_TTL_MINUTES)).unix_timestamp();
    let claims = Claims {
        sub: user_id.to_string(),
        email: email.to_string(),
        exp: exp as usize,
        token_type: "access".to_string(),
    };
    Ok(encode(
        &Header::new(Algorithm::HS256),
        &claims,
        &EncodingKey::from_secret(secret.as_bytes()),
    )?)
}

pub fn create_refresh_token(secret: &str, user_id: &str) -> Result<String> {
    let exp = (OffsetDateTime::now_utc() + Duration::days(REFRESH_TTL_DAYS)).unix_timestamp();
    let claims = Claims {
        sub: user_id.to_string(),
        email: String::new(),
        exp: exp as usize,
        token_type: "refresh".to_string(),
    };
    Ok(encode(
        &Header::new(Algorithm::HS256),
        &claims,
        &EncodingKey::from_secret(secret.as_bytes()),
    )?)
}

/// Verify a token's signature and expiry, returning its claims.
pub fn verify_token(secret: &str, token: &str) -> Result<Claims> {
    let data = decode::<Claims>(
        token,
        &DecodingKey::from_secret(secret.as_bytes()),
        &Validation::new(Algorithm::HS256),
    )?;
    Ok(data.claims)
}

pub fn hash_password(plain: &str) -> Result<String> {
    Ok(bcrypt::hash(plain, bcrypt::DEFAULT_COST)?)
}

pub fn verify_password(plain: &str, hashed: &str) -> bool {
    bcrypt::verify(plain, hashed).unwrap_or(false)
}

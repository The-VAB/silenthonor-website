# File storage utilities for Silent Honor Foundation
#
# Backend priority: Amazon S3 (preferred) → local disk (fallback).
# All public functions keep the same signatures/return shapes so routers are unchanged.
# The stored ``storage_type`` ("s3" | "local") selects the read/delete path later.
import os
import uuid
import asyncio
from middleware.logging_middleware import logger

# ── Amazon S3 configuration ─────────────────────────────────────────────────
# When S3_BUCKET is set the app stores DD-214 files and member documents in a
# single private bucket, under the "dd214/" and "documents/" prefixes.
# Server-side encryption is enforced by the bucket policy; if S3_KMS_KEY_ID is
# provided we request SSE-KMS explicitly, otherwise the bucket default applies.
S3_BUCKET = os.environ.get("S3_BUCKET", "")
S3_KMS_KEY_ID = os.environ.get("S3_KMS_KEY_ID", "")
S3_REGION = os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "us-east-1"))
S3_ENABLED = bool(S3_BUCKET)
S3_DD214_PREFIX = "dd214/"
S3_DOCS_PREFIX = "documents/"

_s3_client = None

def _get_s3():
    """Lazily build a boto3 S3 client. Credentials come from the App Runner
    instance role (or standard AWS env/credential chain)."""
    global _s3_client
    if _s3_client is None:
        import boto3
        _s3_client = boto3.client("s3", region_name=S3_REGION)
    return _s3_client

def _s3_put(key: str, content: bytes) -> None:
    """Synchronous S3 put with server-side encryption. Runs in a worker thread."""
    extra = {}
    if S3_KMS_KEY_ID:
        extra["ServerSideEncryption"] = "aws:kms"
        extra["SSEKMSKeyId"] = S3_KMS_KEY_ID
    else:
        extra["ServerSideEncryption"] = "AES256"
    _get_s3().put_object(Bucket=S3_BUCKET, Key=key, Body=content, **extra)

def _s3_presign(key: str, expires_in: int = 3600) -> str:
    return _get_s3().generate_presigned_url(
        "get_object",
        Params={"Bucket": S3_BUCKET, "Key": key},
        ExpiresIn=expires_in,
    )

def _s3_delete(key: str) -> None:
    _get_s3().delete_object(Bucket=S3_BUCKET, Key=key)

# Local fallback directories
LOCAL_STORAGE_PATH = "/app/uploads/dd214"
LOCAL_DOCS_PATH = "/app/uploads/documents"

# DD-214 local encryption — set DD214_ENCRYPTION_KEY env var to a Fernet key to enable.
# Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
DD214_ENCRYPTION_KEY = os.environ.get("DD214_ENCRYPTION_KEY", "")

def _get_fernet():
    if not DD214_ENCRYPTION_KEY:
        return None
    try:
        from cryptography.fernet import Fernet
        key = DD214_ENCRYPTION_KEY.encode() if isinstance(DD214_ENCRYPTION_KEY, str) else DD214_ENCRYPTION_KEY
        return Fernet(key)
    except Exception as e:
        logger.error(f"Invalid DD214_ENCRYPTION_KEY: {e}")
        return None

def encrypt_dd214(data: bytes) -> bytes:
    f = _get_fernet()
    return f.encrypt(data) if f else data

def decrypt_dd214(data: bytes) -> bytes:
    f = _get_fernet()
    return f.decrypt(data) if f else data

# ── DD-214 storage ──────────────────────────────────────────────────────────

async def upload_dd214(file_content: bytes, original_filename: str, user_id: str) -> dict:
    """
    Upload a DD-214 file to Amazon S3 (encrypted at rest), falling back to local
    disk if S3 is not configured.

    Returns dict with:
    - success: bool
    - filename: str (generated filename)
    - storage_type: "s3" | "local"
    - url: str (download URL, if available)
    - error: str (if failed)
    """
    ext = original_filename.split(".")[-1] if "." in original_filename else "pdf"
    filename = f"{user_id}_{uuid.uuid4()}.{ext}"

    # Prefer S3 when configured (encrypted at rest via SSE-KMS/SSE-S3)
    if S3_ENABLED:
        try:
            await asyncio.to_thread(_s3_put, S3_DD214_PREFIX + filename, file_content)
            logger.info(f"DD-214 uploaded to S3: {S3_DD214_PREFIX}{filename}")
            return {
                "success": True,
                "filename": filename,
                "storage_type": "s3",
                "url": await asyncio.to_thread(_s3_presign, S3_DD214_PREFIX + filename),
            }
        except Exception as e:
            logger.error(f"S3 DD-214 upload error: {e}, falling back to local")

    return await upload_to_local(file_content, filename)

async def upload_to_local(file_content: bytes, filename: str) -> dict:
    """Upload file to local storage, encrypting with AES-256 if DD214_ENCRYPTION_KEY is set."""
    try:
        os.makedirs(LOCAL_STORAGE_PATH, exist_ok=True)
        fernet = _get_fernet()
        if fernet:
            file_content = fernet.encrypt(file_content)
            filename = filename + ".enc"
        filepath = os.path.join(LOCAL_STORAGE_PATH, filename)

        with open(filepath, "wb") as f:
            f.write(file_content)

        logger.info(f"DD-214 saved to local storage: {filename}")
        return {
            "success": True,
            "filename": filename,
            "storage_type": "local",
            "url": f"/uploads/dd214/{filename}"
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

async def delete_dd214(filename: str, storage_type: str = "local") -> bool:
    """Delete DD-214 file from storage"""
    if storage_type == "s3":
        try:
            await asyncio.to_thread(_s3_delete, S3_DD214_PREFIX + filename)
            return True
        except Exception as e:
            logger.error(f"Error deleting DD-214 from S3: {e}")
            return False
    return await delete_from_local(filename)

async def delete_from_local(filename: str) -> bool:
    """Delete file from local storage"""
    try:
        filepath = os.path.join(LOCAL_STORAGE_PATH, filename)
        if os.path.exists(filepath):
            os.remove(filepath)
            return True
        return False
    except Exception as e:
        logger.error(f"Error deleting local file: {e}")
        return False

async def get_dd214_url(filename: str, storage_type: str = "local") -> str:
    """Get URL for accessing DD-214 file"""
    if storage_type == "s3":
        try:
            return await asyncio.to_thread(_s3_presign, S3_DD214_PREFIX + filename)
        except Exception as e:
            logger.error(f"Error presigning DD-214 S3 URL: {e}")
            return ""
    return f"/uploads/dd214/{filename}"

# ── Generic document storage (non-DD-214) ──────────────────────────────────

async def upload_document(file_content: bytes, original_filename: str, member_id: str) -> dict:
    """
    Upload a counselor-uploaded member document to S3 (documents/ prefix),
    falling back to local /app/uploads/documents/.
    Returns dict: success, storage_key, storage_type, error.
    """
    ext = original_filename.rsplit(".", 1)[-1].lower() if "." in original_filename else "pdf"
    storage_key = f"documents/{member_id}_{uuid.uuid4()}.{ext}"

    # Prefer S3 when configured
    if S3_ENABLED:
        try:
            await asyncio.to_thread(_s3_put, storage_key, file_content)
            logger.info(f"Document uploaded to S3: {storage_key}")
            return {"success": True, "storage_key": storage_key, "storage_type": "s3"}
        except Exception as e:
            logger.error(f"S3 document upload error: {e}, falling back to local")

    # Local fallback
    try:
        os.makedirs(LOCAL_DOCS_PATH, exist_ok=True)
        local_filename = storage_key.replace("documents/", "")
        filepath = os.path.join(LOCAL_DOCS_PATH, local_filename)
        with open(filepath, "wb") as f:
            f.write(file_content)
        logger.info(f"Document saved to local storage: {local_filename}")
        return {"success": True, "storage_key": storage_key, "storage_type": "local"}
    except Exception as e:
        return {"success": False, "error": str(e)}

async def get_document_url(storage_key: str, storage_type: str) -> str:
    """Get a download URL for a counselor-uploaded document."""
    if storage_type == "s3":
        try:
            return await asyncio.to_thread(_s3_presign, storage_key)
        except Exception as e:
            logger.error(f"Error presigning document S3 URL: {e}")
            return ""
    # storage_key is "documents/filename.ext", local path strips the prefix
    local_filename = storage_key.replace("documents/", "")
    return f"/uploads/documents/{local_filename}"

async def delete_document(storage_key: str, storage_type: str) -> bool:
    """Delete a counselor-uploaded document from storage."""
    if storage_type == "s3":
        try:
            await asyncio.to_thread(_s3_delete, storage_key)
            return True
        except Exception as e:
            logger.error(f"Error deleting document from S3: {e}")
            return False
    local_filename = storage_key.replace("documents/", "")
    filepath = os.path.join(LOCAL_DOCS_PATH, local_filename)
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
        return True
    except Exception as e:
        logger.error(f"Error deleting document: {e}")
        return False

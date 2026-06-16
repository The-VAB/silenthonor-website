# Supabase Storage utilities for Silent Honor Foundation
import os
import uuid
import httpx
from datetime import datetime, timezone
from middleware.logging_middleware import logger

# Supabase configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
SUPABASE_BUCKET = os.environ.get("SUPABASE_BUCKET", "dd214")

# Local fallback directories
LOCAL_STORAGE_PATH = "/app/uploads/dd214"
LOCAL_DOCS_PATH = "/app/uploads/documents"

def get_storage_headers():
    """Get headers for Supabase Storage API"""
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
    }

async def upload_dd214(file_content: bytes, original_filename: str, user_id: str) -> dict:
    """
    Upload DD-214 file to Supabase Storage.
    Falls back to local storage if Supabase is not configured.

    Returns dict with:
    - success: bool
    - filename: str (generated filename)
    - storage_type: "supabase" | "local"
    - url: str (download URL, if available)
    - error: str (if failed)
    """
    # Generate unique filename
    ext = original_filename.split(".")[-1] if "." in original_filename else "pdf"
    filename = f"{user_id}_{uuid.uuid4()}.{ext}"

    # Try Supabase first if configured
    if SUPABASE_URL and SUPABASE_KEY:
        try:
            result = await upload_to_supabase(file_content, filename)
            if result["success"]:
                return result
            else:
                logger.warning(f"Supabase upload failed: {result.get('error')}, falling back to local")
        except Exception as e:
            logger.error(f"Supabase upload error: {e}, falling back to local")

    # Fall back to local storage
    return await upload_to_local(file_content, filename)

async def upload_to_supabase(file_content: bytes, filename: str) -> dict:
    """Upload file to Supabase Storage"""
    if not SUPABASE_URL or not SUPABASE_KEY:
        return {"success": False, "error": "Supabase not configured"}

    upload_url = f"{SUPABASE_URL}/storage/v1/object/{SUPABASE_BUCKET}/{filename}"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                upload_url,
                headers={
                    **get_storage_headers(),
                    "Content-Type": "application/octet-stream",
                },
                content=file_content
            )

            if response.status_code in [200, 201]:
                # Generate signed URL for download
                signed_url = await get_signed_url(filename)
                return {
                    "success": True,
                    "filename": filename,
                    "storage_type": "supabase",
                    "url": signed_url
                }
            else:
                return {
                    "success": False,
                    "error": f"Supabase returned {response.status_code}: {response.text}"
                }
    except Exception as e:
        return {"success": False, "error": str(e)}

async def upload_to_local(file_content: bytes, filename: str) -> dict:
    """Upload file to local storage"""
    try:
        os.makedirs(LOCAL_STORAGE_PATH, exist_ok=True)
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

async def get_signed_url(filename: str, expires_in: int = 3600) -> str:
    """Get a signed URL for downloading a file from Supabase"""
    if not SUPABASE_URL or not SUPABASE_KEY:
        return ""

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{SUPABASE_URL}/storage/v1/object/sign/{SUPABASE_BUCKET}/{filename}",
                headers=get_storage_headers(),
                json={"expiresIn": expires_in}
            )

            if response.status_code == 200:
                data = response.json()
                return f"{SUPABASE_URL}/storage/v1{data.get('signedURL', '')}"
            else:
                logger.error(f"Failed to get signed URL: {response.text}")
                return ""
    except Exception as e:
        logger.error(f"Error getting signed URL: {e}")
        return ""

async def delete_dd214(filename: str, storage_type: str = "local") -> bool:
    """Delete DD-214 file from storage"""
    if storage_type == "supabase":
        return await delete_from_supabase(filename)
    else:
        return await delete_from_local(filename)

async def delete_from_supabase(filename: str) -> bool:
    """Delete file from Supabase Storage"""
    if not SUPABASE_URL or not SUPABASE_KEY:
        return False

    try:
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"{SUPABASE_URL}/storage/v1/object/{SUPABASE_BUCKET}/{filename}",
                headers=get_storage_headers()
            )
            return response.status_code in [200, 204]
    except Exception as e:
        logger.error(f"Error deleting from Supabase: {e}")
        return False

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
    if storage_type == "supabase":
        return await get_signed_url(filename)
    else:
        return f"/uploads/dd214/{filename}"

# ── Generic document storage (non-DD-214) ──────────────────────────────────

async def upload_document(file_content: bytes, original_filename: str, member_id: str) -> dict:
    """
    Upload a counselor-uploaded member document.
    Stored under documents/ prefix in Supabase, or local /app/uploads/documents/.
    Returns dict: success, storage_key, storage_type, error.
    """
    ext = original_filename.rsplit(".", 1)[-1].lower() if "." in original_filename else "pdf"
    storage_key = f"documents/{member_id}_{uuid.uuid4()}.{ext}"

    if SUPABASE_URL and SUPABASE_KEY:
        try:
            result = await upload_to_supabase(file_content, storage_key)
            if result["success"]:
                return {"success": True, "storage_key": storage_key, "storage_type": "supabase"}
            logger.warning(f"Supabase document upload failed: {result.get('error')}, falling back to local")
        except Exception as e:
            logger.error(f"Supabase document upload error: {e}, falling back to local")

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
    if storage_type == "supabase":
        return await get_signed_url(storage_key)
    else:
        # storage_key is "documents/filename.ext", local path strips the prefix
        local_filename = storage_key.replace("documents/", "")
        return f"/uploads/documents/{local_filename}"

async def delete_document(storage_key: str, storage_type: str) -> bool:
    """Delete a counselor-uploaded document from storage."""
    if storage_type == "supabase":
        return await delete_from_supabase(storage_key)
    else:
        local_filename = storage_key.replace("documents/", "")
        filepath = os.path.join(LOCAL_DOCS_PATH, local_filename)
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
            return True
        except Exception as e:
            logger.error(f"Error deleting document: {e}")
            return False

async def migrate_to_supabase(filename: str) -> dict:
    """
    Migrate a local DD-214 file to Supabase.
    Returns the new storage info.
    """
    if not SUPABASE_URL or not SUPABASE_KEY:
        return {"success": False, "error": "Supabase not configured"}

    filepath = os.path.join(LOCAL_STORAGE_PATH, filename)
    if not os.path.exists(filepath):
        return {"success": False, "error": "Local file not found"}

    try:
        with open(filepath, "rb") as f:
            file_content = f.read()

        result = await upload_to_supabase(file_content, filename)

        if result["success"]:
            # Optionally delete local file after successful migration
            # await delete_from_local(filename)
            logger.info(f"Migrated {filename} to Supabase")

        return result
    except Exception as e:
        return {"success": False, "error": str(e)}

async def check_supabase_connection() -> bool:
    """Check if Supabase Storage is properly configured and accessible"""
    if not SUPABASE_URL or not SUPABASE_KEY:
        return False

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{SUPABASE_URL}/storage/v1/bucket",
                headers=get_storage_headers()
            )
            return response.status_code == 200
    except:
        return False

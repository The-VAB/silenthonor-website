# Logging middleware for Silent Honor Foundation
import logging
from datetime import datetime, timezone
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
import time

# Configure logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("silenthonor")

# Database reference
db = None

def set_db(database):
    global db
    db = database

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()

        # Process request
        response = await call_next(request)

        # Calculate duration
        duration = time.time() - start_time

        # Log request
        logger.info(
            f"{request.method} {request.url.path} - {response.status_code} - {duration:.3f}s"
        )

        return response

async def log_audit_event(
    action: str,
    entity_type: str,
    entity_id: str = None,
    user_id: str = None,
    user_email: str = None,
    details: dict = None,
    ip_address: str = None
):
    """Log an audit event to the database"""
    if db is None:
        logger.warning("Audit logging skipped - database not initialized")
        return

    audit_doc = {
        "action": action,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "user_id": user_id,
        "user_email": user_email,
        "details": details or {},
        "ip_address": ip_address,
        "timestamp": datetime.now(timezone.utc)
    }

    try:
        await db.audit_log.insert_one(audit_doc)
    except Exception as e:
        logger.error(f"Failed to log audit event: {e}")

# Common audit actions
AUDIT_ACTIONS = {
    # Auth
    "USER_REGISTERED": "user_registered",
    "USER_LOGIN": "user_login",
    "USER_LOGOUT": "user_logout",
    "PASSWORD_RESET_REQUESTED": "password_reset_requested",
    "PASSWORD_RESET": "password_reset",
    "PASSWORD_CHANGED": "password_changed",

    # Members
    "MEMBER_CREATED": "member_created",
    "MEMBER_UPDATED": "member_updated",
    "MEMBER_VERIFIED": "member_verified",
    "MEMBER_STAGE_CHANGED": "member_stage_changed",
    "DD214_UPLOADED": "dd214_uploaded",
    "DD214_REVIEWED": "dd214_reviewed",

    # Counselor
    "COUNSELOR_CREATED": "counselor_created",
    "COUNSELOR_ASSIGNED": "counselor_assigned",
    "COUNSELOR_UNASSIGNED": "counselor_unassigned",

    # Courses
    "COURSE_CREATED": "course_created",
    "COURSE_UPDATED": "course_updated",
    "COURSE_DELETED": "course_deleted",
    "LESSON_COMPLETED": "lesson_completed",

    # Disputes
    "DISPUTE_CREATED": "dispute_created",
    "DISPUTE_UPDATED": "dispute_updated",
    "DISPUTE_DELETED": "dispute_deleted",

    # Admin
    "ADMIN_ACTION": "admin_action",
    "STAFF_CREATED": "staff_created",
    "STAFF_UPDATED": "staff_updated",
}

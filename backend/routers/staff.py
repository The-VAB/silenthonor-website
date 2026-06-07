# Staff management router for Silent Honor Foundation
import asyncio
import secrets
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request
from bson import ObjectId

from middleware.auth_middleware import get_current_admin
from middleware.logging_middleware import log_audit_event, AUDIT_ACTIONS
from utils.auth import hash_password
from utils.validators import StaffRequest
from utils.email import send_staff_welcome_email

router = APIRouter(prefix="/api/admin/staff", tags=["Staff"])

# Database reference
db = None

def set_db(database):
    global db
    db = database

def generate_temp_password():
    return secrets.token_urlsafe(12)

@router.get("")
async def get_staff(request: Request):
    await get_current_admin(request)
    staff = await db.users.find({"role": {"$in": ["staff", "admin", "counselor"]}}).to_list(100)
    result = []
    for s in staff:
        client_count = 0
        if s.get("role") == "counselor":
            client_count = await db.users.count_documents({"assigned_counselor_id": s["_id"]})
        result.append({
            "id": str(s["_id"]),
            "email": s.get("email"),
            "first_name": s.get("first_name", ""),
            "last_name": s.get("last_name", ""),
            "role": s.get("role"),
            "title": s.get("title", ""),
            "bio": s.get("bio", ""),
            "specialties": s.get("specialties", []),
            "permissions": s.get("permissions", []),
            "active": s.get("active", True),
            "client_count": client_count,
            "created_at": s.get("created_at").isoformat() if s.get("created_at") else None,
            "last_active": s.get("last_active").isoformat() if s.get("last_active") else None
        })
    return result

@router.get("/counselors")
async def get_counselors(request: Request):
    await get_current_admin(request)
    counselors = await db.users.find({"role": "counselor", "active": True}).to_list(100)
    result = []
    for c in counselors:
        client_count = await db.users.count_documents({"assigned_counselor_id": c["_id"]})
        result.append({
            "id": str(c["_id"]),
            "name": f"{c.get(chr(39)+"first_name"+chr(39), chr(39)+chr(39))} {c.get(chr(39)+"last_name"+chr(39), chr(39)+chr(39))}".strip(),
            "email": c.get("email"),
            "specialties": c.get("specialties", []),
            "client_count": client_count
        })
    return result

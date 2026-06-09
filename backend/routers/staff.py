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

STAFF_ROLES = ["staff", "admin", "counselor"]

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
            "name": f"{s.get('first_name', '')} {s.get('last_name', '')}".strip(),
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

@router.post("")
async def create_staff(request: Request, data: StaffRequest):
    admin = await get_current_admin(request)

    if data.role not in STAFF_ROLES:
        raise HTTPException(status_code=400, detail=f"Role must be one of: {STAFF_ROLES}")

    existing = await db.users.find_one({"email": data.email.lower()})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    temp_password = generate_temp_password()

    user_doc = {
        "email": data.email.lower(),
        "password_hash": hash_password(temp_password),
        "first_name": data.first_name,
        "last_name": data.last_name,
        "role": data.role,
        "title": data.title or "",
        "permissions": data.permissions or [],
        "active": True,
        "created_at": datetime.now(timezone.utc)
    }

    result = await db.users.insert_one(user_doc)
    user_id = str(result.inserted_id)

    await log_audit_event(
        action=AUDIT_ACTIONS.get("STAFF_CREATED", "STAFF_CREATED"),
        entity_type="user",
        entity_id=user_id,
        user_email=admin.get("email"),
        details={"role": data.role, "new_staff_email": data.email}
    )

    asyncio.create_task(send_staff_welcome_email(data.email, data.first_name, data.role, temp_password))

    return {
        "id": user_id,
        "email": data.email,
        "first_name": data.first_name,
        "last_name": data.last_name,
        "name": f"{data.first_name} {data.last_name}".strip(),
        "role": data.role,
        "active": True,
        "created_at": datetime.now(timezone.utc).isoformat()
    }

@router.put("/{staff_id}")
async def update_staff(request: Request, staff_id: str):
    admin = await get_current_admin(request)
    data = await request.json()

    allowed = ["first_name", "last_name", "email", "role", "title", "active"]
    update_data = {k: v for k, v in data.items() if k in allowed}

    if "role" in update_data and update_data["role"] not in STAFF_ROLES:
        raise HTTPException(status_code=400, detail=f"Role must be one of: {STAFF_ROLES}")

    if not update_data:
        raise HTTPException(status_code=400, detail="No valid fields to update")

    update_data["updated_at"] = datetime.now(timezone.utc)

    result = await db.users.update_one(
        {"_id": ObjectId(staff_id), "role": {"$in": STAFF_ROLES}},
        {"$set": update_data}
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Staff member not found")

    await log_audit_event(
        action=AUDIT_ACTIONS.get("STAFF_UPDATED", "STAFF_UPDATED"),
        entity_type="user",
        entity_id=staff_id,
        user_email=admin.get("email"),
        details=update_data
    )

    return {"message": "Staff member updated"}

@router.get("/counselors")
async def get_counselors(request: Request):
    await get_current_admin(request)
    counselors = await db.users.find({"role": "counselor", "active": True}).to_list(100)
    result = []
    for c in counselors:
        client_count = await db.users.count_documents({"assigned_counselor_id": c["_id"]})
        result.append({
            "id": str(c["_id"]),
            "name": f"{c.get('first_name', '')} {c.get('last_name', '')}".strip(),
            "email": c.get("email"),
            "specialties": c.get("specialties", []),
            "client_count": client_count
        })
    return result

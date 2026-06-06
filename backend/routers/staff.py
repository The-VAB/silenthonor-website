# Staff management router for Silent Honor Foundation
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request
from bson import ObjectId

from middleware.auth_middleware import get_current_admin
from middleware.logging_middleware import log_audit_event, AUDIT_ACTIONS
from utils.auth import hash_password
from utils.validators import StaffRequest

router = APIRouter(prefix="/api/admin/staff", tags=["Staff"])

# Database reference
db = None

def set_db(database):
    global db
    db = database

@router.get("")
async def get_staff(request: Request):
    """Get all staff members"""
    await get_current_admin(request)

    staff = await db.users.find({"role": {"$in": ["staff", "admin"]}}).to_list(100)
    return [{
        "id": str(s["_id"]),
        "email": s.get("email"),
        "first_name": s.get("first_name", ""),
        "last_name": s.get("last_name", ""),
        "role": s.get("role"),
        "title": s.get("title", ""),
        "permissions": s.get("permissions", []),
        "active": s.get("active", True),
        "created_at": s.get("created_at").isoformat() if s.get("created_at") else None
    } for s in staff]

@router.post("")
async def create_staff(request: Request):
    """Create new staff member"""
    admin = await get_current_admin(request)
    data = await request.json()

    email = data.get("email", "").lower()
    if not email:
        raise HTTPException(status_code=400, detail="Email required")

    existing = await db.users.find_one({"email": email})
    if existing:
        # Upgrade existing user to staff
        await db.users.update_one(
            {"_id": existing["_id"]},
            {"$set": {
                "role": data.get("role", "staff"),
                "title": data.get("title", ""),
                "permissions": data.get("permissions", []),
                "active": True
            }}
        )

        await log_audit_event(
            action=AUDIT_ACTIONS["STAFF_CREATED"],
            entity_type="user",
            entity_id=str(existing["_id"]),
            user_id=admin["_id"],
            user_email=admin.get("email"),
            details={"upgraded_from_existing": True},
            ip_address=request.client.host if request.client else None
        )

        return {"id": str(existing["_id"]), "message": "User upgraded to staff"}

    staff_doc = {
        "email": email,
        "password_hash": hash_password(data.get("password", "TempPass123!")),
        "first_name": data.get("first_name", ""),
        "last_name": data.get("last_name", ""),
        "role": data.get("role", "staff"),
        "title": data.get("title", ""),
        "permissions": data.get("permissions", []),
        "active": True,
        "verified": True,
        "created_at": datetime.now(timezone.utc)
    }

    result = await db.users.insert_one(staff_doc)

    await log_audit_event(
        action=AUDIT_ACTIONS["STAFF_CREATED"],
        entity_type="user",
        entity_id=str(result.inserted_id),
        user_id=admin["_id"],
        user_email=admin.get("email"),
        ip_address=request.client.host if request.client else None
    )

    return {"id": str(result.inserted_id), "message": "Staff member created"}

@router.get("/{staff_id}")
async def get_staff_member(request: Request, staff_id: str):
    """Get single staff member"""
    await get_current_admin(request)

    staff = await db.users.find_one({"_id": ObjectId(staff_id), "role": {"$in": ["staff", "admin"]}})
    if not staff:
        raise HTTPException(status_code=404, detail="Staff member not found")

    staff["_id"] = str(staff["_id"])
    staff.pop("password_hash", None)
    return staff

@router.put("/{staff_id}")
async def update_staff(request: Request, staff_id: str):
    """Update staff member"""
    admin = await get_current_admin(request)
    data = await request.json()

    # Don't allow changing own admin status
    if staff_id == admin["_id"] and data.get("role") and data.get("role") != "admin":
        raise HTTPException(status_code=400, detail="Cannot change your own admin status")

    update_fields = {}
    for field in ["first_name", "last_name", "title", "permissions", "active"]:
        if field in data:
            update_fields[field] = data[field]

    # Only allow role changes for non-self updates
    if "role" in data and staff_id != admin["_id"]:
        update_fields["role"] = data["role"]

    if update_fields:
        await db.users.update_one(
            {"_id": ObjectId(staff_id)},
            {"$set": update_fields}
        )

    await log_audit_event(
        action=AUDIT_ACTIONS["STAFF_UPDATED"],
        entity_type="user",
        entity_id=staff_id,
        user_id=admin["_id"],
        user_email=admin.get("email"),
        details={"fields_updated": list(update_fields.keys())},
        ip_address=request.client.host if request.client else None
    )

    return {"message": "Staff member updated"}

@router.delete("/{staff_id}")
async def delete_staff(request: Request, staff_id: str):
    """Deactivate staff member"""
    admin = await get_current_admin(request)

    # Don't allow deleting self
    if staff_id == admin["_id"]:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")

    # Don't delete, just deactivate
    await db.users.update_one(
        {"_id": ObjectId(staff_id)},
        {"$set": {"active": False}}
    )

    return {"message": "Staff member deactivated"}

@router.post("/{staff_id}/reset-password")
async def reset_staff_password(request: Request, staff_id: str):
    """Reset staff member's password (admin only)"""
    admin = await get_current_admin(request)
    data = await request.json()

    new_password = data.get("password", "TempPass123!")

    await db.users.update_one(
        {"_id": ObjectId(staff_id)},
        {"$set": {"password_hash": hash_password(new_password)}}
    )

    await log_audit_event(
        action=AUDIT_ACTIONS["PASSWORD_RESET"],
        entity_type="user",
        entity_id=staff_id,
        user_id=admin["_id"],
        user_email=admin.get("email"),
        details={"admin_initiated": True},
        ip_address=request.client.host if request.client else None
    )

    return {"message": "Password reset successfully"}

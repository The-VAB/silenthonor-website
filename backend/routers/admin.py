# Admin router for Silent Honor Foundation
import os
import asyncio
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from bson import ObjectId

from middleware.auth_middleware import get_current_admin
from middleware.logging_middleware import log_audit_event, AUDIT_ACTIONS
from utils.auth import hash_password
from utils.email import send_dd214_approved_email, send_admin_notification
from utils.storage import get_dd214_url

router = APIRouter(prefix="/api/admin", tags=["Admin"])

# Database reference
db = None

def set_db(database):
    global db
    db = database

# Pipeline stages
PIPELINE_STAGES = [
    "applied",
    "dd214_pending",
    "dd214_review",
    "approved",
    "counselor_assigned",
    "intake_complete",
    "active",
    "graduated",
    "inactive"
]

@router.get("/stats")
async def get_admin_stats(request: Request):
    """Get admin dashboard statistics"""
    await get_current_admin(request)

    total_members = await db.users.count_documents({"role": "member"})
    verified_members = await db.users.count_documents({"role": "member", "verified": True})
    pending_verification = await db.users.count_documents({"role": "member", "dd214_status": "pending_review"})
    total_contacts = await db.contacts.count_documents({})
    total_courses = await db.courses.count_documents({})
    total_counselors = await db.users.count_documents({"role": "counselor"})
    total_staff = await db.users.count_documents({"role": "staff"})

    # Pipeline stats
    pipeline_stats = {}
    for stage in PIPELINE_STAGES:
        pipeline_stats[stage] = await db.users.count_documents({"role": "member", "pipeline_stage": stage})

    return {
        "total_members": total_members,
        "verified_members": verified_members,
        "pending_verification": pending_verification,
        "total_contacts": total_contacts,
        "total_courses": total_courses,
        "total_counselors": total_counselors,
        "total_staff": total_staff,
        "pipeline": pipeline_stats
    }

@router.get("/pipeline")
async def get_pipeline_view(request: Request):
    """Get members organized by pipeline stage"""
    await get_current_admin(request)

    pipeline = {}
    for stage in PIPELINE_STAGES:
        members = await db.users.find(
            {"role": "member", "pipeline_stage": stage},
            {"_id": 1, "email": 1, "first_name": 1, "last_name": 1, "branch": 1,
             "dd214_status": 1, "created_at": 1, "assigned_counselor_id": 1}
        ).sort("created_at", -1).to_list(100)

        pipeline[stage] = [{
            "id": str(m["_id"]),
            "email": m["email"],
            "name": f"{m.get('first_name', '')} {m.get('last_name', '')}".strip(),
            "branch": m.get("branch"),
            "dd214_status": m.get("dd214_status"),
            "created_at": m.get("created_at").isoformat() if m.get("created_at") else None,
            "has_counselor": bool(m.get("assigned_counselor_id"))
        } for m in members]

    return pipeline

@router.put("/members/{member_id}/stage")
async def update_member_stage(request: Request, member_id: str):
    """Update member's pipeline stage"""
    admin = await get_current_admin(request)
    data = await request.json()

    new_stage = data.get("stage")
    if new_stage not in PIPELINE_STAGES:
        raise HTTPException(status_code=400, detail=f"Invalid stage. Must be one of: {PIPELINE_STAGES}")

    await db.users.update_one(
        {"_id": ObjectId(member_id)},
        {"$set": {"pipeline_stage": new_stage, "updated_at": datetime.now(timezone.utc)}}
    )

    await log_audit_event(
        action=AUDIT_ACTIONS["MEMBER_STAGE_CHANGED"],
        entity_type="user",
        entity_id=member_id,
        user_id=admin["_id"],
        user_email=admin.get("email"),
        details={"new_stage": new_stage},
        ip_address=request.client.host if request.client else None
    )

    return {"message": f"Member moved to {new_stage}"}

@router.get("/members")
async def get_members(request: Request):
    """Get all members"""
    await get_current_admin(request)

    members = await db.users.find(
        {"role": "member"},
        {"_id": 1, "email": 1, "first_name": 1, "last_name": 1, "branch": 1,
         "service_status": 1, "verified": 1, "dd214_status": 1, "dd214_file": 1,
         "pipeline_stage": 1, "assigned_counselor_id": 1, "created_at": 1}
    ).sort("created_at", -1).to_list(1000)

    result = []
    for m in members:
        result.append({
            "id": str(m["_id"]),
            "email": m["email"],
            "first_name": m.get("first_name", ""),
            "last_name": m.get("last_name", ""),
            "branch": m.get("branch"),
            "service_status": m.get("service_status"),
            "verified": m.get("verified", False),
            "dd214_status": m.get("dd214_status", "pending"),
            "dd214_file": m.get("dd214_file"),
            "pipeline_stage": m.get("pipeline_stage", "applied"),
            "has_counselor": bool(m.get("assigned_counselor_id")),
            "created_at": m.get("created_at").isoformat() if m.get("created_at") else None
        })

    return result

@router.get("/members/{member_id}")
async def get_member(request: Request, member_id: str):
    """Get single member details"""
    await get_current_admin(request)

    member = await db.users.find_one({"_id": ObjectId(member_id)})
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    member["_id"] = str(member["_id"])
    member.pop("password_hash", None)

    # Get assigned counselor info
    if member.get("assigned_counselor_id"):
        counselor = await db.users.find_one({"_id": ObjectId(member["assigned_counselor_id"])})
        if counselor:
            member["counselor"] = {
                "id": str(counselor["_id"]),
                "name": f"{counselor.get('first_name', '')} {counselor.get('last_name', '')}".strip(),
                "email": counselor.get("email")
            }

    return member

@router.get("/dd214/{filename}")
async def get_dd214_file(request: Request, filename: str):
    """Get DD-214 file for review - returns file or redirect to signed URL"""
    await get_current_admin(request)

    # First try local file
    filepath = f"/app/uploads/dd214/{filename}"
    if os.path.exists(filepath):
        return FileResponse(filepath)

    # Try to get Supabase signed URL
    signed_url = await get_dd214_url(filename, "supabase")
    if signed_url:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=signed_url)

    raise HTTPException(status_code=404, detail="File not found")

@router.post("/members/{member_id}/verify")
async def verify_member(request: Request, member_id: str):
    """Verify or reject member's DD-214"""
    admin = await get_current_admin(request)
    data = await request.json()

    status = data.get("status", "verified")
    notes = data.get("notes", "")

    # Get member info before update
    member = await db.users.find_one({"_id": ObjectId(member_id)})
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    update_fields = {
        "verified": status == "verified",
        "dd214_status": status,
        "verified_at": datetime.now(timezone.utc) if status == "verified" else None,
        "verification_notes": notes
    }

    if status == "verified":
        update_fields["pipeline_stage"] = "approved"
    elif status == "rejected":
        update_fields["pipeline_stage"] = "dd214_review"

    await db.users.update_one(
        {"_id": ObjectId(member_id)},
        {"$set": update_fields}
    )

    await log_audit_event(
        action=AUDIT_ACTIONS["DD214_REVIEWED"],
        entity_type="user",
        entity_id=member_id,
        user_id=admin["_id"],
        user_email=admin.get("email"),
        details={"status": status, "notes": notes},
        ip_address=request.client.host if request.client else None
    )

    # Send approval email if verified
    if status == "verified":
        asyncio.create_task(send_dd214_approved_email(
            member.get("email"),
            member.get("first_name", "Member")
        ))

    return {"message": f"Member verification status updated to {status}"}

@router.get("/members/{member_id}/notes")
async def get_member_notes(request: Request, member_id: str):
    """Get intake notes for a member"""
    await get_current_admin(request)
    notes = await db.intake_notes.find({"member_id": ObjectId(member_id)}).sort("created_at", -1).to_list(100)
    return [{
        "id": str(n["_id"]),
        "content": n.get("content", ""),
        "note_type": n.get("note_type", "general"),
        "created_by": n.get("created_by_name", "Admin"),
        "created_at": n.get("created_at").isoformat() if n.get("created_at") else None
    } for n in notes]

@router.post("/members/{member_id}/notes")
async def add_member_note(request: Request, member_id: str):
    """Add intake note for a member"""
    admin = await get_current_admin(request)
    data = await request.json()

    note_doc = {
        "member_id": ObjectId(member_id),
        "content": data.get("content", ""),
        "note_type": data.get("note_type", "general"),
        "created_by": ObjectId(admin["_id"]),
        "created_by_name": f"{admin.get('first_name', '')} {admin.get('last_name', '')}".strip() or "Admin",
        "created_at": datetime.now(timezone.utc)
    }

    result = await db.intake_notes.insert_one(note_doc)
    return {"id": str(result.inserted_id), "message": "Note added"}

@router.delete("/members/{member_id}/notes/{note_id}")
async def delete_member_note(request: Request, member_id: str, note_id: str):
    """Delete intake note"""
    await get_current_admin(request)
    await db.intake_notes.delete_one({"_id": ObjectId(note_id), "member_id": ObjectId(member_id)})
    return {"message": "Note deleted"}

@router.get("/contacts")
async def get_contacts(request: Request):
    """Get all contact form submissions"""
    await get_current_admin(request)

    contacts = await db.contacts.find(
        {},
        {"_id": 1, "first_name": 1, "last_name": 1, "email": 1, "topic": 1,
         "message": 1, "created_at": 1, "responded": 1}
    ).sort("created_at", -1).to_list(500)

    result = []
    for c in contacts:
        result.append({
            "id": str(c["_id"]),
            "first_name": c.get("first_name", ""),
            "last_name": c.get("last_name", ""),
            "email": c["email"],
            "topic": c.get("topic"),
            "message": c.get("message"),
            "created_at": c.get("created_at").isoformat() if c.get("created_at") else None,
            "responded": c.get("responded", False)
        })

    return result

@router.put("/contacts/{contact_id}")
async def update_contact(request: Request, contact_id: str):
    """Mark contact as responded"""
    await get_current_admin(request)
    data = await request.json()

    await db.contacts.update_one(
        {"_id": ObjectId(contact_id)},
        {"$set": {"responded": data.get("responded", True)}}
    )

    return {"message": "Contact updated"}

@router.delete("/contacts/{contact_id}")
async def delete_contact(request: Request, contact_id: str):
    """Delete contact"""
    await get_current_admin(request)
    await db.contacts.delete_one({"_id": ObjectId(contact_id)})
    return {"message": "Contact deleted"}

@router.get("/audit-log")
async def get_audit_log(request: Request):
    """Get audit log entries"""
    await get_current_admin(request)

    logs = await db.audit_log.find().sort("timestamp", -1).to_list(500)
    return [{
        "id": str(l["_id"]),
        "action": l.get("action"),
        "entity_type": l.get("entity_type"),
        "entity_id": l.get("entity_id"),
        "user_email": l.get("user_email"),
        "details": l.get("details", {}),
        "ip_address": l.get("ip_address"),
        "timestamp": l.get("timestamp").isoformat() if l.get("timestamp") else None
    } for l in logs]

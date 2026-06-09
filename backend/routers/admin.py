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

@router.patch("/members/{member_id}")
async def patch_member(request: Request, member_id: str):
    """Update member fields: pipeline_stage, assigned_counselor_id, admin_notes"""
    admin = await get_current_admin(request)
    data = await request.json()

    allowed = ["pipeline_stage", "assigned_counselor_id", "admin_notes"]
    update_data = {k: v for k, v in data.items() if k in allowed and v is not None}

    if "pipeline_stage" in update_data and update_data["pipeline_stage"] not in PIPELINE_STAGES:
        raise HTTPException(status_code=400, detail=f"Invalid stage. Must be one of: {PIPELINE_STAGES}")

    if not update_data:
        return {"message": "Nothing to update"}

    update_data["updated_at"] = datetime.now(timezone.utc)

    result = await db.users.update_one(
        {"_id": ObjectId(member_id)},
        {"$set": update_data}
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Member not found")

    await log_audit_event(
        action=AUDIT_ACTIONS.get("MEMBER_UPDATED", "MEMBER_UPDATED"),
        entity_type="user",
        entity_id=member_id,
        user_email=admin.get("email"),
        details={k: v for k, v in update_data.items() if k != "updated_at"}
    )

    return {"message": "Member updated"}

@router.put("/members/{member_id}/password")
async def set_member_password(request: Request, member_id: str):
    """Set a member's password (admin override)"""
    admin = await get_current_admin(request)
    data = await request.json()

    new_password = data.get("password", "").strip()
    if not new_password or len(new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    member = await db.users.find_one({"_id": ObjectId(member_id)})
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    await db.users.update_one(
        {"_id": ObjectId(member_id)},
        {"$set": {"password_hash": hash_password(new_password), "updated_at": datetime.now(timezone.utc)}}
    )

    await log_audit_event(
        action="ADMIN_SET_PASSWORD",
        entity_type="user",
        entity_id=member_id,
        user_id=admin["_id"],
        user_email=admin.get("email"),
        ip_address=request.client.host if request.client else None
    )

    return {"message": "Password updated"}

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


# Credit repair pipeline stages
CR_STAGES = [
    "cr_waitlist", "cr_consultation", "cr_documents",
    "cr_dispute_1", "cr_dispute_2", "cr_dispute_3",
    "cr_monitoring", "cr_complete"
]

CR_STAGE_LABELS = {
    "cr_waitlist": "Waitlist", "cr_consultation": "Consultation",
    "cr_documents": "Documents", "cr_dispute_1": "Dispute Round 1",
    "cr_dispute_2": "Dispute Round 2", "cr_dispute_3": "Dispute Round 3",
    "cr_monitoring": "Monitoring", "cr_complete": "Complete"
}

# Financial counseling pipeline stages
FC_STAGES = [
    "fc_waitlist", "fc_consultation", "fc_documents",
    "fc_gameplan", "fc_working", "fc_complete"
]

FC_STAGE_LABELS = {
    "fc_waitlist": "Waitlist", "fc_consultation": "Consultation",
    "fc_documents": "Documents", "fc_gameplan": "Game Plan",
    "fc_working": "Working the Plan", "fc_complete": "Complete"
}


@router.get("/analytics")
async def get_analytics(request: Request):
    """Comprehensive analytics for admin dashboard charts"""
    await get_current_admin(request)

    from datetime import timedelta
    now = datetime.now(timezone.utc)

    total_members = await db.users.count_documents({"role": "member"})
    verified_members = await db.users.count_documents({"role": "member", "verified": True})
    pending_dd214 = await db.users.count_documents({"role": "member", "dd214_status": "pending_review"})
    total_counselors = await db.users.count_documents({"role": "counselor", "active": True})
    active_courses = await db.courses.count_documents({"status": "published"})
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    new_this_month = await db.users.count_documents({"role": "member", "created_at": {"$gte": month_start}})

    # Members by month (last 6 months)
    monthly = []
    for i in range(5, -1, -1):
        ms = (now - timedelta(days=30 * i)).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        me = (ms.replace(day=28) + timedelta(days=4)).replace(day=1)
        count = await db.users.count_documents({"role": "member", "created_at": {"$gte": ms, "$lt": me}})
        monthly.append({"month": ms.strftime("%b %Y"), "count": count})

    # Branch breakdown
    branch_agg = await db.users.aggregate([
        {"$match": {"role": "member"}},
        {"$group": {"_id": "$branch", "count": {"$sum": 1}}}
    ]).to_list(20)
    branches = {(b["_id"] or "Not Specified"): b["count"] for b in branch_agg}

    # Pipeline distributions
    pipeline_dist = {}
    for s in PIPELINE_STAGES:
        pipeline_dist[s] = await db.users.count_documents({"role": "member", "pipeline_stage": s})
    cr_dist = {}
    for s in CR_STAGES:
        cr_dist[s] = await db.users.count_documents({"role": "member", "credit_repair_stage": s})
    fc_dist = {}
    for s in FC_STAGES:
        fc_dist[s] = await db.users.count_documents({"role": "member", "financial_counseling_stage": s})

    # DD-214 status
    dd214_dist = {}
    for status in ["pending", "pending_review", "approved", "rejected", "manual_approved"]:
        dd214_dist[status] = await db.users.count_documents({"role": "member", "dd214_status": status})

    return {
        "kpis": {
            "total_members": total_members,
            "verified_members": verified_members,
            "pending_dd214": pending_dd214,
            "total_counselors": total_counselors,
            "active_courses": active_courses,
            "new_this_month": new_this_month
        },
        "monthly_members": monthly,
        "branches": branches,
        "pipeline": pipeline_dist,
        "dd214": dd214_dist,
        "cr_pipeline": cr_dist,
        "fc_pipeline": fc_dist
    }


@router.get("/members/{member_id}/full")
async def get_member_full(request: Request, member_id: str):
    """Get complete member profile including courses, disputes, notes"""
    await get_current_admin(request)

    try:
        oid = ObjectId(member_id)
    except Exception:
        raise HTTPException(status_code=400, detail=f"Invalid member ID format: {member_id}")

    member = await db.users.find_one({"_id": oid})
    if not member:
        raise HTTPException(status_code=404, detail=f"Member {member_id} not found in database")

    # Enrolled courses with progress
    progress_docs = await db.course_progress.find({"user_id": ObjectId(member_id)}).to_list(50)
    courses = []
    for p in progress_docs:
        cid = str(p.get("course_id", ""))
        if len(cid) == 24:
            course = await db.courses.find_one({"_id": ObjectId(cid)})
            if course:
                courses.append({
                    "id": str(course["_id"]),
                    "title": course.get("title", ""),
                    "percent_complete": p.get("percent_complete", 0),
                    "last_accessed": p.get("updated_at").isoformat() if p.get("updated_at") else None
                })

    # Disputes
    disputes = await db.disputes.find({"user_id": ObjectId(member_id)}).sort("created_at", -1).to_list(50)
    dispute_list = [{
        "id": str(d["_id"]),
        "bureau": d.get("bureau"),
        "account": d.get("account"),
        "status": d.get("status"),
        "round": d.get("round"),
        "created_at": d.get("created_at").isoformat() if d.get("created_at") else None
    } for d in disputes]

    # Notes
    notes = await db.intake_notes.find({"member_id": ObjectId(member_id)}).sort("created_at", -1).to_list(50)
    note_list = [{
        "id": str(n["_id"]),
        "content": n.get("content", ""),
        "author": n.get("author", ""),
        "created_at": n.get("created_at").isoformat() if n.get("created_at") else None
    } for n in notes]

    # Counselor name
    counselor_name = None
    if member.get("assigned_counselor_id"):
        try:
            c = await db.users.find_one({"_id": member["assigned_counselor_id"]})
            if c:
                counselor_name = f"{c.get('first_name', '')} {c.get('last_name', '')}".strip()
        except:
            pass

    return {
        "id": str(member["_id"]),
        "email": member.get("email", ""),
        "first_name": member.get("first_name", ""),
        "last_name": member.get("last_name", ""),
        "phone": member.get("phone", ""),
        "state": member.get("state", ""),
        "dob": member.get("dob", ""),
        "branch": member.get("branch", ""),
        "service_status": member.get("service_status", ""),
        "years_of_service": member.get("years_of_service"),
        "separation_year": member.get("separation_year"),
        "challenges": member.get("challenges", ""),
        "how_heard": member.get("how_heard", ""),
        "notes": member.get("notes", ""),
        "role": member.get("role", "member"),
        "verified": member.get("verified", False),
        "dd214_status": member.get("dd214_status", "pending"),
        "dd214_file": member.get("dd214_file"),
        "dd214_approved_by": member.get("dd214_approved_by"),
        "dd214_approved_at": member.get("dd214_approved_at").isoformat() if member.get("dd214_approved_at") else None,
        "pipeline_stage": member.get("pipeline_stage", "applied"),
        "cr_stage": member.get("credit_repair_stage"),
        "fc_stage": member.get("financial_counseling_stage"),
        "assigned_counselor_id": str(member["assigned_counselor_id"]) if member.get("assigned_counselor_id") else None,
        "assigned_counselor_name": counselor_name,
        "admin_notes": member.get("admin_notes", ""),
        "created_at": member.get("created_at").isoformat() if member.get("created_at") else None,
        "courses": courses,
        "disputes": dispute_list,
        "notes_history": note_list
    }


@router.get("/pipeline/credit-repair")
async def get_cr_pipeline(request: Request):
    """Members organized by credit repair stage"""
    await get_current_admin(request)
    pipeline = {}
    for stage in CR_STAGES:
        members = await db.users.find(
            {"role": "member", "credit_repair_stage": stage},
            {"_id": 1, "email": 1, "first_name": 1, "last_name": 1, "branch": 1, "created_at": 1}
        ).sort("created_at", -1).to_list(100)
        pipeline[stage] = [{
            "id": str(m["_id"]),
            "name": f"{m.get('first_name', '')} {m.get('last_name', '')}".strip() or m["email"],
            "branch": m.get("branch"),
            "created_at": m.get("created_at").isoformat() if m.get("created_at") else None
        } for m in members]
    return {"stages": pipeline, "labels": CR_STAGE_LABELS}


@router.get("/pipeline/financial-counseling")
async def get_fc_pipeline(request: Request):
    """Members organized by financial counseling stage"""
    await get_current_admin(request)
    pipeline = {}
    for stage in FC_STAGES:
        members = await db.users.find(
            {"role": "member", "financial_counseling_stage": stage},
            {"_id": 1, "email": 1, "first_name": 1, "last_name": 1, "branch": 1, "created_at": 1}
        ).sort("created_at", -1).to_list(100)
        pipeline[stage] = [{
            "id": str(m["_id"]),
            "name": f"{m.get('first_name', '')} {m.get('last_name', '')}".strip() or m["email"],
            "branch": m.get("branch"),
            "created_at": m.get("created_at").isoformat() if m.get("created_at") else None
        } for m in members]
    return {"stages": pipeline, "labels": FC_STAGE_LABELS}


@router.patch("/members/{member_id}/cr-stage")
async def update_cr_stage(request: Request, member_id: str):
    admin = await get_current_admin(request)
    data = await request.json()
    new_stage = data.get("stage")
    if new_stage not in CR_STAGES:
        raise HTTPException(status_code=400, detail="Invalid CR stage")
    await db.users.update_one(
        {"_id": ObjectId(member_id)},
        {"$set": {"credit_repair_stage": new_stage, "updated_at": datetime.now(timezone.utc)}}
    )
    await log_audit_event(action="CR_STAGE_UPDATED", entity_type="user", entity_id=member_id,
                          user_email=admin.get("email"), details={"stage": new_stage})
    return {"message": "CR stage updated"}


@router.patch("/members/{member_id}/fc-stage")
async def update_fc_stage(request: Request, member_id: str):
    admin = await get_current_admin(request)
    data = await request.json()
    new_stage = data.get("stage")
    if new_stage not in FC_STAGES:
        raise HTTPException(status_code=400, detail="Invalid FC stage")
    await db.users.update_one(
        {"_id": ObjectId(member_id)},
        {"$set": {"financial_counseling_stage": new_stage, "updated_at": datetime.now(timezone.utc)}}
    )
    await log_audit_event(action="FC_STAGE_UPDATED", entity_type="user", entity_id=member_id,
                          user_email=admin.get("email"), details={"stage": new_stage})
    return {"message": "FC stage updated"}


@router.post("/members/{member_id}/approve-dd214")
async def approve_dd214_manual(request: Request, member_id: str):
    """Manually approve DD-214 without requiring document upload"""
    admin = await get_current_admin(request)
    data = await request.json()

    member = await db.users.find_one({"_id": ObjectId(member_id)})
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    await db.users.update_one(
        {"_id": ObjectId(member_id)},
        {"$set": {
            "dd214_status": "manual_approved",
            "dd214_approved_by": admin.get("email"),
            "dd214_approved_at": datetime.now(timezone.utc),
            "dd214_approval_notes": data.get("notes", ""),
            "verified": True,
            "updated_at": datetime.now(timezone.utc)
        }}
    )

    await log_audit_event(action="DD214_MANUAL_APPROVED", entity_type="user", entity_id=member_id,
                          user_email=admin.get("email"), details={"notes": data.get("notes", "")})

    asyncio.create_task(send_dd214_approved_email(member.get("email"), member.get("first_name", "Member")))
    return {"message": "DD-214 manually approved, member verified"}



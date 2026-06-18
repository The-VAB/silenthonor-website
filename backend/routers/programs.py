# Programs router for Silent Honor Foundation
# Handles program applications (Credit Repair, Financial Counseling) and announcements
import asyncio
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request
from bson import ObjectId

from middleware.auth_middleware import get_current_user, get_current_admin
from middleware.logging_middleware import log_audit_event, AUDIT_ACTIONS
from utils.email import send_email, send_counselor_assigned_email, send_program_approved_email

router = APIRouter(prefix="/api", tags=["Programs"])

# Database reference
db = None

def set_db(database):
    global db
    db = database

# ═══════════════════════════════════════════════════════════════════════════
# ANNOUNCEMENTS ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/announcements")
async def get_announcements(request: Request):
    """Get active, non-expired announcements (public)"""
    now = datetime.now(timezone.utc)

    announcements = await db.announcements.find({
        "active": True,
        "$or": [
            {"expires_at": None},
            {"expires_at": {"$gt": now}}
        ]
    }).sort("created_at", -1).to_list(20)

    return [{
        "id": str(a["_id"]),
        "title": a.get("title", ""),
        "content": a.get("content", ""),
        "type": a.get("type", "info"),
        "created_at": a.get("created_at").isoformat() if a.get("created_at") else None
    } for a in announcements]

@router.post("/admin/announcements")
async def create_announcement(request: Request):
    """Create new announcement (admin only)"""
    admin = await get_current_admin(request)
    data = await request.json()

    expires_at = None
    if data.get("expires_at"):
        try:
            expires_at = datetime.fromisoformat(data["expires_at"].replace("Z", "+00:00"))
        except:
            pass

    announcement_doc = {
        "title": data.get("title", ""),
        "content": data.get("content", ""),
        "type": data.get("type", "info"),  # info, warning, success
        "active": data.get("active", True),
        "expires_at": expires_at,
        "created_by": ObjectId(admin["_id"]),
        "created_by_name": f"{admin.get('first_name', '')} {admin.get('last_name', '')}".strip(),
        "created_at": datetime.now(timezone.utc)
    }

    result = await db.announcements.insert_one(announcement_doc)

    await log_audit_event(
        action="ANNOUNCEMENT_CREATED",
        entity_type="announcement",
        entity_id=str(result.inserted_id),
        user_id=admin["_id"],
        user_email=admin.get("email"),
        details={"title": data.get("title")},
        ip_address=request.client.host if request.client else None
    )

    return {"id": str(result.inserted_id), "message": "Announcement created"}

@router.get("/admin/announcements")
async def get_all_announcements(request: Request):
    """Get all announcements including inactive (admin only)"""
    await get_current_admin(request)

    announcements = await db.announcements.find().sort("created_at", -1).to_list(100)

    return [{
        "id": str(a["_id"]),
        "title": a.get("title", ""),
        "content": a.get("content", ""),
        "type": a.get("type", "info"),
        "active": a.get("active", True),
        "expires_at": a.get("expires_at").isoformat() if a.get("expires_at") else None,
        "created_by_name": a.get("created_by_name", "Admin"),
        "created_at": a.get("created_at").isoformat() if a.get("created_at") else None
    } for a in announcements]

@router.put("/admin/announcements/{announcement_id}")
async def update_announcement(request: Request, announcement_id: str):
    """Update announcement (admin only)"""
    admin = await get_current_admin(request)
    data = await request.json()

    update_fields = {}
    for field in ["title", "content", "type", "active"]:
        if field in data:
            update_fields[field] = data[field]

    if "expires_at" in data:
        if data["expires_at"]:
            try:
                update_fields["expires_at"] = datetime.fromisoformat(data["expires_at"].replace("Z", "+00:00"))
            except:
                pass
        else:
            update_fields["expires_at"] = None

    update_fields["updated_at"] = datetime.now(timezone.utc)

    await db.announcements.update_one(
        {"_id": ObjectId(announcement_id)},
        {"$set": update_fields}
    )

    await log_audit_event(
        action="ANNOUNCEMENT_UPDATED",
        entity_type="announcement",
        entity_id=announcement_id,
        user_id=admin["_id"],
        user_email=admin.get("email"),
        ip_address=request.client.host if request.client else None
    )

    return {"message": "Announcement updated"}

@router.delete("/admin/announcements/{announcement_id}")
async def delete_announcement(request: Request, announcement_id: str):
    """Delete announcement (admin only)"""
    admin = await get_current_admin(request)

    await db.announcements.delete_one({"_id": ObjectId(announcement_id)})

    await log_audit_event(
        action="ANNOUNCEMENT_DELETED",
        entity_type="announcement",
        entity_id=announcement_id,
        user_id=admin["_id"],
        user_email=admin.get("email"),
        ip_address=request.client.host if request.client else None
    )

    return {"message": "Announcement deleted"}

# ═══════════════════════════════════════════════════════════════════════════
# PROGRAM APPLICATION ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════

@router.post("/member/apply/credit-repair")
async def apply_credit_repair(request: Request):
    """Submit credit repair program application (verified members only)"""
    user = await get_current_user(request)

    # Check if member is verified
    member = await db.users.find_one({"_id": ObjectId(user["_id"])})
    if not member or not member.get("verified"):
        raise HTTPException(status_code=403, detail="You must be a verified member to apply for programs")

    # Check for existing pending or approved application
    existing = await db.program_applications.find_one({
        "member_id": ObjectId(user["_id"]),
        "program_type": "credit_repair",
        "status": {"$in": ["pending", "approved"]}
    })
    if existing:
        raise HTTPException(status_code=400, detail="You already have a pending or approved credit repair application")

    data = await request.json()

    application_doc = {
        "member_id": ObjectId(user["_id"]),
        "member_email": user.get("email"),
        "member_name": f"{user.get('first_name', '')} {user.get('last_name', '')}".strip(),
        "program_type": "credit_repair",
        "status": "pending",
        "applied_at": datetime.now(timezone.utc),
        "reviewed_at": None,
        "reviewed_by": None,
        "counselor_id": None,
        "application_data": {
            "experian_score": data.get("experian_score"),
            "equifax_score": data.get("equifax_score"),
            "transunion_score": data.get("transunion_score"),
            "total_debt": data.get("total_debt"),
            "monthly_income": data.get("monthly_income"),
            "recent_bankruptcy": data.get("recent_bankruptcy"),
            "bankruptcy_chapter": data.get("bankruptcy_chapter"),
            "bankruptcy_year": data.get("bankruptcy_year"),
            "outstanding_collections": data.get("outstanding_collections"),
            "negative_items_count": data.get("negative_items_count"),
            "primary_credit_issues": data.get("primary_credit_issues", []),
            "worked_with_credit_repair_before": data.get("worked_with_credit_repair_before"),
            "credit_repair_goals": data.get("credit_repair_goals"),
            "target_timeline": data.get("target_timeline"),
            "credit_reports_uploaded": data.get("credit_reports_uploaded", False),
            "additional_notes": data.get("additional_notes")
        },
        "notes": ""
    }

    result = await db.program_applications.insert_one(application_doc)

    # Update member's credit repair stage
    await db.users.update_one(
        {"_id": ObjectId(user["_id"])},
        {"$set": {"credit_repair_stage": "cr_waitlist"}}
    )

    await log_audit_event(
        action="PROGRAM_APPLICATION_SUBMITTED",
        entity_type="program_application",
        entity_id=str(result.inserted_id),
        user_id=user["_id"],
        user_email=user.get("email"),
        details={"program_type": "credit_repair"},
        ip_address=request.client.host if request.client else None
    )

    # Notify admin
    from utils.email import send_admin_notification
    asyncio.create_task(send_admin_notification(
        "New Credit Repair Application",
        f"{application_doc['member_name']} ({user.get('email')}) has applied for the Credit Repair program."
    ))

    return {"id": str(result.inserted_id), "message": "Credit repair application submitted successfully"}

@router.post("/member/apply/financial-counseling")
async def apply_financial_counseling(request: Request):
    """Submit financial counseling program application (verified members only)"""
    user = await get_current_user(request)

    # Check if member is verified
    member = await db.users.find_one({"_id": ObjectId(user["_id"])})
    if not member or not member.get("verified"):
        raise HTTPException(status_code=403, detail="You must be a verified member to apply for programs")

    # Check for existing pending or approved application
    existing = await db.program_applications.find_one({
        "member_id": ObjectId(user["_id"]),
        "program_type": "financial_counseling",
        "status": {"$in": ["pending", "approved"]}
    })
    if existing:
        raise HTTPException(status_code=400, detail="You already have a pending or approved financial counseling application")

    data = await request.json()

    application_doc = {
        "member_id": ObjectId(user["_id"]),
        "member_email": user.get("email"),
        "member_name": f"{user.get('first_name', '')} {user.get('last_name', '')}".strip(),
        "program_type": "financial_counseling",
        "status": "pending",
        "applied_at": datetime.now(timezone.utc),
        "reviewed_at": None,
        "reviewed_by": None,
        "counselor_id": None,
        "application_data": {
            "primary_challenges": data.get("primary_challenges", []),
            "monthly_income": data.get("monthly_income"),
            "monthly_expenses": data.get("monthly_expenses"),
            "total_debt": data.get("total_debt"),
            "debt_types": data.get("debt_types", []),
            "has_written_budget": data.get("has_written_budget"),
            "has_emergency_fund": data.get("has_emergency_fund"),
            "emergency_fund_months": data.get("emergency_fund_months"),
            "worked_with_counselor_before": data.get("worked_with_counselor_before"),
            "top_financial_goals": data.get("top_financial_goals"),
            "areas_need_help": data.get("areas_need_help"),
            "additional_notes": data.get("additional_notes")
        },
        "notes": ""
    }

    result = await db.program_applications.insert_one(application_doc)

    # Update member's financial counseling stage
    await db.users.update_one(
        {"_id": ObjectId(user["_id"])},
        {"$set": {"financial_counseling_stage": "fc_waitlist"}}
    )

    await log_audit_event(
        action="PROGRAM_APPLICATION_SUBMITTED",
        entity_type="program_application",
        entity_id=str(result.inserted_id),
        user_id=user["_id"],
        user_email=user.get("email"),
        details={"program_type": "financial_counseling"},
        ip_address=request.client.host if request.client else None
    )

    # Notify admin
    from utils.email import send_admin_notification
    asyncio.create_task(send_admin_notification(
        "New Financial Counseling Application",
        f"{application_doc['member_name']} ({user.get('email')}) has applied for the Financial Counseling program."
    ))

    return {"id": str(result.inserted_id), "message": "Financial counseling application submitted successfully"}

@router.get("/member/programs")
async def get_member_programs(request: Request):
    """Get member's program applications and their status"""
    user = await get_current_user(request)

    applications = await db.program_applications.find({
        "member_id": ObjectId(user["_id"])
    }).sort("applied_at", -1).to_list(10)

    # Get member's program stages
    member = await db.users.find_one({"_id": ObjectId(user["_id"])})

    result = {
        "credit_repair": None,
        "financial_counseling": None,
        "credit_repair_stage": member.get("credit_repair_stage"),
        "financial_counseling_stage": member.get("financial_counseling_stage")
    }

    for app in applications:
        program_type = app.get("program_type")
        if program_type == "credit_repair" and result["credit_repair"] is None:
            counselor = None
            if app.get("counselor_id"):
                c = await db.users.find_one({"_id": app["counselor_id"]})
                if c:
                    counselor = {
                        "id": str(c["_id"]),
                        "name": f"{c.get('first_name', '')} {c.get('last_name', '')}".strip()
                    }

            result["credit_repair"] = {
                "id": str(app["_id"]),
                "status": app.get("status"),
                "applied_at": app.get("applied_at").isoformat() if app.get("applied_at") else None,
                "counselor": counselor
            }
        elif program_type == "financial_counseling" and result["financial_counseling"] is None:
            counselor = None
            if app.get("counselor_id"):
                c = await db.users.find_one({"_id": app["counselor_id"]})
                if c:
                    counselor = {
                        "id": str(c["_id"]),
                        "name": f"{c.get('first_name', '')} {c.get('last_name', '')}".strip()
                    }

            result["financial_counseling"] = {
                "id": str(app["_id"]),
                "status": app.get("status"),
                "applied_at": app.get("applied_at").isoformat() if app.get("applied_at") else None,
                "counselor": counselor
            }

    return result

# ═══════════════════════════════════════════════════════════════════════════
# ADMIN APPLICATION MANAGEMENT ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/admin/applications")
async def get_applications(request: Request):
    """Get all program applications with filters (admin only)"""
    await get_current_admin(request)

    # Get query params
    program_type = request.query_params.get("program_type")
    status = request.query_params.get("status")

    query = {}
    if program_type:
        query["program_type"] = program_type
    if status:
        query["status"] = status

    applications = await db.program_applications.find(query).sort("applied_at", -1).to_list(500)

    result = []
    for app in applications:
        counselor_name = None
        if app.get("counselor_id"):
            c = await db.users.find_one({"_id": app["counselor_id"]})
            if c:
                counselor_name = f"{c.get('first_name', '')} {c.get('last_name', '')}".strip()

        result.append({
            "id": str(app["_id"]),
            "member_id": str(app.get("member_id")),
            "member_email": app.get("member_email"),
            "member_name": app.get("member_name"),
            "program_type": app.get("program_type"),
            "status": app.get("status"),
            "applied_at": app.get("applied_at").isoformat() if app.get("applied_at") else None,
            "reviewed_at": app.get("reviewed_at").isoformat() if app.get("reviewed_at") else None,
            "counselor_name": counselor_name
        })

    return result

@router.get("/admin/applications/{application_id}")
async def get_application_detail(request: Request, application_id: str):
    """Get full application detail (admin only)"""
    await get_current_admin(request)

    app = await db.program_applications.find_one({"_id": ObjectId(application_id)})
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    counselor = None
    if app.get("counselor_id"):
        c = await db.users.find_one({"_id": app["counselor_id"]})
        if c:
            counselor = {
                "id": str(c["_id"]),
                "name": f"{c.get('first_name', '')} {c.get('last_name', '')}".strip(),
                "email": c.get("email")
            }

    reviewed_by = None
    if app.get("reviewed_by"):
        r = await db.users.find_one({"_id": app["reviewed_by"]})
        if r:
            reviewed_by = f"{r.get('first_name', '')} {r.get('last_name', '')}".strip()

    return {
        "id": str(app["_id"]),
        "member_id": str(app.get("member_id")),
        "member_email": app.get("member_email"),
        "member_name": app.get("member_name"),
        "program_type": app.get("program_type"),
        "status": app.get("status"),
        "applied_at": app.get("applied_at").isoformat() if app.get("applied_at") else None,
        "reviewed_at": app.get("reviewed_at").isoformat() if app.get("reviewed_at") else None,
        "reviewed_by": reviewed_by,
        "counselor": counselor,
        "application_data": app.get("application_data", {}),
        "notes": app.get("notes", "")
    }

@router.put("/admin/applications/{application_id}/approve")
async def approve_application(request: Request, application_id: str):
    """Approve application and assign counselor (admin only)"""
    admin = await get_current_admin(request)
    data = await request.json()

    counselor_id = data.get("counselor_id") or None

    app = await db.program_applications.find_one({"_id": ObjectId(application_id)})
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    app_update = {
        "status": "approved",
        "reviewed_at": datetime.now(timezone.utc),
        "reviewed_by": ObjectId(admin["_id"]),
        "notes": data.get("notes", app.get("notes", ""))
    }
    if counselor_id:
        app_update["counselor_id"] = ObjectId(counselor_id)

    # Update application
    await db.program_applications.update_one(
        {"_id": ObjectId(application_id)},
        {"$set": app_update}
    )

    # Update member's pipeline stage and counselor assignment
    program_type = app.get("program_type")
    member_id = app.get("member_id")

    update_fields = {}
    if counselor_id:
        update_fields["assigned_counselor_id"] = ObjectId(counselor_id)

    if program_type == "credit_repair":
        update_fields["credit_repair_stage"] = "cr_consultation"
    elif program_type == "financial_counseling":
        update_fields["financial_counseling_stage"] = "fc_consultation"

    if update_fields:
        await db.users.update_one(
            {"_id": member_id},
            {"$set": update_fields}
        )

    # Get member and counselor for email
    member = await db.users.find_one({"_id": member_id})
    counselor = await db.users.find_one({"_id": ObjectId(counselor_id)}) if counselor_id else None

    if member:
        program_label = "Credit Repair" if program_type == "credit_repair" else "Financial Counseling"
        counselor_name = f"{counselor.get('first_name', '')} {counselor.get('last_name', '')}".strip() if counselor else None
        asyncio.create_task(send_program_approved_email(
            member.get("email"),
            member.get("first_name", "Member"),
            program_label,
            bool(counselor),
            counselor_name
        ))
        if counselor:
            asyncio.create_task(send_counselor_assigned_email(
                member.get("email"),
                member.get("first_name", "Member"),
                counselor_name
            ))

    await log_audit_event(
        action="PROGRAM_APPLICATION_APPROVED",
        entity_type="program_application",
        entity_id=application_id,
        user_id=admin["_id"],
        user_email=admin.get("email"),
        details={"program_type": program_type, "counselor_id": counselor_id},
        ip_address=request.client.host if request.client else None
    )

    return {"message": "Application approved and counselor assigned"}

@router.put("/admin/applications/{application_id}/reject")
async def reject_application(request: Request, application_id: str):
    """Reject application with reason (admin only)"""
    admin = await get_current_admin(request)
    data = await request.json()

    app = await db.program_applications.find_one({"_id": ObjectId(application_id)})
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    reason = data.get("reason", "")

    await db.program_applications.update_one(
        {"_id": ObjectId(application_id)},
        {"$set": {
            "status": "rejected",
            "reviewed_at": datetime.now(timezone.utc),
            "reviewed_by": ObjectId(admin["_id"]),
            "notes": reason
        }}
    )

    # Clear member's program stage
    program_type = app.get("program_type")
    member_id = app.get("member_id")

    if program_type == "credit_repair":
        await db.users.update_one({"_id": member_id}, {"$unset": {"credit_repair_stage": ""}})
    elif program_type == "financial_counseling":
        await db.users.update_one({"_id": member_id}, {"$unset": {"financial_counseling_stage": ""}})

    # Optionally send rejection email
    member = await db.users.find_one({"_id": member_id})
    if member:
        program_name = "Credit Repair" if program_type == "credit_repair" else "Financial Counseling"
        asyncio.create_task(send_email(
            member.get("email"),
            f"Update on Your {program_name} Application - Silent Honor Foundation",
            f"""
            <html>
            <body style="font-family: Arial, sans-serif; background: #0B1220; color: #ffffff; padding: 40px;">
                <div style="max-width: 600px; margin: 0 auto; background: #111827; padding: 40px; border: 1px solid #374151;">
                    <h1 style="color: #ffffff;">Application Update</h1>
                    <p style="color: #9CA3AF;">Hi {member.get('first_name', 'Member')},</p>
                    <p style="color: #9CA3AF;">Thank you for your interest in our {program_name} program. After review, we are unable to approve your application at this time.</p>
                    {f'<p style="color: #9CA3AF;"><strong>Reason:</strong> {reason}</p>' if reason else ''}
                    <p style="color: #9CA3AF;">If you have questions, please contact us at m.lugenbell@silenthonor.org</p>
                    <p style="color: #6B7280; margin-top: 40px; padding-top: 20px; border-top: 1px solid #374151;">Silent Honor Foundation | Veterans Helping Veterans</p>
                </div>
            </body>
            </html>
            """,
            f"Your {program_name} application update. Contact m.lugenbell@silenthonor.org for questions."
        ))

    await log_audit_event(
        action="PROGRAM_APPLICATION_REJECTED",
        entity_type="program_application",
        entity_id=application_id,
        user_id=admin["_id"],
        user_email=admin.get("email"),
        details={"program_type": program_type, "reason": reason},
        ip_address=request.client.host if request.client else None
    )

    return {"message": "Application rejected"}

# ═══════════════════════════════════════════════════════════════════════════
# PIPELINE STAGE MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════

# Valid pipeline stages
ONBOARDING_STAGES = ["applied", "dd214_pending", "dd214_review", "approved", "active", "inactive", "graduated"]
CREDIT_REPAIR_STAGES = ["cr_waitlist", "cr_consultation", "cr_documents", "cr_dispute_1", "cr_dispute_2", "cr_dispute_3", "cr_monitoring", "cr_complete"]
FINANCIAL_COUNSELING_STAGES = ["fc_waitlist", "fc_consultation", "fc_documents", "fc_gameplan", "fc_working", "fc_complete"]

@router.put("/admin/members/{member_id}/stage")
async def update_member_pipeline_stage(request: Request, member_id: str):
    """Update member's pipeline stage (any of the three pipelines)"""
    admin = await get_current_admin(request)
    data = await request.json()

    pipeline_type = data.get("pipeline_type", "onboarding")  # onboarding, credit_repair, financial_counseling
    new_stage = data.get("stage")

    # Validate stage based on pipeline type
    if pipeline_type == "onboarding":
        if new_stage not in ONBOARDING_STAGES:
            raise HTTPException(status_code=400, detail=f"Invalid onboarding stage. Must be one of: {ONBOARDING_STAGES}")
        field = "pipeline_stage"
    elif pipeline_type == "credit_repair":
        if new_stage not in CREDIT_REPAIR_STAGES:
            raise HTTPException(status_code=400, detail=f"Invalid credit repair stage. Must be one of: {CREDIT_REPAIR_STAGES}")
        field = "credit_repair_stage"
    elif pipeline_type == "financial_counseling":
        if new_stage not in FINANCIAL_COUNSELING_STAGES:
            raise HTTPException(status_code=400, detail=f"Invalid financial counseling stage. Must be one of: {FINANCIAL_COUNSELING_STAGES}")
        field = "financial_counseling_stage"
    else:
        raise HTTPException(status_code=400, detail="Invalid pipeline_type. Must be: onboarding, credit_repair, or financial_counseling")

    await db.users.update_one(
        {"_id": ObjectId(member_id)},
        {"$set": {field: new_stage, "updated_at": datetime.now(timezone.utc)}}
    )

    await log_audit_event(
        action="MEMBER_STAGE_CHANGED",
        entity_type="user",
        entity_id=member_id,
        user_id=admin["_id"],
        user_email=admin.get("email"),
        details={"pipeline_type": pipeline_type, "new_stage": new_stage},
        ip_address=request.client.host if request.client else None
    )

    return {"message": f"Member {pipeline_type} stage updated to {new_stage}"}

@router.get("/admin/pipeline")
async def get_all_pipelines(request: Request):
    """Get all members grouped by their stages across all three pipelines"""
    await get_current_admin(request)

    result = {
        "onboarding": {},
        "credit_repair": {},
        "financial_counseling": {}
    }

    # Initialize all stages
    for stage in ONBOARDING_STAGES:
        result["onboarding"][stage] = []
    for stage in CREDIT_REPAIR_STAGES:
        result["credit_repair"][stage] = []
    for stage in FINANCIAL_COUNSELING_STAGES:
        result["financial_counseling"][stage] = []

    # Get all members
    members = await db.users.find(
        {"role": "member"},
        {"_id": 1, "email": 1, "first_name": 1, "last_name": 1, "branch": 1,
         "pipeline_stage": 1, "credit_repair_stage": 1, "financial_counseling_stage": 1,
         "assigned_counselor_id": 1, "created_at": 1, "updated_at": 1}
    ).to_list(1000)

    for m in members:
        member_data = {
            "id": str(m["_id"]),
            "name": f"{m.get('first_name', '')} {m.get('last_name', '')}".strip(),
            "email": m.get("email"),
            "branch": m.get("branch"),
            "has_counselor": bool(m.get("assigned_counselor_id")),
            "created_at": m.get("created_at").isoformat() if m.get("created_at") else None,
            "updated_at": m.get("updated_at").isoformat() if m.get("updated_at") else None
        }

        # Onboarding pipeline
        onboarding_stage = m.get("pipeline_stage", "applied")
        if onboarding_stage in result["onboarding"]:
            result["onboarding"][onboarding_stage].append(member_data)

        # Credit repair pipeline (only if they have a stage)
        cr_stage = m.get("credit_repair_stage")
        if cr_stage and cr_stage in result["credit_repair"]:
            result["credit_repair"][cr_stage].append(member_data)

        # Financial counseling pipeline (only if they have a stage)
        fc_stage = m.get("financial_counseling_stage")
        if fc_stage and fc_stage in result["financial_counseling"]:
            result["financial_counseling"][fc_stage].append(member_data)

    return result

# ═══════════════════════════════════════════════════════════════════════════
# MEMBER DEACTIVATION/REACTIVATION
# ═══════════════════════════════════════════════════════════════════════════

@router.put("/admin/members/{member_id}/deactivate")
async def deactivate_member(request: Request, member_id: str):
    """Deactivate member - they cannot log in"""
    admin = await get_current_admin(request)

    await db.users.update_one(
        {"_id": ObjectId(member_id)},
        {"$set": {
            "is_active": False,
            "pipeline_stage": "inactive",
            "deactivated_at": datetime.now(timezone.utc),
            "deactivated_by": ObjectId(admin["_id"])
        }}
    )

    await log_audit_event(
        action="MEMBER_DEACTIVATED",
        entity_type="user",
        entity_id=member_id,
        user_id=admin["_id"],
        user_email=admin.get("email"),
        ip_address=request.client.host if request.client else None
    )

    return {"message": "Member deactivated"}

@router.put("/admin/members/{member_id}/reactivate")
async def reactivate_member(request: Request, member_id: str):
    """Reactivate member - they can log in again"""
    admin = await get_current_admin(request)

    await db.users.update_one(
        {"_id": ObjectId(member_id)},
        {"$set": {
            "is_active": True,
            "pipeline_stage": "active",
            "reactivated_at": datetime.now(timezone.utc),
            "reactivated_by": ObjectId(admin["_id"])
        }}
    )

    await log_audit_event(
        action="MEMBER_REACTIVATED",
        entity_type="user",
        entity_id=member_id,
        user_id=admin["_id"],
        user_email=admin.get("email"),
        ip_address=request.client.host if request.client else None
    )

    return {"message": "Member reactivated"}

# Counselor router for Silent Honor Foundation
import asyncio
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request
from bson import ObjectId

from middleware.auth_middleware import get_current_counselor, get_current_admin
from middleware.logging_middleware import log_audit_event, AUDIT_ACTIONS
from fastapi import UploadFile, File, Form
from utils.auth import hash_password
from utils.validators import CounselorRequest
from utils.email import send_counselor_assigned_email
from utils.storage import get_dd214_url, upload_document, get_document_url, delete_document

router = APIRouter(prefix="/api", tags=["Counselor"])

# Database reference
db = None

# Program track values for the counselor's caseload view (separate from the
# 9-value intake pipeline_stage and the admin-managed cr_stage/fc_stage sub-stages)
PROGRAM_TRACKS = ["onboarding", "credit_repair", "financial_counseling"]

# NOTE (future phases): dispute_tracker, game_plan, and tasks collections are
# Phase 4/6/8 additions. Caseload flags stub overdue_task/new_document as False
# until those collections exist. waitlist_status is Phase 9.

def set_db(database):
    global db
    db = database

# Member-facing endpoints
@router.get("/member/counselor")
@router.get("/counselor/assigned")
async def get_assigned_counselor(request: Request):
    """Get member's assigned counselor (deprecated - use /api/member/counselor)"""
    from middleware.auth_middleware import get_current_user
    user = await get_current_user(request)

    member = await db.users.find_one({"_id": ObjectId(user["_id"])})
    counselor_id = member.get("assigned_counselor_id")

    if not counselor_id:
        return {"id": None, "name": None, "message": "No counselor assigned yet"}

    counselor = await db.users.find_one({"_id": ObjectId(counselor_id)})
    if not counselor:
        return {"id": None, "name": None, "message": "Counselor not found"}

    return {
        "id": str(counselor["_id"]),
        "name": f"{counselor.get('first_name', '')} {counselor.get('last_name', '')}".strip(),
        "email": counselor.get("email"),
        "title": counselor.get("title", "Certified Financial Counselor"),
        "bio": counselor.get("bio", ""),
        "specialties": counselor.get("specialties", []),
        "calendly_url": counselor.get("calendly_url")
    }

# Counselor portal endpoints
@router.get("/counselor/members")
async def get_counselor_members(request: Request):
    """Get all members assigned to this counselor"""
    counselor = await get_current_counselor(request)

    members = await db.users.find(
        {"assigned_counselor_id": ObjectId(counselor["_id"])},
        {"_id": 1, "email": 1, "first_name": 1, "last_name": 1, "branch": 1,
         "pipeline_stage": 1, "created_at": 1}
    ).sort("created_at", -1).to_list(100)

    return [{
        "id": str(m["_id"]),
        "email": m["email"],
        "name": f"{m.get('first_name', '')} {m.get('last_name', '')}".strip(),
        "branch": m.get("branch"),
        "pipeline_stage": m.get("pipeline_stage", "active"),
        "created_at": m.get("created_at").isoformat() if m.get("created_at") else None
    } for m in members]

@router.get("/counselor/caseload")
async def get_counselor_caseload(request: Request):
    """Get all assigned members with program track, last activity, and computed flags"""
    counselor = await get_current_counselor(request)
    counselor_oid = ObjectId(counselor["_id"])

    members = await db.users.find(
        {"assigned_counselor_id": counselor_oid},
        {"_id": 1, "first_name": 1, "last_name": 1, "email": 1, "branch": 1,
         "program_track": 1, "credit_repair_stage": 1, "financial_counseling_stage": 1,
         "last_activity_date": 1, "created_at": 1}
    ).to_list(200)

    if not members:
        return []

    member_ids = [m["_id"] for m in members]

    # Single aggregation: count unread messages from each member to this counselor
    pipeline = [
        {"$match": {"to_user_id": counselor_oid, "from_user_id": {"$in": member_ids}, "read": False}},
        {"$group": {"_id": "$from_user_id", "count": {"$sum": 1}}}
    ]
    unread_docs = await db.messages.aggregate(pipeline).to_list(200)
    unread_map = {str(doc["_id"]): doc["count"] for doc in unread_docs}

    result = []
    for m in members:
        mid = str(m["_id"])
        last_activity = m.get("last_activity_date") or m.get("created_at")
        result.append({
            "id": mid,
            "name": f"{m.get('first_name', '')} {m.get('last_name', '')}".strip(),
            "email": m.get("email", ""),
            "branch": m.get("branch"),
            "program_track": m.get("program_track", "onboarding"),
            "cr_stage": m.get("credit_repair_stage"),
            "fc_stage": m.get("financial_counseling_stage"),
            "last_activity": last_activity.isoformat() if last_activity else None,
            "flags": {
                "unread_message": unread_map.get(mid, 0) > 0,
                "overdue_task": False,   # Phase 6: tasks collection not yet implemented
                "new_document": False    # Phase 3: documents collection not yet implemented
            }
        })

    result.sort(key=lambda x: x["last_activity"] or "", reverse=True)
    return result


@router.patch("/counselor/members/{member_id}/program-track")
async def update_program_track(request: Request, member_id: str):
    """Update a member's program track (onboarding/credit_repair/financial_counseling)"""
    counselor = await get_current_counselor(request)
    data = await request.json()

    new_track = data.get("program_track")
    if new_track not in PROGRAM_TRACKS:
        raise HTTPException(status_code=400, detail=f"program_track must be one of: {PROGRAM_TRACKS}")

    member = await db.users.find_one({
        "_id": ObjectId(member_id),
        "assigned_counselor_id": ObjectId(counselor["_id"])
    })
    if not member:
        raise HTTPException(status_code=404, detail="Member not found or not assigned to you")

    now = datetime.now(timezone.utc)
    update_fields = {
        "program_track": new_track,
        "last_activity_date": now,
        "updated_at": now
    }

    # Initialize sub-stage to first value only if not already set
    if new_track == "credit_repair" and not member.get("credit_repair_stage"):
        update_fields["credit_repair_stage"] = "cr_waitlist"
    if new_track == "financial_counseling" and not member.get("financial_counseling_stage"):
        update_fields["financial_counseling_stage"] = "fc_waitlist"

    await db.users.update_one({"_id": ObjectId(member_id)}, {"$set": update_fields})
    return {"message": "Program track updated", "program_track": new_track}


@router.get("/counselor/members/{member_id}")
async def get_counselor_member_detail(request: Request, member_id: str):
    """Get detailed info about assigned member"""
    counselor = await get_current_counselor(request)

    member = await db.users.find_one({
        "_id": ObjectId(member_id),
        "assigned_counselor_id": ObjectId(counselor["_id"])
    })

    if not member:
        raise HTTPException(status_code=404, detail="Member not found or not assigned to you")

    member["_id"] = str(member["_id"])
    member.pop("password_hash", None)

    # Get credit scores
    credit_scores = await db.credit_scores.find(
        {"user_id": ObjectId(member_id)}
    ).sort("date", -1).to_list(10)

    # Get disputes
    disputes = await db.disputes.find(
        {"user_id": ObjectId(member_id)}
    ).sort("created_at", -1).to_list(50)

    # Get notes
    notes = await db.intake_notes.find(
        {"member_id": ObjectId(member_id)}
    ).sort("created_at", -1).to_list(50)

    return {
        "member": member,
        "credit_scores": [{
            "id": str(s["_id"]),
            "date": s.get("date").isoformat() if s.get("date") else None,
            "equifax": s.get("equifax"),
            "experian": s.get("experian"),
            "transunion": s.get("transunion")
        } for s in credit_scores],
        "disputes": [{
            "id": str(d["_id"]),
            "bureau": d.get("bureau"),
            "account_name": d.get("account_name"),
            "status": d.get("status"),
            "created_at": d.get("created_at").isoformat() if d.get("created_at") else None
        } for d in disputes],
        "notes": [{
            "id": str(n["_id"]),
            "content": n.get("content"),
            "note_type": n.get("note_type"),
            "created_by": n.get("created_by_name"),
            "created_at": n.get("created_at").isoformat() if n.get("created_at") else None
        } for n in notes]
    }

@router.post("/counselor/members/{member_id}/notes")
async def add_counselor_note(request: Request, member_id: str):
    """Add note to assigned member"""
    counselor = await get_current_counselor(request)
    data = await request.json()

    # Verify member is assigned to this counselor
    member = await db.users.find_one({
        "_id": ObjectId(member_id),
        "assigned_counselor_id": ObjectId(counselor["_id"])
    })

    if not member:
        raise HTTPException(status_code=404, detail="Member not found or not assigned to you")

    note_doc = {
        "member_id": ObjectId(member_id),
        "content": data.get("content", ""),
        "note_type": data.get("note_type", "counselor"),
        "created_by": ObjectId(counselor["_id"]),
        "created_by_name": f"{counselor.get('first_name', '')} {counselor.get('last_name', '')}".strip(),
        "created_at": datetime.now(timezone.utc)
    }

    result = await db.intake_notes.insert_one(note_doc)

    # Bump last_activity_date on the member so caseload "Last Activity" column reflects counselor work
    await db.users.update_one(
        {"_id": ObjectId(member_id)},
        {"$set": {"last_activity_date": datetime.now(timezone.utc)}}
    )

    return {"id": str(result.inserted_id), "message": "Note added"}

@router.get("/counselor/stats")
async def get_counselor_stats(request: Request):
    """Get statistics for counselor dashboard"""
    counselor = await get_current_counselor(request)

    assigned_count = await db.users.count_documents({"assigned_counselor_id": ObjectId(counselor["_id"])})

    # Get members in different stages
    intake_count = await db.users.count_documents({
        "assigned_counselor_id": ObjectId(counselor["_id"]),
        "pipeline_stage": "intake_complete"
    })

    active_count = await db.users.count_documents({
        "assigned_counselor_id": ObjectId(counselor["_id"]),
        "pipeline_stage": "active"
    })

    # Get unread messages
    unread = await db.messages.count_documents({
        "to_user_id": ObjectId(counselor["_id"]),
        "read": False
    })

    return {
        "assigned_members": assigned_count,
        "intake_pending": intake_count,
        "active_members": active_count,
        "unread_messages": unread
    }

DOCUMENT_CATEGORIES = [
    "dd214", "credit_report", "dispute_letter", "goodwill_letter",
    "validation_letter", "correspondence", "other"
]
ALLOWED_DOC_TYPES = ["application/pdf", "image/jpeg", "image/jpg", "image/png",
                     "application/msword",
                     "application/vnd.openxmlformats-officedocument.wordprocessingml.document"]
MAX_DOC_SIZE = 20 * 1024 * 1024  # 20 MB

@router.get("/counselor/members/{member_id}/documents")
async def get_member_documents(request: Request, member_id: str):
    """List all documents for an assigned member, including synthetic DD-214 entry"""
    counselor = await get_current_counselor(request)

    member = await db.users.find_one({
        "_id": ObjectId(member_id),
        "assigned_counselor_id": ObjectId(counselor["_id"])
    }, {"dd214_file": 1, "dd214_storage_type": 1, "dd214_status": 1, "dd214_uploaded_at": 1})
    if not member:
        raise HTTPException(status_code=404, detail="Member not found or not assigned to you")

    docs = []

    # Synthetic DD-214 entry from user doc fields
    if member.get("dd214_file"):
        dd214_url = await get_dd214_url(member["dd214_file"], member.get("dd214_storage_type", "local"))
        docs.append({
            "id": f"dd214-{member_id}",
            "display_name": "DD-214",
            "category": "dd214",
            "storage_type": member.get("dd214_storage_type", "local"),
            "uploaded_at": member.get("dd214_uploaded_at").isoformat() if member.get("dd214_uploaded_at") else None,
            "uploaded_by": None,
            "download_url": dd214_url,
            "is_system": True,
            "dd214_status": member.get("dd214_status")
        })

    # Counselor-uploaded documents from documents collection
    cursor = db.documents.find({"member_id": ObjectId(member_id)}).sort("uploaded_at", -1)
    async for doc in cursor:
        url = await get_document_url(doc["storage_key"], doc.get("storage_type", "local"))
        docs.append({
            "id": str(doc["_id"]),
            "display_name": doc.get("display_name", "Document"),
            "category": doc.get("category", "other"),
            "storage_type": doc.get("storage_type", "local"),
            "file_size": doc.get("file_size"),
            "uploaded_at": doc.get("uploaded_at").isoformat() if doc.get("uploaded_at") else None,
            "uploaded_by": doc.get("uploaded_by_name"),
            "download_url": url,
            "is_system": False
        })

    return docs


@router.post("/counselor/members/{member_id}/documents")
async def upload_member_document(
    request: Request,
    member_id: str,
    file: UploadFile = File(...),
    category: str = Form(...),
    display_name: str = Form("")
):
    """Upload a document for an assigned member"""
    counselor = await get_current_counselor(request)

    member = await db.users.find_one({
        "_id": ObjectId(member_id),
        "assigned_counselor_id": ObjectId(counselor["_id"])
    }, {"_id": 1})
    if not member:
        raise HTTPException(status_code=404, detail="Member not found or not assigned to you")

    if category not in DOCUMENT_CATEGORIES:
        raise HTTPException(status_code=400, detail=f"category must be one of: {DOCUMENT_CATEGORIES}")

    if file.content_type not in ALLOWED_DOC_TYPES:
        raise HTTPException(status_code=400, detail="Invalid file type. Allowed: PDF, JPG, PNG, DOC, DOCX")

    contents = await file.read()
    if len(contents) > MAX_DOC_SIZE:
        raise HTTPException(status_code=400, detail="File too large. Maximum 20 MB.")

    result = await upload_document(contents, file.filename or "document", member_id)
    if not result["success"]:
        raise HTTPException(status_code=500, detail=f"Upload failed: {result.get('error')}")

    now = datetime.now(timezone.utc)
    doc_name = display_name.strip() or (file.filename or "Document")

    await db.documents.insert_one({
        "member_id": ObjectId(member_id),
        "display_name": doc_name,
        "category": category,
        "storage_key": result["storage_key"],
        "storage_type": result["storage_type"],
        "file_size": len(contents),
        "original_filename": file.filename,
        "uploaded_at": now,
        "uploaded_by": ObjectId(counselor["_id"]),
        "uploaded_by_name": f"{counselor.get('first_name', '')} {counselor.get('last_name', '')}".strip()
    })

    await db.users.update_one(
        {"_id": ObjectId(member_id)},
        {"$set": {"last_activity_date": now}}
    )

    return {"message": "Document uploaded successfully", "display_name": doc_name}


@router.delete("/counselor/documents/{doc_id}")
async def delete_member_document(request: Request, doc_id: str):
    """Delete a counselor-uploaded document"""
    counselor = await get_current_counselor(request)

    try:
        oid = ObjectId(doc_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid document ID")

    doc = await db.documents.find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Confirm counselor is assigned to the member
    member = await db.users.find_one({
        "_id": doc["member_id"],
        "assigned_counselor_id": ObjectId(counselor["_id"])
    }, {"_id": 1})
    if not member:
        raise HTTPException(status_code=403, detail="Not authorized to delete this document")

    await delete_document(doc["storage_key"], doc.get("storage_type", "local"))
    await db.documents.delete_one({"_id": oid})
    return {"message": "Document deleted"}


# Admin counselor management
@router.get("/admin/counselors")
async def get_counselors(request: Request):
    """Get all counselors (admin only)"""
    await get_current_admin(request)
    counselors = await db.users.find({"role": "counselor"}).to_list(100)

    result = []
    for c in counselors:
        assigned_count = await db.users.count_documents({"assigned_counselor_id": c["_id"]})
        result.append({
            "id": str(c["_id"]),
            "name": f"{c.get('first_name', '')} {c.get('last_name', '')}".strip(),
            "email": c.get("email"),
            "title": c.get("title", ""),
            "specialties": c.get("specialties", []),
            "bio": c.get("bio", ""),
            "assigned_members": assigned_count,
            "active": c.get("active", True)
        })

    return result

@router.post("/admin/counselors")
async def create_counselor(request: Request):
    """Create new counselor (admin only)"""
    admin = await get_current_admin(request)
    data = await request.json()

    email = data.get("email", "").lower()
    if not email:
        raise HTTPException(status_code=400, detail="Email required")

    existing = await db.users.find_one({"email": email})
    if existing:
        # Upgrade existing user to counselor
        await db.users.update_one(
            {"_id": existing["_id"]},
            {"$set": {
                "role": "counselor",
                "title": data.get("title", ""),
                "bio": data.get("bio", ""),
                "specialties": data.get("specialties", []),
                "active": True
            }}
        )

        await log_audit_event(
            action=AUDIT_ACTIONS["COUNSELOR_CREATED"],
            entity_type="user",
            entity_id=str(existing["_id"]),
            user_id=admin["_id"],
            user_email=admin.get("email"),
            details={"upgraded_from_existing": True},
            ip_address=request.client.host if request.client else None
        )

        return {"id": str(existing["_id"]), "message": "User upgraded to counselor"}

    counselor_doc = {
        "email": email,
        "password_hash": hash_password(data.get("password", "TempPass123!")),
        "first_name": data.get("first_name", ""),
        "last_name": data.get("last_name", ""),
        "role": "counselor",
        "title": data.get("title", ""),
        "bio": data.get("bio", ""),
        "specialties": data.get("specialties", []),
        "active": True,
        "verified": True,
        "created_at": datetime.now(timezone.utc)
    }

    result = await db.users.insert_one(counselor_doc)

    await log_audit_event(
        action=AUDIT_ACTIONS["COUNSELOR_CREATED"],
        entity_type="user",
        entity_id=str(result.inserted_id),
        user_id=admin["_id"],
        user_email=admin.get("email"),
        ip_address=request.client.host if request.client else None
    )

    return {"id": str(result.inserted_id), "message": "Counselor created"}

@router.put("/admin/counselors/{counselor_id}")
async def update_counselor(request: Request, counselor_id: str):
    """Update counselor (admin only)"""
    await get_current_admin(request)
    data = await request.json()

    update_fields = {}
    for field in ["first_name", "last_name", "title", "bio", "specialties", "active"]:
        if field in data:
            update_fields[field] = data[field]

    if update_fields:
        await db.users.update_one(
            {"_id": ObjectId(counselor_id)},
            {"$set": update_fields}
        )

    return {"message": "Counselor updated"}

@router.delete("/admin/counselors/{counselor_id}")
async def delete_counselor(request: Request, counselor_id: str):
    """Deactivate counselor (admin only)"""
    await get_current_admin(request)

    # Don't delete, just deactivate
    await db.users.update_one(
        {"_id": ObjectId(counselor_id)},
        {"$set": {"active": False}}
    )

    return {"message": "Counselor deactivated"}

@router.post("/admin/counselors/{counselor_id}/assign/{member_id}")
async def assign_counselor(request: Request, counselor_id: str, member_id: str):
    """Assign counselor to member"""
    admin = await get_current_admin(request)

    counselor = await db.users.find_one({"_id": ObjectId(counselor_id), "role": "counselor"})
    if not counselor:
        raise HTTPException(status_code=404, detail="Counselor not found")

    # Get member info
    member = await db.users.find_one({"_id": ObjectId(member_id)})
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    await db.users.update_one(
        {"_id": ObjectId(member_id)},
        {"$set": {
            "assigned_counselor_id": ObjectId(counselor_id),
            "pipeline_stage": "counselor_assigned"
        }}
    )

    await log_audit_event(
        action=AUDIT_ACTIONS["COUNSELOR_ASSIGNED"],
        entity_type="user",
        entity_id=member_id,
        user_id=admin["_id"],
        user_email=admin.get("email"),
        details={"counselor_id": counselor_id},
        ip_address=request.client.host if request.client else None
    )

    # Send notification email to member
    counselor_name = f"{counselor.get('first_name', '')} {counselor.get('last_name', '')}".strip()
    asyncio.create_task(send_counselor_assigned_email(
        member.get("email"),
        member.get("first_name", "Member"),
        counselor_name
    ))

    return {"message": "Counselor assigned to member"}

@router.delete("/admin/counselors/{counselor_id}/unassign/{member_id}")
async def unassign_counselor(request: Request, counselor_id: str, member_id: str):
    """Unassign counselor from member"""
    admin = await get_current_admin(request)

    await db.users.update_one(
        {"_id": ObjectId(member_id)},
        {"$unset": {"assigned_counselor_id": ""}}
    )

    await log_audit_event(
        action=AUDIT_ACTIONS["COUNSELOR_UNASSIGNED"],
        entity_type="user",
        entity_id=member_id,
        user_id=admin["_id"],
        user_email=admin.get("email"),
        details={"counselor_id": counselor_id},
        ip_address=request.client.host if request.client else None
    )

    return {"message": "Counselor unassigned"}

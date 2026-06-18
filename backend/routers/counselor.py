# Counselor router for Silent Honor Foundation
import asyncio
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException, Request
from bson import ObjectId

from middleware.auth_middleware import get_current_counselor, get_current_admin
from middleware.logging_middleware import log_audit_event, AUDIT_ACTIONS
from fastapi import UploadFile, File, Form
from utils.auth import hash_password
from utils.validators import CounselorRequest
from utils.email import send_counselor_assigned_email, send_dispute_update_email
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


def sanitize_doc(obj):
    """Recursively convert ObjectId and datetime to JSON-safe types."""
    if isinstance(obj, ObjectId):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: sanitize_doc(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize_doc(i) for i in obj]
    return obj

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
    now = datetime.now(timezone.utc)

    # Batch: unread messages from each member to this counselor
    pipeline = [
        {"$match": {"to_user_id": counselor_oid, "from_user_id": {"$in": member_ids}, "read": False}},
        {"$group": {"_id": "$from_user_id", "count": {"$sum": 1}}}
    ]
    unread_docs = await db.messages.aggregate(pipeline).to_list(200)
    unread_map = {str(doc["_id"]): doc["count"] for doc in unread_docs}

    # Batch: overdue tasks per member
    overdue_pipeline = [
        {"$match": {"counselor_id": counselor_oid, "member_id": {"$in": member_ids},
                    "due_date": {"$lt": now}, "completed": False}},
        {"$group": {"_id": "$member_id", "count": {"$sum": 1}}}
    ]
    overdue_docs = await db.tasks.aggregate(overdue_pipeline).to_list(200)
    overdue_map = {str(doc["_id"]): doc["count"] for doc in overdue_docs}

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
                "overdue_task": overdue_map.get(mid, 0) > 0,
                "new_document": False  # Phase 8 placeholder
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

    member.pop("password_hash", None)
    member = sanitize_doc(member)

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
    """Get statistics and recent activity for counselor dashboard"""
    counselor = await get_current_counselor(request)
    counselor_oid = ObjectId(counselor["_id"])
    now = datetime.now(timezone.utc)

    # Caseload capacity
    counselor_doc = await db.users.find_one({"_id": counselor_oid}, {"max_caseload": 1})
    max_caseload = (counselor_doc or {}).get("max_caseload", 12)
    assigned_count = await db.users.count_documents({"assigned_counselor_id": counselor_oid, "role": "member"})
    open_slots = max(0, max_caseload - assigned_count)

    # Build member ID list + name map for activity feed
    member_docs = await db.users.find(
        {"assigned_counselor_id": counselor_oid, "role": "member"},
        {"_id": 1, "first_name": 1, "last_name": 1}
    ).to_list(500)
    member_ids = [m["_id"] for m in member_docs]
    member_name_map = {
        str(m["_id"]): f"{m.get('first_name', '')} {m.get('last_name', '')}".strip()
        for m in member_docs
    }

    # Waitlist count: members who applied for a program and have no counselor yet
    waitlist_count = await db.users.count_documents({
        "role": "member",
        "$and": [
            {"$or": [{"assigned_counselor_id": {"$exists": False}}, {"assigned_counselor_id": None}]},
            {"$or": [{"credit_repair_stage": "cr_waitlist"}, {"financial_counseling_stage": "fc_waitlist"}]}
        ]
    })

    # Tasks due today or overdue (not yet completed)
    today_end = datetime(now.year, now.month, now.day, 23, 59, 59, tzinfo=timezone.utc)
    tasks_due = await db.tasks.count_documents({
        "counselor_id": counselor_oid,
        "completed": False,
        "due_date": {"$lte": today_end}
    })

    # Unread messages
    unread = await db.messages.count_documents({"to_user_id": counselor_oid, "read": False})

    # Recent activity — notes, disputes, completed tasks
    activity = []

    # Notes added by this counselor (created_by field)
    recent_notes = await db.intake_notes.find(
        {"created_by": counselor_oid},
        {"member_id": 1, "content": 1, "created_at": 1}
    ).sort("created_at", -1).limit(8).to_list(8)
    for n in recent_notes:
        mid = str(n.get("member_id", ""))
        content = n.get("content", "")
        preview = content[:60] + ("…" if len(content) > 60 else "")
        dt = n.get("created_at")
        activity.append({
            "type": "note",
            "member_id": mid,
            "member_name": member_name_map.get(mid, "Member"),
            "description": preview,
            "date": dt.isoformat() if dt else None
        })

    # Disputes for counselor's members (disputes use user_id for member)
    if member_ids:
        recent_disputes = await db.disputes.find(
            {"user_id": {"$in": member_ids}},
            {"user_id": 1, "account_name": 1, "bureau": 1, "status": 1, "created_at": 1}
        ).sort("created_at", -1).limit(8).to_list(8)
        for d in recent_disputes:
            mid = str(d.get("user_id", ""))
            bureau_label = {"equifax": "Equifax", "experian": "Experian", "transunion": "TransUnion"}.get(d.get("bureau", ""), d.get("bureau", ""))
            dt = d.get("created_at")
            activity.append({
                "type": "dispute",
                "member_id": mid,
                "member_name": member_name_map.get(mid, "Member"),
                "description": f"{d.get('account_name', 'Account')} · {bureau_label} · {d.get('status', '')}",
                "date": dt.isoformat() if dt else None
            })

    # Recently completed tasks by this counselor
    recent_tasks = await db.tasks.find(
        {"counselor_id": counselor_oid, "completed": True},
        {"member_id": 1, "title": 1, "completed_at": 1}
    ).sort("completed_at", -1).limit(5).to_list(5)
    for t in recent_tasks:
        mid = str(t.get("member_id", ""))
        dt = t.get("completed_at")
        activity.append({
            "type": "task_done",
            "member_id": mid,
            "member_name": member_name_map.get(mid, "Member") if mid else "",
            "description": t.get("title", ""),
            "date": dt.isoformat() if dt else None
        })

    activity.sort(key=lambda x: x.get("date") or "", reverse=True)

    return {
        "assigned_members": assigned_count,
        "max_caseload": max_caseload,
        "open_slots": open_slots,
        "waitlist_count": waitlist_count,
        "tasks_due": tasks_due,
        "unread_messages": unread,
        "recent_activity": activity[:15]
    }

BUREAUS = ["equifax", "experian", "transunion"]
DISPUTE_STATUSES = ["draft", "pending", "sent", "responded", "closed"]

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


@router.get("/counselor/members/{member_id}/credit-scores")
async def get_member_credit_scores(request: Request, member_id: str):
    """List credit scores normalizing old all-3-bureau schema and new per-bureau schema"""
    counselor = await get_current_counselor(request)

    member = await db.users.find_one({
        "_id": ObjectId(member_id),
        "assigned_counselor_id": ObjectId(counselor["_id"])
    }, {"_id": 1})
    if not member:
        raise HTTPException(status_code=404, detail="Member not found or not assigned to you")

    oid = ObjectId(member_id)
    # Query both old schema (user_id field) and new schema (member_id field)
    docs = await db.credit_scores.find(
        {"$or": [{"user_id": oid}, {"member_id": oid}]}
    ).to_list(200)

    history = []
    for doc in docs:
        bureau = doc.get("bureau")
        if bureau:
            # New per-bureau schema
            date_val = doc.get("date_pulled") or doc.get("created_at")
            history.append({
                "id": str(doc["_id"]),
                "bureau": bureau,
                "score": doc.get("score"),
                "date_pulled": date_val.isoformat() if date_val else None
            })
        else:
            # Old all-3-bureau schema: expand each doc into up to 3 per-bureau entries
            date_val = doc.get("date") or doc.get("created_at")
            date_iso = date_val.isoformat() if date_val else None
            for b in BUREAUS:
                val = doc.get(b)
                if val is not None:
                    history.append({
                        "id": str(doc["_id"]) + "_" + b,
                        "bureau": b,
                        "score": val,
                        "date_pulled": date_iso
                    })

    history.sort(key=lambda x: x["date_pulled"] or "", reverse=True)

    # First occurrence of each bureau in date-descending order = latest
    latest = {}
    for entry in history:
        b = entry["bureau"]
        if b not in latest:
            latest[b] = {"score": entry["score"], "date": entry["date_pulled"]}

    return {"latest": latest, "history": history}


@router.post("/counselor/members/{member_id}/credit-scores")
async def add_member_credit_score(request: Request, member_id: str):
    """Add a single-bureau credit score entry for an assigned member"""
    counselor = await get_current_counselor(request)
    data = await request.json()

    member = await db.users.find_one({
        "_id": ObjectId(member_id),
        "assigned_counselor_id": ObjectId(counselor["_id"])
    }, {"_id": 1})
    if not member:
        raise HTTPException(status_code=404, detail="Member not found or not assigned to you")

    bureau = data.get("bureau")
    if bureau not in BUREAUS:
        raise HTTPException(status_code=400, detail=f"bureau must be one of: {BUREAUS}")

    try:
        score = int(data.get("score"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="score must be an integer")
    if not (300 <= score <= 850):
        raise HTTPException(status_code=400, detail="score must be between 300 and 850")

    date_pulled_str = data.get("date_pulled")
    try:
        date_pulled = datetime.fromisoformat(str(date_pulled_str)) if date_pulled_str else datetime.now(timezone.utc)
        if date_pulled.tzinfo is None:
            date_pulled = date_pulled.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="date_pulled must be a valid date (YYYY-MM-DD)")

    now = datetime.now(timezone.utc)
    await db.credit_scores.insert_one({
        "member_id": ObjectId(member_id),
        "bureau": bureau,
        "score": score,
        "date_pulled": date_pulled,
        "created_at": now
    })

    await db.users.update_one(
        {"_id": ObjectId(member_id)},
        {"$set": {"last_activity_date": now}}
    )

    return {"message": "Credit score added"}


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


@router.get("/counselor/tasks")
async def get_counselor_tasks(request: Request):
    """Get all tasks for this counselor across the caseload"""
    counselor = await get_current_counselor(request)
    counselor_oid = ObjectId(counselor["_id"])

    tasks = await db.tasks.find(
        {"counselor_id": counselor_oid}
    ).sort("due_date", 1).to_list(500)

    # Batch-fetch member names
    member_ids = list({t["member_id"] for t in tasks})
    members = await db.users.find(
        {"_id": {"$in": member_ids}},
        {"_id": 1, "first_name": 1, "last_name": 1}
    ).to_list(200)
    member_map = {
        str(m["_id"]): f"{m.get('first_name', '')} {m.get('last_name', '')}".strip()
        for m in members
    }

    now = datetime.now(timezone.utc)
    result = []
    for t in tasks:
        mid = str(t["member_id"])
        due = t.get("due_date")
        completed = t.get("completed", False)
        overdue = not completed and due and due < now
        result.append({
            "id": str(t["_id"]),
            "title": t.get("title", ""),
            "task_type": t.get("task_type", "custom"),
            "member_id": mid,
            "member_name": member_map.get(mid, "Unknown"),
            "dispute_id": str(t["dispute_id"]) if t.get("dispute_id") else None,
            "due_date": due.isoformat() if due else None,
            "completed": completed,
            "completed_at": t.get("completed_at").isoformat() if t.get("completed_at") else None,
            "overdue": overdue,
            "created_at": t.get("created_at").isoformat() if t.get("created_at") else None
        })

    return result


@router.post("/counselor/tasks")
async def create_counselor_task(request: Request):
    """Create a custom task for a member on this counselor's caseload"""
    counselor = await get_current_counselor(request)
    data = await request.json()

    member_id = data.get("member_id", "")
    try:
        member_oid = ObjectId(member_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid member_id")

    member = await db.users.find_one({
        "_id": member_oid,
        "assigned_counselor_id": ObjectId(counselor["_id"])
    }, {"_id": 1})
    if not member:
        raise HTTPException(status_code=404, detail="Member not found or not assigned to you")

    title = (data.get("title") or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="title is required")

    due_date_str = data.get("due_date")
    try:
        due_date = datetime.fromisoformat(str(due_date_str)) if due_date_str else datetime.now(timezone.utc)
        if due_date.tzinfo is None:
            due_date = due_date.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="due_date must be a valid date (YYYY-MM-DD)")

    now = datetime.now(timezone.utc)
    await db.tasks.insert_one({
        "counselor_id": ObjectId(counselor["_id"]),
        "member_id": member_oid,
        "title": title,
        "task_type": "custom",
        "dispute_id": None,
        "due_date": due_date,
        "completed": False,
        "completed_at": None,
        "created_at": now
    })

    return {"message": "Task created"}


@router.patch("/counselor/tasks/{task_id}/complete")
async def toggle_task_complete(request: Request, task_id: str):
    """Mark a task complete or incomplete"""
    counselor = await get_current_counselor(request)
    data = await request.json()

    try:
        oid = ObjectId(task_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid task ID")

    task = await db.tasks.find_one({"_id": oid, "counselor_id": ObjectId(counselor["_id"])})
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    completed = bool(data.get("completed", True))
    now = datetime.now(timezone.utc)
    await db.tasks.update_one(
        {"_id": oid},
        {"$set": {"completed": completed, "completed_at": now if completed else None}}
    )
    return {"message": "Task updated", "completed": completed}


@router.delete("/counselor/tasks/{task_id}")
async def delete_counselor_task(request: Request, task_id: str):
    """Delete a task"""
    counselor = await get_current_counselor(request)

    try:
        oid = ObjectId(task_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid task ID")

    result = await db.tasks.delete_one({"_id": oid, "counselor_id": ObjectId(counselor["_id"])})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Task not found")

    return {"message": "Task deleted"}


ACCOUNT_TYPES = ["revolving", "installment", "collection", "mortgage", "auto", "other"]
ACCOUNT_STATUSES = ["open", "closed", "collection"]
GAME_PLAN_ACTIONS = ["dispute", "goodwill", "no_action", "debt_validation", "pay_for_delete", "cross_bureau_dispute"]


def compute_game_plan_action(account, today):
    """Rules engine: returns recommended action, rationale, and priority for one credit account."""
    status = account.get("account_status", "open")
    acct_type = account.get("account_type", "revolving")
    has_late = account.get("has_late_payments", False)
    late_date = account.get("late_payment_date")
    inaccuracy = account.get("cross_bureau_inaccuracy", False)
    override = account.get("counselor_action_override")

    # Compute days since last late payment
    days_since = None
    if has_late and late_date:
        try:
            ld = late_date.date() if hasattr(late_date, "date") else datetime.fromisoformat(str(late_date)).date()
            days_since = (today - ld).days
        except Exception:
            pass

    # Rules (priority order)
    if inaccuracy:
        action, priority = "cross_bureau_dispute", "high"
        rationale = ("Cross-bureau inaccuracy flagged. Dispute with all reporting bureaus simultaneously "
                     "via certified mail — same account reported differently across bureaus is a clear FCRA violation.")
    elif acct_type == "collection" or status == "collection":
        action, priority = "debt_validation", "high"
        rationale = ("Collection account: send a certified debt validation letter demanding proof the debt is yours and the amount is correct. "
                     "⚠️ Verify the SOL for your state before making any payment — paying can reset the clock.")
    elif status == "closed":
        action, priority = "dispute", "medium"
        rationale = ("Closed account: verify all reported information is accurate under the FCRA. "
                     "Any inaccuracy — balance, payment history, dates — is disputable via certified mail.")
    elif has_late and days_since is not None and days_since < 180:
        action, priority = "goodwill", "medium"
        rationale = (f"Open account with a late payment {days_since} days ago. "
                     "Send a goodwill letter to the creditor requesting removal as a courtesy for your payment history.")
    elif has_late and days_since is not None and days_since >= 180:
        action, priority = "no_action", "low"
        rationale = (f"Late payment is {days_since} days old — past the 180-day threshold. "
                     "Allow it to age off naturally; intervention at this stage rarely improves the outcome.")
    else:
        action, priority = "pay_for_delete", "low"
        rationale = ("No clear dispute grounds identified. If a balance remains, negotiate a pay-for-delete agreement in writing "
                     "before making any payment — get the removal promise on paper first.")

    return {
        "recommended_action": action,
        "rationale": rationale,
        "priority": priority,
        "final_action": override if override and override in GAME_PLAN_ACTIONS else action,
        "is_overridden": bool(override and override in GAME_PLAN_ACTIONS and override != action)
    }


@router.get("/counselor/waitlist")
async def get_waitlist(request: Request):
    """Get members who have applied for a program and are awaiting counselor assignment"""
    counselor = await get_current_counselor(request)
    counselor_oid = ObjectId(counselor["_id"])

    counselor_doc = await db.users.find_one({"_id": counselor_oid}, {"max_caseload": 1})
    max_caseload = (counselor_doc or {}).get("max_caseload", 12)
    current_count = await db.users.count_documents({"assigned_counselor_id": counselor_oid, "role": "member"})

    # Only members who have applied for a program (cr_waitlist or fc_waitlist) and have no counselor yet
    no_counselor = {"$or": [{"assigned_counselor_id": {"$exists": False}}, {"assigned_counselor_id": None}]}
    has_application = {"$or": [
        {"credit_repair_stage": "cr_waitlist"},
        {"financial_counseling_stage": "fc_waitlist"}
    ]}
    members = await db.users.find(
        {"role": "member", "$and": [no_counselor, has_application]},
        {"_id": 1, "first_name": 1, "last_name": 1, "email": 1, "branch": 1,
         "state": 1, "credit_repair_stage": 1, "financial_counseling_stage": 1, "created_at": 1}
    ).sort("created_at", 1).to_list(500)

    def program_label(m):
        has_cr = m.get("credit_repair_stage") == "cr_waitlist"
        has_fc = m.get("financial_counseling_stage") == "fc_waitlist"
        if has_cr and has_fc:
            return "Credit Repair & Financial Counseling"
        if has_cr:
            return "Credit Repair"
        return "Financial Counseling"

    return {
        "capacity": {
            "current": current_count,
            "max": max_caseload,
            "available": max(0, max_caseload - current_count)
        },
        "members": [{
            "id": str(m["_id"]),
            "name": f"{m.get('first_name', '')} {m.get('last_name', '')}".strip(),
            "email": m.get("email", ""),
            "branch": m.get("branch"),
            "state": m.get("state"),
            "program": program_label(m),
            "has_cr": m.get("credit_repair_stage") == "cr_waitlist",
            "has_fc": m.get("financial_counseling_stage") == "fc_waitlist",
            "created_at": m.get("created_at").isoformat() if m.get("created_at") else None
        } for m in members]
    }


@router.post("/counselor/waitlist/{member_id}/claim")
async def claim_member(request: Request, member_id: str):
    """Self-assign an unassigned member from the waitlist"""
    counselor = await get_current_counselor(request)
    counselor_oid = ObjectId(counselor["_id"])

    # Check capacity before claiming
    counselor_doc = await db.users.find_one({"_id": counselor_oid}, {"max_caseload": 1})
    max_caseload = (counselor_doc or {}).get("max_caseload", 12)
    current_count = await db.users.count_documents({"assigned_counselor_id": counselor_oid, "role": "member"})
    if current_count >= max_caseload:
        raise HTTPException(
            status_code=400,
            detail=f"You are at your maximum caseload ({max_caseload} members). Contact an admin to increase your limit."
        )

    member = await db.users.find_one({"_id": ObjectId(member_id), "role": "member"})
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    if member.get("assigned_counselor_id"):
        raise HTTPException(status_code=409, detail="This member was just claimed by another counselor")

    # Derive program_track from which application is waiting
    if member.get("credit_repair_stage") == "cr_waitlist":
        program_track = "credit_repair"
    elif member.get("financial_counseling_stage") == "fc_waitlist":
        program_track = "financial_counseling"
    else:
        program_track = member.get("program_track") or "onboarding"

    now = datetime.now(timezone.utc)
    await db.users.update_one(
        {"_id": ObjectId(member_id)},
        {"$set": {
            "assigned_counselor_id": counselor_oid,
            "pipeline_stage": "counselor_assigned",
            "program_track": program_track,
            "last_activity_date": now
        }}
    )

    # Notify member by email (fire-and-forget — same pattern as admin assign)
    counselor_name = f"{counselor.get('first_name', '')} {counselor.get('last_name', '')}".strip()
    asyncio.create_task(send_counselor_assigned_email(
        member.get("email"),
        member.get("first_name", "Member"),
        counselor_name
    ))

    return {"message": f"{member.get('first_name', 'Member')} added to your caseload"}


@router.get("/counselor/members/{member_id}/game-plan")
async def get_member_game_plan(request: Request, member_id: str):
    """Return credit accounts with auto-computed game plan recommendations"""
    counselor = await get_current_counselor(request)

    member = await db.users.find_one({
        "_id": ObjectId(member_id),
        "assigned_counselor_id": ObjectId(counselor["_id"])
    }, {"_id": 1})
    if not member:
        raise HTTPException(status_code=404, detail="Member not found or not assigned to you")

    accounts = await db.credit_accounts.find(
        {"member_id": ObjectId(member_id)}
    ).sort("added_at", 1).to_list(200)

    today = datetime.now(timezone.utc).date()
    result = []
    for a in accounts:
        plan = compute_game_plan_action(a, today)
        late_date = a.get("late_payment_date")
        result.append({
            "id": str(a["_id"]),
            "creditor_name": a.get("creditor_name", ""),
            "account_type": a.get("account_type", "other"),
            "account_status": a.get("account_status", "open"),
            "bureaus": a.get("bureaus", []),
            "balance": a.get("balance"),
            "has_late_payments": a.get("has_late_payments", False),
            "late_payment_date": late_date.isoformat()[:10] if late_date else None,
            "cross_bureau_inaccuracy": a.get("cross_bureau_inaccuracy", False),
            "counselor_action_override": a.get("counselor_action_override"),
            "notes": a.get("notes", ""),
            **plan
        })

    return result


@router.post("/counselor/members/{member_id}/credit-accounts")
async def add_credit_account(request: Request, member_id: str):
    """Add a credit account for game plan analysis"""
    counselor = await get_current_counselor(request)
    data = await request.json()

    member = await db.users.find_one({
        "_id": ObjectId(member_id),
        "assigned_counselor_id": ObjectId(counselor["_id"])
    }, {"_id": 1})
    if not member:
        raise HTTPException(status_code=404, detail="Member not found or not assigned to you")

    creditor_name = (data.get("creditor_name") or "").strip()
    if not creditor_name:
        raise HTTPException(status_code=400, detail="creditor_name is required")

    acct_type = data.get("account_type", "other")
    if acct_type not in ACCOUNT_TYPES:
        raise HTTPException(status_code=400, detail=f"account_type must be one of: {ACCOUNT_TYPES}")

    acct_status = data.get("account_status", "open")
    if acct_status not in ACCOUNT_STATUSES:
        raise HTTPException(status_code=400, detail=f"account_status must be one of: {ACCOUNT_STATUSES}")

    bureaus = [b for b in (data.get("bureaus") or []) if b in BUREAUS]

    late_payment_date = None
    if data.get("late_payment_date"):
        try:
            lpd = datetime.fromisoformat(str(data["late_payment_date"]))
            late_payment_date = lpd if lpd.tzinfo else lpd.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            pass

    try:
        balance = float(data["balance"]) if data.get("balance") not in (None, "") else None
    except (TypeError, ValueError):
        balance = None

    now = datetime.now(timezone.utc)
    await db.credit_accounts.insert_one({
        "member_id": ObjectId(member_id),
        "counselor_id": ObjectId(counselor["_id"]),
        "creditor_name": creditor_name,
        "account_type": acct_type,
        "account_status": acct_status,
        "bureaus": bureaus,
        "balance": balance,
        "has_late_payments": bool(data.get("has_late_payments", False)),
        "late_payment_date": late_payment_date,
        "cross_bureau_inaccuracy": bool(data.get("cross_bureau_inaccuracy", False)),
        "counselor_action_override": None,
        "notes": (data.get("notes") or "").strip(),
        "added_at": now
    })

    await db.users.update_one(
        {"_id": ObjectId(member_id)},
        {"$set": {"last_activity_date": now}}
    )
    return {"message": "Account added"}


@router.patch("/counselor/credit-accounts/{account_id}")
async def update_credit_account(request: Request, account_id: str):
    """Update a credit account (fields or action override)"""
    counselor = await get_current_counselor(request)
    data = await request.json()

    try:
        oid = ObjectId(account_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid account ID")

    account = await db.credit_accounts.find_one({"_id": oid})
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    member = await db.users.find_one({
        "_id": account["member_id"],
        "assigned_counselor_id": ObjectId(counselor["_id"])
    }, {"_id": 1})
    if not member:
        raise HTTPException(status_code=403, detail="Not authorized to update this account")

    update_fields = {}
    for field in ["creditor_name", "account_type", "account_status", "notes", "counselor_action_override"]:
        if field in data:
            update_fields[field] = data[field] or None if field == "counselor_action_override" else data[field]

    if "bureaus" in data:
        update_fields["bureaus"] = [b for b in (data["bureaus"] or []) if b in BUREAUS]

    if "has_late_payments" in data:
        update_fields["has_late_payments"] = bool(data["has_late_payments"])

    if "cross_bureau_inaccuracy" in data:
        update_fields["cross_bureau_inaccuracy"] = bool(data["cross_bureau_inaccuracy"])

    if "balance" in data:
        try:
            update_fields["balance"] = float(data["balance"]) if data["balance"] not in (None, "") else None
        except (TypeError, ValueError):
            pass

    if "late_payment_date" in data:
        lpd = data.get("late_payment_date")
        if lpd:
            try:
                d = datetime.fromisoformat(str(lpd))
                update_fields["late_payment_date"] = d if d.tzinfo else d.replace(tzinfo=timezone.utc)
            except (ValueError, TypeError):
                pass
        else:
            update_fields["late_payment_date"] = None

    if update_fields:
        update_fields["updated_at"] = datetime.now(timezone.utc)
        await db.credit_accounts.update_one({"_id": oid}, {"$set": update_fields})

    return {"message": "Account updated"}


@router.delete("/counselor/credit-accounts/{account_id}")
async def delete_credit_account(request: Request, account_id: str):
    """Delete a credit account"""
    counselor = await get_current_counselor(request)

    try:
        oid = ObjectId(account_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid account ID")

    account = await db.credit_accounts.find_one({"_id": oid})
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    member = await db.users.find_one({
        "_id": account["member_id"],
        "assigned_counselor_id": ObjectId(counselor["_id"])
    }, {"_id": 1})
    if not member:
        raise HTTPException(status_code=403, detail="Not authorized to delete this account")

    await db.credit_accounts.delete_one({"_id": oid})
    return {"message": "Account deleted"}


@router.get("/counselor/members/{member_id}/disputes")
async def get_member_disputes(request: Request, member_id: str):
    """List disputes for an assigned member"""
    counselor = await get_current_counselor(request)

    member = await db.users.find_one({
        "_id": ObjectId(member_id),
        "assigned_counselor_id": ObjectId(counselor["_id"])
    }, {"_id": 1})
    if not member:
        raise HTTPException(status_code=404, detail="Member not found or not assigned to you")

    disputes = await db.disputes.find(
        {"user_id": ObjectId(member_id)}
    ).sort("created_at", -1).to_list(100)

    return [{
        "id": str(d["_id"]),
        "bureau": d.get("bureau", ""),
        "account_name": d.get("account_name", ""),
        "account_number": d.get("account_number", ""),
        "dispute_reason": d.get("dispute_reason", ""),
        "status": d.get("status", "draft"),
        "date_sent": d.get("date_sent").isoformat() if d.get("date_sent") else None,
        "date_response": d.get("date_response").isoformat() if d.get("date_response") else None,
        "response_outcome": d.get("response_outcome"),
        "tracking_number": d.get("tracking_number"),
        "notes": d.get("notes", ""),
        "created_at": d.get("created_at").isoformat() if d.get("created_at") else None
    } for d in disputes]


@router.post("/counselor/members/{member_id}/disputes")
async def create_member_dispute(request: Request, member_id: str):
    """Create a dispute on behalf of an assigned member"""
    counselor = await get_current_counselor(request)
    data = await request.json()

    member = await db.users.find_one({
        "_id": ObjectId(member_id),
        "assigned_counselor_id": ObjectId(counselor["_id"])
    }, {"_id": 1})
    if not member:
        raise HTTPException(status_code=404, detail="Member not found or not assigned to you")

    bureau = data.get("bureau", "")
    if bureau not in BUREAUS:
        raise HTTPException(status_code=400, detail="bureau must be equifax, experian, or transunion")

    account_name = (data.get("account_name") or "").strip()
    if not account_name:
        raise HTTPException(status_code=400, detail="account_name is required")

    now = datetime.now(timezone.utc)
    dispute_result = await db.disputes.insert_one({
        "user_id": ObjectId(member_id),
        "bureau": bureau,
        "account_name": account_name,
        "account_number": (data.get("account_number") or "").strip(),
        "dispute_reason": data.get("dispute_reason", ""),
        "status": "draft",
        "date_sent": None,
        "date_response": None,
        "response_outcome": None,
        "tracking_number": None,
        "notes": (data.get("notes") or "").strip(),
        "created_by_counselor": ObjectId(counselor["_id"]),
        "created_at": now
    })

    # Auto-create a task: send certified dispute letter, due in 7 days
    bureau_label = "TransUnion" if bureau == "transunion" else bureau.capitalize()
    await db.tasks.insert_one({
        "counselor_id": ObjectId(counselor["_id"]),
        "member_id": ObjectId(member_id),
        "title": f"Send certified dispute letter — {account_name} @ {bureau_label}",
        "task_type": "dispute_letter",
        "dispute_id": dispute_result.inserted_id,
        "due_date": now + timedelta(days=7),
        "completed": False,
        "completed_at": None,
        "created_at": now
    })

    await db.users.update_one(
        {"_id": ObjectId(member_id)},
        {"$set": {"last_activity_date": now}}
    )

    return {"message": "Dispute created"}


@router.patch("/counselor/disputes/{dispute_id}")
async def update_member_dispute(request: Request, dispute_id: str):
    """Update a dispute. Hard rule: status=sent requires a tracking_number."""
    counselor = await get_current_counselor(request)
    data = await request.json()

    try:
        oid = ObjectId(dispute_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid dispute ID")

    dispute = await db.disputes.find_one({"_id": oid})
    if not dispute:
        raise HTTPException(status_code=404, detail="Dispute not found")

    member = await db.users.find_one({
        "_id": dispute["user_id"],
        "assigned_counselor_id": ObjectId(counselor["_id"])
    }, {"_id": 1})
    if not member:
        raise HTTPException(status_code=403, detail="Not authorized to update this dispute")

    new_status = data.get("status")
    if new_status and new_status not in DISPUTE_STATUSES:
        raise HTTPException(status_code=400, detail=f"status must be one of: {DISPUTE_STATUSES}")

    # Hard rule: certified mail tracking number required to mark as sent
    incoming_tracking = (data.get("tracking_number") or "").strip()
    existing_tracking = (dispute.get("tracking_number") or "").strip()
    effective_tracking = incoming_tracking or existing_tracking
    if new_status == "sent" and not effective_tracking:
        raise HTTPException(
            status_code=400,
            detail="A certified mail tracking number is required before marking as Sent"
        )

    update_fields = {}
    for field in ["bureau", "account_name", "account_number", "dispute_reason",
                  "status", "tracking_number", "notes", "response_outcome"]:
        if field in data:
            update_fields[field] = data[field]

    for date_field in ["date_sent", "date_response"]:
        val = data.get(date_field)
        if val:
            try:
                update_fields[date_field] = datetime.fromisoformat(val.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                pass

    # Auto-stamp date_sent when status first moves to sent
    if new_status == "sent" and not dispute.get("date_sent") and "date_sent" not in update_fields:
        update_fields["date_sent"] = datetime.now(timezone.utc)

    now = datetime.now(timezone.utc)
    update_fields["updated_at"] = now
    await db.disputes.update_one({"_id": oid}, {"$set": update_fields})

    await db.users.update_one(
        {"_id": dispute["user_id"]},
        {"$set": {"last_activity_date": now}}
    )

    # Email member on significant status transitions
    if new_status in ("sent", "responded", "resolved", "rejected"):
        member_doc = await db.users.find_one({"_id": dispute["user_id"]}, {"email": 1, "first_name": 1})
        if member_doc and member_doc.get("email"):
            asyncio.create_task(send_dispute_update_email(
                member_doc["email"],
                member_doc.get("first_name", "Member"),
                dispute.get("account_name", "Account"),
                dispute.get("bureau", "Bureau"),
                new_status
            ))

    return {"message": "Dispute updated"}


@router.delete("/counselor/disputes/{dispute_id}")
async def delete_member_dispute(request: Request, dispute_id: str):
    """Delete a dispute (counselor must be assigned to that member)"""
    counselor = await get_current_counselor(request)

    try:
        oid = ObjectId(dispute_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid dispute ID")

    dispute = await db.disputes.find_one({"_id": oid})
    if not dispute:
        raise HTTPException(status_code=404, detail="Dispute not found")

    member = await db.users.find_one({
        "_id": dispute["user_id"],
        "assigned_counselor_id": ObjectId(counselor["_id"])
    }, {"_id": 1})
    if not member:
        raise HTTPException(status_code=403, detail="Not authorized to delete this dispute")

    await db.disputes.delete_one({"_id": oid})
    return {"message": "Dispute deleted"}


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

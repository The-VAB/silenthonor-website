# Members router for Silent Honor Foundation
import asyncio
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request, UploadFile, File
from bson import ObjectId

from middleware.auth_middleware import get_current_user
from middleware.logging_middleware import log_audit_event, AUDIT_ACTIONS
from utils.storage import upload_dd214 as storage_upload_dd214
from utils.email import send_admin_notification

router = APIRouter(prefix="/api/member", tags=["Members"])

# Database reference
db = None

def set_db(database):
    global db
    db = database

@router.get("/profile")
async def get_profile(request: Request):
    """Get current member's profile"""
    user = await get_current_user(request)
    return user

@router.put("/profile")
async def update_profile(request: Request):
    """Update member profile"""
    user = await get_current_user(request)
    data = await request.json()

    allowed_fields = ["first_name", "last_name", "phone", "state", "email_preferences"]
    update_data = {k: v for k, v in data.items() if k in allowed_fields}

    if update_data:
        await db.users.update_one(
            {"_id": ObjectId(user["_id"])},
            {"$set": update_data}
        )

    return {"message": "Profile updated successfully"}

@router.get("/counselor")
async def get_assigned_counselor(request: Request):
    """Get member's assigned counselor"""
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

@router.get("/courses")
async def get_courses(request: Request):
    """Get member's courses with progress — verified members only"""
    user = await get_current_user(request)

    if not user.get("verified"):
        raise HTTPException(status_code=403, detail="Your account must be verified to access courses.")

    progress = await db.course_progress.find(
        {"user_id": ObjectId(user["_id"])},
        {"course_id": 1, "completed_lessons": 1, "updated_at": 1}
    ).to_list(100)

    # Get courses from database
    db_courses = await db.courses.find({"status": {"$in": ["live", "published", "coming_soon"]}}).sort("created_at", 1).to_list(100)

    courses = []
    for c in db_courses:
        lesson_count = await db.lessons.count_documents({"course_id": str(c["_id"])})
        courses.append({
            "id": str(c["_id"]),
            "title": c.get("title", ""),
            "total_lessons": lesson_count,
            "status": c.get("status", "draft")
        })

    # Merge progress
    progress_map = {str(p.get("course_id")): p for p in progress}
    for course in courses:
        p = progress_map.get(course["id"], {})
        completed = p.get("completed_lessons", [])
        if isinstance(completed, int):
            course["completed_lessons"] = completed
        else:
            course["completed_lessons"] = len(completed)
        course["progress"] = round((course["completed_lessons"] / course["total_lessons"]) * 100) if course["total_lessons"] > 0 else 0

    return courses

@router.post("/courses/{course_id}/progress")
async def update_course_progress(request: Request, course_id: str):
    """Update course progress — verified members only"""
    user = await get_current_user(request)

    if not user.get("verified"):
        raise HTTPException(status_code=403, detail="Your account must be verified to access courses.")

    data = await request.json()

    await db.course_progress.update_one(
        {"user_id": ObjectId(user["_id"]), "course_id": course_id},
        {"$set": {
            "completed_lessons": data.get("completed_lessons", 0),
            "updated_at": datetime.now(timezone.utc)
        }},
        upsert=True
    )

    return {"message": "Progress updated"}

@router.get("/dashboard")
async def get_dashboard_data(request: Request):
    """Get all dashboard data for member"""
    user = await get_current_user(request)
    user_id = ObjectId(user["_id"])

    # Get credit scores
    latest_credit = await db.credit_scores.find_one(
        {"user_id": user_id},
        sort=[("date", -1)]
    )

    # Get disputes count
    disputes_count = await db.disputes.count_documents({"user_id": user_id})
    pending_disputes = await db.disputes.count_documents({"user_id": user_id, "status": {"$in": ["pending", "sent"]}})

    # Get unread messages
    unread_messages = await db.messages.count_documents({"to_user_id": user_id, "read": False})

    # Get course progress
    progress = await db.course_progress.find({"user_id": user_id}).to_list(100)
    courses_in_progress = len([p for p in progress if 0 < p.get("percent_complete", 0) < 100])
    courses_completed = len([p for p in progress if p.get("percent_complete", 0) == 100])

    # Get counselor info
    member = await db.users.find_one({"_id": user_id})
    counselor_assigned = bool(member.get("assigned_counselor_id"))

    return {
        "credit_scores": {
            "equifax": latest_credit.get("equifax") if latest_credit else None,
            "experian": latest_credit.get("experian") if latest_credit else None,
            "transunion": latest_credit.get("transunion") if latest_credit else None,
            "date": latest_credit.get("date").isoformat() if latest_credit and latest_credit.get("date") else None
        },
        "disputes": {
            "total": disputes_count,
            "pending": pending_disputes
        },
        "messages": {
            "unread": unread_messages
        },
        "courses": {
            "in_progress": courses_in_progress,
            "completed": courses_completed
        },
        "counselor_assigned": counselor_assigned,
        "pipeline_stage": member.get("pipeline_stage", "applied"),
        "dd214_status": member.get("dd214_status", "pending")
    }

# DD-214 Upload
@router.post("/dd214")
@router.post("/upload/dd214")
async def upload_dd214(request: Request, file: UploadFile = File(...)):
    """Upload DD-214 document to Supabase or local storage"""
    user = await get_current_user(request)

    # Validate file type
    allowed_types = ["application/pdf", "image/jpeg", "image/jpg", "image/png"]
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Invalid file type. Only PDF, JPG, PNG allowed.")

    # Validate file size (10MB max)
    contents = await file.read()
    if len(contents) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large. Maximum 10MB.")

    # Upload to storage (Supabase or local fallback)
    result = await storage_upload_dd214(contents, file.filename, user["_id"])

    if not result["success"]:
        raise HTTPException(status_code=500, detail=f"Upload failed: {result.get('error')}")

    filename = result["filename"]
    storage_type = result["storage_type"]

    # Update user record
    await db.users.update_one(
        {"_id": ObjectId(user["_id"])},
        {"$set": {
            "dd214_file": filename,
            "dd214_storage_type": storage_type,
            "dd214_status": "pending_review",
            "dd214_uploaded_at": datetime.now(timezone.utc),
            "pipeline_stage": "dd214_pending"
        }}
    )

    await log_audit_event(
        action=AUDIT_ACTIONS["DD214_UPLOADED"],
        entity_type="user",
        entity_id=user["_id"],
        user_email=user.get("email"),
        details={"storage_type": storage_type},
        ip_address=request.client.host if request.client else None
    )

    # Notify admin of new DD-214 upload
    member_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
    asyncio.create_task(send_admin_notification(
        "New DD-214 Upload",
        f"{member_name} ({user.get('email')}) has uploaded their DD-214 for verification."
    ))

    return {"message": "File uploaded successfully", "filename": filename, "storage_type": storage_type}

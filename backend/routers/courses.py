# Courses router for Silent Honor Foundation
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request
from bson import ObjectId

from middleware.auth_middleware import get_current_user, get_current_admin
from middleware.logging_middleware import log_audit_event, AUDIT_ACTIONS
from utils.validators import CourseRequest, LessonRequest, ModuleRequest

router = APIRouter(prefix="/api", tags=["Courses"])

# Database reference
db = None

def set_db(database):
    global db
    db = database

# Member-facing course endpoints
@router.get("/courses/progress")
async def get_all_course_progress(request: Request):
    """Get member's progress across all courses"""
    user = await get_current_user(request)
    progress = await db.course_progress.find({"user_id": ObjectId(user["_id"])}).to_list(100)
    return [{
        "course_id": str(p.get("course_id")),
        "completed_lessons": p.get("completed_lessons", []),
        "percent_complete": p.get("percent_complete", 0),
        "last_accessed": p.get("updated_at").isoformat() if p.get("updated_at") else None
    } for p in progress]

@router.get("/courses/{course_id}")
async def get_course_for_member(request: Request, course_id: str):
    """Get course with lessons for member"""
    user = await get_current_user(request)

    course = await db.courses.find_one({"_id": ObjectId(course_id)}) if len(course_id) == 24 else None

    if course:
        lessons = await db.lessons.find({"course_id": course_id}).sort("order", 1).to_list(100)

        progress = await db.course_progress.find_one({
            "user_id": ObjectId(user["_id"]),
            "course_id": course_id
        })
        completed_lessons = progress.get("completed_lessons", []) if progress else []

        return {
            "id": str(course["_id"]),
            "title": course.get("title", ""),
            "description": course.get("description", ""),
            "category": course.get("category"),
            "thumbnail": course.get("thumbnail"),
            "lessons": [{
                "id": str(l["_id"]),
                "title": l.get("title", ""),
                "content": l.get("content", ""),
                "duration": l.get("duration", "10 min"),
                "video_url": l.get("video_url"),
                "order": l.get("order", 0),
                "completed": str(l["_id"]) in completed_lessons
            } for l in lessons]
        }

    raise HTTPException(status_code=404, detail="Course not found")

@router.post("/courses/{course_id}/lessons/{lesson_id}/complete")
async def mark_lesson_complete(request: Request, course_id: str, lesson_id: str):
    """Mark lesson as complete"""
    user = await get_current_user(request)

    progress = await db.course_progress.find_one({
        "user_id": ObjectId(user["_id"]),
        "course_id": course_id
    })

    completed_lessons = progress.get("completed_lessons", []) if progress else []

    if lesson_id not in completed_lessons:
        completed_lessons.append(lesson_id)

    total_lessons = await db.lessons.count_documents({"course_id": course_id})
    percent = round((len(completed_lessons) / total_lessons) * 100) if total_lessons > 0 else 0

    await db.course_progress.update_one(
        {"user_id": ObjectId(user["_id"]), "course_id": course_id},
        {"$set": {
            "completed_lessons": completed_lessons,
            "percent_complete": percent,
            "updated_at": datetime.now(timezone.utc)
        }},
        upsert=True
    )

    await log_audit_event(
        action=AUDIT_ACTIONS["LESSON_COMPLETED"],
        entity_type="course",
        entity_id=course_id,
        user_id=user["_id"],
        user_email=user.get("email"),
        details={"lesson_id": lesson_id, "percent_complete": percent}
    )

    return {"message": "Lesson marked complete", "percent_complete": percent}

# Waitlist endpoints
@router.post("/courses/{course_id}/waitlist")
async def join_waitlist(request: Request, course_id: str):
    """Join course waitlist"""
    user = await get_current_user(request)

    existing = await db.waitlist.find_one({
        "course_id": course_id,
        "user_id": ObjectId(user["_id"])
    })
    if existing:
        return {"message": "Already on waitlist"}

    waitlist_doc = {
        "course_id": course_id,
        "user_id": ObjectId(user["_id"]),
        "user_email": user.get("email"),
        "user_name": f"{user.get('first_name', '')} {user.get('last_name', '')}".strip(),
        "created_at": datetime.now(timezone.utc)
    }

    await db.waitlist.insert_one(waitlist_doc)
    return {"message": "Added to waitlist"}

@router.delete("/courses/{course_id}/waitlist")
async def leave_waitlist(request: Request, course_id: str):
    """Leave course waitlist"""
    user = await get_current_user(request)
    await db.waitlist.delete_one({"course_id": course_id, "user_id": ObjectId(user["_id"])})
    return {"message": "Removed from waitlist"}

@router.get("/admin/waitlist")
async def get_waitlist(request: Request):
    """Get all waitlist entries (admin only)"""
    await get_current_admin(request)
    entries = await db.waitlist.find().sort("created_at", -1).to_list(500)
    return [{
        "id": str(e["_id"]),
        "course_id": e.get("course_id"),
        "user_id": str(e.get("user_id")),
        "user_email": e.get("user_email"),
        "user_name": e.get("user_name"),
        "created_at": e.get("created_at").isoformat() if e.get("created_at") else None
    } for e in entries]

# Admin course management
@router.get("/admin/courses")
async def get_admin_courses(request: Request):
    """Get all courses (admin only)"""
    await get_current_admin(request)
    courses = await db.courses.find().sort("created_at", -1).to_list(100)
    result = []
    for c in courses:
        lesson_count = await db.lessons.count_documents({"course_id": str(c["_id"])})
        result.append({
            "id": str(c["_id"]),
            "title": c.get("title", ""),
            "description": c.get("description", ""),
            "status": c.get("status", "draft"),
            "total_lessons": lesson_count,
            "category": c.get("category"),
            "thumbnail": c.get("thumbnail"),
            "created_at": c.get("created_at").isoformat() if c.get("created_at") else None
        })
    return result

@router.post("/admin/courses")
async def create_course(request: Request, data: CourseRequest):
    """Create new course (admin only)"""
    admin = await get_current_admin(request)
    course_doc = {
        "title": data.title,
        "description": data.description,
        "status": data.status,
        "category": data.category,
        "thumbnail": data.thumbnail,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }
    result = await db.courses.insert_one(course_doc)

    await log_audit_event(
        action=AUDIT_ACTIONS["COURSE_CREATED"],
        entity_type="course",
        entity_id=str(result.inserted_id),
        user_id=admin["_id"],
        user_email=admin.get("email"),
        ip_address=request.client.host if request.client else None
    )

    return {"id": str(result.inserted_id), "message": "Course created successfully"}

@router.get("/admin/courses/{course_id}")
async def get_course(request: Request, course_id: str):
    """Get course with modules and lessons (admin only)"""
    await get_current_admin(request)
    course = await db.courses.find_one({"_id": ObjectId(course_id)})
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    modules = await db.modules.find({"course_id": course_id}).sort("order", 1).to_list(100)
    module_list = []
    for m in modules:
        lessons = await db.lessons.find({"module_id": str(m["_id"])}).sort("order", 1).to_list(100)
        module_list.append({
            "id": str(m["_id"]),
            "title": m.get("title", ""),
            "description": m.get("description", ""),
            "order": m.get("order", 0),
            "lessons": [{
                "id": str(l["_id"]),
                "title": l.get("title", ""),
                "content": l.get("content", ""),
                "lesson_type": l.get("lesson_type", "text"),
                "order": l.get("order", 0),
                "video_url": l.get("video_url"),
                "resource_url": l.get("resource_url"),
                "duration": l.get("duration")
            } for l in lessons]
        })

    # Also include unmodularized lessons for backward compat
    flat_lessons = await db.lessons.find({"course_id": course_id, "module_id": None}).sort("order", 1).to_list(100)

    return {
        "id": str(course["_id"]),
        "title": course.get("title", ""),
        "description": course.get("description", ""),
        "status": course.get("status", "draft"),
        "category": course.get("category"),
        "thumbnail": course.get("thumbnail"),
        "modules": module_list,
        "flat_lessons": [{
            "id": str(l["_id"]),
            "title": l.get("title", ""),
            "content": l.get("content", ""),
            "lesson_type": l.get("lesson_type", "text"),
            "order": l.get("order", 0),
            "video_url": l.get("video_url"),
            "resource_url": l.get("resource_url"),
            "duration": l.get("duration")
        } for l in flat_lessons]
    }

@router.put("/admin/courses/{course_id}")
async def update_course(request: Request, course_id: str, data: CourseRequest):
    """Update course (admin only)"""
    admin = await get_current_admin(request)
    await db.courses.update_one(
        {"_id": ObjectId(course_id)},
        {"$set": {
            "title": data.title,
            "description": data.description,
            "status": data.status,
            "category": data.category,
            "thumbnail": data.thumbnail,
            "updated_at": datetime.now(timezone.utc)
        }}
    )

    await log_audit_event(
        action=AUDIT_ACTIONS["COURSE_UPDATED"],
        entity_type="course",
        entity_id=course_id,
        user_id=admin["_id"],
        user_email=admin.get("email"),
        ip_address=request.client.host if request.client else None
    )

    return {"message": "Course updated successfully"}

@router.delete("/admin/courses/{course_id}")
async def delete_course(request: Request, course_id: str):
    """Delete course and its lessons (admin only)"""
    admin = await get_current_admin(request)
    await db.courses.delete_one({"_id": ObjectId(course_id)})
    await db.lessons.delete_many({"course_id": course_id})

    await log_audit_event(
        action=AUDIT_ACTIONS["COURSE_DELETED"],
        entity_type="course",
        entity_id=course_id,
        user_id=admin["_id"],
        user_email=admin.get("email"),
        ip_address=request.client.host if request.client else None
    )

    return {"message": "Course and lessons deleted"}

# Lesson Management
@router.post("/admin/lessons")
async def create_lesson(request: Request, data: LessonRequest):
    """Create lesson (admin only)"""
    await get_current_admin(request)
    lesson_doc = {
        "course_id": data.course_id,
        "title": data.title,
        "content": data.content,
        "order": data.order,
        "video_url": data.video_url,
        "duration": data.duration,
        "created_at": datetime.now(timezone.utc)
    }
    result = await db.lessons.insert_one(lesson_doc)
    return {"id": str(result.inserted_id), "message": "Lesson created successfully"}

@router.put("/admin/lessons/{lesson_id}")
async def update_lesson(request: Request, lesson_id: str, data: LessonRequest):
    """Update lesson (admin only)"""
    await get_current_admin(request)
    await db.lessons.update_one(
        {"_id": ObjectId(lesson_id)},
        {"$set": {
            "title": data.title,
            "content": data.content,
            "order": data.order,
            "video_url": data.video_url,
            "duration": data.duration,
            "updated_at": datetime.now(timezone.utc)
        }}
    )
    return {"message": "Lesson updated successfully"}

@router.delete("/admin/lessons/{lesson_id}")
async def delete_lesson(request: Request, lesson_id: str):
    """Delete lesson (admin only)"""
    await get_current_admin(request)
    await db.lessons.delete_one({"_id": ObjectId(lesson_id)})
    return {"message": "Lesson deleted"}


# Module Management
@router.get("/admin/courses/{course_id}/modules")
async def get_modules(request: Request, course_id: str):
    await get_current_admin(request)
    modules = await db.modules.find({"course_id": course_id}).sort("order", 1).to_list(100)
    result = []
    for m in modules:
        lesson_count = await db.lessons.count_documents({"module_id": str(m["_id"])})
        result.append({
            "id": str(m["_id"]),
            "title": m.get("title", ""),
            "description": m.get("description", ""),
            "order": m.get("order", 0),
            "lesson_count": lesson_count
        })
    return result


@router.post("/admin/courses/{course_id}/modules")
async def create_module(request: Request, course_id: str):
    await get_current_admin(request)
    course = await db.courses.find_one({"_id": ObjectId(course_id)})
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    data = await request.json()
    module_doc = {
        "course_id": course_id,
        "title": data.get("title", "New Module"),
        "description": data.get("description", ""),
        "order": data.get("order", 0),
        "created_at": datetime.now(timezone.utc)
    }
    result = await db.modules.insert_one(module_doc)
    return {"id": str(result.inserted_id), "message": "Module created"}


@router.put("/admin/modules/{module_id}")
async def update_module(request: Request, module_id: str):
    await get_current_admin(request)
    data = await request.json()
    allowed = ["title", "description", "order"]
    update_data = {k: v for k, v in data.items() if k in allowed}
    update_data["updated_at"] = datetime.now(timezone.utc)
    result = await db.modules.update_one({"_id": ObjectId(module_id)}, {"$set": update_data})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Module not found")
    return {"message": "Module updated"}


@router.delete("/admin/modules/{module_id}")
async def delete_module(request: Request, module_id: str):
    await get_current_admin(request)
    await db.modules.delete_one({"_id": ObjectId(module_id)})
    await db.lessons.delete_many({"module_id": module_id})
    return {"message": "Module and its lessons deleted"}


@router.get("/admin/modules/{module_id}/lessons")
async def get_module_lessons(request: Request, module_id: str):
    await get_current_admin(request)
    lessons = await db.lessons.find({"module_id": module_id}).sort("order", 1).to_list(100)
    return [{
        "id": str(l["_id"]),
        "title": l.get("title", ""),
        "content": l.get("content", ""),
        "lesson_type": l.get("lesson_type", "text"),
        "order": l.get("order", 0),
        "video_url": l.get("video_url"),
        "resource_url": l.get("resource_url"),
        "duration": l.get("duration")
    } for l in lessons]


@router.post("/admin/modules/{module_id}/lessons")
async def create_module_lesson(request: Request, module_id: str):
    await get_current_admin(request)
    module = await db.modules.find_one({"_id": ObjectId(module_id)})
    if not module:
        raise HTTPException(status_code=404, detail="Module not found")
    data = await request.json()
    lesson_doc = {
        "course_id": module["course_id"],
        "module_id": module_id,
        "title": data.get("title", "New Lesson"),
        "content": data.get("content", ""),
        "lesson_type": data.get("lesson_type", "text"),
        "order": data.get("order", 0),
        "video_url": data.get("video_url"),
        "resource_url": data.get("resource_url"),
        "duration": data.get("duration"),
        "created_at": datetime.now(timezone.utc)
    }
    result = await db.lessons.insert_one(lesson_doc)
    return {"id": str(result.inserted_id), "message": "Lesson created"}


@router.put("/admin/modules/{module_id}/lessons/{lesson_id}")
async def update_module_lesson(request: Request, module_id: str, lesson_id: str):
    await get_current_admin(request)
    data = await request.json()
    allowed = ["title", "content", "lesson_type", "order", "video_url", "resource_url", "duration"]
    update_data = {k: v for k, v in data.items() if k in allowed}
    update_data["updated_at"] = datetime.now(timezone.utc)
    result = await db.lessons.update_one({"_id": ObjectId(lesson_id), "module_id": module_id}, {"$set": update_data})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Lesson not found")
    return {"message": "Lesson updated"}


# Member-facing courses list
@router.get("/member/courses")
async def get_member_courses(request: Request):
    """Get all published courses for members with their progress"""
    user = await get_current_user(request)
    courses = await db.courses.find({"status": "published"}).sort("created_at", -1).to_list(100)
    result = []
    for c in courses:
        lesson_count = await db.lessons.count_documents({"course_id": str(c["_id"])})
        progress = await db.course_progress.find_one({
            "user_id": ObjectId(user["_id"]),
            "course_id": str(c["_id"])
        })
        result.append({
            "id": str(c["_id"]),
            "title": c.get("title", ""),
            "description": c.get("description", ""),
            "category": c.get("category"),
            "thumbnail": c.get("thumbnail"),
            "total_lessons": lesson_count,
            "percent_complete": progress.get("percent_complete", 0) if progress else 0,
            "enrolled": progress is not None,
            "status": c.get("status", "draft")
        })
    return result

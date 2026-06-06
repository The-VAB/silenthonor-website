# Content management router for Silent Honor Foundation
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request
from bson import ObjectId

from middleware.auth_middleware import get_current_admin
from utils.validators import ContentUpdateRequest, ContactRequest

router = APIRouter(prefix="/api", tags=["Content"])

# Database reference
db = None

def set_db(database):
    global db
    db = database

# Public endpoints
@router.get("/content/{page}/{section}")
async def get_public_content(page: str, section: str):
    """Get public site content"""
    content = await db.site_content.find_one({"page": page, "section": section})
    if content:
        return content.get("content", {})
    return {}

@router.post("/contact")
async def submit_contact(data: ContactRequest):
    """Submit contact form"""
    contact_doc = {
        "first_name": data.first_name,
        "last_name": data.last_name,
        "email": data.email.lower(),
        "branch": data.branch,
        "status": data.status,
        "topic": data.topic,
        "message": data.message,
        "created_at": datetime.now(timezone.utc),
        "responded": False
    }

    await db.contacts.insert_one(contact_doc)
    return {"message": "Message received. We'll be in touch within 2-3 business days."}

@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "Silent Honor Foundation API"}

# Admin content management
@router.get("/admin/content")
async def get_all_content(request: Request):
    """Get all site content (admin only)"""
    await get_current_admin(request)
    content = await db.site_content.find().to_list(100)
    result = {}
    for c in content:
        page = c.get("page", "unknown")
        if page not in result:
            result[page] = {}
        result[page][c.get("section", "unknown")] = c.get("content", {})
    return result

@router.get("/admin/content/{page}")
async def get_page_content(request: Request, page: str):
    """Get page content (admin only)"""
    await get_current_admin(request)
    content = await db.site_content.find({"page": page}).to_list(50)
    result = {}
    for c in content:
        result[c.get("section", "unknown")] = c.get("content", {})
    return result

@router.put("/admin/content")
async def update_content(request: Request, data: ContentUpdateRequest):
    """Update site content (admin only)"""
    await get_current_admin(request)
    await db.site_content.update_one(
        {"page": data.page, "section": data.section},
        {"$set": {
            "content": data.content,
            "updated_at": datetime.now(timezone.utc)
        }},
        upsert=True
    )
    return {"message": "Content updated successfully"}

# Team member management
@router.get("/admin/team")
async def get_team_members(request: Request):
    """Get team members (admin only)"""
    await get_current_admin(request)
    members = await db.team_members.find().sort("order", 1).to_list(50)
    return [{
        "id": str(m["_id"]),
        "name": m.get("name", ""),
        "role": m.get("role", ""),
        "bio": m.get("bio", ""),
        "tags": m.get("tags", []),
        "photo": m.get("photo"),
        "order": m.get("order", 0),
        "is_board": m.get("is_board", False)
    } for m in members]

@router.post("/admin/team")
async def create_team_member(request: Request):
    """Create team member (admin only)"""
    await get_current_admin(request)
    data = await request.json()
    member_doc = {
        "name": data.get("name", ""),
        "role": data.get("role", ""),
        "bio": data.get("bio", ""),
        "tags": data.get("tags", []),
        "photo": data.get("photo"),
        "order": data.get("order", 0),
        "is_board": data.get("is_board", False),
        "created_at": datetime.now(timezone.utc)
    }
    result = await db.team_members.insert_one(member_doc)
    return {"id": str(result.inserted_id), "message": "Team member added"}

@router.put("/admin/team/{member_id}")
async def update_team_member(request: Request, member_id: str):
    """Update team member (admin only)"""
    await get_current_admin(request)
    data = await request.json()
    await db.team_members.update_one(
        {"_id": ObjectId(member_id)},
        {"$set": {
            "name": data.get("name"),
            "role": data.get("role"),
            "bio": data.get("bio"),
            "tags": data.get("tags", []),
            "photo": data.get("photo"),
            "order": data.get("order", 0),
            "is_board": data.get("is_board", False),
            "updated_at": datetime.now(timezone.utc)
        }}
    )
    return {"message": "Team member updated"}

@router.delete("/admin/team/{member_id}")
async def delete_team_member(request: Request, member_id: str):
    """Delete team member (admin only)"""
    await get_current_admin(request)
    await db.team_members.delete_one({"_id": ObjectId(member_id)})
    return {"message": "Team member deleted"}

# Public team endpoint
@router.get("/team")
async def get_public_team():
    """Get public team members list"""
    members = await db.team_members.find().sort("order", 1).to_list(50)
    return [{
        "id": str(m["_id"]),
        "name": m.get("name", ""),
        "role": m.get("role", ""),
        "bio": m.get("bio", ""),
        "tags": m.get("tags", []),
        "photo": m.get("photo"),
        "is_board": m.get("is_board", False)
    } for m in members]

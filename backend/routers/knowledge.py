# Knowledge base router for Silent Honor Foundation
#
# One shared knowledge base grounds both AI assistants (Battle Buddy for staff, Major
# Finance for members). The `visibility` field is the security wall between them: the
# member-facing read endpoint below can ONLY ever return member_visible + published
# entries, enforced here on the server -- never trust the client to filter it.
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request
from bson import ObjectId

from middleware.auth_middleware import get_current_user, get_current_admin
from utils.validators import KnowledgeEntryCreate, KnowledgeEntryUpdate

router = APIRouter(prefix="/api", tags=["Knowledge Base"])

# Database reference
db = None

def set_db(database):
    global db
    db = database

# Roles allowed to manage knowledge entries: admins/staff (ED, Ops) and counselors
# (for their domain content). Members can only ever read member-visible content.
_EDITOR_ROLES = ("admin", "staff", "counselor")

async def _require_kb_editor(request: Request) -> dict:
    user = await get_current_user(request)
    user_roles = user.get("roles") or [user.get("role", "")]
    if not any(r in user_roles for r in _EDITOR_ROLES):
        raise HTTPException(status_code=403, detail="Not authorized to manage the knowledge base")
    return user

def _serialize(entry: dict, include_internal: bool = False) -> dict:
    """Member-facing serialization by default -- only content, never the internal
    visibility/status/attribution fields. Pass include_internal=True for staff management."""
    out = {
        "id": str(entry["_id"]),
        "title": entry.get("title", ""),
        "body": entry.get("body", ""),
        "category": entry.get("category"),
        "tags": entry.get("tags", []),
    }
    if include_internal:
        out.update({
            "visibility": entry.get("visibility", "staff_only"),
            "status": entry.get("status", "draft"),
            "version": entry.get("version", 1),
            "created_by": entry.get("created_by"),
            "updated_by": entry.get("updated_by"),
            "created_at": entry.get("created_at").isoformat() if entry.get("created_at") else None,
            "updated_at": entry.get("updated_at").isoformat() if entry.get("updated_at") else None,
        })
    return out

# ── Member-facing read (the server-enforced wall) ────────────────────────────
@router.get("/knowledge")
async def list_member_knowledge(request: Request, category: str = None, q: str = None):
    """Member-facing knowledge list. Returns ONLY published + member_visible entries --
    this is the wall that keeps Major Finance (and members) out of staff-only content.
    Any logged-in user may read; the filter is enforced here regardless of role."""
    await get_current_user(request)  # require authentication
    query = {"status": "published", "visibility": "member_visible"}
    if category:
        query["category"] = category
    if q:
        query["$or"] = [
            {"title": {"$regex": q, "$options": "i"}},
            {"body": {"$regex": q, "$options": "i"}},
        ]
    entries = await db.knowledge_base.find(query).sort("title", 1).to_list(500)
    return [_serialize(e) for e in entries]

# ── Staff management ─────────────────────────────────────────────────────────
@router.get("/admin/knowledge")
async def list_all_knowledge(request: Request, visibility: str = None, status: str = None,
                             category: str = None, q: str = None):
    """Full knowledge list for management -- all visibilities and statuses."""
    await _require_kb_editor(request)
    query = {}
    if visibility:
        query["visibility"] = visibility
    if status:
        query["status"] = status
    if category:
        query["category"] = category
    if q:
        query["$or"] = [
            {"title": {"$regex": q, "$options": "i"}},
            {"body": {"$regex": q, "$options": "i"}},
        ]
    entries = await db.knowledge_base.find(query).sort("updated_at", -1).to_list(1000)
    return [_serialize(e, include_internal=True) for e in entries]

@router.get("/admin/knowledge/{entry_id}")
async def get_knowledge_entry(request: Request, entry_id: str):
    await _require_kb_editor(request)
    entry = await db.knowledge_base.find_one({"_id": ObjectId(entry_id)})
    if not entry:
        raise HTTPException(status_code=404, detail="Knowledge entry not found")
    return _serialize(entry, include_internal=True)

@router.post("/admin/knowledge")
async def create_knowledge_entry(request: Request, data: KnowledgeEntryCreate):
    editor = await _require_kb_editor(request)
    now = datetime.now(timezone.utc)
    doc = {
        "title": data.title,
        "body": data.body,
        "category": data.category,
        "tags": data.tags,
        "visibility": data.visibility,
        "status": data.status,
        "version": 1,
        "created_by": editor.get("email"),
        "updated_by": editor.get("email"),
        "created_at": now,
        "updated_at": now,
    }
    result = await db.knowledge_base.insert_one(doc)
    doc["_id"] = result.inserted_id
    return _serialize(doc, include_internal=True)

@router.put("/admin/knowledge/{entry_id}")
async def update_knowledge_entry(request: Request, entry_id: str, data: KnowledgeEntryUpdate):
    editor = await _require_kb_editor(request)
    entry = await db.knowledge_base.find_one({"_id": ObjectId(entry_id)})
    if not entry:
        raise HTTPException(status_code=404, detail="Knowledge entry not found")
    updates = {k: v for k, v in data.model_dump().items() if v is not None}
    if not updates:
        return _serialize(entry, include_internal=True)
    updates["updated_by"] = editor.get("email")
    updates["updated_at"] = datetime.now(timezone.utc)
    updates["version"] = entry.get("version", 1) + 1
    await db.knowledge_base.update_one({"_id": ObjectId(entry_id)}, {"$set": updates})
    entry = await db.knowledge_base.find_one({"_id": ObjectId(entry_id)})
    return _serialize(entry, include_internal=True)

@router.post("/admin/knowledge/{entry_id}/publish")
async def publish_knowledge_entry(request: Request, entry_id: str):
    editor = await _require_kb_editor(request)
    result = await db.knowledge_base.update_one(
        {"_id": ObjectId(entry_id)},
        {"$set": {"status": "published", "updated_by": editor.get("email"),
                  "updated_at": datetime.now(timezone.utc)}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Knowledge entry not found")
    return {"message": "Entry published"}

@router.post("/admin/knowledge/{entry_id}/retire")
async def retire_knowledge_entry(request: Request, entry_id: str):
    editor = await _require_kb_editor(request)
    result = await db.knowledge_base.update_one(
        {"_id": ObjectId(entry_id)},
        {"$set": {"status": "retired", "updated_by": editor.get("email"),
                  "updated_at": datetime.now(timezone.utc)}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Knowledge entry not found")
    return {"message": "Entry retired"}

@router.delete("/admin/knowledge/{entry_id}")
async def delete_knowledge_entry(request: Request, entry_id: str):
    """Hard delete -- admin only. Prefer retire for anything already published."""
    await get_current_admin(request)
    result = await db.knowledge_base.delete_one({"_id": ObjectId(entry_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Knowledge entry not found")
    return {"message": "Entry deleted"}

# Messages router for Silent Honor Foundation
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request
from bson import ObjectId

from middleware.auth_middleware import get_current_user

router = APIRouter(prefix="/api/messages", tags=["Messages"])

# Database reference
db = None

def set_db(database):
    global db
    db = database

@router.get("")
async def get_messages(request: Request, conversation_id: str = None):
    """Get messages (optionally filtered by conversation)"""
    user = await get_current_user(request)
    user_id = ObjectId(user["_id"])

    query = {"$or": [{"from_user_id": user_id}, {"to_user_id": user_id}]}
    if conversation_id:
        other_id = ObjectId(conversation_id)
        query = {"$or": [
            {"from_user_id": user_id, "to_user_id": other_id},
            {"from_user_id": other_id, "to_user_id": user_id}
        ]}

    messages = await db.messages.find(query).sort("created_at", 1).to_list(500)
    return [{
        "id": str(m["_id"]),
        "from_user_id": str(m["from_user_id"]),
        "to_user_id": str(m["to_user_id"]),
        "content": m.get("content", ""),
        "read": m.get("read", False),
        "created_at": m.get("created_at").isoformat() if m.get("created_at") else None
    } for m in messages]

@router.post("")
async def send_message(request: Request):
    """Send a message"""
    user = await get_current_user(request)
    data = await request.json()

    to_user_id = data.get("to_user_id")
    content = data.get("content", "").strip()

    if not to_user_id or not content:
        raise HTTPException(status_code=400, detail="Recipient and content required")

    # Verify recipient exists
    recipient = await db.users.find_one({"_id": ObjectId(to_user_id)})
    if not recipient:
        raise HTTPException(status_code=404, detail="Recipient not found")

    message_doc = {
        "from_user_id": ObjectId(user["_id"]),
        "to_user_id": ObjectId(to_user_id),
        "content": content,
        "read": False,
        "created_at": datetime.now(timezone.utc)
    }

    result = await db.messages.insert_one(message_doc)
    return {
        "id": str(result.inserted_id),
        "message": "Message sent",
        "created_at": message_doc["created_at"].isoformat()
    }

@router.get("/conversations")
async def get_conversations(request: Request):
    """Get all conversations for current user"""
    user = await get_current_user(request)
    user_id = ObjectId(user["_id"])

    pipeline = [
        {"$match": {"$or": [{"from_user_id": user_id}, {"to_user_id": user_id}]}},
        {"$sort": {"created_at": -1}},
        {"$group": {
            "_id": {"$cond": [
                {"$eq": ["$from_user_id", user_id]},
                "$to_user_id",
                "$from_user_id"
            ]},
            "last_message": {"$first": "$content"},
            "last_time": {"$first": "$created_at"},
            "unread_count": {"$sum": {"$cond": [
                {"$and": [{"$eq": ["$to_user_id", user_id]}, {"$eq": ["$read", False]}]},
                1, 0
            ]}}
        }}
    ]

    convos = await db.messages.aggregate(pipeline).to_list(100)

    result = []
    for c in convos:
        partner = await db.users.find_one({"_id": c["_id"]})
        if partner:
            result.append({
                "id": str(c["_id"]),
                "name": f"{partner.get('first_name', '')} {partner.get('last_name', '')}".strip() or partner.get("email"),
                "title": partner.get("title", partner.get("role", "").replace("_", " ").title()),
                "role": partner.get("role"),
                "last_message": c.get("last_message", ""),
                "last_time": c.get("last_time").isoformat() if c.get("last_time") else None,
                "unread": c.get("unread_count", 0)
            })

    return result

@router.get("/unread")
async def get_unread_count(request: Request):
    """Get unread message count"""
    user = await get_current_user(request)
    count = await db.messages.count_documents({
        "to_user_id": ObjectId(user["_id"]),
        "read": False
    })
    return {"unread": count}

@router.put("/{message_id}/read")
async def mark_message_read(request: Request, message_id: str):
    """Mark message as read"""
    user = await get_current_user(request)
    await db.messages.update_one(
        {"_id": ObjectId(message_id), "to_user_id": ObjectId(user["_id"])},
        {"$set": {"read": True}}
    )
    return {"message": "Marked as read"}

@router.put("/conversation/{user_id}/read")
async def mark_conversation_read(request: Request, user_id: str):
    """Mark all messages in conversation as read"""
    user = await get_current_user(request)
    await db.messages.update_many(
        {"from_user_id": ObjectId(user_id), "to_user_id": ObjectId(user["_id"]), "read": False},
        {"$set": {"read": True}}
    )
    return {"message": "Conversation marked as read"}

# Admin message view
@router.get("/admin/all")
async def get_all_messages(request: Request):
    """Get all messages (admin only)"""
    from middleware.auth_middleware import get_current_admin
    await get_current_admin(request)

    pipeline = [
        {"$lookup": {
            "from": "users",
            "localField": "from_user_id",
            "foreignField": "_id",
            "as": "from_user"
        }},
        {"$lookup": {
            "from": "users",
            "localField": "to_user_id",
            "foreignField": "_id",
            "as": "to_user"
        }},
        {"$unwind": {"path": "$from_user", "preserveNullAndEmptyArrays": True}},
        {"$unwind": {"path": "$to_user", "preserveNullAndEmptyArrays": True}},
        {"$sort": {"created_at": -1}},
        {"$limit": 500}
    ]

    messages = await db.messages.aggregate(pipeline).to_list(500)
    return [{
        "id": str(m["_id"]),
        "from_user": {
            "id": str(m["from_user_id"]),
            "name": f"{m.get('from_user', {}).get('first_name', '')} {m.get('from_user', {}).get('last_name', '')}".strip(),
            "email": m.get("from_user", {}).get("email", "")
        },
        "to_user": {
            "id": str(m["to_user_id"]),
            "name": f"{m.get('to_user', {}).get('first_name', '')} {m.get('to_user', {}).get('last_name', '')}".strip(),
            "email": m.get("to_user", {}).get("email", "")
        },
        "content": m.get("content", ""),
        "read": m.get("read", False),
        "created_at": m.get("created_at").isoformat() if m.get("created_at") else None
    } for m in messages]

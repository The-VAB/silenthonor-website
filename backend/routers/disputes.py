# Disputes router for Silent Honor Foundation
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request
from bson import ObjectId

from middleware.auth_middleware import get_current_user, get_current_admin
from middleware.logging_middleware import log_audit_event, AUDIT_ACTIONS

router = APIRouter(prefix="/api", tags=["Disputes"])

# Database reference
db = None

def set_db(database):
    global db
    db = database

@router.get("/disputes")
async def get_disputes(request: Request):
    """Get member's disputes"""
    user = await get_current_user(request)
    disputes = await db.disputes.find({"user_id": ObjectId(user["_id"])}).sort("created_at", -1).to_list(100)
    return [{
        "id": str(d["_id"]),
        "bureau": d.get("bureau", ""),
        "account_name": d.get("account_name", ""),
        "account_number": d.get("account_number", ""),
        "dispute_reason": d.get("dispute_reason", ""),
        "status": d.get("status", "pending"),
        "date_sent": d.get("date_sent").isoformat() if d.get("date_sent") else None,
        "date_response": d.get("date_response").isoformat() if d.get("date_response") else None,
        "response_outcome": d.get("response_outcome"),
        "tracking_number": d.get("tracking_number"),
        "notes": d.get("notes", ""),
        "created_at": d.get("created_at").isoformat() if d.get("created_at") else None
    } for d in disputes]

@router.post("/disputes")
async def create_dispute(request: Request):
    """Create new dispute"""
    user = await get_current_user(request)
    data = await request.json()

    dispute_doc = {
        "user_id": ObjectId(user["_id"]),
        "bureau": data.get("bureau", ""),
        "account_name": data.get("account_name", ""),
        "account_number": data.get("account_number", ""),
        "dispute_reason": data.get("dispute_reason", ""),
        "status": data.get("status", "draft"),
        "date_sent": None,
        "date_response": None,
        "response_outcome": None,
        "tracking_number": data.get("tracking_number"),
        "notes": data.get("notes", ""),
        "created_at": datetime.now(timezone.utc)
    }

    result = await db.disputes.insert_one(dispute_doc)

    await log_audit_event(
        action=AUDIT_ACTIONS["DISPUTE_CREATED"],
        entity_type="dispute",
        entity_id=str(result.inserted_id),
        user_id=user["_id"],
        user_email=user.get("email"),
        ip_address=request.client.host if request.client else None
    )

    return {"id": str(result.inserted_id), "message": "Dispute created"}

@router.put("/disputes/{dispute_id}")
async def update_dispute(request: Request, dispute_id: str):
    """Update dispute"""
    user = await get_current_user(request)
    data = await request.json()

    dispute = await db.disputes.find_one({"_id": ObjectId(dispute_id), "user_id": ObjectId(user["_id"])})
    if not dispute:
        raise HTTPException(status_code=404, detail="Dispute not found")

    update_fields = {}
    allowed = ["bureau", "account_name", "account_number", "dispute_reason", "status",
               "tracking_number", "notes", "response_outcome"]
    for field in allowed:
        if field in data:
            update_fields[field] = data[field]

    if "date_sent" in data and data["date_sent"]:
        update_fields["date_sent"] = datetime.fromisoformat(data["date_sent"].replace("Z", "+00:00"))
    if "date_response" in data and data["date_response"]:
        update_fields["date_response"] = datetime.fromisoformat(data["date_response"].replace("Z", "+00:00"))

    update_fields["updated_at"] = datetime.now(timezone.utc)

    await db.disputes.update_one({"_id": ObjectId(dispute_id)}, {"$set": update_fields})

    await log_audit_event(
        action=AUDIT_ACTIONS["DISPUTE_UPDATED"],
        entity_type="dispute",
        entity_id=dispute_id,
        user_id=user["_id"],
        user_email=user.get("email"),
        details={"fields_updated": list(update_fields.keys())},
        ip_address=request.client.host if request.client else None
    )

    return {"message": "Dispute updated"}

@router.delete("/disputes/{dispute_id}")
async def delete_dispute(request: Request, dispute_id: str):
    """Delete dispute"""
    user = await get_current_user(request)
    result = await db.disputes.delete_one({"_id": ObjectId(dispute_id), "user_id": ObjectId(user["_id"])})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Dispute not found")

    await log_audit_event(
        action=AUDIT_ACTIONS["DISPUTE_DELETED"],
        entity_type="dispute",
        entity_id=dispute_id,
        user_id=user["_id"],
        user_email=user.get("email"),
        ip_address=request.client.host if request.client else None
    )

    return {"message": "Dispute deleted"}

@router.get("/admin/disputes")
async def get_all_disputes(request: Request):
    """Get all disputes (admin only)"""
    await get_current_admin(request)

    pipeline = [
        {"$lookup": {
            "from": "users",
            "localField": "user_id",
            "foreignField": "_id",
            "as": "user"
        }},
        {"$unwind": {"path": "$user", "preserveNullAndEmptyArrays": True}},
        {"$sort": {"created_at": -1}}
    ]

    disputes = await db.disputes.aggregate(pipeline).to_list(500)
    return [{
        "id": str(d["_id"]),
        "user_id": str(d["user_id"]),
        "user_name": f"{d.get('user', {}).get('first_name', '')} {d.get('user', {}).get('last_name', '')}".strip(),
        "user_email": d.get("user", {}).get("email", ""),
        "bureau": d.get("bureau", ""),
        "account_name": d.get("account_name", ""),
        "account_number": d.get("account_number", ""),
        "dispute_reason": d.get("dispute_reason", ""),
        "status": d.get("status", "pending"),
        "date_sent": d.get("date_sent").isoformat() if d.get("date_sent") else None,
        "date_response": d.get("date_response").isoformat() if d.get("date_response") else None,
        "response_outcome": d.get("response_outcome"),
        "tracking_number": d.get("tracking_number"),
        "notes": d.get("notes", ""),
        "created_at": d.get("created_at").isoformat() if d.get("created_at") else None
    } for d in disputes]

@router.get("/admin/disputes/{dispute_id}")
async def get_dispute_detail(request: Request, dispute_id: str):
    """Get single dispute details (admin only)"""
    await get_current_admin(request)

    dispute = await db.disputes.find_one({"_id": ObjectId(dispute_id)})
    if not dispute:
        raise HTTPException(status_code=404, detail="Dispute not found")

    # Get member info
    member = await db.users.find_one({"_id": dispute["user_id"]})

    return {
        "id": str(dispute["_id"]),
        "user_id": str(dispute["user_id"]),
        "member": {
            "name": f"{member.get('first_name', '')} {member.get('last_name', '')}".strip() if member else "",
            "email": member.get("email", "") if member else ""
        },
        "bureau": dispute.get("bureau", ""),
        "account_name": dispute.get("account_name", ""),
        "account_number": dispute.get("account_number", ""),
        "dispute_reason": dispute.get("dispute_reason", ""),
        "status": dispute.get("status", "pending"),
        "date_sent": dispute.get("date_sent").isoformat() if dispute.get("date_sent") else None,
        "date_response": dispute.get("date_response").isoformat() if dispute.get("date_response") else None,
        "response_outcome": dispute.get("response_outcome"),
        "tracking_number": dispute.get("tracking_number"),
        "notes": dispute.get("notes", ""),
        "created_at": dispute.get("created_at").isoformat() if dispute.get("created_at") else None
    }

@router.put("/admin/disputes/{dispute_id}")
async def admin_update_dispute(request: Request, dispute_id: str):
    """Update any dispute (admin only)"""
    admin = await get_current_admin(request)
    data = await request.json()

    update_fields = {}
    allowed = ["bureau", "account_name", "account_number", "dispute_reason", "status",
               "tracking_number", "notes", "response_outcome"]
    for field in allowed:
        if field in data:
            update_fields[field] = data[field]

    if "date_sent" in data and data["date_sent"]:
        update_fields["date_sent"] = datetime.fromisoformat(data["date_sent"].replace("Z", "+00:00"))
    if "date_response" in data and data["date_response"]:
        update_fields["date_response"] = datetime.fromisoformat(data["date_response"].replace("Z", "+00:00"))

    update_fields["updated_at"] = datetime.now(timezone.utc)

    await db.disputes.update_one({"_id": ObjectId(dispute_id)}, {"$set": update_fields})

    await log_audit_event(
        action=AUDIT_ACTIONS["DISPUTE_UPDATED"],
        entity_type="dispute",
        entity_id=dispute_id,
        user_id=admin["_id"],
        user_email=admin.get("email"),
        details={"fields_updated": list(update_fields.keys()), "admin_action": True},
        ip_address=request.client.host if request.client else None
    )

    return {"message": "Dispute updated"}

# Credit Score router for Silent Honor Foundation
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request
from bson import ObjectId

from middleware.auth_middleware import get_current_user, get_current_admin

router = APIRouter(prefix="/api/credit", tags=["Credit"])

# Database reference
db = None

def set_db(database):
    global db
    db = database

@router.get("/history")
async def get_credit_history(request: Request):
    """Get member's credit score history"""
    user = await get_current_user(request)
    scores = await db.credit_scores.find({"user_id": ObjectId(user["_id"])}).sort("date", -1).to_list(100)
    return [{
        "id": str(s["_id"]),
        "date": s.get("date").isoformat() if s.get("date") else None,
        "equifax": s.get("equifax"),
        "experian": s.get("experian"),
        "transunion": s.get("transunion"),
        "source": s.get("source", "manual"),
        "notes": s.get("notes", "")
    } for s in scores]

@router.get("/latest")
async def get_latest_credit(request: Request):
    """Get member's latest credit scores"""
    user = await get_current_user(request)
    score = await db.credit_scores.find_one(
        {"user_id": ObjectId(user["_id"])},
        sort=[("date", -1)]
    )
    if not score:
        return {"equifax": None, "experian": None, "transunion": None}
    return {
        "id": str(score["_id"]),
        "date": score.get("date").isoformat() if score.get("date") else None,
        "equifax": score.get("equifax"),
        "experian": score.get("experian"),
        "transunion": score.get("transunion")
    }

@router.post("/score")
async def add_credit_score(request: Request):
    """Add new credit score entry"""
    user = await get_current_user(request)
    data = await request.json()

    # Parse date
    date_str = data.get("date")
    if date_str:
        try:
            score_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except:
            score_date = datetime.now(timezone.utc)
    else:
        score_date = datetime.now(timezone.utc)

    score_doc = {
        "user_id": ObjectId(user["_id"]),
        "date": score_date,
        "equifax": data.get("equifax"),
        "experian": data.get("experian"),
        "transunion": data.get("transunion"),
        "source": data.get("source", "manual"),
        "notes": data.get("notes", ""),
        "created_at": datetime.now(timezone.utc)
    }

    result = await db.credit_scores.insert_one(score_doc)
    return {"id": str(result.inserted_id), "message": "Credit score recorded"}

@router.put("/{score_id}")
async def update_credit_score(request: Request, score_id: str):
    """Update credit score entry"""
    user = await get_current_user(request)
    data = await request.json()

    score = await db.credit_scores.find_one({
        "_id": ObjectId(score_id),
        "user_id": ObjectId(user["_id"])
    })
    if not score:
        raise HTTPException(status_code=404, detail="Score not found")

    update_fields = {}
    if "equifax" in data:
        update_fields["equifax"] = data["equifax"]
    if "experian" in data:
        update_fields["experian"] = data["experian"]
    if "transunion" in data:
        update_fields["transunion"] = data["transunion"]
    if "source" in data:
        update_fields["source"] = data["source"]
    if "notes" in data:
        update_fields["notes"] = data["notes"]
    if "date" in data and data["date"]:
        try:
            update_fields["date"] = datetime.fromisoformat(data["date"].replace("Z", "+00:00"))
        except:
            pass

    update_fields["updated_at"] = datetime.now(timezone.utc)

    await db.credit_scores.update_one({"_id": ObjectId(score_id)}, {"$set": update_fields})
    return {"message": "Score updated"}

@router.delete("/{score_id}")
async def delete_credit_score(request: Request, score_id: str):
    """Delete credit score entry"""
    user = await get_current_user(request)
    result = await db.credit_scores.delete_one({
        "_id": ObjectId(score_id),
        "user_id": ObjectId(user["_id"])
    })
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Score not found")
    return {"message": "Score deleted"}

@router.get("/stats")
async def get_credit_stats(request: Request):
    """Get credit score statistics and trends"""
    user = await get_current_user(request)
    scores = await db.credit_scores.find({"user_id": ObjectId(user["_id"])}).sort("date", -1).to_list(24)

    if not scores:
        return {
            "current": {"equifax": None, "experian": None, "transunion": None},
            "change_30_days": {"equifax": None, "experian": None, "transunion": None},
            "average": {"equifax": None, "experian": None, "transunion": None}
        }

    current = scores[0] if scores else None

    # Find score from ~30 days ago
    thirty_days_ago = datetime.now(timezone.utc).replace(day=datetime.now(timezone.utc).day - 30) if datetime.now(timezone.utc).day > 30 else None
    old_score = None
    if thirty_days_ago:
        for s in scores:
            if s.get("date") and s["date"] <= thirty_days_ago:
                old_score = s
                break

    # Calculate averages
    eq_scores = [s["equifax"] for s in scores if s.get("equifax")]
    ex_scores = [s["experian"] for s in scores if s.get("experian")]
    tu_scores = [s["transunion"] for s in scores if s.get("transunion")]

    return {
        "current": {
            "equifax": current.get("equifax") if current else None,
            "experian": current.get("experian") if current else None,
            "transunion": current.get("transunion") if current else None,
            "date": current.get("date").isoformat() if current and current.get("date") else None
        },
        "change_30_days": {
            "equifax": (current.get("equifax") - old_score.get("equifax")) if current and old_score and current.get("equifax") and old_score.get("equifax") else None,
            "experian": (current.get("experian") - old_score.get("experian")) if current and old_score and current.get("experian") and old_score.get("experian") else None,
            "transunion": (current.get("transunion") - old_score.get("transunion")) if current and old_score and current.get("transunion") and old_score.get("transunion") else None
        },
        "average": {
            "equifax": round(sum(eq_scores) / len(eq_scores)) if eq_scores else None,
            "experian": round(sum(ex_scores) / len(ex_scores)) if ex_scores else None,
            "transunion": round(sum(tu_scores) / len(tu_scores)) if tu_scores else None
        }
    }

# Admin credit endpoints
@router.get("/admin/all")
async def get_all_credit_scores(request: Request):
    """Get all credit scores (admin only)"""
    await get_current_admin(request)

    pipeline = [
        {"$lookup": {
            "from": "users",
            "localField": "user_id",
            "foreignField": "_id",
            "as": "user"
        }},
        {"$unwind": {"path": "$user", "preserveNullAndEmptyArrays": True}},
        {"$sort": {"date": -1}},
        {"$limit": 500}
    ]

    scores = await db.credit_scores.aggregate(pipeline).to_list(500)
    return [{
        "id": str(s["_id"]),
        "user_id": str(s["user_id"]),
        "user_name": f"{s.get('user', {}).get('first_name', '')} {s.get('user', {}).get('last_name', '')}".strip(),
        "user_email": s.get("user", {}).get("email", ""),
        "date": s.get("date").isoformat() if s.get("date") else None,
        "equifax": s.get("equifax"),
        "experian": s.get("experian"),
        "transunion": s.get("transunion"),
        "source": s.get("source", "manual")
    } for s in scores]

@router.get("/admin/member/{member_id}")
async def get_member_credit_history(request: Request, member_id: str):
    """Get specific member's credit history (admin only)"""
    await get_current_admin(request)

    scores = await db.credit_scores.find({"user_id": ObjectId(member_id)}).sort("date", -1).to_list(100)
    return [{
        "id": str(s["_id"]),
        "date": s.get("date").isoformat() if s.get("date") else None,
        "equifax": s.get("equifax"),
        "experian": s.get("experian"),
        "transunion": s.get("transunion"),
        "source": s.get("source", "manual"),
        "notes": s.get("notes", "")
    } for s in scores]

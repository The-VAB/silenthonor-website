"""
Financial Counseling router — 10-tool tab on the Member Detail page.

Collection: fc_data (one document per member, upserted on first save)
  member_id    : ObjectId
  intake       : dict
  budgets      : list[dict]   (append-only versions)
  debt_plan    : dict
  goals        : list[dict]   (mutable, by id)
  session_notes: list[dict]   (append-only)
  housing      : dict
  retirement   : dict
  tax_ref      : dict
  fraud_checklist : dict
  referrals_used  : list[dict] (append-only)
  updated_at   : datetime
"""

from fastapi import APIRouter, HTTPException, Request
from bson import ObjectId
from datetime import datetime, timezone
import uuid

from middleware.auth_middleware import get_current_counselor

router = APIRouter(prefix="/api", tags=["Financial Counseling"])

db = None


def set_db(database):
    global db
    db = database


def _sanitize(obj):
    if isinstance(obj, ObjectId):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize(i) for i in obj]
    return obj


async def _verify_access(member_id: str, counselor: dict):
    """Counselors: must be assigned. Admins: any member."""
    try:
        mid = ObjectId(member_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid member ID")
    member = await db.users.find_one({"_id": mid, "role": "member"})
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    user_roles = counselor.get("roles") or [counselor.get("role", "")]
    if "admin" not in user_roles:
        cid = ObjectId(counselor["_id"])
        if member.get("assigned_counselor_id") != cid:
            raise HTTPException(status_code=403, detail="Not assigned to this member")
    return member


def _now():
    return datetime.now(timezone.utc)


# ── GET all FC data ────────────────────────────────────────────────────────────

@router.get("/counselor/members/{member_id}/fc")
async def get_fc_data(member_id: str, request: Request):
    counselor = await get_current_counselor(request)
    await _verify_access(member_id, counselor)
    doc = await db.fc_data.find_one({"member_id": ObjectId(member_id)})
    if not doc:
        return {}
    return _sanitize(doc)


# ── Tool 1: Client Intake ─────────────────────────────────────────────────────

@router.put("/counselor/members/{member_id}/fc/intake")
async def save_intake(member_id: str, request: Request):
    counselor = await get_current_counselor(request)
    await _verify_access(member_id, counselor)
    body = await request.json()
    now = _now()
    body.update({"completed": True, "completed_at": now})
    await db.fc_data.update_one(
        {"member_id": ObjectId(member_id)},
        {"$set": {"intake": body, "updated_at": now}},
        upsert=True
    )
    return {"message": "Intake saved"}


# ── Tool 2: Budgeting ─────────────────────────────────────────────────────────

@router.post("/counselor/members/{member_id}/fc/budgets")
async def save_budget(member_id: str, request: Request):
    counselor = await get_current_counselor(request)
    await _verify_access(member_id, counselor)
    body = await request.json()
    now = _now()
    doc = await db.fc_data.find_one({"member_id": ObjectId(member_id)}, {"budgets": 1})
    version = len((doc or {}).get("budgets", [])) + 1
    body.update({"id": str(uuid.uuid4()), "version": version, "created_at": now})
    await db.fc_data.update_one(
        {"member_id": ObjectId(member_id)},
        {"$push": {"budgets": body}, "$set": {"updated_at": now}},
        upsert=True
    )
    return {"id": body["id"], "version": version}


# ── Tool 3: Debt Payoff ───────────────────────────────────────────────────────

@router.put("/counselor/members/{member_id}/fc/debt-plan")
async def save_debt_plan(member_id: str, request: Request):
    counselor = await get_current_counselor(request)
    await _verify_access(member_id, counselor)
    body = await request.json()
    now = _now()
    body["updated_at"] = now
    await db.fc_data.update_one(
        {"member_id": ObjectId(member_id)},
        {"$set": {"debt_plan": body, "updated_at": now}},
        upsert=True
    )
    return {"message": "Debt plan saved"}


# ── Tool 4: Goals ─────────────────────────────────────────────────────────────

@router.post("/counselor/members/{member_id}/fc/goals")
async def add_goal(member_id: str, request: Request):
    counselor = await get_current_counselor(request)
    await _verify_access(member_id, counselor)
    body = await request.json()
    now = _now()
    body.update({"id": str(uuid.uuid4()), "status": "active", "created_at": now})
    await db.fc_data.update_one(
        {"member_id": ObjectId(member_id)},
        {"$push": {"goals": body}, "$set": {"updated_at": now}},
        upsert=True
    )
    return {"id": body["id"]}


@router.patch("/counselor/members/{member_id}/fc/goals/{goal_id}")
async def update_goal(member_id: str, goal_id: str, request: Request):
    counselor = await get_current_counselor(request)
    await _verify_access(member_id, counselor)
    body = await request.json()
    now = _now()
    set_fields = {f"goals.$[elem].{k}": v for k, v in body.items()}
    set_fields["updated_at"] = now
    result = await db.fc_data.update_one(
        {"member_id": ObjectId(member_id)},
        {"$set": set_fields},
        array_filters=[{"elem.id": goal_id}]
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Goal not found")
    return {"message": "Goal updated"}


@router.delete("/counselor/members/{member_id}/fc/goals/{goal_id}")
async def delete_goal(member_id: str, goal_id: str, request: Request):
    counselor = await get_current_counselor(request)
    await _verify_access(member_id, counselor)
    now = _now()
    await db.fc_data.update_one(
        {"member_id": ObjectId(member_id)},
        {"$pull": {"goals": {"id": goal_id}}, "$set": {"updated_at": now}}
    )
    return {"message": "Goal deleted"}


# ── Tool 5: Session Notes ─────────────────────────────────────────────────────

@router.post("/counselor/members/{member_id}/fc/session-notes")
async def add_session_note(member_id: str, request: Request):
    counselor = await get_current_counselor(request)
    await _verify_access(member_id, counselor)
    body = await request.json()
    now = _now()
    counselor_name = (
        (counselor.get("first_name") or "") + " " + (counselor.get("last_name") or "")
    ).strip() or "Counselor"
    body.update({"id": str(uuid.uuid4()), "created_at": now, "created_by": counselor_name})
    await db.fc_data.update_one(
        {"member_id": ObjectId(member_id)},
        {"$push": {"session_notes": body}, "$set": {"updated_at": now}},
        upsert=True
    )
    return {"id": body["id"]}


# ── Tool 6: Housing ───────────────────────────────────────────────────────────

@router.put("/counselor/members/{member_id}/fc/housing")
async def save_housing(member_id: str, request: Request):
    counselor = await get_current_counselor(request)
    await _verify_access(member_id, counselor)
    body = await request.json()
    body["updated_at"] = _now()
    await db.fc_data.update_one(
        {"member_id": ObjectId(member_id)},
        {"$set": {"housing": body, "updated_at": body["updated_at"]}},
        upsert=True
    )
    return {"message": "Housing data saved"}


# ── Tool 7: Retirement ────────────────────────────────────────────────────────

@router.put("/counselor/members/{member_id}/fc/retirement")
async def save_retirement(member_id: str, request: Request):
    counselor = await get_current_counselor(request)
    await _verify_access(member_id, counselor)
    body = await request.json()
    body["updated_at"] = _now()
    await db.fc_data.update_one(
        {"member_id": ObjectId(member_id)},
        {"$set": {"retirement": body, "updated_at": body["updated_at"]}},
        upsert=True
    )
    return {"message": "Retirement data saved"}


# ── Tool 8: Tax Reference ─────────────────────────────────────────────────────

@router.put("/counselor/members/{member_id}/fc/tax-ref")
async def save_tax_ref(member_id: str, request: Request):
    counselor = await get_current_counselor(request)
    await _verify_access(member_id, counselor)
    body = await request.json()
    body["updated_at"] = _now()
    await db.fc_data.update_one(
        {"member_id": ObjectId(member_id)},
        {"$set": {"tax_ref": body, "updated_at": body["updated_at"]}},
        upsert=True
    )
    return {"message": "Tax reference saved"}


# ── Tool 9: Fraud Checklist ───────────────────────────────────────────────────

@router.put("/counselor/members/{member_id}/fc/fraud-checklist")
async def save_fraud_checklist(member_id: str, request: Request):
    counselor = await get_current_counselor(request)
    await _verify_access(member_id, counselor)
    body = await request.json()
    body["updated_at"] = _now()
    await db.fc_data.update_one(
        {"member_id": ObjectId(member_id)},
        {"$set": {"fraud_checklist": body, "updated_at": body["updated_at"]}},
        upsert=True
    )
    return {"message": "Fraud checklist saved"}


# ── Tool 10: Referral Library ─────────────────────────────────────────────────

@router.post("/counselor/members/{member_id}/fc/referrals")
async def log_referral(member_id: str, request: Request):
    counselor = await get_current_counselor(request)
    await _verify_access(member_id, counselor)
    body = await request.json()
    now = _now()
    counselor_name = (
        (counselor.get("first_name") or "") + " " + (counselor.get("last_name") or "")
    ).strip() or "Counselor"
    body.update({"id": str(uuid.uuid4()), "logged_at": now, "logged_by": counselor_name})
    await db.fc_data.update_one(
        {"member_id": ObjectId(member_id)},
        {"$push": {"referrals_used": body}, "$set": {"updated_at": now}},
        upsert=True
    )
    return {"id": body["id"]}

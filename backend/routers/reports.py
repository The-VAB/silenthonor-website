# Reports router for Silent Honor Foundation
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Request
from bson import ObjectId

from middleware.auth_middleware import get_current_admin

router = APIRouter(prefix="/api/admin/reports", tags=["Reports"])

# Database reference
db = None

def set_db(database):
    global db
    db = database

@router.get("/overview")
async def get_overview_report(request: Request):
    """Get overview report with key metrics"""
    await get_current_admin(request)

    # Member counts
    total_members = await db.users.count_documents({"role": "member"})
    verified_members = await db.users.count_documents({"role": "member", "verified": True})
    active_members = await db.users.count_documents({"role": "member", "pipeline_stage": "active"})
    graduated_members = await db.users.count_documents({"role": "member", "pipeline_stage": "graduated"})

    # New members this month
    start_of_month = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    new_this_month = await db.users.count_documents({
        "role": "member",
        "created_at": {"$gte": start_of_month}
    })

    # Counselor stats
    total_counselors = await db.users.count_documents({"role": "counselor", "active": True})
    assigned_members = await db.users.count_documents({
        "role": "member",
        "assigned_counselor_id": {"$exists": True, "$ne": None}
    })

    # Course stats
    total_courses = await db.courses.count_documents({"status": {"$in": ["live", "published"]}})
    total_lessons_completed = await db.course_progress.count_documents({"percent_complete": 100})

    # Dispute stats
    total_disputes = await db.disputes.count_documents({})
    resolved_disputes = await db.disputes.count_documents({"status": "resolved"})
    pending_disputes = await db.disputes.count_documents({"status": {"$in": ["pending", "sent"]}})

    # Contact form stats
    total_contacts = await db.contacts.count_documents({})
    unresponded_contacts = await db.contacts.count_documents({"responded": False})

    return {
        "members": {
            "total": total_members,
            "verified": verified_members,
            "active": active_members,
            "graduated": graduated_members,
            "new_this_month": new_this_month,
            "with_counselor": assigned_members
        },
        "counselors": {
            "total": total_counselors,
            "avg_caseload": round(assigned_members / total_counselors) if total_counselors > 0 else 0
        },
        "courses": {
            "total": total_courses,
            "completions": total_lessons_completed
        },
        "disputes": {
            "total": total_disputes,
            "resolved": resolved_disputes,
            "pending": pending_disputes,
            "resolution_rate": round((resolved_disputes / total_disputes) * 100) if total_disputes > 0 else 0
        },
        "contacts": {
            "total": total_contacts,
            "unresponded": unresponded_contacts
        }
    }

@router.get("/pipeline")
async def get_pipeline_report(request: Request):
    """Get pipeline distribution report"""
    await get_current_admin(request)

    pipeline_stages = [
        "applied", "dd214_pending", "dd214_review", "approved",
        "counselor_assigned", "intake_complete", "active", "graduated", "inactive"
    ]

    distribution = {}
    for stage in pipeline_stages:
        count = await db.users.count_documents({"role": "member", "pipeline_stage": stage})
        distribution[stage] = count

    # Also get count of members without a stage (legacy)
    no_stage = await db.users.count_documents({
        "role": "member",
        "$or": [
            {"pipeline_stage": {"$exists": False}},
            {"pipeline_stage": None}
        ]
    })
    distribution["unassigned"] = no_stage

    return {
        "distribution": distribution,
        "stages": pipeline_stages
    }

@router.get("/branches")
async def get_branch_report(request: Request):
    """Get member distribution by military branch"""
    await get_current_admin(request)

    pipeline = [
        {"$match": {"role": "member"}},
        {"$group": {"_id": "$branch", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]

    results = await db.users.aggregate(pipeline).to_list(20)
    return [{
        "branch": r["_id"] or "Not Specified",
        "count": r["count"]
    } for r in results]

@router.get("/credit-progress")
async def get_credit_progress_report(request: Request):
    """Get credit score improvement report"""
    await get_current_admin(request)

    # Get members with at least 2 credit scores
    pipeline = [
        {"$group": {
            "_id": "$user_id",
            "scores": {"$push": {"date": "$date", "equifax": "$equifax", "experian": "$experian", "transunion": "$transunion"}},
            "count": {"$sum": 1}
        }},
        {"$match": {"count": {"$gte": 2}}},
        {"$limit": 100}
    ]

    results = await db.credit_scores.aggregate(pipeline).to_list(100)

    improvements = []
    for r in results:
        scores = sorted(r["scores"], key=lambda x: x.get("date") or datetime.min)
        if len(scores) >= 2:
            first = scores[0]
            last = scores[-1]

            # Calculate average improvement across bureaus
            changes = []
            if first.get("equifax") and last.get("equifax"):
                changes.append(last["equifax"] - first["equifax"])
            if first.get("experian") and last.get("experian"):
                changes.append(last["experian"] - first["experian"])
            if first.get("transunion") and last.get("transunion"):
                changes.append(last["transunion"] - first["transunion"])

            if changes:
                avg_change = round(sum(changes) / len(changes))
                improvements.append(avg_change)

    # Calculate overall statistics
    positive_changes = [c for c in improvements if c > 0]
    negative_changes = [c for c in improvements if c < 0]

    return {
        "members_tracked": len(improvements),
        "average_change": round(sum(improvements) / len(improvements)) if improvements else 0,
        "members_improved": len(positive_changes),
        "members_declined": len(negative_changes),
        "average_improvement": round(sum(positive_changes) / len(positive_changes)) if positive_changes else 0
    }

@router.get("/activity")
async def get_activity_report(request: Request, days: int = 30):
    """Get activity report for last N days"""
    await get_current_admin(request)

    start_date = datetime.now(timezone.utc) - timedelta(days=days)

    # New registrations
    new_members = await db.users.count_documents({
        "role": "member",
        "created_at": {"$gte": start_date}
    })

    # DD-214 uploads
    dd214_uploads = await db.users.count_documents({
        "dd214_uploaded_at": {"$gte": start_date}
    })

    # Disputes created
    new_disputes = await db.disputes.count_documents({
        "created_at": {"$gte": start_date}
    })

    # Messages sent
    new_messages = await db.messages.count_documents({
        "created_at": {"$gte": start_date}
    })

    # Credit scores logged
    new_scores = await db.credit_scores.count_documents({
        "created_at": {"$gte": start_date}
    })

    # Lessons completed
    lessons_completed = await db.course_progress.count_documents({
        "updated_at": {"$gte": start_date}
    })

    # Contacts received
    new_contacts = await db.contacts.count_documents({
        "created_at": {"$gte": start_date}
    })

    return {
        "period_days": days,
        "start_date": start_date.isoformat(),
        "metrics": {
            "new_members": new_members,
            "dd214_uploads": dd214_uploads,
            "new_disputes": new_disputes,
            "messages_sent": new_messages,
            "credit_scores_logged": new_scores,
            "course_activity": lessons_completed,
            "contact_submissions": new_contacts
        }
    }

@router.get("/counselor-performance")
async def get_counselor_performance(request: Request):
    """Get counselor performance metrics"""
    await get_current_admin(request)

    counselors = await db.users.find({"role": "counselor", "active": True}).to_list(50)

    results = []
    for c in counselors:
        counselor_id = c["_id"]

        # Assigned members count
        assigned = await db.users.count_documents({"assigned_counselor_id": counselor_id})

        # Active members
        active = await db.users.count_documents({
            "assigned_counselor_id": counselor_id,
            "pipeline_stage": "active"
        })

        # Graduated members
        graduated = await db.users.count_documents({
            "assigned_counselor_id": counselor_id,
            "pipeline_stage": "graduated"
        })

        # Messages sent (last 30 days)
        thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
        messages = await db.messages.count_documents({
            "from_user_id": counselor_id,
            "created_at": {"$gte": thirty_days_ago}
        })

        # Notes added (last 30 days)
        notes = await db.intake_notes.count_documents({
            "created_by": counselor_id,
            "created_at": {"$gte": thirty_days_ago}
        })

        results.append({
            "id": str(counselor_id),
            "name": f"{c.get('first_name', '')} {c.get('last_name', '')}".strip(),
            "email": c.get("email"),
            "assigned_members": assigned,
            "active_members": active,
            "graduated_members": graduated,
            "messages_last_30_days": messages,
            "notes_last_30_days": notes,
            "graduation_rate": round((graduated / assigned) * 100) if assigned > 0 else 0
        })

    return results

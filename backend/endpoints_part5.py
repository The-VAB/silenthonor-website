# Part 5 Endpoints: Messages, Disputes, Credit Scores, Counselors, Notes, Waitlist

from datetime import datetime, timezone
from fastapi import HTTPException, Request, UploadFile, File
from bson import ObjectId

def register_part5_endpoints(app, db, get_current_user, get_current_admin, hash_password):
    """Register Part 5 endpoints on the FastAPI app"""

    # ═══════════════════════════════════════════════════════════════════════════
    # MESSAGING SYSTEM
    # ═══════════════════════════════════════════════════════════════════════════

    @app.get("/api/messages")
    async def get_messages(request: Request, conversation_id: str = None):
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

    @app.post("/api/messages")
    async def send_message(request: Request):
        user = await get_current_user(request)
        data = await request.json()

        to_user_id = data.get("to_user_id")
        content = data.get("content", "").strip()

        if not to_user_id or not content:
            raise HTTPException(status_code=400, detail="Recipient and content required")

        message_doc = {
            "from_user_id": ObjectId(user["_id"]),
            "to_user_id": ObjectId(to_user_id),
            "content": content,
            "read": False,
            "created_at": datetime.now(timezone.utc)
        }

        result = await db.messages.insert_one(message_doc)
        return {"id": str(result.inserted_id), "message": "Message sent"}

    @app.get("/api/messages/conversations")
    async def get_conversations(request: Request):
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
                    "title": partner.get("role", "").replace("_", " ").title(),
                    "last_message": c.get("last_message", ""),
                    "last_time": c.get("last_time").isoformat() if c.get("last_time") else None,
                    "unread": c.get("unread_count", 0) > 0
                })

        return result

    @app.put("/api/messages/{message_id}/read")
    async def mark_message_read(request: Request, message_id: str):
        user = await get_current_user(request)
        await db.messages.update_one(
            {"_id": ObjectId(message_id), "to_user_id": ObjectId(user["_id"])},
            {"$set": {"read": True}}
        )
        return {"message": "Marked as read"}

    # ═══════════════════════════════════════════════════════════════════════════
    # DISPUTE TRACKER
    # ═══════════════════════════════════════════════════════════════════════════

    @app.get("/api/disputes")
    async def get_disputes(request: Request):
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

    @app.post("/api/disputes")
    async def create_dispute(request: Request):
        user = await get_current_user(request)
        data = await request.json()

        dispute_doc = {
            "user_id": ObjectId(user["_id"]),
            "bureau": data.get("bureau", ""),
            "account_name": data.get("account_name", ""),
            "account_number": data.get("account_number", ""),
            "dispute_reason": data.get("dispute_reason", ""),
            "status": "draft",
            "date_sent": None,
            "date_response": None,
            "response_outcome": None,
            "tracking_number": data.get("tracking_number"),
            "notes": data.get("notes", ""),
            "created_at": datetime.now(timezone.utc)
        }

        result = await db.disputes.insert_one(dispute_doc)
        return {"id": str(result.inserted_id), "message": "Dispute created"}

    @app.put("/api/disputes/{dispute_id}")
    async def update_dispute(request: Request, dispute_id: str):
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
        return {"message": "Dispute updated"}

    @app.delete("/api/disputes/{dispute_id}")
    async def delete_dispute(request: Request, dispute_id: str):
        user = await get_current_user(request)
        result = await db.disputes.delete_one({"_id": ObjectId(dispute_id), "user_id": ObjectId(user["_id"])})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Dispute not found")
        return {"message": "Dispute deleted"}

    @app.get("/api/admin/disputes")
    async def get_all_disputes(request: Request):
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
            "status": d.get("status", "pending"),
            "date_sent": d.get("date_sent").isoformat() if d.get("date_sent") else None,
            "created_at": d.get("created_at").isoformat() if d.get("created_at") else None
        } for d in disputes]

    # ═══════════════════════════════════════════════════════════════════════════
    # CREDIT SCORE TRACKER
    # ═══════════════════════════════════════════════════════════════════════════

    @app.get("/api/credit/history")
    async def get_credit_history(request: Request):
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

    @app.get("/api/credit/latest")
    async def get_latest_credit(request: Request):
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

    @app.post("/api/credit/score")
    async def add_credit_score(request: Request):
        user = await get_current_user(request)
        data = await request.json()

        score_doc = {
            "user_id": ObjectId(user["_id"]),
            "date": datetime.fromisoformat(data.get("date", datetime.now(timezone.utc).isoformat()).replace("Z", "+00:00")) if data.get("date") else datetime.now(timezone.utc),
            "equifax": data.get("equifax"),
            "experian": data.get("experian"),
            "transunion": data.get("transunion"),
            "source": data.get("source", "manual"),
            "notes": data.get("notes", ""),
            "created_at": datetime.now(timezone.utc)
        }

        result = await db.credit_scores.insert_one(score_doc)
        return {"id": str(result.inserted_id), "message": "Credit score recorded"}

    @app.delete("/api/credit/{score_id}")
    async def delete_credit_score(request: Request, score_id: str):
        user = await get_current_user(request)
        result = await db.credit_scores.delete_one({"_id": ObjectId(score_id), "user_id": ObjectId(user["_id"])})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Score not found")
        return {"message": "Score deleted"}

    # ═══════════════════════════════════════════════════════════════════════════
    # COUNSELOR MANAGEMENT
    # ═══════════════════════════════════════════════════════════════════════════

    @app.get("/api/counselor/assigned")
    async def get_assigned_counselor(request: Request):
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
            "specialties": counselor.get("specialties", [])
        }

    @app.get("/api/admin/counselors")
    async def get_counselors(request: Request):
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
                "assigned_members": assigned_count,
                "active": c.get("active", True)
            })

        return result

    @app.post("/api/admin/counselors")
    async def create_counselor(request: Request):
        await get_current_admin(request)
        data = await request.json()

        email = data.get("email", "").lower()
        if not email:
            raise HTTPException(status_code=400, detail="Email required")

        existing = await db.users.find_one({"email": email})
        if existing:
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
        return {"id": str(result.inserted_id), "message": "Counselor created"}

    @app.post("/api/admin/counselors/{counselor_id}/assign/{member_id}")
    async def assign_counselor(request: Request, counselor_id: str, member_id: str):
        await get_current_admin(request)

        counselor = await db.users.find_one({"_id": ObjectId(counselor_id), "role": "counselor"})
        if not counselor:
            raise HTTPException(status_code=404, detail="Counselor not found")

        await db.users.update_one(
            {"_id": ObjectId(member_id)},
            {"$set": {"assigned_counselor_id": ObjectId(counselor_id)}}
        )

        return {"message": "Counselor assigned to member"}

    @app.delete("/api/admin/counselors/{counselor_id}/unassign/{member_id}")
    async def unassign_counselor(request: Request, counselor_id: str, member_id: str):
        await get_current_admin(request)
        await db.users.update_one(
            {"_id": ObjectId(member_id)},
            {"$unset": {"assigned_counselor_id": ""}}
        )
        return {"message": "Counselor unassigned"}

    # ═══════════════════════════════════════════════════════════════════════════
    # INTAKE NOTES (Admin)
    # ═══════════════════════════════════════════════════════════════════════════

    @app.get("/api/admin/members/{member_id}/notes")
    async def get_member_notes(request: Request, member_id: str):
        await get_current_admin(request)
        notes = await db.intake_notes.find({"member_id": ObjectId(member_id)}).sort("created_at", -1).to_list(100)
        return [{
            "id": str(n["_id"]),
            "content": n.get("content", ""),
            "note_type": n.get("note_type", "general"),
            "created_by": n.get("created_by_name", "Admin"),
            "created_at": n.get("created_at").isoformat() if n.get("created_at") else None
        } for n in notes]

    @app.post("/api/admin/members/{member_id}/notes")
    async def add_member_note(request: Request, member_id: str):
        admin = await get_current_admin(request)
        data = await request.json()

        note_doc = {
            "member_id": ObjectId(member_id),
            "content": data.get("content", ""),
            "note_type": data.get("note_type", "general"),
            "created_by": ObjectId(admin["_id"]),
            "created_by_name": f"{admin.get('first_name', '')} {admin.get('last_name', '')}".strip() or "Admin",
            "created_at": datetime.now(timezone.utc)
        }

        result = await db.intake_notes.insert_one(note_doc)
        return {"id": str(result.inserted_id), "message": "Note added"}

    @app.delete("/api/admin/members/{member_id}/notes/{note_id}")
    async def delete_member_note(request: Request, member_id: str, note_id: str):
        await get_current_admin(request)
        await db.intake_notes.delete_one({"_id": ObjectId(note_id), "member_id": ObjectId(member_id)})
        return {"message": "Note deleted"}

    # ═══════════════════════════════════════════════════════════════════════════
    # COURSE WAITLIST
    # ═══════════════════════════════════════════════════════════════════════════

    @app.post("/api/courses/{course_id}/waitlist")
    async def join_waitlist(request: Request, course_id: str):
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

    @app.delete("/api/courses/{course_id}/waitlist")
    async def leave_waitlist(request: Request, course_id: str):
        user = await get_current_user(request)
        await db.waitlist.delete_one({"course_id": course_id, "user_id": ObjectId(user["_id"])})
        return {"message": "Removed from waitlist"}

    @app.get("/api/admin/waitlist")
    async def get_waitlist(request: Request):
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

    # ═══════════════════════════════════════════════════════════════════════════
    # MEMBER COURSE ACCESS (Public-facing)
    # ═══════════════════════════════════════════════════════════════════════════

    @app.get("/api/courses/progress")
    async def get_all_course_progress(request: Request):
        user = await get_current_user(request)
        progress = await db.course_progress.find({"user_id": ObjectId(user["_id"])}).to_list(100)
        return [{
            "course_id": str(p.get("course_id")),
            "completed_lessons": p.get("completed_lessons", []),
            "percent_complete": p.get("percent_complete", 0),
            "last_accessed": p.get("updated_at").isoformat() if p.get("updated_at") else None
        } for p in progress]

    @app.get("/api/courses/{course_id}")
    async def get_course_for_member(request: Request, course_id: str):
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
                "lessons": [{
                    "id": str(l["_id"]),
                    "title": l.get("title", ""),
                    "content": l.get("content", ""),
                    "duration": l.get("duration", "10 min"),
                    "video_url": l.get("video_url"),
                    "completed": str(l["_id"]) in completed_lessons
                } for l in lessons]
            }

        raise HTTPException(status_code=404, detail="Course not found")

    @app.post("/api/courses/{course_id}/lessons/{lesson_id}/complete")
    async def mark_lesson_complete(request: Request, course_id: str, lesson_id: str):
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

        return {"message": "Lesson marked complete", "percent_complete": percent}

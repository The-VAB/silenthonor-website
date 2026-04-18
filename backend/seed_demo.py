"""
Silent Honor Foundation — Demo Seed Script

Populates MongoDB with realistic sample data for demos / engineer handoff:
- 8 veteran members (mix of verified / pending_review / pending)
- 1 live course with 5 lessons
- 1 coming-soon course
- 5 contact form submissions
- Default site content for home hero

Usage:
    cd /app/backend && python seed_demo.py

Idempotent: all demo records are prefixed with DEMO_ (or email @demo.silenthonor.org)
so rerunning the script wipes & re-seeds without touching real data.
"""
import os
import asyncio
import bcrypt
from datetime import datetime, timezone, timedelta
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "silenthonor")
DEMO_EMAIL_DOMAIN = "@demo.silenthonor.org"
DEMO_PASSWORD = "Demo2024!"


def hash_pw(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


DEMO_MEMBERS = [
    {"email": f"james.morgan{DEMO_EMAIL_DOMAIN}", "first_name": "James", "last_name": "Morgan",
     "branch": "Army", "service_status": "Veteran", "state": "TX",
     "verified": True, "dd214_status": "verified", "dd214_file": None},
    {"email": f"maria.reyes{DEMO_EMAIL_DOMAIN}", "first_name": "Maria", "last_name": "Reyes",
     "branch": "Navy", "service_status": "Retired", "state": "FL",
     "verified": True, "dd214_status": "verified", "dd214_file": None},
    {"email": f"david.chen{DEMO_EMAIL_DOMAIN}", "first_name": "David", "last_name": "Chen",
     "branch": "Marine Corps", "service_status": "Veteran", "state": "CA",
     "verified": True, "dd214_status": "verified", "dd214_file": None},
    {"email": f"sarah.johnson{DEMO_EMAIL_DOMAIN}", "first_name": "Sarah", "last_name": "Johnson",
     "branch": "Air Force", "service_status": "Active Duty", "state": "CO",
     "verified": False, "dd214_status": "pending_review", "dd214_file": "demo_sample.pdf"},
    {"email": f"michael.brown{DEMO_EMAIL_DOMAIN}", "first_name": "Michael", "last_name": "Brown",
     "branch": "Coast Guard", "service_status": "Veteran", "state": "WA",
     "verified": False, "dd214_status": "pending_review", "dd214_file": "demo_sample.pdf"},
    {"email": f"jennifer.lee{DEMO_EMAIL_DOMAIN}", "first_name": "Jennifer", "last_name": "Lee",
     "branch": "National Guard", "service_status": "Reserve", "state": "NY",
     "verified": False, "dd214_status": "pending", "dd214_file": None},
    {"email": f"robert.garcia{DEMO_EMAIL_DOMAIN}", "first_name": "Robert", "last_name": "Garcia",
     "branch": "Army", "service_status": "Veteran", "state": "AZ",
     "verified": False, "dd214_status": "pending", "dd214_file": None},
    {"email": f"ashley.williams{DEMO_EMAIL_DOMAIN}", "first_name": "Ashley", "last_name": "Williams",
     "branch": "Space Force", "service_status": "Active Duty", "state": "MO",
     "verified": False, "dd214_status": "pending", "dd214_file": None},
]


DEMO_COURSES = [
    {
        "title": "DEMO_Credit Education for Veterans",
        "description": "Master your credit report, dispute errors, and rebuild your score from any starting point. Taught by a Certified Credit Counselor.",
        "status": "live",
        "category": "Credit",
        "thumbnail": None,
        "lessons": [
            {"title": "Introduction to Credit", "content": "What credit is, how it works, and why it matters for veterans transitioning to civilian life.", "duration": "18 min", "order": 1},
            {"title": "How Credit Scores Are Calculated", "content": "Breakdown of FICO vs VantageScore and the five factors that move your score.", "duration": "22 min", "order": 2},
            {"title": "Reading Your Credit Report", "content": "Line-by-line walkthrough of Experian, Equifax, and TransUnion reports.", "duration": "25 min", "order": 3},
            {"title": "Disputing Errors", "content": "Step-by-step dispute process with sample letters for veterans.", "duration": "20 min", "order": 4},
            {"title": "Rebuilding After Damage", "content": "Practical 90-day action plan to raise a damaged score.", "duration": "28 min", "order": 5},
        ],
    },
    {
        "title": "DEMO_Financial Literacy Foundations",
        "description": "The financial fundamentals most people learn the hard way — budgeting, debt, savings, income.",
        "status": "coming_soon",
        "category": "Finance",
        "thumbnail": None,
        "lessons": [],
    },
]


DEMO_CONTACTS = [
    {"first_name": "Thomas", "last_name": "Reid", "email": f"thomas.reid{DEMO_EMAIL_DOMAIN}",
     "branch": "Army", "status": "Veteran", "topic": "Credit Help",
     "message": "Hi, I'm a 10-year Army vet trying to buy my first home. My credit score is 580 and I don't know where to start. Can you help?"},
    {"first_name": "Linda", "last_name": "Patel", "email": f"linda.patel{DEMO_EMAIL_DOMAIN}",
     "branch": "Family Member", "status": "Family", "topic": "Financial Coaching",
     "message": "My husband is retiring from the Navy next year and we'd love coaching on how to manage his pension + disability income."},
    {"first_name": "Carlos", "last_name": "Mendez", "email": f"carlos.mendez{DEMO_EMAIL_DOMAIN}",
     "branch": "Marine Corps", "status": "Veteran", "topic": "VA Loan",
     "message": "Interested in learning about VA loan closing cost assistance — when does that program launch?"},
    {"first_name": "Amanda", "last_name": "Foster", "email": f"amanda.foster{DEMO_EMAIL_DOMAIN}",
     "branch": "Air Force", "status": "Active Duty", "topic": "Courses",
     "message": "Are the courses self-paced? I'm deployed and only get internet a few hours a week."},
    {"first_name": "Greg", "last_name": "Sanders", "email": f"greg.sanders{DEMO_EMAIL_DOMAIN}",
     "branch": None, "status": None, "topic": "Partnership / Donation",
     "message": "I run a small business in St. Louis and want to sponsor a cohort of veterans through your program. What's the process?"},
]


async def seed():
    print(f"Connecting to {MONGO_URL} / {DB_NAME} ...")
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    # ---- Members ----
    print("\n[1/4] Seeding demo members...")
    deleted = await db.users.delete_many({"email": {"$regex": DEMO_EMAIL_DOMAIN + "$"}})
    print(f"  removed {deleted.deleted_count} old demo members")

    now = datetime.now(timezone.utc)
    for i, m in enumerate(DEMO_MEMBERS):
        doc = {
            **m,
            "password_hash": hash_pw(DEMO_PASSWORD),
            "role": "member",
            "created_at": now - timedelta(days=30 - i * 3),
        }
        if m.get("dd214_status") in ("pending_review", "verified"):
            doc["dd214_uploaded_at"] = now - timedelta(days=5 - (i % 5))
        if m.get("verified"):
            doc["verified_at"] = now - timedelta(days=3)
        await db.users.insert_one(doc)
    print(f"  inserted {len(DEMO_MEMBERS)} members (password: {DEMO_PASSWORD})")

    # ---- Courses + Lessons ----
    print("\n[2/4] Seeding demo courses + lessons...")
    old_courses = await db.courses.find({"title": {"$regex": "^DEMO_"}}).to_list(100)
    old_ids = [str(c["_id"]) for c in old_courses]
    await db.lessons.delete_many({"course_id": {"$in": old_ids}})
    await db.courses.delete_many({"title": {"$regex": "^DEMO_"}})
    print(f"  removed {len(old_courses)} old demo courses and their lessons")

    for c in DEMO_COURSES:
        lessons = c.pop("lessons", [])
        course_doc = {**c, "created_at": now, "updated_at": now}
        result = await db.courses.insert_one(course_doc)
        course_id = str(result.inserted_id)
        for lesson in lessons:
            await db.lessons.insert_one({
                **lesson,
                "course_id": course_id,
                "video_url": None,
                "created_at": now,
            })
        print(f"  + {c['title']}  ({len(lessons)} lessons, status={c['status']})")

    # ---- Contacts ----
    print("\n[3/4] Seeding demo contact submissions...")
    deleted = await db.contacts.delete_many({"email": {"$regex": DEMO_EMAIL_DOMAIN + "$"}})
    print(f"  removed {deleted.deleted_count} old demo contacts")

    for i, contact in enumerate(DEMO_CONTACTS):
        await db.contacts.insert_one({
            **contact,
            "created_at": now - timedelta(hours=i * 18),
            "responded": i >= 3,
        })
    print(f"  inserted {len(DEMO_CONTACTS)} contact submissions")

    # ---- Site content (home hero) ----
    print("\n[4/4] Seeding default site content...")
    await db.site_content.update_one(
        {"page": "home", "section": "hero"},
        {"$set": {
            "page": "home",
            "section": "hero",
            "content": {
                "tagline": "Honor Earned. Futures Rebuilt.",
                "headline": "Financial freedom, built for veterans.",
                "subhead": "Free financial education, credit coaching, and homeownership prep — from people who understand the mission.",
            },
            "updated_at": now,
        }},
        upsert=True,
    )
    print("  upserted home.hero content block")

    print("\n✓ Demo seed complete.")
    print(f"  Members: {await db.users.count_documents({'role': 'member'})}  "
          f"Courses: {await db.courses.count_documents({})}  "
          f"Contacts: {await db.contacts.count_documents({})}")
    print(f"\n  Try it: log in with any demo member:")
    print(f"    james.morgan{DEMO_EMAIL_DOMAIN} / {DEMO_PASSWORD}    (verified)")
    print(f"    sarah.johnson{DEMO_EMAIL_DOMAIN} / {DEMO_PASSWORD}  (DD-214 under review)")
    print(f"    robert.garcia{DEMO_EMAIL_DOMAIN} / {DEMO_PASSWORD}  (no DD-214 yet)")

    client.close()


if __name__ == "__main__":
    asyncio.run(seed())

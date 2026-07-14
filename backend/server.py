"""
Silent Honor Foundation API
Main application entry point with modular router architecture
"""
from dotenv import load_dotenv
load_dotenv()

import os
import asyncio
from datetime import datetime, timezone, timedelta
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from motor.motor_asyncio import AsyncIOMotorClient

# Import routers and middleware
from routers import all_routers, initialize_routers
from middleware import initialize_middleware, RequestLoggingMiddleware, logger
from utils.auth import hash_password, verify_password

# Initialize FastAPI
app = FastAPI(
    title="Silent Honor Foundation API",
    description="Backend API for Silent Honor Foundation veteran services",
    version="2.0.0"
)

# CORS Configuration
# Origins are env-driven (CORS_ORIGINS, comma-separated) so the same binary works
# across the new domain (silenthonorfoundation.org), the legacy domain
# (silenthonor.org), and local dev without a code change + redeploy. The default set
# covers both production domains + www so a credentialed cross-site request from the
# static frontend to the api.* subdomain is not silently blocked by CORS.
_DEFAULT_CORS_ORIGINS = [
    "https://silenthonorfoundation.org",
    "https://www.silenthonorfoundation.org",
    "https://silenthonor.org",
    "https://www.silenthonor.org",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
_env_origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip()]
ALLOWED_ORIGINS = _env_origins or _DEFAULT_CORS_ORIGINS

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add request logging middleware
app.add_middleware(RequestLoggingMiddleware)

# Resolve the directory that holds the frontend (index.html, css/, js/, images/).
# Emergent/Docker copies everything under /app; on the VPS the FastAPI service runs
# from backend/ and the frontend lives one level up (the repo root). Resolve it once
# so static mounts and HTML routes work in every deployment shape instead of assuming
# a hardcoded /app.
def _resolve_base_dir() -> str:
    env_dir = os.environ.get("APP_DIR")
    if env_dir and os.path.isfile(os.path.join(env_dir, "index.html")):
        return env_dir
    if os.path.isfile("/app/index.html"):
        return "/app"
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

BASE_DIR = _resolve_base_dir()
# Uploads are kept alongside the running service (matches utils/storage.py, which the
# live server already uses) rather than the frontend dir.
UPLOADS_DIR = os.environ.get("UPLOADS_DIR", "/app/uploads")

# Serve static files
def _mount_static(url: str, directory: str, name: str):
    if os.path.isdir(directory):
        app.mount(url, StaticFiles(directory=directory), name=name)
    else:
        logger.warning(f"Static dir not found, skipping mount {url} -> {directory}")

try:
    _mount_static("/css", os.path.join(BASE_DIR, "css"), "css")
    _mount_static("/js", os.path.join(BASE_DIR, "js"), "js")
    _mount_static("/images", os.path.join(BASE_DIR, "images"), "images")
    if os.path.isdir(UPLOADS_DIR):
        app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")
except Exception as e:
    logger.warning(f"Could not mount static files: {e}")

# MongoDB connection — accept both MONGO_URL/DB_NAME (what this service reads) and the
# MONGODB_URI/MONGODB_DB names used by docker-compose/.env.example, so the compose stack
# actually reaches Mongo instead of silently falling back to localhost.
MONGO_URL = os.environ.get("MONGO_URL") or os.environ.get("MONGODB_URI", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME") or os.environ.get("MONGODB_DB", "silenthonor")

client = None
db = None

async def daily_task_reminder_loop():
    """Fire send_task_reminders every day at 8 AM UTC."""
    from utils.email import send_task_reminders
    while True:
        now = datetime.now(timezone.utc)
        target = now.replace(hour=8, minute=0, second=0, microsecond=0)
        if now >= target:
            target += timedelta(days=1)
        await asyncio.sleep((target - now).total_seconds())
        try:
            await send_task_reminders(db)
            logger.info("Daily task reminders sent")
        except Exception as e:
            logger.error(f"Task reminder error: {e}")


@app.on_event("startup")
async def startup_db():
    global client, db
    logger.info("Starting Silent Honor Foundation API...")

    # Connect to MongoDB
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    logger.info(f"Connected to MongoDB: {DB_NAME}")

    # Initialize middleware with database
    initialize_middleware(db)

    # Initialize routers with database
    initialize_routers(db)

    # Register all routers
    for router in all_routers:
        app.include_router(router)

    # Create indexes
    await create_indexes()

    # Seed admin user
    await seed_admin()

    # One-time migration: bring legacy static courses into the DB-managed course system
    await migrate_legacy_courses()

    # Create required directories
    os.makedirs(os.path.join(UPLOADS_DIR, "dd214"), exist_ok=True)
    os.makedirs(os.path.join(UPLOADS_DIR, "documents"), exist_ok=True)

    # Start daily task reminder loop (fires at 8 AM UTC)
    asyncio.create_task(daily_task_reminder_loop())

    logger.info("API startup complete")

@app.on_event("shutdown")
async def shutdown_db():
    global client
    if client:
        client.close()
        logger.info("MongoDB connection closed")

async def create_indexes():
    """Create database indexes"""
    try:
        # User indexes
        await db.users.create_index("email", unique=True)
        await db.users.create_index("role")
        await db.users.create_index("pipeline_stage")
        await db.users.create_index("credit_repair_stage")
        await db.users.create_index("financial_counseling_stage")
        await db.users.create_index("assigned_counselor_id")
        await db.users.create_index("program_track")
        await db.users.create_index("last_activity_date")

        # Documents collection
        await db.documents.create_index("member_id")
        await db.documents.create_index("uploaded_at")

        # Token indexes
        await db.password_reset_tokens.create_index("expires_at", expireAfterSeconds=0)
        await db.token_blacklist.create_index("expires_at", expireAfterSeconds=0)

        # Login attempts
        await db.login_attempts.create_index("identifier")

        # Messages
        await db.messages.create_index([("from_user_id", 1), ("to_user_id", 1)])
        await db.messages.create_index("created_at")

        # Disputes
        await db.disputes.create_index("user_id")
        await db.disputes.create_index("status")

        # Credit scores
        await db.credit_scores.create_index([("user_id", 1), ("date", -1)])
        await db.credit_scores.create_index([("member_id", 1), ("bureau", 1), ("date_pulled", -1)])

        # Tasks
        await db.tasks.create_index([("counselor_id", 1), ("due_date", 1)])
        await db.tasks.create_index([("member_id", 1)])
        await db.tasks.create_index([("dispute_id", 1)])

        # Financial counseling data
        await db.fc_data.create_index("member_id", unique=True)

        # Credit accounts (game plan)
        await db.credit_accounts.create_index([("member_id", 1)])
        await db.credit_accounts.create_index([("counselor_id", 1)])

        # Course progress
        await db.course_progress.create_index([("user_id", 1), ("course_id", 1)])

        # Audit log
        await db.audit_log.create_index("timestamp")
        await db.audit_log.create_index("action")

        logger.info("Database indexes created")
    except Exception as e:
        logger.error(f"Error creating indexes: {e}")

async def seed_admin():
    """Seed admin user if not exists"""
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@silenthonor.org")
    admin_password = os.environ.get("ADMIN_PASSWORD", "admin123")

    existing = await db.users.find_one({"email": admin_email})
    if existing is None:
        hashed = hash_password(admin_password)
        await db.users.insert_one({
            "email": admin_email,
            "password_hash": hashed,
            "first_name": "Admin",
            "last_name": "User",
            "role": "admin",
            "verified": True,
            "active": True,
            "created_at": datetime.now(timezone.utc)
        })
        logger.info(f"Admin user created: {admin_email}")
    elif not verify_password(admin_password, existing["password_hash"]):
        await db.users.update_one(
            {"email": admin_email},
            {"$set": {"password_hash": hash_password(admin_password)}}
        )
        logger.info(f"Admin password updated: {admin_email}")

    # Write credentials to a local test file for DEVELOPMENT ONLY. Never in production —
    # this file previously leaked a real admin password into the public git repo.
    if os.environ.get("ENVIRONMENT", "development").lower() == "production":
        return
    try:
        memory_dir = os.path.join(BASE_DIR, "memory")
        os.makedirs(memory_dir, exist_ok=True)
        with open(os.path.join(memory_dir, "test_credentials.md"), "w") as f:
            f.write("# Test Credentials (development only — gitignored)\n\n")
            f.write("## Admin Account\n")
            f.write(f"- Email: {admin_email}\n")
            f.write(f"- Password: {admin_password}\n")
            f.write("- Role: admin\n\n")
            f.write("## API Documentation\n")
            f.write("- OpenAPI: /docs\n")
            f.write("- ReDoc: /redoc\n")
    except Exception as e:
        logger.warning(f"Could not write test credentials: {e}")

async def migrate_legacy_courses():
    """One-time migration: move the old hardcoded member courses into db.courses
    so they show up in the admin course manager and can be edited/deleted/published."""
    marker = await db.migrations.find_one({"name": "legacy_courses_v1"})
    if marker:
        return

    legacy_courses = [
        {
            "legacy_id": "credit-education",
            "title": "Credit Education for Veterans",
            "description": "Learn the fundamentals of credit scores, credit reports, and how to build and repair your credit as a veteran.",
            "category": "credit",
            "status": "published",
            "lessons": [
                {"title": "Understanding Your Credit Score", "duration": "15 min", "content": "<p>Your credit score is a three-digit number that represents your creditworthiness. Lenders use this score to determine whether to approve your loan applications and what interest rate to charge.</p><h3>Key Components</h3><ul><li><strong>Payment History (35%)</strong> - Your track record of paying bills on time</li><li><strong>Credit Utilization (30%)</strong> - How much of your available credit you use</li><li><strong>Length of Credit History (15%)</strong> - How long you have had credit accounts</li><li><strong>Credit Mix (10%)</strong> - The variety of credit types you have</li><li><strong>New Credit (10%)</strong> - Recent credit inquiries and new accounts</li></ul>"},
                {"title": "Reading Your Credit Report", "duration": "20 min", "content": "<p>Your credit report contains detailed information about your credit history. Learning to read it is essential for maintaining good credit health.</p><h3>What to Look For</h3><ul><li>Personal information accuracy</li><li>Account statuses and payment history</li><li>Public records and collections</li><li>Credit inquiries</li></ul><p>You are entitled to one free credit report from each bureau annually at AnnualCreditReport.com.</p>"},
                {"title": "Building Credit from Scratch", "duration": "18 min", "content": "<p>If you have no credit history, building it can seem challenging. Here are proven strategies to establish credit.</p><h3>Getting Started</h3><ul><li>Become an authorized user on a family member account</li><li>Apply for a secured credit card</li><li>Consider a credit-builder loan</li><li>Report rent payments to credit bureaus</li></ul>"},
                {"title": "Common Credit Mistakes", "duration": "12 min", "content": "<p>Avoiding these common mistakes can save you from credit score damage.</p><h3>Mistakes to Avoid</h3><ul><li>Paying late or missing payments</li><li>Maxing out credit cards</li><li>Closing old accounts</li><li>Applying for too much credit at once</li><li>Ignoring your credit report</li></ul>"},
                {"title": "Dispute Process Overview", "duration": "25 min", "content": "<p>If you find errors on your credit report, you have the right to dispute them. This lesson covers the dispute process.</p><h3>The Dispute Process</h3><ol><li>Identify the error on your report</li><li>Gather supporting documentation</li><li>Write a dispute letter via certified mail</li><li>Wait for investigation (30-45 days)</li><li>Review results and follow up if needed</li></ol><p><strong>Important:</strong> Always dispute via certified mail, never online. This preserves your legal rights under the Fair Credit Reporting Act.</p>"}
            ]
        },
        {
            "legacy_id": "financial-literacy",
            "title": "Financial Literacy Foundations",
            "description": "Build essential money management skills, including budgeting, saving, and planning for your financial future.",
            "category": "financial",
            "status": "published",
            "lessons": []
        },
        {
            "legacy_id": "money-mission",
            "title": "Money Mission: Complete Financial Literacy",
            "description": "A comprehensive financial literacy program covering budgeting, saving, investing, and long-term financial planning.",
            "category": "financial",
            "status": "coming_soon",
            "lessons": []
        },
        {
            "legacy_id": "va-loan",
            "title": "VA Loan & Homeownership Prep",
            "description": "Everything veterans need to know to use their VA home loan benefit and prepare for homeownership.",
            "category": "housing",
            "status": "coming_soon",
            "lessons": [
                {"title": "VA Loan Basics", "duration": "20 min", "content": "<p>VA loans are a powerful benefit for veterans, offering favorable terms not available with conventional mortgages.</p><h3>Key Benefits</h3><ul><li>No down payment required</li><li>No private mortgage insurance (PMI)</li><li>Competitive interest rates</li><li>Limited closing costs</li><li>No prepayment penalty</li></ul>"},
                {"title": "Eligibility Requirements", "duration": "15 min", "content": "<p>Understanding VA loan eligibility is the first step to homeownership.</p><h3>Service Requirements</h3><ul><li>90 consecutive days active duty during wartime</li><li>181 days active duty during peacetime</li><li>6 years in the National Guard or Reserves</li><li>Surviving spouse of veteran who died in service</li></ul>"}
            ]
        }
    ]

    for lc in legacy_courses:
        existing = await db.courses.find_one({"legacy_id": lc["legacy_id"]})
        if existing:
            continue
        now = datetime.now(timezone.utc)
        result = await db.courses.insert_one({
            "legacy_id": lc["legacy_id"],
            "title": lc["title"],
            "description": lc["description"],
            "category": lc["category"],
            "status": lc["status"],
            "thumbnail": None,
            "created_at": now,
            "updated_at": now
        })
        course_id = str(result.inserted_id)
        for i, lesson in enumerate(lc["lessons"]):
            await db.lessons.insert_one({
                "course_id": course_id,
                "module_id": None,
                "title": lesson["title"],
                "content": lesson["content"],
                "lesson_type": "text",
                "order": i,
                "video_url": None,
                "resource_url": None,
                "duration": lesson["duration"],
                "created_at": now
            })

    await db.migrations.insert_one({"name": "legacy_courses_v1", "applied_at": datetime.now(timezone.utc)})
    logger.info("Legacy courses migrated into db.courses")

# HTML page serving.
# In production the static frontend is served by nginx; these routes are a fallback so
# the API host can also serve pages (Emergent/all-in-one). Resolved against BASE_DIR and
# guarded so a missing file returns a clean 404 instead of a 500.
from fastapi.responses import HTMLResponse

def _serve_page(name: str):
    filepath = os.path.join(BASE_DIR, f"{name}.html")
    if os.path.isfile(filepath):
        return FileResponse(filepath, media_type="text/html")
    fallback = os.path.join(BASE_DIR, "404.html")
    if os.path.isfile(fallback):
        return FileResponse(fallback, status_code=404, media_type="text/html")
    return HTMLResponse("<h1>404 — Page Not Found</h1>", status_code=404)

@app.get("/{page}.html")
async def serve_html_page(page: str):
    return _serve_page(page)

# Clean URL routes
@app.get("/")
async def serve_index():
    return _serve_page("index")

@app.get("/login")
async def serve_login():
    return _serve_page("login")

@app.get("/signup")
async def serve_signup():
    return _serve_page("signup")

@app.get("/dashboard")
async def serve_dashboard():
    return _serve_page("dashboard")

@app.get("/admin")
async def serve_admin():
    return _serve_page("admin")

@app.get("/contact")
async def serve_contact():
    return _serve_page("contact")

@app.get("/courses")
async def serve_courses():
    return _serve_page("courses")

@app.get("/counselor")
async def serve_counselor():
    return _serve_page("counselor")

@app.get("/credit-tracker")
async def serve_credit_tracker():
    return _serve_page("credit-tracker")

@app.get("/dispute-tracker")
async def serve_dispute_tracker():
    return _serve_page("dispute-tracker")

@app.get("/messages")
async def serve_messages():
    return _serve_page("messages")

@app.get("/reset-password")
async def serve_reset_password():
    return _serve_page("reset-password")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))

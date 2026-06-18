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

# CORS Configuration - DO NOT MODIFY THESE SETTINGS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://silenthonor.org", "https://www.silenthonor.org"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add request logging middleware
app.add_middleware(RequestLoggingMiddleware)

# Serve static files
try:
    app.mount("/css", StaticFiles(directory="/app/css"), name="css")
    app.mount("/js", StaticFiles(directory="/app/js"), name="js")
    app.mount("/images", StaticFiles(directory="/app/images"), name="images")
    app.mount("/uploads", StaticFiles(directory="/app/uploads"), name="uploads")
except Exception as e:
    logger.warning(f"Could not mount static files: {e}")

# MongoDB connection
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "silenthonor")

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
    os.makedirs("/app/uploads/dd214", exist_ok=True)
    os.makedirs("/app/uploads/documents", exist_ok=True)
    os.makedirs("/app/memory", exist_ok=True)

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

    # Write credentials to test file (for development only)
    try:
        with open("/app/memory/test_credentials.md", "w") as f:
            f.write("# Test Credentials\n\n")
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

# HTML page serving
@app.get("/{page}.html")
async def serve_html_page(page: str):
    filepath = f"/app/{page}.html"
    if os.path.exists(filepath):
        return FileResponse(filepath, media_type="text/html")
    return FileResponse("/app/404.html", status_code=404, media_type="text/html")

# Clean URL routes
@app.get("/")
async def serve_index():
    return FileResponse("/app/index.html", media_type="text/html")

@app.get("/login")
async def serve_login():
    return FileResponse("/app/login.html", media_type="text/html")

@app.get("/signup")
async def serve_signup():
    return FileResponse("/app/signup.html", media_type="text/html")

@app.get("/dashboard")
async def serve_dashboard():
    return FileResponse("/app/dashboard.html", media_type="text/html")

@app.get("/admin")
async def serve_admin():
    return FileResponse("/app/admin.html", media_type="text/html")

@app.get("/contact")
async def serve_contact():
    return FileResponse("/app/contact.html", media_type="text/html")

@app.get("/courses")
async def serve_courses():
    return FileResponse("/app/courses.html", media_type="text/html")

@app.get("/counselor")
async def serve_counselor():
    return FileResponse("/app/counselor.html", media_type="text/html")

@app.get("/credit-tracker")
async def serve_credit_tracker():
    return FileResponse("/app/credit-tracker.html", media_type="text/html")

@app.get("/dispute-tracker")
async def serve_dispute_tracker():
    return FileResponse("/app/dispute-tracker.html", media_type="text/html")

@app.get("/messages")
async def serve_messages():
    return FileResponse("/app/messages.html", media_type="text/html")

@app.get("/reset-password")
async def serve_reset_password():
    return FileResponse("/app/reset-password.html", media_type="text/html")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)

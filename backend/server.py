"""
Silent Honor Foundation API
Main application entry point with modular router architecture
"""
from dotenv import load_dotenv
load_dotenv()

import os
from datetime import datetime, timezone
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
    app.mount("/uploads", StaticFiles(directory="/app/uploads"), name="uploads")
except Exception as e:
    logger.warning(f"Could not mount static files: {e}")

# MongoDB connection
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "silenthonor")

client = None
db = None

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

    # Create required directories
    os.makedirs("/app/uploads/dd214", exist_ok=True)
    os.makedirs("/app/memory", exist_ok=True)

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

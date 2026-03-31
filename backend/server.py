from dotenv import load_dotenv
load_dotenv()

import os
import secrets
import bcrypt
import jwt
import aiofiles
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import FastAPI, HTTPException, Request, Response, UploadFile, File, Form, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from pydantic import BaseModel, EmailStr
import uuid

# JWT Configuration
JWT_ALGORITHM = "HS256"

def get_jwt_secret() -> str:
    return os.environ.get("JWT_SECRET", "default_secret_change_me")

# Password utilities
def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))

# JWT utilities
def create_access_token(user_id: str, email: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=60),
        "type": "access"
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)

def create_refresh_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(days=7),
        "type": "refresh"
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)

# Pydantic models
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    first_name: str
    last_name: str
    phone: Optional[str] = None
    state: Optional[str] = None
    branch: Optional[str] = None
    service_status: Optional[str] = None
    years_of_service: Optional[str] = None
    separation_year: Optional[str] = None
    challenges: Optional[list] = []
    notes: Optional[str] = None

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class ContactRequest(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    branch: Optional[str] = None
    status: Optional[str] = None
    topic: Optional[str] = None
    message: str

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

# Initialize FastAPI
app = FastAPI(title="Silent Honor Foundation API")

# CORS
frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:3000")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files
app.mount("/css", StaticFiles(directory="/app/css"), name="css")
app.mount("/js", StaticFiles(directory="/app/js"), name="js")
app.mount("/uploads", StaticFiles(directory="/app/uploads"), name="uploads")

# MongoDB connection
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "silenthonor")

client = None
db = None

@app.on_event("startup")
async def startup_db():
    global client, db
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    
    # Create indexes
    await db.users.create_index("email", unique=True)
    await db.password_reset_tokens.create_index("expires_at", expireAfterSeconds=0)
    await db.login_attempts.create_index("identifier")
    
    # Seed admin
    await seed_admin()
    
    # Create uploads directory
    os.makedirs("/app/uploads/dd214", exist_ok=True)

@app.on_event("shutdown")
async def shutdown_db():
    global client
    if client:
        client.close()

async def seed_admin():
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
            "created_at": datetime.now(timezone.utc)
        })
        print(f"Admin user created: {admin_email}")
    elif not verify_password(admin_password, existing["password_hash"]):
        await db.users.update_one(
            {"email": admin_email},
            {"$set": {"password_hash": hash_password(admin_password)}}
        )
        print(f"Admin password updated: {admin_email}")
    
    # Write credentials to test file
    os.makedirs("/app/memory", exist_ok=True)
    with open("/app/memory/test_credentials.md", "w") as f:
        f.write("# Test Credentials\n\n")
        f.write("## Admin Account\n")
        f.write(f"- Email: {admin_email}\n")
        f.write(f"- Password: {admin_password}\n")
        f.write("- Role: admin\n\n")
        f.write("## Auth Endpoints\n")
        f.write("- POST /api/auth/register\n")
        f.write("- POST /api/auth/login\n")
        f.write("- POST /api/auth/logout\n")
        f.write("- GET /api/auth/me\n")

# Auth helper
async def get_current_user(request: Request) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user = await db.users.find_one({"_id": ObjectId(payload["sub"])})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        user["_id"] = str(user["_id"])
        user.pop("password_hash", None)
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

async def get_current_admin(request: Request) -> dict:
    user = await get_current_user(request)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user

# Brute force protection
async def check_brute_force(identifier: str):
    attempt = await db.login_attempts.find_one({"identifier": identifier})
    if attempt and attempt.get("count", 0) >= 5:
        lockout_until = attempt.get("lockout_until")
        if lockout_until and datetime.now(timezone.utc) < lockout_until:
            raise HTTPException(status_code=429, detail="Too many failed attempts. Try again later.")
        else:
            await db.login_attempts.delete_one({"identifier": identifier})

async def record_failed_attempt(identifier: str):
    attempt = await db.login_attempts.find_one({"identifier": identifier})
    if attempt:
        new_count = attempt.get("count", 0) + 1
        update = {"$set": {"count": new_count}}
        if new_count >= 5:
            update["$set"]["lockout_until"] = datetime.now(timezone.utc) + timedelta(minutes=15)
        await db.login_attempts.update_one({"identifier": identifier}, update)
    else:
        await db.login_attempts.insert_one({"identifier": identifier, "count": 1})

async def clear_failed_attempts(identifier: str):
    await db.login_attempts.delete_one({"identifier": identifier})

# Health check
@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "service": "Silent Honor Foundation API"}

# Auth endpoints
@app.post("/api/auth/register")
async def register(request: Request, response: Response, data: RegisterRequest):
    email = data.email.lower()
    
    # Check if email exists
    existing = await db.users.find_one({"email": email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create user
    user_doc = {
        "email": email,
        "password_hash": hash_password(data.password),
        "first_name": data.first_name,
        "last_name": data.last_name,
        "phone": data.phone,
        "state": data.state,
        "branch": data.branch,
        "service_status": data.service_status,
        "years_of_service": data.years_of_service,
        "separation_year": data.separation_year,
        "challenges": data.challenges,
        "notes": data.notes,
        "role": "member",
        "verified": False,
        "dd214_file": None,
        "dd214_status": "pending",
        "created_at": datetime.now(timezone.utc)
    }
    
    result = await db.users.insert_one(user_doc)
    user_id = str(result.inserted_id)
    
    # Create tokens
    access_token = create_access_token(user_id, email)
    refresh_token = create_refresh_token(user_id)
    
    # Set cookies
    response.set_cookie(key="access_token", value=access_token, httponly=True, secure=False, samesite="lax", max_age=3600, path="/")
    response.set_cookie(key="refresh_token", value=refresh_token, httponly=True, secure=False, samesite="lax", max_age=604800, path="/")
    
    return {
        "id": user_id,
        "email": email,
        "first_name": data.first_name,
        "last_name": data.last_name,
        "role": "member",
        "verified": False
    }

@app.post("/api/auth/login")
async def login(request: Request, response: Response, data: LoginRequest):
    email = data.email.lower()
    client_ip = request.client.host if request.client else "unknown"
    identifier = f"{client_ip}:{email}"
    
    await check_brute_force(identifier)
    
    user = await db.users.find_one({"email": email})
    if not user:
        await record_failed_attempt(identifier)
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    if not verify_password(data.password, user["password_hash"]):
        await record_failed_attempt(identifier)
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    await clear_failed_attempts(identifier)
    
    user_id = str(user["_id"])
    access_token = create_access_token(user_id, email)
    refresh_token = create_refresh_token(user_id)
    
    response.set_cookie(key="access_token", value=access_token, httponly=True, secure=False, samesite="lax", max_age=3600, path="/")
    response.set_cookie(key="refresh_token", value=refresh_token, httponly=True, secure=False, samesite="lax", max_age=604800, path="/")
    
    return {
        "id": user_id,
        "email": user["email"],
        "first_name": user.get("first_name", ""),
        "last_name": user.get("last_name", ""),
        "role": user.get("role", "member"),
        "verified": user.get("verified", False),
        "branch": user.get("branch"),
        "service_status": user.get("service_status")
    }

@app.post("/api/auth/logout")
async def logout(response: Response):
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
    return {"message": "Logged out successfully"}

@app.get("/api/auth/me")
async def get_me(request: Request):
    user = await get_current_user(request)
    return user

@app.post("/api/auth/refresh")
async def refresh_token(request: Request, response: Response):
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=401, detail="No refresh token")
    
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")
        
        user = await db.users.find_one({"_id": ObjectId(payload["sub"])})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        
        user_id = str(user["_id"])
        access_token = create_access_token(user_id, user["email"])
        
        response.set_cookie(key="access_token", value=access_token, httponly=True, secure=False, samesite="lax", max_age=3600, path="/")
        
        return {"message": "Token refreshed"}
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Refresh token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

@app.post("/api/auth/forgot-password")
async def forgot_password(data: ForgotPasswordRequest):
    email = data.email.lower()
    user = await db.users.find_one({"email": email})
    
    # Always return success to prevent email enumeration
    if user:
        token = secrets.token_urlsafe(32)
        await db.password_reset_tokens.insert_one({
            "token": token,
            "user_id": user["_id"],
            "email": email,
            "expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
            "used": False
        })
        print(f"Password reset link: /reset-password?token={token}")
    
    return {"message": "If an account exists with this email, a reset link has been sent."}

@app.post("/api/auth/reset-password")
async def reset_password(data: ResetPasswordRequest):
    reset_doc = await db.password_reset_tokens.find_one({
        "token": data.token,
        "used": False,
        "expires_at": {"$gt": datetime.now(timezone.utc)}
    })
    
    if not reset_doc:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
    
    await db.users.update_one(
        {"_id": reset_doc["user_id"]},
        {"$set": {"password_hash": hash_password(data.new_password)}}
    )
    
    await db.password_reset_tokens.update_one(
        {"_id": reset_doc["_id"]},
        {"$set": {"used": True}}
    )
    
    return {"message": "Password reset successfully"}

# DD-214 Upload
@app.post("/api/upload/dd214")
async def upload_dd214(request: Request, file: UploadFile = File(...)):
    user = await get_current_user(request)
    
    # Validate file type
    allowed_types = ["application/pdf", "image/jpeg", "image/jpg", "image/png"]
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Invalid file type. Only PDF, JPG, PNG allowed.")
    
    # Validate file size (10MB max)
    contents = await file.read()
    if len(contents) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large. Maximum 10MB.")
    
    # Generate unique filename
    ext = file.filename.split(".")[-1] if "." in file.filename else "pdf"
    filename = f"{uuid.uuid4()}.{ext}"
    filepath = f"/app/uploads/dd214/{filename}"
    
    # Save file
    async with aiofiles.open(filepath, "wb") as f:
        await f.write(contents)
    
    # Update user record
    await db.users.update_one(
        {"_id": ObjectId(user["_id"])},
        {"$set": {
            "dd214_file": filename,
            "dd214_status": "pending_review",
            "dd214_uploaded_at": datetime.now(timezone.utc)
        }}
    )
    
    return {"message": "File uploaded successfully", "filename": filename}

# Contact form
@app.post("/api/contact")
async def submit_contact(data: ContactRequest):
    contact_doc = {
        "first_name": data.first_name,
        "last_name": data.last_name,
        "email": data.email.lower(),
        "branch": data.branch,
        "status": data.status,
        "topic": data.topic,
        "message": data.message,
        "created_at": datetime.now(timezone.utc),
        "responded": False
    }
    
    await db.contacts.insert_one(contact_doc)
    return {"message": "Message received. We'll be in touch within 2-3 business days."}

# Member profile update
@app.put("/api/member/profile")
async def update_profile(request: Request):
    user = await get_current_user(request)
    data = await request.json()
    
    allowed_fields = ["first_name", "last_name", "phone", "state", "email_preferences"]
    update_data = {k: v for k, v in data.items() if k in allowed_fields}
    
    if update_data:
        await db.users.update_one(
            {"_id": ObjectId(user["_id"])},
            {"$set": update_data}
        )
    
    return {"message": "Profile updated successfully"}

# Member course progress
@app.get("/api/member/courses")
async def get_courses(request: Request):
    user = await get_current_user(request)
    
    progress = await db.course_progress.find({"user_id": ObjectId(user["_id"])}).to_list(100)
    
    courses = [
        {
            "id": "credit-education",
            "title": "Credit Education for Veterans",
            "total_lessons": 7,
            "status": "live"
        },
        {
            "id": "financial-literacy",
            "title": "Financial Literacy Foundations",
            "total_lessons": 6,
            "status": "live"
        },
        {
            "id": "money-mission",
            "title": "Money Mission: Complete Financial Literacy",
            "total_lessons": 34,
            "status": "coming_soon"
        },
        {
            "id": "va-loan",
            "title": "VA Loan & Homeownership Prep",
            "total_lessons": 6,
            "status": "coming_soon"
        }
    ]
    
    # Merge progress
    progress_map = {str(p["course_id"]): p for p in progress}
    for course in courses:
        p = progress_map.get(course["id"], {})
        course["completed_lessons"] = p.get("completed_lessons", 0)
        course["progress"] = round((course["completed_lessons"] / course["total_lessons"]) * 100) if course["total_lessons"] > 0 else 0
    
    return courses

@app.post("/api/member/courses/{course_id}/progress")
async def update_course_progress(request: Request, course_id: str):
    user = await get_current_user(request)
    data = await request.json()
    
    await db.course_progress.update_one(
        {"user_id": ObjectId(user["_id"]), "course_id": course_id},
        {"$set": {
            "completed_lessons": data.get("completed_lessons", 0),
            "updated_at": datetime.now(timezone.utc)
        }},
        upsert=True
    )
    
    return {"message": "Progress updated"}

# Admin endpoints
@app.get("/api/admin/members")
async def get_members(request: Request):
    await get_current_admin(request)
    
    members = await db.users.find({"role": "member"}).to_list(1000)
    result = []
    for m in members:
        result.append({
            "id": str(m["_id"]),
            "email": m["email"],
            "first_name": m.get("first_name", ""),
            "last_name": m.get("last_name", ""),
            "branch": m.get("branch"),
            "service_status": m.get("service_status"),
            "verified": m.get("verified", False),
            "dd214_status": m.get("dd214_status", "pending"),
            "dd214_file": m.get("dd214_file"),
            "created_at": m.get("created_at").isoformat() if m.get("created_at") else None
        })
    
    return result

@app.get("/api/admin/members/{member_id}")
async def get_member(request: Request, member_id: str):
    await get_current_admin(request)
    
    member = await db.users.find_one({"_id": ObjectId(member_id)})
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    
    member["_id"] = str(member["_id"])
    member.pop("password_hash", None)
    return member

@app.get("/api/admin/dd214/{filename}")
async def get_dd214_file(request: Request, filename: str):
    await get_current_admin(request)
    
    filepath = f"/app/uploads/dd214/{filename}"
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(filepath)

@app.post("/api/admin/members/{member_id}/verify")
async def verify_member(request: Request, member_id: str):
    await get_current_admin(request)
    data = await request.json()
    
    status = data.get("status", "verified")
    
    await db.users.update_one(
        {"_id": ObjectId(member_id)},
        {"$set": {
            "verified": status == "verified",
            "dd214_status": status,
            "verified_at": datetime.now(timezone.utc) if status == "verified" else None
        }}
    )
    
    return {"message": f"Member verification status updated to {status}"}

@app.get("/api/admin/contacts")
async def get_contacts(request: Request):
    await get_current_admin(request)
    
    contacts = await db.contacts.find().sort("created_at", -1).to_list(500)
    result = []
    for c in contacts:
        result.append({
            "id": str(c["_id"]),
            "first_name": c.get("first_name", ""),
            "last_name": c.get("last_name", ""),
            "email": c["email"],
            "topic": c.get("topic"),
            "message": c.get("message"),
            "created_at": c.get("created_at").isoformat() if c.get("created_at") else None,
            "responded": c.get("responded", False)
        })
    
    return result

@app.get("/api/admin/stats")
async def get_admin_stats(request: Request):
    await get_current_admin(request)
    
    total_members = await db.users.count_documents({"role": "member"})
    verified_members = await db.users.count_documents({"role": "member", "verified": True})
    pending_verification = await db.users.count_documents({"role": "member", "dd214_status": "pending_review"})
    total_contacts = await db.contacts.count_documents({})
    
    return {
        "total_members": total_members,
        "verified_members": verified_members,
        "pending_verification": pending_verification,
        "total_contacts": total_contacts
    }

# Serve HTML pages
@app.get("/{page}.html")
async def serve_html_page(page: str):
    filepath = f"/app/{page}.html"
    if os.path.exists(filepath):
        return FileResponse(filepath, media_type="text/html")
    raise HTTPException(status_code=404, detail="Page not found")

# Serve specific HTML pages without .html extension
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

@app.get("/")
async def serve_index():
    return FileResponse("/app/index.html", media_type="text/html")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)

# Authentication middleware for Silent Honor Foundation
import jwt
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException, Request
from bson import ObjectId
from utils.auth import get_jwt_secret, JWT_ALGORITHM

# Database reference (set at startup)
db = None

def set_db(database):
    global db
    db = database

async def get_current_user(request: Request) -> dict:
    """Extract and validate current user from JWT token"""
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

        # Check if token is blacklisted
        blacklisted = await db.token_blacklist.find_one({"token": token})
        if blacklisted:
            raise HTTPException(status_code=401, detail="Token has been revoked")

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
    """Get current user and verify admin role"""
    user = await get_current_user(request)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user

async def get_current_counselor(request: Request) -> dict:
    """Get current user and verify counselor role"""
    user = await get_current_user(request)
    if user.get("role") not in ["counselor", "admin"]:
        raise HTTPException(status_code=403, detail="Counselor access required")
    return user

async def get_current_staff(request: Request) -> dict:
    """Get current user and verify staff/admin role"""
    user = await get_current_user(request)
    if user.get("role") not in ["staff", "admin"]:
        raise HTTPException(status_code=403, detail="Staff access required")
    return user

# Brute force protection
async def check_brute_force(identifier: str):
    """Check if user is locked out due to too many failed attempts"""
    attempt = await db.login_attempts.find_one({"identifier": identifier})
    if attempt and attempt.get("count", 0) >= 5:
        lockout_until = attempt.get("lockout_until")
        if lockout_until and datetime.now(timezone.utc) < lockout_until:
            raise HTTPException(status_code=429, detail="Too many failed attempts. Try again later.")
        else:
            await db.login_attempts.delete_one({"identifier": identifier})

async def record_failed_attempt(identifier: str):
    """Record a failed login attempt"""
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
    """Clear failed login attempts after successful login"""
    await db.login_attempts.delete_one({"identifier": identifier})

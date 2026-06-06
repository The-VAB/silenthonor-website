# Authentication router for Silent Honor Foundation
import secrets
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException, Request, Response
from bson import ObjectId

from utils.auth import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    get_jwt_secret,
    JWT_ALGORITHM
)
from utils.validators import (
    RegisterRequest,
    LoginRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    ChangePasswordRequest
)
from middleware.auth_middleware import (
    get_current_user,
    check_brute_force,
    record_failed_attempt,
    clear_failed_attempts
)
from middleware.logging_middleware import log_audit_event, AUDIT_ACTIONS
from utils.email import send_welcome_email, send_password_reset_email
import jwt
import asyncio

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

# Database reference (set at startup)
db = None

def set_db(database):
    global db
    db = database

@router.post("/register")
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
        "pipeline_stage": "applied",
        "created_at": datetime.now(timezone.utc)
    }

    result = await db.users.insert_one(user_doc)
    user_id = str(result.inserted_id)

    # Create tokens
    access_token = create_access_token(user_id, email)
    refresh_token = create_refresh_token(user_id)

    # Set cookies (NEVER CHANGE THESE SETTINGS)
    response.set_cookie(key="access_token", value=access_token, httponly=True, secure=True, samesite="none", max_age=3600, path="/")
    response.set_cookie(key="refresh_token", value=refresh_token, httponly=True, secure=True, samesite="none", max_age=2592000, path="/")

    # Audit log
    await log_audit_event(
        action=AUDIT_ACTIONS["USER_REGISTERED"],
        entity_type="user",
        entity_id=user_id,
        user_email=email,
        ip_address=request.client.host if request.client else None
    )

    # Send welcome email (non-blocking)
    asyncio.create_task(send_welcome_email(email, data.first_name))

    return {
        "id": user_id,
        "email": email,
        "first_name": data.first_name,
        "last_name": data.last_name,
        "role": "member",
        "verified": False
    }

@router.post("/login")
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

    # Set cookies (NEVER CHANGE THESE SETTINGS)
    response.set_cookie(key="access_token", value=access_token, httponly=True, secure=True, samesite="none", max_age=3600, path="/")
    response.set_cookie(key="refresh_token", value=refresh_token, httponly=True, secure=True, samesite="none", max_age=2592000, path="/")

    # Audit log
    await log_audit_event(
        action=AUDIT_ACTIONS["USER_LOGIN"],
        entity_type="user",
        entity_id=user_id,
        user_email=email,
        ip_address=client_ip
    )

    return {
        "id": user_id,
        "email": user["email"],
        "first_name": user.get("first_name", ""),
        "last_name": user.get("last_name", ""),
        "role": user.get("role", "member"),
        "verified": user.get("verified", False),
        "branch": user.get("branch"),
        "service_status": user.get("service_status"),
        "pipeline_stage": user.get("pipeline_stage", "applied")
    }

@router.post("/logout")
async def logout(request: Request, response: Response):
    # Blacklist current access token
    token = request.cookies.get("access_token")
    if token:
        try:
            payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
            await db.token_blacklist.insert_one({
                "token": token,
                "user_id": payload.get("sub"),
                "expires_at": datetime.fromtimestamp(payload.get("exp"), tz=timezone.utc)
            })
        except:
            pass

    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")

    # Audit log
    await log_audit_event(
        action=AUDIT_ACTIONS["USER_LOGOUT"],
        entity_type="user",
        ip_address=request.client.host if request.client else None
    )

    return {"message": "Logged out successfully"}

@router.get("/me")
async def get_me(request: Request):
    user = await get_current_user(request)
    return user

@router.post("/refresh")
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

        # Set cookie (NEVER CHANGE THESE SETTINGS)
        response.set_cookie(key="access_token", value=access_token, httponly=True, secure=True, samesite="none", max_age=3600, path="/")

        return {"message": "Token refreshed"}
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Refresh token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

@router.post("/forgot-password")
async def forgot_password(request: Request, data: ForgotPasswordRequest):
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

        # Send password reset email (non-blocking)
        first_name = user.get("first_name", "Member")
        asyncio.create_task(send_password_reset_email(email, first_name, token))

        await log_audit_event(
            action=AUDIT_ACTIONS["PASSWORD_RESET_REQUESTED"],
            entity_type="user",
            entity_id=str(user["_id"]),
            user_email=email,
            ip_address=request.client.host if request.client else None
        )

    return {"message": "If an account exists with this email, a reset link has been sent."}

@router.post("/reset-password")
async def reset_password(request: Request, data: ResetPasswordRequest):
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

    await log_audit_event(
        action=AUDIT_ACTIONS["PASSWORD_RESET"],
        entity_type="user",
        entity_id=str(reset_doc["user_id"]),
        user_email=reset_doc.get("email"),
        ip_address=request.client.host if request.client else None
    )

    return {"message": "Password reset successfully"}

@router.post("/change-password")
async def change_password(request: Request, data: ChangePasswordRequest):
    user = await get_current_user(request)

    # Get full user with password hash
    full_user = await db.users.find_one({"_id": ObjectId(user["_id"])})
    if not full_user:
        raise HTTPException(status_code=404, detail="User not found")

    if not verify_password(data.current_password, full_user["password_hash"]):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    await db.users.update_one(
        {"_id": ObjectId(user["_id"])},
        {"$set": {"password_hash": hash_password(data.new_password)}}
    )

    await log_audit_event(
        action=AUDIT_ACTIONS["PASSWORD_CHANGED"],
        entity_type="user",
        entity_id=user["_id"],
        user_email=user.get("email"),
        ip_address=request.client.host if request.client else None
    )

    return {"message": "Password changed successfully"}

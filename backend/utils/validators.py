# Validation utilities for Silent Honor Foundation
from typing import Optional
from pydantic import BaseModel, EmailStr

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

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

class CourseRequest(BaseModel):
    title: str
    description: str
    status: str = "draft"
    total_lessons: int = 0
    category: Optional[str] = None
    thumbnail: Optional[str] = None

class LessonRequest(BaseModel):
    course_id: str
    title: str
    content: str
    order: int = 0
    video_url: Optional[str] = None
    duration: Optional[str] = None

class ContentUpdateRequest(BaseModel):
    page: str
    section: str
    content: dict

class CounselorRequest(BaseModel):
    email: EmailStr
    first_name: str
    last_name: str
    password: Optional[str] = None
    title: Optional[str] = "Financial Counselor"
    bio: Optional[str] = ""
    specialties: Optional[list] = []

class StaffRequest(BaseModel):
    email: EmailStr
    first_name: str
    last_name: str
    password: Optional[str] = None
    role: str = "staff"
    title: Optional[str] = ""
    permissions: Optional[list] = []

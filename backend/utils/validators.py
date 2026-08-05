# Validation utilities for Silent Honor Foundation
from typing import Optional, List, Literal
from pydantic import BaseModel, EmailStr

class RegisterRequest(BaseModel):
    email: EmailStr
    password: Optional[str] = None
    google_credential: Optional[str] = None
    first_name: str
    last_name: str
    dob: Optional[str] = None
    phone: Optional[str] = None
    state: Optional[str] = None
    branch: Optional[str] = None
    service_status: Optional[str] = None
    years_of_service: Optional[int] = None
    separation_year: Optional[int] = None
    how_heard: Optional[str] = None
    challenges: Optional[str] = None
    notes: Optional[str] = None
    consent_contact: Optional[bool] = False

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class GoogleLoginRequest(BaseModel):
    credential: str

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
    bio: Optional[str] = ""
    specialties: Optional[list] = []
    credentials: Optional[str] = ""
    functional_role: Optional[str] = ""
    permissions: Optional[list] = []
    calendly_url: Optional[str] = None

class ModuleRequest(BaseModel):
    course_id: str
    title: str
    order: int = 0
    description: Optional[str] = None

class LessonRequest(BaseModel):
    course_id: str
    module_id: Optional[str] = None
    title: str
    content: str = ""
    lesson_type: str = "text"
    order: int = 0
    video_url: Optional[str] = None
    resource_url: Optional[str] = None
    duration: Optional[str] = None

# Knowledge base entries. Both AI assistants (Battle Buddy, Major Finance) draw from
# these; `visibility` is the wall between them -- Major Finance (member-facing) may only
# ever read member_visible entries. Defaults are the safe ones: a new entry is staff_only
# and draft, so nothing becomes member-visible or live by accident.
class KnowledgeEntryCreate(BaseModel):
    title: str
    body: str
    category: Optional[str] = None
    tags: List[str] = []
    visibility: Literal["member_visible", "staff_only"] = "staff_only"
    status: Literal["draft", "published", "retired"] = "draft"

class KnowledgeEntryUpdate(BaseModel):
    title: Optional[str] = None
    body: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    visibility: Optional[Literal["member_visible", "staff_only"]] = None
    status: Optional[Literal["draft", "published", "retired"]] = None

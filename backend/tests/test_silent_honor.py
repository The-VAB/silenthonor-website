"""
Silent Honor Foundation — Backend API tests
Covers: health, auth (register/login/logout/me), admin endpoints
(members, stats, contacts, course CRUD, DD-214 verify), contact form,
DD-214 upload, member courses.
"""
import io
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("PREVIEW_URL") or "https://build-launch-21.preview.emergentagent.com"
BASE_URL = BASE_URL.rstrip("/")

ADMIN_EMAIL = "admin@silenthonor.org"
ADMIN_PASSWORD = "SilentHonor2024!"


# ---------- Fixtures ----------
@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text}"
    assert r.json()["role"] == "admin"
    return s


@pytest.fixture(scope="module")
def member_creds():
    suffix = uuid.uuid4().hex[:8]
    return {
        "email": f"TEST_member_{suffix}@example.com",
        "password": "MemberPass!234",
        "first_name": "Test",
        "last_name": "Member",
        "branch": "army",
        "service_status": "veteran",
    }


@pytest.fixture(scope="module")
def member_session(member_creds):
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/register", json=member_creds)
    assert r.status_code == 200, f"Register failed: {r.status_code} {r.text}"
    data = r.json()
    assert data["email"] == member_creds["email"].lower()
    assert data["role"] == "member"
    assert "id" in data
    s.member_id = data["id"]
    return s


# ---------- Health ----------
def test_health():
    r = requests.get(f"{BASE_URL}/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "healthy"


# ---------- Auth ----------
class TestAuth:
    def test_admin_login_sets_cookie(self):
        r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
        assert r.status_code == 200
        body = r.json()
        assert body["role"] == "admin"
        assert body["email"].lower() == ADMIN_EMAIL
        assert "access_token" in r.cookies

    def test_invalid_login(self):
        # use a unique identifier to avoid brute-force lockout effects
        bad_email = f"nope_{uuid.uuid4().hex[:6]}@example.com"
        r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": bad_email, "password": "wrong"})
        assert r.status_code == 401
        assert "detail" in r.json()

    def test_register_and_me(self, member_session, member_creds):
        r = member_session.get(f"{BASE_URL}/api/auth/me")
        assert r.status_code == 200
        data = r.json()
        assert data["email"] == member_creds["email"].lower()
        assert data["role"] == "member"
        assert "password_hash" not in data
        assert "_id" not in data or isinstance(data.get("_id"), str)

    def test_member_login(self, member_creds):
        s = requests.Session()
        r = s.post(f"{BASE_URL}/api/auth/login", json={"email": member_creds["email"], "password": member_creds["password"]})
        assert r.status_code == 200
        assert r.json()["role"] == "member"

    def test_logout_clears_cookies(self, member_creds):
        s = requests.Session()
        s.post(f"{BASE_URL}/api/auth/login", json={"email": member_creds["email"], "password": member_creds["password"]})
        r = s.post(f"{BASE_URL}/api/auth/logout")
        assert r.status_code == 200
        me = s.get(f"{BASE_URL}/api/auth/me")
        assert me.status_code == 401


# ---------- Contact form (public) ----------
def test_contact_submission():
    payload = {
        "first_name": "TEST",
        "last_name": "Contact",
        "email": f"TEST_contact_{uuid.uuid4().hex[:6]}@example.com",
        "branch": "navy",
        "status": "veteran",
        "topic": "general",
        "message": "Automated pytest contact submission",
    }
    r = requests.post(f"{BASE_URL}/api/contact", json=payload)
    assert r.status_code == 200
    assert "message" in r.json()


# ---------- Admin endpoints ----------
class TestAdmin:
    def test_stats(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/admin/stats")
        assert r.status_code == 200
        data = r.json()
        for k in ("total_members", "verified_members", "pending_verification", "total_contacts", "total_courses"):
            assert k in data
            assert isinstance(data[k], int)

    def test_members_list(self, admin_session, member_session, member_creds):
        r = admin_session.get(f"{BASE_URL}/api/admin/members")
        assert r.status_code == 200
        arr = r.json()
        assert isinstance(arr, list)
        emails = [m["email"] for m in arr]
        assert member_creds["email"].lower() in emails
        # Ensure no Mongo _id leak
        for m in arr:
            assert "_id" not in m
            assert "id" in m

    def test_contacts_list(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/admin/contacts")
        assert r.status_code == 200
        arr = r.json()
        assert isinstance(arr, list)

    def test_admin_requires_auth(self):
        r = requests.get(f"{BASE_URL}/api/admin/stats")
        assert r.status_code == 401

    def test_admin_denies_member(self, member_session):
        r = member_session.get(f"{BASE_URL}/api/admin/stats")
        assert r.status_code == 403


# ---------- Course CRUD ----------
class TestCourseCRUD:
    created_id = None

    def test_create_course(self, admin_session):
        payload = {
            "title": "TEST_PytestCourse",
            "description": "Created by pytest",
            "status": "draft",
            "total_lessons": 0,
            "category": "testing",
        }
        r = admin_session.post(f"{BASE_URL}/api/admin/courses", json=payload)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "id" in body
        TestCourseCRUD.created_id = body["id"]

    def test_get_courses_contains_created(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/admin/courses")
        assert r.status_code == 200
        ids = [c["id"] for c in r.json()]
        assert TestCourseCRUD.created_id in ids

    def test_update_course(self, admin_session):
        cid = TestCourseCRUD.created_id
        payload = {
            "title": "TEST_PytestCourseUpdated",
            "description": "Updated",
            "status": "live",
            "total_lessons": 0,
        }
        r = admin_session.put(f"{BASE_URL}/api/admin/courses/{cid}", json=payload)
        assert r.status_code == 200
        # verify
        r = admin_session.get(f"{BASE_URL}/api/admin/courses/{cid}")
        assert r.status_code == 200
        assert r.json()["title"] == "TEST_PytestCourseUpdated"
        assert r.json()["status"] == "live"

    def test_delete_course(self, admin_session):
        cid = TestCourseCRUD.created_id
        r = admin_session.delete(f"{BASE_URL}/api/admin/courses/{cid}")
        assert r.status_code == 200
        r = admin_session.get(f"{BASE_URL}/api/admin/courses/{cid}")
        assert r.status_code == 404


# ---------- DD-214 upload + admin verify ----------
class TestDD214:
    def test_upload_and_verify_flow(self, member_session, admin_session):
        # Create a tiny PDF-like payload
        pdf_bytes = b"%PDF-1.4\n%TEST_DD214\n%%EOF"
        files = {"file": ("dd214_test.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
        r = member_session.post(f"{BASE_URL}/api/upload/dd214", files=files)
        assert r.status_code == 200, r.text
        assert "filename" in r.json()

        # Admin sees member with dd214_status=pending_review
        r = admin_session.get(f"{BASE_URL}/api/admin/members")
        assert r.status_code == 200
        member_id = member_session.member_id
        target = next((m for m in r.json() if m["id"] == member_id), None)
        assert target is not None
        assert target["dd214_status"] == "pending_review"
        assert target["dd214_file"] is not None

        # Admin approves
        r = admin_session.post(f"{BASE_URL}/api/admin/members/{member_id}/verify", json={"status": "verified"})
        assert r.status_code == 200

        # Verify persistence
        r = admin_session.get(f"{BASE_URL}/api/admin/members/{member_id}")
        assert r.status_code == 200
        data = r.json()
        assert data["verified"] is True
        assert data["dd214_status"] == "verified"

    def test_upload_rejects_invalid_type(self, member_session):
        files = {"file": ("bad.txt", io.BytesIO(b"not a pdf"), "text/plain")}
        r = member_session.post(f"{BASE_URL}/api/upload/dd214", files=files)
        assert r.status_code == 400


# ---------- Member courses ----------
def test_member_courses(member_session):
    r = member_session.get(f"{BASE_URL}/api/member/courses")
    assert r.status_code == 200
    arr = r.json()
    assert isinstance(arr, list)
    assert len(arr) >= 1
    for c in arr:
        for k in ("id", "title", "total_lessons", "progress", "completed_lessons", "status"):
            assert k in c


# ---------- Static HTML serving ----------
@pytest.mark.parametrize("path", ["/index.html", "/login.html", "/signup.html", "/dashboard.html", "/admin.html", "/contact.html", "/courses.html"])
def test_html_pages_accessible(path):
    r = requests.get(f"{BASE_URL}{path}")
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "")

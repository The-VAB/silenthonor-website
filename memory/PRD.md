# Silent Honor Foundation Website - PRD

## Original Problem Statement
Build out the Silent Honor Foundation website from GitHub repo - a full nonprofit site for veterans with membership portal and backend. Uses Zeffy for donations, needs DD-214 document viewing for member verification.

## Architecture
- **Frontend**: Static HTML/CSS/JS served via Python HTTP server (port 3000)
- **Backend**: FastAPI with MongoDB (port 8001)
- **Database**: MongoDB (local)
- **Auth**: JWT-based with httponly cookies
- **File Storage**: Local storage for DD-214 documents in `/app/uploads/dd214/`

## User Personas
1. **Veterans (Members)**: Register, upload DD-214, access courses and dashboard
2. **Administrators**: Review DD-214 documents, approve/reject member verification, view contact submissions
3. **Visitors**: Browse public pages, donate via Zeffy, submit contact forms

## Core Requirements (Static)
- 10 public HTML pages (Home, About, Services, Courses, Contact, Donate, Login, Signup, Dashboard, Admin)
- Member authentication (register/login/logout)
- DD-214 document upload with admin verification
- Contact form submissions stored in MongoDB
- External Zeffy integration for donations
- Admin panel for member management

## What's Been Implemented (March 31, 2026)

### Backend API (100% Complete)
- [x] Health check endpoint
- [x] User registration with all military info fields
- [x] User login with JWT tokens
- [x] Logout endpoint
- [x] Current user (/me) endpoint
- [x] Token refresh
- [x] Password forgot/reset flow
- [x] DD-214 file upload (PDF, JPG, PNG - max 10MB)
- [x] Contact form submission
- [x] Member profile update
- [x] Course progress tracking
- [x] Admin: Get all members
- [x] Admin: Get single member details
- [x] Admin: View DD-214 files
- [x] Admin: Verify/reject members
- [x] Admin: Get contact submissions
- [x] Admin: Dashboard stats
- [x] Brute force login protection

### Frontend Pages (100% Complete)
- [x] Homepage with hero, features, services preview
- [x] About page with story and mission
- [x] Services page with all service cards
- [x] Courses page with curriculum
- [x] Contact page with form
- [x] Donate page linked to Zeffy
- [x] Login page with auth flow
- [x] Signup page with 3-step registration
- [x] Member dashboard
- [x] Admin dashboard with member management

### Integrations
- [x] Zeffy donation form (external: https://www.zeffy.com/en-US/donation-form/8375cf26-7c08-420b-91d8-2bb30723e3b1)
- [x] MongoDB for data persistence
- [x] JWT authentication

## Prioritized Backlog

### P0 (Critical)
- All critical features implemented ✓

### P1 (High)
- [ ] Email verification for new members
- [ ] Password reset email sending (currently logs to console)
- [ ] Image placeholder for about page hero

### P2 (Medium)
- [ ] Course content/lesson pages
- [ ] Member resource library
- [ ] Email notifications for admin on new registrations

### P3 (Nice to Have)
- [ ] Dark/light theme toggle
- [ ] Member profile avatar upload
- [ ] Course completion certificates

## Next Tasks
1. Implement email service for verification and password reset
2. Add actual course content/lesson pages
3. Create member resource library
4. Add notification system for admins

## Technical Notes
- All HTML pages require .html extension in URLs
- Admin seeded on startup: admin@silenthonor.org
- DD-214 files stored in /app/uploads/dd214/
- Frontend uses window.location.origin for API calls

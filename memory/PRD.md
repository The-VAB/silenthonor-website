# Silent Honor Foundation — Product Requirements

## Original Problem Statement
Build a full non-profit site for **Silent Honor Foundation** using HTML/CSS/JS frontend backed by FastAPI + MongoDB. The site serves veterans with free financial education/coaching and includes:
- Public marketing pages (home, about, services, courses, contact, donate, thank-you)
- Custom auth (signup/login/logout) with JWT cookies
- Member dashboard with profile, DD-214 upload, and course progress
- Admin portal for member verification, DD-214 review, and CMS (courses/lessons/team/content)
- Zeffy integration for donations (external link only)

## Personas
- **Veteran Member** — signs up, uploads DD-214 for verification, browses courses.
- **Admin / Foundation Staff** — approves DD-214, manages courses & content, reviews contact requests.
- **Anonymous Visitor** — reads pages, donates, or signs up.

## Tech Stack
- Backend: FastAPI + MongoDB (motor async), JWT (httpOnly cookies), bcrypt password hashing, brute-force lockout
- Frontend: Vanilla HTML / CSS / JS (no build step), served via `serve` on port 3000 (and also via FastAPI static routes on 8001)
- Storage: local `/app/uploads/dd214` for DD-214 files
- Deployment: Emergent Kubernetes pod (ingress routes `/api/*` → 8001, everything else → 3000)

## What's Been Implemented (Feb 2026)
- [Feb 18] Core FastAPI backend with auth, member, admin, courses, lessons, team, site_content endpoints
- [Feb 18] Static frontend pages with transparent logo, topographic background, Oswald/Lora typography
- [Feb 18] Zeffy donation button wired site-wide via `components.js`
- [Feb 18] Admin seeded on startup, credentials written to `/app/memory/test_credentials.md`
- [Feb 18] DD-214 upload + admin review flow (approve / reject)
- [Feb 18] Courses CRUD + member course progress tracking
- [Feb 18] Reverted temporary Go High Level (GHL) integration — restored custom `dashboard.html`, rebuilt `admin.html`, restored local `contact.html` form, stripped all clientclub/leadconnector URLs
- [Feb 18] Nav shows dynamic "Member Login / Dashboard / Admin" based on auth state
- [Feb 18] Full pytest suite created at `/app/backend/tests/test_silent_honor.py` (26/26 passing)

## Key Files
- `/app/backend/server.py` — all API routes + static mounts
- `/app/backend/tests/test_silent_honor.py` — regression suite
- `/app/js/components.js` — nav + footer injection, auth-aware member button
- `/app/login.html`, `/app/signup.html`, `/app/dashboard.html`, `/app/admin.html` — portal pages
- `/app/contact.html`, `/app/courses.html`, `/app/about.html`, `/app/services.html`, `/app/index.html`, `/app/donate.html`, `/app/thankyou.html`

## API Endpoints
- Auth: `POST /api/auth/register`, `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/me`, `POST /api/auth/refresh`, `POST /api/auth/forgot-password`, `POST /api/auth/reset-password`
- Member: `PUT /api/member/profile`, `GET /api/member/courses`, `POST /api/member/courses/{id}/progress`, `POST /api/upload/dd214`
- Admin: `GET /api/admin/stats`, `GET /api/admin/members`, `GET /api/admin/members/{id}`, `POST /api/admin/members/{id}/verify`, `GET /api/admin/dd214/{file}`, `GET /api/admin/contacts`
- Admin CMS: `GET|POST|PUT|DELETE /api/admin/courses[/{id}]`, `POST|PUT|DELETE /api/admin/lessons[/{id}]`, `GET|PUT /api/admin/content[/{page}]`, `GET|POST|PUT|DELETE /api/admin/team[/{id}]`
- Public: `GET /api/health`, `POST /api/contact`, `GET /api/content/{page}/{section}`

## DB Schema (MongoDB)
- `users` — email (unique), password_hash, first_name, last_name, phone, state, branch, service_status, role (member|admin), verified, dd214_file, dd214_status (pending|pending_review|verified|rejected), dd214_uploaded_at, created_at
- `courses` — title, description, status (draft|live|coming_soon|archived), category, thumbnail, created_at
- `lessons` — course_id, title, content, order, video_url, duration
- `contacts` — first_name, last_name, email, branch, status, topic, message, responded, created_at
- `team_members` — name, role, bio, tags[], photo, order, is_board
- `site_content` — page, section, content (object)
- `course_progress` — user_id, course_id, completed_lessons, updated_at
- `password_reset_tokens` (TTL index), `login_attempts` (brute-force)

## Roadmap

### P0 — Ready for GitHub export ✅
- [x] Revert GHL integration, restore local admin + dashboard
- [x] All backend endpoints tested (26/26)
- [x] Full auth flow verified in UI

### P1 — Near-term
- [ ] Refactor `server.py` (~930 lines) into routers (auth/admin/member/cms)
- [ ] Whitelist `/{page}.html` route to known pages only
- [ ] Build member-facing course lesson viewer (lessons currently created via admin, not yet rendered for members)
- [ ] Implement profile edit UI on dashboard
- [ ] Hook `forgot-password` / `reset-password` endpoints to a real email provider (Resend/SendGrid)

### P2 — Backlog
- [ ] Tighten CORS `allow_origins` to production FRONTEND_URL
- [ ] Move DD-214 storage to S3 with signed URLs
- [ ] Rate-limit DD-214 uploads
- [ ] Add analytics (member signups, course completions)
- [ ] Admin CMS UI for editing team members and site_content (endpoints exist, UI pending)

### Known Code Review Notes (from iteration_3)
- CORS `*` with `allow_credentials=True` works only because frontend & API share origin
- `secure=False` cookies acceptable for preview, production needs `secure=True`
- `JWT_SECRET` has a default fallback — enforce env-only in production
- Admin password written to `test_credentials.md` on startup — do not ship to prod

## Credentials
Stored in `/app/memory/test_credentials.md`

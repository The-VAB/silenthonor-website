# Silent Honor Foundation — Website & Member Portal
## Technical Handoff Document

**Organization:** Silent Honor Foundation Inc.  
**EIN:** 99-3172064 | **Status:** 501(c)(3) Nonprofit  
**Current Domain:** silenthonor.org (WordPress hosted)  
**Contact:** [Executive Director — Michael Lugenbell]

---

## What This Repo Contains

This repository is a complete, production-ready **design specification and frontend build** for the Silent Honor Foundation website and member portal. Every page is fully built in HTML/CSS/JS with a shared design system. Your job is to implement the backend, authentication, database, file storage, and third-party integrations to make it fully functional.

---

## File Structure

```
/
├── index.html          — Homepage
├── about.html          — About Us (board, staff, story)
├── services.html       — Services page
├── courses.html        — Course catalog (public)
├── contact.html        — Contact form + FAQ
├── donate.html         — Donation page
├── signup.html         — Member signup (3-step with DD-214 upload)
├── login.html          — Member login
├── dashboard.html      — Full member dashboard (6 panels)
├── css/
│   └── global.css      — Shared design system (all tokens, nav, footer, components)
└── js/
    ├── main.js         — Topographic background generator, scroll reveals, nav behavior
    └── components.js   — Shared nav + footer HTML injection
```

---

## Pages Overview

| Page | Status | Notes |
|------|--------|-------|
| index.html | ✅ Complete | Hero, services preview, impact stats, courses preview, donate CTA |
| about.html | ✅ Complete | Story, values, board of directors (4 members + 2 open seats), staff, open positions |
| services.html | ✅ Complete | 6 services with full detail, 4-step process, eligibility section |
| courses.html | ✅ Complete | 4 courses (2 live, 2 coming soon), full module preview |
| contact.html | ✅ Complete | Full intake form, FAQ accordion, contact info |
| donate.html | ✅ Complete | Amount selector, frequency toggle, form, impact-per-dollar |
| signup.html | ✅ Complete | 3-step form: personal → service info → DD-214 upload + consent |
| login.html | ✅ Complete | Email/password, remember me, forgot password, signup CTA |
| dashboard.html | ✅ Complete | 6-panel dashboard: Overview, Courses, Resources, Coaching, Vet Life, Community, Profile |

---

## Design System

**Fonts (Google Fonts — already linked in each page):**
- Display/headings: `Oswald` (400, 500, 600, 700)
- Body/serif: `Lora` (400, 600, italic variants)
- UI/labels: `Barlow` (300, 400, 500)

**Color Tokens (in global.css `:root`):**
```css
--red:        #B91C1C    /* Primary brand red */
--red-dark:   #7F1D1D    /* Darker red for panels */
--red-light:  #EF4444    /* Accent / hover red */
--navy:       #0B1220    /* Main background */
--navy-mid:   #111827    /* Card backgrounds */
--navy-light: #1A2540    /* Elevated surfaces */
--gold:       #C9952A    /* Secondary accent */
--gold-light: #F0B429    /* Gold hover/active */
--muted:      #6B7A99    /* Secondary text */
```

**Topographic background:**  
Generated dynamically via JavaScript in `js/main.js` → `buildTopo()`. Uses SVG path generation with layered sine waves. Renders into `.topo-bg svg`. No external assets required.

---

## Backend Requirements

### 1. Authentication System
**Recommended:** Implement via **GoHighLevel (GHL)** OR a backend like Firebase Auth / Supabase Auth.

Requirements:
- Email + password authentication
- JWT or session-based auth
- Password reset via email
- "Remember me" (persistent session)
- Redirect unauthenticated users away from `dashboard.html`

Wire points in code:
- `login.html` → `handleLogin()` function → currently redirects to `dashboard.html` directly
- `signup.html` → `submitSignup()` function → currently shows alert placeholder
- `dashboard.html` → `sidebar-signout` button → redirects to `login.html`

---

### 2. Member Database
**Recommended:** GHL CRM + custom fields, OR Supabase / Firebase Firestore.

Fields to capture at signup:

**Step 1 — Personal:**
- First name, last name
- Email (unique key)
- Password (hashed — never store plaintext)
- Phone (optional)
- State of residence

**Step 2 — Service Info:**
- Branch of service
- Service status (veteran, active, reserve, etc.)
- Years of service
- Separation/ETS year
- Financial challenges (multi-select checkboxes)
- Free text notes

**Step 3 — Verification:**
- DD-214 / military records file reference (store file ID, not the file itself in the DB)
- Consent timestamps (4 checkboxes — log timestamp + IP)
- Email opt-in status

**GHL Integration:**
- Create contact in GHL on signup
- Tag with: `veteran-member`, branch tag, status tag
- Add to email automation workflow for onboarding sequence
- Connect to GHL pipeline for coaching waitlist

---

### 3. DD-214 / Military Records File Storage
**⚠️ CRITICAL — Handle with care. This is sensitive federal document data.**

**Requirements:**
- AES-256 encryption at rest
- TLS in transit (HTTPS only — enforce)
- Access restricted to authorized admin/staff only
- Never stored in the member-facing database row directly
- Stored in a secure, private bucket (NOT publicly accessible)
- File reference (ID/key) stored in member record

**Recommended storage:**
- AWS S3 with server-side encryption (SSE-S3 or SSE-KMS) + bucket policy blocking public access
- OR Google Cloud Storage with uniform bucket-level access disabled for public
- OR Supabase Storage with RLS policies

**File upload flow:**
1. Member uploads in `signup.html` → `file-upload-zone`
2. File goes to backend endpoint (NOT directly to S3 from browser — use signed URL or server-side upload)
3. Backend validates: file type (PDF, JPG, PNG), file size (max 10MB), runs basic virus scan if possible
4. File stored in private bucket with UUID filename (not original filename)
5. UUID reference stored in member record with upload timestamp
6. Verification status set to `pending` → admin reviews → set to `verified`

**Wire point in code:**
- `signup.html` → `handleFile()` and `submitSignup()` functions

---

### 4. Course Access Gating
All courses in `courses.html` should be behind authentication. Currently the "Start Course" buttons link to `#`.

**Options:**
- **GHL Communities:** House courses in GHL Communities (same platform as Veteran Alliance). Members sign up → get added to Silent Honor GHL community → courses unlocked. This is the cleanest integration given existing GHL usage.
- **WordPress LMS:** If staying on WordPress, use **LifterLMS** (free tier) or **LearnDash** to gate courses behind membership.
- **Custom:** Build course player pages and protect them with auth middleware.

**Dashboard integration:**
- `dashboard.html` panel `panel-courses` shows progress (currently hardcoded sample data)
- Wire to actual course completion API/webhooks from GHL or LMS
- Progress bars use inline `style="width: X%"` — replace with dynamic values

---

### 5. Contact Form
`contact.html` → form submission:
- **Option A (Recommended):** POST to GHL form webhook → creates contact/opportunity in GHL pipeline
- **Option B:** POST to backend → send email via SendGrid/Mailgun → log in CRM

---

### 6. Donation Processing
`donate.html` → payment form:
- **Recommended:** Stripe (nonprofit rates available — apply at stripe.com/nonprofit)
- Replace the card input fields with **Stripe Elements** for PCI compliance
- OR embed a **Stripe Payment Link** in an iframe
- Tax receipt emails: trigger via Stripe webhook → send via SendGrid
- Log donations in GHL as opportunities/transactions

---

### 7. Dashboard Data
`dashboard.html` currently uses hardcoded sample data. Wire up:

| Panel | Data Source |
|-------|------------|
| Overview stats | Member record + LMS completion API |
| Course progress bars | LMS webhook data per member |
| Coaching waitlist position | GHL pipeline position or custom queue |
| Resource downloads | Static files hosted on CDN or S3 public bucket |
| Profile fields | Member database record |
| Email preferences | GHL contact tags or preference center |

---

## GHL Integration Map

Silent Honor is already using GoHighLevel. Here's how to connect the website:

```
Website signup form
    → POST to GHL webhook
    → Create/update contact in GHL
    → Apply tags: veteran-member, [branch], [status]
    → Add to "New Member" automation
    → Trigger onboarding email sequence:
        Email 1 (immediate): Welcome + course links
        Email 2 (Day 3): Financial tip + resource library link
        Email 3 (Day 7): Coaching waitlist CTA
        Email 4 (Day 14): Newsletter introduction
        Email 5 (Day 30): Check-in + next course recommendation
```

---

## WordPress Deployment Notes

The current site at silenthonor.org runs WordPress. Options:

**Option A — Keep WordPress, use Elementor:**
- Install Elementor Pro
- Recreate pages using the HTML/CSS as design spec
- Use Elementor's custom HTML widget to embed sections
- Use Memberpress or Paid Memberships Pro for gating

**Option B — Replace with static site on WordPress:**
- Use a "blank canvas" WordPress theme (Hello Elementor or GeneratePress)
- Upload HTML/CSS/JS files as a static child theme
- Use WordPress only for routing and PHP templating
- Backend via WordPress REST API + custom plugin

**Option C — Decouple entirely:**
- Move frontend to Netlify or Vercel (free tier)
- Keep WordPress for admin/CMS only
- Connect via headless WP API

**Recommendation:** Option B is cleanest for a solo IT volunteer. Preserves existing WordPress hosting, adds no new platform costs.

---

## Privacy Policy & Terms of Use Requirements

**⚠️ These MUST be created before launch — they are referenced in the signup consent checkboxes.**

Required documents:
1. **Privacy Policy** — Must cover: data collected, how it's used, DD-214 storage and access, third-party services (GHL, Stripe), retention period, right to deletion
2. **Terms of Use** — Must cover: eligibility, nonprofit disclaimer, no financial advice disclaimer, member conduct
3. **Document Retention Policy** — How long DD-214s are kept; how to request deletion

**Recommended:** Use a nonprofit attorney to draft these, OR use a tool like Termly.io and have an attorney review. Do NOT use a generic generator without legal review given the military records component.

---

## Security Checklist Before Launch

- [ ] HTTPS enforced on all pages (SSL certificate active)
- [ ] DD-214 upload endpoint is server-side only (no client-side S3 direct upload)
- [ ] File storage bucket is private (no public URLs)
- [ ] Passwords hashed with bcrypt or Argon2 (never MD5/SHA1)
- [ ] Auth tokens stored in httpOnly cookies (not localStorage)
- [ ] CSRF protection on all forms
- [ ] Rate limiting on login endpoint (prevent brute force)
- [ ] Input sanitization on all form fields
- [ ] Privacy Policy and Terms of Use live before any data collection begins
- [ ] Member data backup automated

---

## Questions?

Contact Michael Lugenbell via the Silent Honor contact page or through the organization's internal channels.

All design decisions, color choices, layout, and content were developed collaboratively with the Executive Director. Do not redesign without explicit approval — implement as specced.

---

*This document was prepared as part of the Silent Honor Foundation website build project.*  
*Last updated: 2025*

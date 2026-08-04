// Dev-only fixtures. Active only when VITE_MOCK=1 or ?mock=1, so the UI can be
// built and previewed offline without a live admin session. Never runs in a normal build.
import type {
  Analytics,
  AdminStats,
  Me,
  MemberRow,
  MemberFull,
  StaffRow,
  StaffFull,
  Application,
  Counselor,
} from "./types";

const me: Me = {
  id: "mock-admin",
  email: "m.lugenbell@silenthonor.org",
  first_name: "Michael",
  last_name: "Lugenbell",
  roles: ["admin"],
  verified: true,
};

const stats: AdminStats = {
  total_members: 128,
  pending_verification: 7,
  pending_dd214: 7,
  active_courses: 4,
  total_counselors: 3,
  unread_messages: 3,
  open_applications: 5,
};

const analytics: Analytics = {
  kpis: { total_members: 128, verified_members: 96, new_this_month: 14, pending_dd214: 7, active_courses: 4, total_counselors: 3 },
  monthly_members: [
    { month: "Jan", count: 6 }, { month: "Feb", count: 9 }, { month: "Mar", count: 8 }, { month: "Apr", count: 12 },
    { month: "May", count: 11 }, { month: "Jun", count: 15 }, { month: "Jul", count: 13 }, { month: "Aug", count: 14 },
  ],
  pipeline: { New: 22, Contacted: 18, Active: 63, Graduated: 19, Paused: 6 },
  branches: { Army: 41, "Air Force": 24, Navy: 22, "Marine Corps": 19, "National Guard": 8, "Coast Guard": 8, "Space Force": 6 },
  dd214: { Verified: 96, Pending: 7, "Not Submitted": 25 },
  cr_pipeline: { cr_waitlist: 12, cr_consultation: 8, cr_documents: 6, cr_dispute_1: 9, cr_dispute_2: 5, cr_dispute_3: 3, cr_monitoring: 4, cr_complete: 7 },
  fc_pipeline: { fc_waitlist: 10, fc_consultation: 6, fc_documents: 5, fc_gameplan: 4, fc_working: 8, fc_complete: 5 },
};

const courses = [
  { id: "co1", title: "The Money Mission", category: "Financial Literacy", status: "published", total_lessons: 34 },
  { id: "co2", title: "Credit Foundations", category: "Credit", status: "published", total_lessons: 12 },
  { id: "co3", title: "VA Loan Playbook", category: "Homeownership", status: "draft", total_lessons: 8 },
];
function courseDetail(id: string) {
  const row = courses.find((c) => c.id === id) ?? courses[0];
  return {
    ...row,
    description: "A step-by-step path from financial stress to stability after service.",
    modules: [
      { id: "mo1", title: "Getting Started", lessons: [
        { id: "l1", title: "Welcome & Orientation", lesson_type: "video", duration: "6 min" },
        { id: "l2", title: "Setting Your Money Goals", lesson_type: "text" },
      ] },
      { id: "mo2", title: "Budgeting Basics", lessons: [
        { id: "l3", title: "The Zero-Based Budget", lesson_type: "video", duration: "11 min" },
        { id: "l4", title: "Budget Worksheet", lesson_type: "resource" },
      ] },
    ],
    flat_lessons: [{ id: "l5", title: "Bonus: Deployment Finances", lesson_type: "text" }],
  };
}

const knowledge = [
  { id: "k1", title: "Dispute Letter Templates", category: "Credit Repair", visibility: "staff_only", status: "published", updated_at: "2026-07-28", tags: ["disputes", "templates"] },
  { id: "k2", title: "How VA Disability Affects Credit", category: "Education", visibility: "member_visible", status: "published", updated_at: "2026-07-10", tags: ["va"] },
  { id: "k3", title: "Intake Call Script (draft)", category: "Onboarding", visibility: "staff_only", status: "draft", updated_at: "2026-08-01", tags: [] },
];

const announcements = [
  { id: "an1", title: "New Course: VA Loan Playbook", content: "Now live for all members.", type: "success", active: true, created_at: "2026-07-30", expires_at: null },
  { id: "an2", title: "Holiday Hours", content: "Office closed July 4.", type: "info", active: false, created_at: "2026-06-28", expires_at: "2026-07-05" },
];

const contacts = [
  { id: "ct1", first_name: "Andre", last_name: "Wells", email: "awells@example.com", topic: "Membership", message: "How do I verify my service if I lost my DD-214?", responded: false, created_at: "2026-08-02" },
  { id: "ct2", first_name: "Lena", last_name: "Ford", email: "lford@example.com", topic: "Credit Repair", message: "Do you help with medical collections?", responded: true, created_at: "2026-07-29" },
];

const audit = [
  { timestamp: "2026-08-04T14:20:00Z", user_email: "m.lugenbell@silenthonor.org", action: "member_verified", entity_type: "member", entity_id: "abc12345", ip_address: "10.0.0.5" },
  { timestamp: "2026-08-04T13:02:00Z", user_email: "rortiz@silenthonor.org", action: "dispute_filed", entity_type: "dispute", entity_id: "def67890", ip_address: "10.0.0.9" },
  { timestamp: "2026-08-03T18:44:00Z", user_email: "m.lugenbell@silenthonor.org", action: "course_published", entity_type: "course", entity_id: "co3aa112", ip_address: "10.0.0.5" },
];

const ADMIN_U = { id: "mock-admin", name: "Michael Lugenbell", email: "m.lugenbell@silenthonor.org" };
const messages = [
  { from_user: { id: "m1", name: "Marcus Reyes", email: "mreyes@example.com" }, to_user: ADMIN_U, content: "Hey, I finished the budgeting module!", created_at: "2026-08-03T10:00:00Z", read: true },
  { from_user: ADMIN_U, to_user: { id: "m1", name: "Marcus Reyes" }, content: "That's great, Marcus. Ready for a coaching call?", created_at: "2026-08-03T10:05:00Z", read: true },
  { from_user: { id: "m1", name: "Marcus Reyes", email: "mreyes@example.com" }, to_user: ADMIN_U, content: "Yes — this Thursday works.", created_at: "2026-08-03T10:12:00Z", read: false },
  { from_user: { id: "m4", name: "Sofia Marin", email: "smarin@example.com" }, to_user: ADMIN_U, content: "When will my application be reviewed?", created_at: "2026-08-04T09:30:00Z", read: false },
];

const pipeline = {
  onboarding: {
    applied: [{ id: "m6", name: "Priya Nair", email: "pnair@example.com", branch: "Coast Guard", created_at: "2026-08-01" }],
    dd214_review: [
      { id: "m2", name: "Danielle Cho", branch: "Air Force", created_at: "2026-07-21" },
      { id: "m4", name: "Sofia Marin", branch: "Navy", created_at: "2026-07-28" },
    ],
    approved: [{ id: "m3", name: "Terrence Blake", branch: "Army", created_at: "2026-05-14" }],
    active: [{ id: "m1", name: "Marcus Reyes", branch: "Marine Corps", created_at: "2026-06-02" }],
    graduated: [{ id: "m5", name: "Jon Whitaker", branch: "Army", created_at: "2026-02-09" }],
  },
  credit_repair: {
    cr_waitlist: [{ id: "m3", name: "Terrence Blake", branch: "Army", created_at: "2026-07-01" }],
    cr_dispute_2: [{ id: "m1", name: "Marcus Reyes", branch: "Marine Corps", created_at: "2026-06-02" }],
  },
  financial_counseling: {
    fc_working: [{ id: "m1", name: "Marcus Reyes", branch: "Marine Corps", created_at: "2026-06-02" }],
  },
};

const members: MemberRow[] = [
  { id: "m1", first_name: "Marcus", last_name: "Reyes", email: "mreyes@example.com", branch: "Marine Corps", pipeline_stage: "active", dd214_status: "verified", verified: true, created_at: "2026-06-02", dd214_file: "reyes-dd214.pdf" },
  { id: "m2", first_name: "Danielle", last_name: "Cho", email: "dcho@example.com", branch: "Air Force", pipeline_stage: "dd214_review", dd214_status: "pending_review", verified: false, created_at: "2026-07-21", dd214_file: "cho-dd214.pdf" },
  { id: "m3", first_name: "Terrence", last_name: "Blake", email: "tblake@example.com", branch: "Army", pipeline_stage: "approved", dd214_status: "verified", verified: true, created_at: "2026-05-14" },
  { id: "m4", first_name: "Sofia", last_name: "Marin", email: "smarin@example.com", branch: "Navy", pipeline_stage: "dd214_review", dd214_status: "pending_review", verified: false, created_at: "2026-07-28", dd214_file: "marin-dd214.pdf" },
  { id: "m5", first_name: "Jon", last_name: "Whitaker", email: "jwhit@example.com", branch: "Army", pipeline_stage: "graduated", dd214_status: "verified", verified: true, created_at: "2026-02-09" },
  { id: "m6", first_name: "Priya", last_name: "Nair", email: "pnair@example.com", branch: "Coast Guard", pipeline_stage: "applied", dd214_status: "not_submitted", verified: false, created_at: "2026-08-01" },
];

function memberFull(id: string): MemberFull {
  const row = members.find((m) => m.id === id) ?? members[0];
  return {
    ...row,
    phone: "(555) 010-2233",
    state: "TX",
    dob: "1989-04-12",
    service_status: "Veteran",
    years_of_service: 8,
    separation_year: 2019,
    assigned_counselor_id: "c1",
    admin_notes: "Referred by VA rep. Priority credit repair.",
    challenges: "Credit repair, getting out of debt, VA loan / homeownership",
    cr_stage: id === "m1" ? "cr_dispute_2" : undefined,
    fc_stage: id === "m1" ? "fc_working" : undefined,
    disputes: id === "m1" ? [
      { bureau: "Experian", account: "Capital One", round: 1, status: "in_progress", created_at: "2026-07-01" },
      { bureau: "Equifax", account: "Medical - ER", round: 1, status: "resolved", created_at: "2026-06-18" },
    ] : [],
    courses: [
      { title: "The Money Mission", percent_complete: 62, last_accessed: "2026-07-30" },
      { title: "Credit Foundations", percent_complete: 100, last_accessed: "2026-06-22" },
    ],
    notes_history: [
      { content: "Completed intake call. Motivated, has all docs ready.", author: "Michael Lugenbell", created_at: "2026-07-25T15:00:00Z" },
      { content: "Uploaded DD-214, pending review.", author: "System", created_at: "2026-07-21T09:12:00Z" },
    ],
    dd214_approved_by: row.verified ? "Michael Lugenbell" : undefined,
    dd214_approved_at: row.verified ? "2026-06-03" : undefined,
  };
}

const counselors: Counselor[] = [
  { id: "c1", name: "Rachel Ortiz" },
  { id: "c2", name: "Devon Price" },
];

const staff: StaffRow[] = [
  { id: "c1", first_name: "Rachel", last_name: "Ortiz", name: "Rachel Ortiz", email: "rortiz@silenthonor.org", role: "counselor", title: "Lead Financial Coach", client_count: 14, active: true, specialties: ["Credit repair", "VA loans"], created_at: "2026-01-10", last_active: "2026-08-03" },
  { id: "c2", first_name: "Devon", last_name: "Price", name: "Devon Price", email: "dprice@silenthonor.org", role: "counselor", title: "Credit Specialist", client_count: 9, active: true, specialties: ["Disputes", "Budgeting"], created_at: "2026-03-02", last_active: "2026-08-02" },
  { id: "a1", first_name: "Michael", last_name: "Lugenbell", name: "Michael Lugenbell", email: "m.lugenbell@silenthonor.org", role: "admin", title: "Executive Director", client_count: 0, active: true, created_at: "2025-11-01", last_active: "2026-08-04" },
];

function staffFull(id: string): StaffFull {
  const row = staff.find((s) => s.id === id) ?? staff[0];
  const isC = row.role === "counselor";
  return {
    ...row,
    credentials: isC ? "AFC® Accredited Financial Counselor" : "MBA",
    bio: "Veteran advocate focused on getting service members to financial stability after separation.",
    calendly_url: isC ? "https://calendly.com/silent-honor/intro" : null,
    clients: isC ? [
      { id: "m1", name: "Marcus Reyes", email: "mreyes@example.com", pipeline_stage: "active", notes_count: 3, disputes_count: 2 },
      { id: "m3", name: "Terrence Blake", email: "tblake@example.com", pipeline_stage: "approved", notes_count: 1, disputes_count: 0 },
    ] : [],
    recent_activity: isC ? [
      { created_at: "2026-08-02", member_name: "Marcus Reyes", content: "Filed dispute round 2 with Experian." },
      { created_at: "2026-07-30", member_name: "Terrence Blake", content: "Completed budget game plan." },
    ] : [],
  };
}

const applications: Application[] = [
  { id: "app1", member_name: "Danielle Cho", member_email: "dcho@example.com", program_type: "credit_repair", status: "pending", applied_at: "2026-07-29", application_data: { current_score: 588, goal: "Buy a home in 2027", debts_in_collections: "2", monthly_income: "$4,200", biggest_challenge: "Medical debt from deployment injury" } },
  { id: "app2", member_name: "Sofia Marin", member_email: "smarin@example.com", program_type: "financial_counseling", status: "pending", applied_at: "2026-07-30", application_data: { monthly_income: "$3,800", monthly_expenses: "$3,600", savings: "$500", goals: ["Emergency fund", "Pay off car"] } },
  { id: "app3", member_name: "Marcus Reyes", member_email: "mreyes@example.com", program_type: "credit_repair", status: "approved", applied_at: "2026-06-01", application_data: { current_score: 610 } },
];

function match(path: string, method: string): unknown | undefined {
  const p = path.split("?")[0];
  if (method !== "GET") return undefined;
  if (p === "/api/auth/me") return me;
  if (p === "/api/admin/stats") return stats;
  if (p === "/api/admin/analytics") return analytics;
  if (p === "/api/admin/members") return members;
  if (p === "/api/admin/staff") return staff;
  if (p === "/api/admin/staff/counselors") return counselors;
  if (p === "/api/admin/applications") return applications;
  if (p === "/api/admin/courses") return courses;
  if (p === "/api/admin/knowledge") return knowledge;
  if (p === "/api/admin/announcements") return announcements;
  if (p === "/api/admin/contacts") return contacts;
  if (p === "/api/admin/audit-log") return audit;
  if (p === "/api/messages/admin/all") return messages;
  if (p === "/api/admin/pipeline") return pipeline;

  let mm = p.match(/^\/api\/admin\/members\/([^/]+)\/full$/);
  if (mm) return memberFull(mm[1]);
  mm = p.match(/^\/api\/admin\/staff\/([^/]+)\/full$/);
  if (mm) return staffFull(mm[1]);
  mm = p.match(/^\/api\/admin\/courses\/([^/]+)$/);
  if (mm) return courseDetail(mm[1]);
  mm = p.match(/^\/api\/admin\/applications\/([^/]+)$/);
  if (mm) return applications.find((a) => a.id === mm![1]) ?? applications[0];
  return undefined;
}

export const MOCK_ON =
  import.meta.env.DEV &&
  (import.meta.env.VITE_MOCK === "1" ||
    (typeof location !== "undefined" && new URLSearchParams(location.search).has("mock")));

export function mockResponse(path: string, method: string): unknown | undefined {
  return match(path, method);
}

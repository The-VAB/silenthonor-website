// Shared API response types, derived from how the current admin console consumes them.

export interface Me {
  id?: string;
  email: string;
  first_name?: string;
  last_name?: string;
  roles?: string[];
  role?: string;
  verified?: boolean;
}

export interface AnalyticsKpis {
  total_members: number;
  verified_members: number;
  new_this_month: number;
  pending_dd214: number;
  active_courses: number;
  total_counselors: number;
}

export interface MonthlyPoint {
  month: string;
  count: number;
}

export interface Analytics {
  kpis: AnalyticsKpis;
  monthly_members: MonthlyPoint[];
  pipeline: Record<string, number>;
  branches: Record<string, number>;
  dd214: Record<string, number>;
  cr_pipeline?: Record<string, number>;
  fc_pipeline?: Record<string, number>;
}

// ---- Content ----
export interface Knowledge {
  id: string;
  title: string;
  category?: string;
  visibility: "member_visible" | "staff_only";
  status: "published" | "draft" | "retired";
  body?: string;
  tags?: string[];
  updated_at?: string;
}
export interface Announcement {
  id: string;
  title: string;
  content?: string;
  type: "info" | "success" | "warning";
  active?: boolean;
  created_at?: string;
  expires_at?: string | null;
}
export interface Lesson {
  id: string;
  title: string;
  lesson_type?: "video" | "text" | "resource";
  content?: string;
  video_url?: string | null;
  resource_url?: string | null;
  duration?: string | null;
}
export interface Module {
  id: string;
  title: string;
  lessons?: Lesson[];
}
export interface CourseRow {
  id: string;
  title: string;
  category?: string;
  status: string;
  total_lessons?: number;
}
export interface CourseDetail extends CourseRow {
  description?: string;
  thumbnail?: string;
  modules?: Module[];
  flat_lessons?: Lesson[];
}

// ---- Inbox ----
export interface Contact {
  id: string;
  first_name?: string;
  last_name?: string;
  email: string;
  topic?: string;
  message?: string;
  responded?: boolean;
  created_at?: string;
}
export interface AuditEntry {
  timestamp?: string;
  user_email?: string;
  action?: string;
  entity_type?: string;
  entity_id?: string;
  ip_address?: string;
}
export interface MsgUser {
  id: string;
  name?: string;
  email?: string;
}
export interface Message {
  from_user: MsgUser;
  to_user: MsgUser;
  content: string;
  created_at?: string;
  read?: boolean;
}

// ---- Assistant ----
export interface AssistantStatus {
  assistant: string;
  enabled: boolean;
}
export interface AssistantAction {
  type: string; // send_message | set_stage | create_announcement | add_note | log_call | verify_dd214
  member_id?: string;
  body?: string;
  pipeline_type?: string;
  stage?: string;
  title?: string;
  content?: string;
  kind?: string;
  summary?: string;
  status?: string;
  counselor_id?: string;
  label?: string;
}
export interface ChatMsg {
  role: "user" | "assistant";
  content: string;
}

// ---- Pipeline ----
export type PipelineData = Record<string, Record<string, { id: string; name?: string; email?: string; branch?: string; created_at?: string }[]>>;

export interface AdminStats {
  total_members?: number;
  pending_verification?: number;
  active_courses?: number;
  total_counselors?: number;
  unread_messages?: number;
  open_applications?: number;
  [k: string]: number | undefined;
}

// ---- People ----
export interface MemberRow {
  id: string;
  first_name?: string;
  last_name?: string;
  email: string;
  branch?: string;
  pipeline_stage?: string;
  dd214_status?: string;
  dd214_file?: string;
  verified?: boolean;
  created_at?: string;
}

export interface Dispute {
  bureau?: string;
  account?: string;
  round?: number | string;
  status?: string;
  created_at?: string;
}
export interface CourseProgress {
  title: string;
  percent_complete: number;
  last_accessed?: string;
}
export interface NoteItem {
  content: string;
  author?: string;
  created_at?: string;
}
export interface MemberFull extends MemberRow {
  phone?: string;
  state?: string;
  dob?: string;
  service_status?: string;
  years_of_service?: number | string;
  separation_year?: number | string;
  assigned_counselor_id?: string | null;
  admin_notes?: string;
  challenges?: string;
  notes?: string;
  cr_stage?: string;
  credit_repair_stage?: string;
  fc_stage?: string;
  financial_counseling_stage?: string;
  disputes?: Dispute[];
  courses?: CourseProgress[];
  notes_history?: NoteItem[];
  dd214_approved_by?: string;
  dd214_approved_at?: string;
}

export interface Counselor {
  id: string;
  name: string;
}

export interface Application {
  id: string;
  member_name?: string;
  member_email?: string;
  program_type: string;
  status: string;
  applied_at?: string;
  application_data?: Record<string, unknown>;
}

export interface StaffRow {
  id: string;
  first_name?: string;
  last_name?: string;
  name?: string;
  email: string;
  role: string;
  title?: string;
  credentials?: string;
  bio?: string;
  specialties?: string[];
  calendly_url?: string | null;
  client_count?: number;
  active?: boolean;
  created_at?: string;
  last_active?: string;
}
export interface StaffClient {
  id: string;
  name?: string;
  email: string;
  pipeline_stage?: string;
  notes_count?: number;
  disputes_count?: number;
}
export interface StaffActivity {
  created_at?: string;
  member_name?: string;
  content?: string;
}
export interface StaffFull extends StaffRow {
  clients?: StaffClient[];
  recent_activity?: StaffActivity[];
}

export function roleOf(me: Me | undefined | null): string[] {
  if (!me) return [];
  return me.roles ?? (me.role ? [me.role] : []);
}

export function fullName(me: { first_name?: string; last_name?: string; email?: string }): string {
  const n = [me.first_name, me.last_name].filter(Boolean).join(" ").trim();
  return n || me.email || "Admin";
}

export function initials(me: { first_name?: string; last_name?: string; email?: string }): string {
  const f = me.first_name?.[0] ?? "";
  const l = me.last_name?.[0] ?? "";
  const i = (f + l).toUpperCase();
  return i || (me.email?.[0] ?? "A").toUpperCase();
}

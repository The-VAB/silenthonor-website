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
}

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

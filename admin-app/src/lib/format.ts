// Formatting + status→badge helpers shared across pages.

export function fmtDate(v?: string | null): string {
  if (!v) return "—";
  const d = new Date(v);
  if (isNaN(d.getTime())) return "—";
  return d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

export function fmtTime(v?: string | null): string {
  if (!v) return "—";
  const d = new Date(v);
  if (isNaN(d.getTime())) return "—";
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export type Tone = "ok" | "warn" | "danger" | "info" | "muted";

// Human label for a snake_case stage/status.
export function humanize(s?: string | null): string {
  if (!s) return "—";
  return s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

const OK = new Set([
  "verified",
  "approved",
  "manual_approved",
  "active",
  "complete",
  "graduated",
  "cr_complete",
  "fc_complete",
  "resolved",
  "read",
]);
const WARN = new Set([
  "pending",
  "pending_review",
  "applied",
  "dd214_pending",
  "dd214_review",
  "waitlist",
  "cr_waitlist",
  "fc_waitlist",
  "consultation",
  "in_progress",
  "monitoring",
  "unread",
  "new",
]);
const DANGER = new Set(["rejected", "denied", "inactive", "failed", "archived"]);
const INFO = new Set(["credit_repair", "financial_counseling", "onboarding", "contacted"]);

export function toneFor(status?: string | null): Tone {
  if (!status) return "muted";
  const s = status.toLowerCase();
  if (OK.has(s)) return "ok";
  if (WARN.has(s)) return "warn";
  if (DANGER.has(s)) return "danger";
  if (INFO.has(s)) return "info";
  // stage prefixes
  if (s.startsWith("cr_") || s.startsWith("fc_") || s.startsWith("dispute_")) return "info";
  return "muted";
}

export function initialsOf(first?: string, last?: string, email?: string): string {
  const f = first?.[0] ?? "";
  const l = last?.[0] ?? "";
  const i = (f + l).toUpperCase();
  return i || (email?.[0] ?? "?").toUpperCase();
}

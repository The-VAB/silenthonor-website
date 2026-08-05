// Small presentational primitives shared across pages.
import type { ReactNode } from "react";
import { toneFor, humanize } from "@/lib/format";

/** Renders a status/stage string as a toned chip. */
export function StatusBadge({ value }: { value?: string | null }) {
  if (!value) return <span className="cell-sub">—</span>;
  return <span className={`badge ${toneFor(value)}`}>{humanize(value)}</span>;
}

export function Card({
  title,
  sub,
  actions,
  children,
  pad = false,
}: {
  title?: string;
  sub?: string;
  actions?: ReactNode;
  children: ReactNode;
  pad?: boolean;
}) {
  return (
    <section className="card">
      {title && (
        <div className="card-head">
          <div>
            <h3>{title}</h3>
            {sub && <div className="sub">{sub}</div>}
          </div>
          {actions}
        </div>
      )}
      <div className={pad ? "card-pad" : undefined}>{children}</div>
    </section>
  );
}

export function Stat({
  label,
  value,
  meta,
  accent,
}: {
  label: string;
  value: ReactNode;
  meta?: ReactNode;
  accent?: "gold" | "red" | "navy";
}) {
  return (
    <div className={`stat${accent && accent !== "gold" ? " " + accent : ""}`}>
      <div className="label">{label}</div>
      <div className="value">{value}</div>
      {meta && <div className="meta">{meta}</div>}
    </div>
  );
}

type Tone = "ok" | "warn" | "danger" | "info" | "muted";
export function Badge({ tone, children }: { tone: Tone; children: ReactNode }) {
  return <span className={`badge ${tone}`}>{children}</span>;
}

export function Spinner() {
  return (
    <div className="center-state">
      <div>
        <div className="spinner" style={{ margin: "0 auto" }} />
        <p style={{ color: "var(--ink-3)", marginTop: 14, fontSize: 13 }}>Loading…</p>
      </div>
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="empty">{children}</div>;
}

export function ErrorState({ error, retry }: { error: unknown; retry?: () => void }) {
  const msg = error instanceof Error ? error.message : "Something went wrong.";
  return (
    <div className="center-state">
      <div>
        <p style={{ color: "var(--danger)", fontWeight: 600 }}>{msg}</p>
        {retry && (
          <button className="btn" style={{ marginTop: 12 }} onClick={retry}>
            Try again
          </button>
        )}
      </div>
    </div>
  );
}

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { get } from "@/lib/api";
import { fmtDate, humanize, initialsOf } from "@/lib/format";
import type { StaffFull } from "@/lib/types";
import { Drawer } from "@/components/Drawer";
import { StatusBadge, Badge, Spinner, Empty } from "@/components/ui";

function Field({ label, value }: { label: string; value?: React.ReactNode }) {
  return (
    <div className="field-row">
      <div className="field-label">{label}</div>
      <div className="field-static">{value || "—"}</div>
    </div>
  );
}

export default function StaffDrawer({ staffId, onClose }: { staffId: string; onClose: () => void }) {
  const [tab, setTab] = useState("overview");
  const q = useQuery<StaffFull>({
    queryKey: ["admin", "staff", staffId],
    queryFn: () => get<StaffFull>(`/api/admin/staff/${staffId}/full`),
  });

  const s = q.data;
  const isCounselor = s?.role === "counselor";
  const tabs = [
    { key: "overview", label: "Overview" },
    ...(isCounselor ? [{ key: "clients", label: "Clients" }, { key: "activity", label: "Activity" }] : []),
  ];
  const name = s ? `${s.first_name ?? ""} ${s.last_name ?? ""}`.trim() || s.email : "Loading…";

  return (
    <Drawer
      avatar={s ? initialsOf(s.first_name, s.last_name, s.email) : "…"}
      title={name}
      meta={s && `${(s.role ?? "").toUpperCase()}${s.title ? " · " + s.title : ""} · ${s.active ? "Active" : "Inactive"}`}
      tabs={tabs}
      active={tab}
      onTab={setTab}
      onClose={onClose}
    >
      {q.isLoading || !s ? (
        <Spinner />
      ) : tab === "overview" ? (
        <>
          <div className="info-grid" style={{ marginBottom: 16 }}>
            <Field label="Email" value={s.email} />
            <Field label="Role" value={<Badge tone={s.role === "admin" ? "danger" : "info"}>{humanize(s.role)}</Badge>} />
            <Field label="Title" value={s.title} />
            <Field label="Credentials" value={s.credentials} />
            <Field label="Status" value={s.active ? <StatusBadge value="active" /> : <StatusBadge value="inactive" />} />
            <Field label="Joined" value={fmtDate(s.created_at)} />
            <Field label="Last Active" value={fmtDate(s.last_active)} />
            {s.calendly_url && (
              <Field label="Calendly" value={<a className="link" href={s.calendly_url} target="_blank" rel="noreferrer">Booking link</a>} />
            )}
          </div>
          <Field label="Specialties" value={(s.specialties ?? []).length ? s.specialties!.join(", ") : "—"} />
          <div className="field-row">
            <div className="field-label">Bio</div>
            <div className="field-static" style={{ whiteSpace: "pre-wrap" }}>{s.bio || "—"}</div>
          </div>
        </>
      ) : tab === "clients" ? (
        (s.clients ?? []).length === 0 ? (
          <Empty>No clients assigned yet.</Empty>
        ) : (
          <>
            <div className="cell-sub" style={{ marginBottom: 10 }}>
              {s.clients!.length} assigned client{s.clients!.length === 1 ? "" : "s"}
            </div>
            {s.clients!.map((c) => (
              <div className="list-row" key={c.id} style={{ cursor: "default" }}>
                <div>
                  <div style={{ fontWeight: 600, fontSize: 13 }}>{c.name || c.email}</div>
                  <div className="cell-sub">
                    {c.email} · {c.notes_count ?? 0} notes · {c.disputes_count ?? 0} disputes
                  </div>
                </div>
                <StatusBadge value={c.pipeline_stage} />
              </div>
            ))}
          </>
        )
      ) : (
        (s.recent_activity ?? []).length === 0 ? (
          <Empty>No activity logged yet.</Empty>
        ) : (
          s.recent_activity!.map((a, i) => (
            <div className="note-item" key={i}>
              <div className="cell-sub" style={{ marginBottom: 2 }}>
                {fmtDate(a.created_at)} · <b>{a.member_name}</b>
              </div>
              <div style={{ fontSize: 13 }}>{a.content}</div>
            </div>
          ))
        )
      )}
    </Drawer>
  );
}

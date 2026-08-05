import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { get, apiUrl } from "@/lib/api";
import { fmtDate, fmtTime, humanize, initialsOf } from "@/lib/format";
import type { Counselor, MemberFull } from "@/lib/types";
import { Drawer } from "@/components/Drawer";
import { StatusBadge, Spinner, Empty } from "@/components/ui";
import { useMemberActions } from "@/hooks/useMemberActions";

const TABS = [
  { key: "overview", label: "Overview" },
  { key: "cr", label: "Credit Repair" },
  { key: "fc", label: "Fin. Counseling" },
  { key: "courses", label: "Courses" },
  { key: "docs", label: "DD-214" },
  { key: "notes", label: "Notes" },
];

const CR_STAGES = [
  ["cr_waitlist", "Waitlist"], ["cr_consultation", "Consultation"], ["cr_documents", "Documents"],
  ["cr_dispute_1", "Dispute 1"], ["cr_dispute_2", "Dispute 2"], ["cr_dispute_3", "Dispute 3"],
  ["cr_monitoring", "Monitoring"], ["cr_complete", "Complete"],
] as const;
const FC_STAGES = [
  ["fc_waitlist", "Waitlist"], ["fc_consultation", "Consultation"], ["fc_documents", "Documents"],
  ["fc_gameplan", "Game Plan"], ["fc_working", "Working"], ["fc_complete", "Complete"],
] as const;
const PIPELINE_STAGES = ["applied", "dd214_pending", "dd214_review", "approved", "active", "inactive", "graduated"];

function Field({ label, value }: { label: string; value?: React.ReactNode }) {
  return (
    <div className="field-row">
      <div className="field-label">{label}</div>
      <div className="field-static">{value || "—"}</div>
    </div>
  );
}

function StageTrack({ stages, current }: { stages: readonly (readonly [string, string])[]; current?: string }) {
  const idx = stages.findIndex(([s]) => s === current);
  return (
    <div className="stage-track" style={{ margin: "6px 0 16px" }}>
      {stages.map(([s, label], i) => (
        <div className={"seg" + (idx >= i ? " on" : "")} key={s}>
          <div className="rail" />
          <div className="lbl">{label}</div>
        </div>
      ))}
    </div>
  );
}

export default function MemberDrawer({ memberId, onClose }: { memberId: string; onClose: () => void }) {
  const [tab, setTab] = useState("overview");
  const [note, setNote] = useState("");
  const [manualOpen, setManualOpen] = useState(false);
  const [manualNotes, setManualNotes] = useState("");
  const A = useMemberActions();

  const q = useQuery<MemberFull>({
    queryKey: ["admin", "member", memberId],
    queryFn: () => get<MemberFull>(`/api/admin/members/${memberId}/full`),
  });
  const counselorsQ = useQuery<Counselor[]>({
    queryKey: ["admin", "counselors"],
    queryFn: () => get<Counselor[]>("/api/admin/staff/counselors"),
    staleTime: 5 * 60 * 1000,
  });

  const m = q.data;
  const name = m ? `${m.first_name ?? ""} ${m.last_name ?? ""}`.trim() || m.email : "Loading…";
  const reload = () => A.refreshMember(memberId);

  const crStage = m?.cr_stage || m?.credit_repair_stage;
  const fcStage = m?.fc_stage || m?.financial_counseling_stage;
  const ddStatus = m?.dd214_status || "pending";

  return (
    <Drawer
      avatar={m ? initialsOf(m.first_name, m.last_name, m.email) : "…"}
      title={name}
      meta={m && `${m.branch ?? ""}${m.service_status ? " · " + m.service_status : ""} · Joined ${fmtDate(m.created_at)}`}
      tabs={TABS}
      active={tab}
      onTab={setTab}
      onClose={onClose}
      footer={
        m && (
          <>
            {!m.verified && (
              <button className="btn primary" onClick={() => A.verify(memberId).then(reload)}>
                Verify Member
              </button>
            )}
            <div style={{ flex: 1 }} />
            <button className="btn" onClick={() => A.archive(memberId, name)}>
              Archive
            </button>
            <button className="btn" style={{ color: "var(--danger)" }} onClick={() => A.remove(memberId, name).then((ok) => ok && onClose())}>
              Delete
            </button>
          </>
        )
      }
    >
      {q.isLoading || !m ? (
        <Spinner />
      ) : tab === "overview" ? (
        <>
          <div className="info-grid" style={{ marginBottom: 18 }}>
            <Field label="Email" value={m.email} />
            <Field label="Phone" value={m.phone} />
            <Field label="State" value={m.state} />
            <Field label="Date of Birth" value={m.dob} />
            <Field label="Branch" value={m.branch} />
            <Field label="Service Status" value={m.service_status} />
            <Field label="Years of Service" value={m.years_of_service} />
            <Field label="Separation Year" value={m.separation_year} />
          </div>

          <div className="section-label">Case Management</div>
          <div className="form-grid-2">
            <div className="field-row">
              <div className="field-label">Pipeline Stage</div>
              <select
                defaultValue={m.pipeline_stage}
                onChange={(e) => A.saveOverview(memberId, { pipeline_stage: e.target.value }).then(reload)}
                style={{ width: "100%" }}
              >
                {PIPELINE_STAGES.map((s) => (
                  <option key={s} value={s}>
                    {humanize(s)}
                  </option>
                ))}
              </select>
            </div>
            <div className="field-row">
              <div className="field-label">Assigned Counselor</div>
              <select
                defaultValue={m.assigned_counselor_id ?? ""}
                onChange={(e) => A.saveOverview(memberId, { assigned_counselor_id: e.target.value || null }).then(reload)}
                style={{ width: "100%" }}
              >
                <option value="">— None —</option>
                {(counselorsQ.data ?? []).map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div className="field-row">
            <div className="field-label">Admin Notes</div>
            <textarea
              defaultValue={m.admin_notes ?? ""}
              rows={3}
              style={{ width: "100%" }}
              onBlur={(e) => {
                if (e.target.value !== (m.admin_notes ?? "")) A.saveOverview(memberId, { admin_notes: e.target.value }).then(reload);
              }}
            />
          </div>
          <div className="field-row">
            <div className="field-label">Member Needs / Background</div>
            <div style={{ padding: 10, background: "var(--surface)", border: "1px solid var(--line)", borderRadius: 8, fontSize: 13 }}>
              {m.challenges || m.notes || "—"}
            </div>
          </div>
        </>
      ) : tab === "cr" ? (
        <ProgramTab
          enrolled={!!crStage}
          label="Credit Repair"
          stages={CR_STAGES}
          current={crStage}
          onEnroll={() => A.setStage(memberId, "credit_repair", "cr_waitlist", reload)}
          onStage={(s) => A.setStage(memberId, "credit_repair", s, reload)}
        >
          <div className="section-label">Disputes Filed</div>
          {m.disputes && m.disputes.length ? (
            <div className="table-wrap">
              <table className="tbl">
                <thead>
                  <tr>
                    <th>Bureau</th>
                    <th>Account</th>
                    <th>Round</th>
                    <th>Status</th>
                    <th>Date</th>
                  </tr>
                </thead>
                <tbody>
                  {m.disputes.map((d, i) => (
                    <tr key={i}>
                      <td>{d.bureau || "—"}</td>
                      <td>{d.account || "—"}</td>
                      <td>{d.round ?? "—"}</td>
                      <td><StatusBadge value={d.status} /></td>
                      <td>{fmtDate(d.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="cell-sub">No disputes on file.</div>
          )}
        </ProgramTab>
      ) : tab === "fc" ? (
        <ProgramTab
          enrolled={!!fcStage}
          label="Financial Counseling"
          stages={FC_STAGES}
          current={fcStage}
          onEnroll={() => A.setStage(memberId, "financial_counseling", "fc_waitlist", reload)}
          onStage={(s) => A.setStage(memberId, "financial_counseling", s, reload)}
        />
      ) : tab === "courses" ? (
        (m.courses ?? []).length === 0 ? (
          <Empty>No courses enrolled.</Empty>
        ) : (
          m.courses!.map((c, i) => (
            <div key={i} style={{ marginBottom: 12 }}>
              <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 5 }}>{c.title}</div>
              <div className="progress-bar">
                <div className="progress-fill" style={{ width: `${c.percent_complete}%` }} />
              </div>
              <div className="cell-sub" style={{ marginTop: 3 }}>
                {c.percent_complete}% complete · Last: {fmtDate(c.last_accessed)}
              </div>
            </div>
          ))
        )
      ) : tab === "docs" ? (
        <>
          <div className="field-label">DD-214 Status</div>
          <div style={{ margin: "6px 0 16px" }}>
            <StatusBadge value={ddStatus} />
            {m.dd214_approved_by && (
              <div className="cell-sub" style={{ marginTop: 6 }}>
                Approved by {m.dd214_approved_by} on {fmtDate(m.dd214_approved_at)}
              </div>
            )}
          </div>
          {m.dd214_file ? (
            <a className="btn" href={apiUrl(`/api/admin/dd214/${m.dd214_file}`)} target="_blank" rel="noreferrer">
              View DD-214 File
            </a>
          ) : (
            <div className="cell-sub">No DD-214 file uploaded.</div>
          )}
          {ddStatus !== "approved" && ddStatus !== "manual_approved" && ddStatus !== "verified" && (
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 16 }}>
              <button className="btn primary" onClick={() => A.setDd214(memberId, "verified", reload)}>
                Approve DD-214
              </button>
              <button className="btn" style={{ color: "var(--danger)" }} onClick={() => A.setDd214(memberId, "rejected", reload)}>
                Reject
              </button>
              <button className="btn" onClick={() => setManualOpen(true)}>
                Manual Approve
              </button>
            </div>
          )}
          {manualOpen && (
            <div style={{ marginTop: 16 }}>
              <div className="field-label">Manual approval notes</div>
              <textarea value={manualNotes} onChange={(e) => setManualNotes(e.target.value)} rows={3} style={{ width: "100%" }} />
              <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
                <button className="btn primary" onClick={() => A.manualApprove(memberId, manualNotes).then(() => { setManualOpen(false); reload(); })}>
                  Confirm Manual Approval
                </button>
                <button className="btn" onClick={() => setManualOpen(false)}>
                  Cancel
                </button>
              </div>
            </div>
          )}
        </>
      ) : (
        // notes
        <>
          <div className="field-label">Add Note</div>
          <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={3} style={{ width: "100%" }} placeholder="Add a note about this member…" />
          <button
            className="btn primary sm"
            style={{ marginTop: 8, marginBottom: 18 }}
            disabled={!note.trim()}
            onClick={() => A.addNote(memberId, note.trim(), () => { setNote(""); reload(); })}
          >
            Add Note
          </button>
          <div className="section-label">Note History</div>
          {(m.notes_history ?? []).length === 0 ? (
            <div className="cell-sub">No notes yet.</div>
          ) : (
            m.notes_history!.map((n, i) => (
              <div className="note-item" key={i}>
                <div style={{ fontSize: 13, marginBottom: 4 }}>{n.content}</div>
                <div className="cell-sub">
                  {n.author || "Admin"} · {fmtTime(n.created_at)}
                </div>
              </div>
            ))
          )}
        </>
      )}
    </Drawer>
  );
}

function ProgramTab({
  enrolled,
  label,
  stages,
  current,
  onEnroll,
  onStage,
  children,
}: {
  enrolled: boolean;
  label: string;
  stages: readonly (readonly [string, string])[];
  current?: string;
  onEnroll: () => void;
  onStage: (s: string) => void;
  children?: React.ReactNode;
}) {
  if (!enrolled) {
    return (
      <div style={{ textAlign: "center", padding: "30px 0" }}>
        <p className="cell-sub" style={{ marginBottom: 14 }}>Not enrolled in {label}.</p>
        <button className="btn primary" onClick={onEnroll}>
          Enroll in {label}
        </button>
      </div>
    );
  }
  return (
    <>
      <div className="field-row">
        <div className="field-label">{label} Stage</div>
        <select value={current} onChange={(e) => onStage(e.target.value)} style={{ width: "100%" }}>
          {stages.map(([s, l]) => (
            <option key={s} value={s}>
              {l}
            </option>
          ))}
        </select>
      </div>
      <StageTrack stages={stages} current={current} />
      {children}
    </>
  );
}

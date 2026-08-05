import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { get, apiUrl } from "@/lib/api";
import { fmtDate } from "@/lib/format";
import type { MemberRow } from "@/lib/types";
import { Spinner, ErrorState } from "@/components/ui";
import { Modal } from "@/components/Modal";
import { IconDd214 } from "@/components/icons";
import { useMemberActions } from "@/hooks/useMemberActions";
import MemberDrawer from "./MemberDrawer";

export default function Dd214() {
  const [openId, setOpenId] = useState<string | null>(null);
  const [manualFor, setManualFor] = useState<MemberRow | null>(null);
  const [notes, setNotes] = useState("");
  const A = useMemberActions();

  const query = useQuery<MemberRow[]>({
    queryKey: ["admin", "members"],
    queryFn: () => get<MemberRow[]>("/api/admin/members"),
  });

  if (query.isLoading) return <Spinner />;
  if (query.isError) return <ErrorState error={query.error} retry={() => query.refetch()} />;

  const pending = (query.data ?? []).filter((m) => m.dd214_status === "pending_review");
  const nameOf = (m: MemberRow) => `${m.first_name ?? ""} ${m.last_name ?? ""}`.trim() || m.email;

  return (
    <>
      <div className="page-head">
        <div>
          <h1>DD-214 Review</h1>
          <p>Verify service records to approve members. {pending.length} awaiting review.</p>
        </div>
      </div>

      {pending.length === 0 ? (
        <div className="empty" style={{ background: "var(--surface)", border: "1px solid var(--line)", borderRadius: "var(--r)", padding: "56px 20px" }}>
          <IconDd214 style={{ width: 34, height: 34, opacity: 0.4 }} />
          <div style={{ marginTop: 10, fontWeight: 600, color: "var(--ink-2)" }}>All caught up</div>
          <div style={{ marginTop: 2 }}>No pending DD-214 reviews.</div>
        </div>
      ) : (
        <div className="dd-grid">
          {pending.map((m) => (
            <div className="dd-card" key={m.id}>
              <div className="nm">{nameOf(m)}</div>
              <div className="mt">
                {m.branch || "Unknown branch"} · Joined {fmtDate(m.created_at)}
              </div>
              {m.dd214_file ? (
                <a className="btn sm" href={apiUrl(`/api/admin/dd214/${m.dd214_file}`)} target="_blank" rel="noreferrer">
                  View DD-214
                </a>
              ) : (
                <div className="cell-sub">No file uploaded</div>
              )}
              <div className="acts">
                <button className="btn primary sm" onClick={() => A.setDd214(m.id, "verified")}>
                  Approve
                </button>
                <button className="btn sm" style={{ color: "var(--danger)" }} onClick={() => A.setDd214(m.id, "rejected")}>
                  Reject
                </button>
                <button className="btn sm" onClick={() => { setManualFor(m); setNotes(""); }}>
                  Manual
                </button>
                <button className="btn sm" onClick={() => setOpenId(m.id)}>
                  Details
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {openId && <MemberDrawer memberId={openId} onClose={() => setOpenId(null)} />}

      {manualFor && (
        <Modal
          title="Manual Approval"
          onClose={() => setManualFor(null)}
          footer={
            <>
              <button className="btn" onClick={() => setManualFor(null)}>
                Cancel
              </button>
              <button className="btn primary" onClick={() => A.manualApprove(manualFor.id, notes).then((ok) => ok && setManualFor(null))}>
                Approve Manually
              </button>
            </>
          }
        >
          <p className="cell-sub" style={{ marginBottom: 12 }}>
            Manually approving <b>{nameOf(manualFor)}</b> without a DD-214 file. Add a note explaining why (optional).
          </p>
          <textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={3} style={{ width: "100%" }} placeholder="e.g. Verified service by phone with VA records" />
        </Modal>
      )}
    </>
  );
}

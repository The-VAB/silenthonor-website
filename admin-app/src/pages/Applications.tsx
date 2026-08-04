import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { get, put } from "@/lib/api";
import { fmtDate, humanize } from "@/lib/format";
import type { Application, Counselor } from "@/lib/types";
import { Card, StatusBadge, Badge, Spinner, ErrorState } from "@/components/ui";
import { Modal } from "@/components/Modal";
import { useToast } from "@/components/toast";

export default function Applications() {
  const [type, setType] = useState("");
  const [status, setStatus] = useState("pending");
  const [approveFor, setApproveFor] = useState<Application | null>(null);
  const [counselorId, setCounselorId] = useState("");
  const [viewId, setViewId] = useState<string | null>(null);
  const toast = useToast();
  const qc = useQueryClient();

  const query = useQuery<Application[]>({
    queryKey: ["admin", "applications", type, status],
    queryFn: () => {
      const p = new URLSearchParams();
      if (type) p.set("program_type", type);
      if (status) p.set("status", status);
      return get<Application[]>(`/api/admin/applications?${p.toString()}`);
    },
  });
  const counselorsQ = useQuery<Counselor[]>({
    queryKey: ["admin", "counselors"],
    queryFn: () => get<Counselor[]>("/api/admin/staff/counselors"),
    staleTime: 5 * 60 * 1000,
  });

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["admin", "applications"] });
    qc.invalidateQueries({ queryKey: ["admin", "stats"] });
  };

  async function doApprove() {
    if (!approveFor) return;
    try {
      await put(`/api/admin/applications/${approveFor.id}/approve`, { counselor_id: counselorId || null });
      toast("Application approved", "success");
      setApproveFor(null);
      refresh();
    } catch (e) {
      toast(e instanceof Error ? e.message : "Error", "error");
    }
  }

  async function doReject(id: string) {
    const reason = window.prompt("Reason for rejection (optional):");
    if (reason === null) return;
    try {
      await put(`/api/admin/applications/${id}/reject`, { reason });
      toast("Application rejected", "success");
      refresh();
    } catch (e) {
      toast(e instanceof Error ? e.message : "Error", "error");
    }
  }

  const progBadge = (t: string) =>
    t === "credit_repair" ? <Badge tone="info">Credit Repair</Badge> : <Badge tone="muted">Fin. Counseling</Badge>;

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Applications</h1>
          <p>Program enrollment requests awaiting review.</p>
        </div>
      </div>

      <div className="toolbar">
        <select value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="pending">Pending</option>
          <option value="approved">Approved</option>
          <option value="rejected">Rejected</option>
          <option value="">All statuses</option>
        </select>
        <select value={type} onChange={(e) => setType(e.target.value)}>
          <option value="">All programs</option>
          <option value="credit_repair">Credit Repair</option>
          <option value="financial_counseling">Financial Counseling</option>
        </select>
        <div className="spacer" />
        <span className="count-pill">{query.data?.length ?? 0} applications</span>
      </div>

      {query.isLoading ? (
        <Spinner />
      ) : query.isError ? (
        <ErrorState error={query.error} retry={() => query.refetch()} />
      ) : (
        <Card>
          <div className="table-wrap">
            <table className="tbl">
              <thead>
                <tr>
                  <th>Member</th>
                  <th>Program</th>
                  <th>Applied</th>
                  <th>Status</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {(query.data ?? []).length === 0 ? (
                  <tr>
                    <td colSpan={5}>
                      <div className="empty">No applications found.</div>
                    </td>
                  </tr>
                ) : (
                  query.data!.map((a) => (
                    <tr key={a.id} className="row-click" onClick={() => setViewId(a.id)}>
                      <td>
                        <div className="cell-name">{a.member_name || "Member"}</div>
                        <div className="cell-sub">{a.member_email}</div>
                      </td>
                      <td>{progBadge(a.program_type)}</td>
                      <td className="cell-sub">{fmtDate(a.applied_at)}</td>
                      <td><StatusBadge value={a.status} /></td>
                      <td onClick={(e) => e.stopPropagation()} style={{ whiteSpace: "nowrap" }}>
                        {a.status === "pending" && (
                          <>
                            <button className="btn primary sm" style={{ marginRight: 6 }} onClick={() => { setApproveFor(a); setCounselorId(""); }}>
                              Approve
                            </button>
                            <button className="btn sm" style={{ marginRight: 6, color: "var(--danger)" }} onClick={() => doReject(a.id)}>
                              Reject
                            </button>
                          </>
                        )}
                        <button className="btn sm" onClick={() => setViewId(a.id)}>
                          View
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {approveFor && (
        <Modal
          title="Approve Application"
          onClose={() => setApproveFor(null)}
          footer={
            <>
              <button className="btn" onClick={() => setApproveFor(null)}>
                Cancel
              </button>
              <button className="btn primary" onClick={doApprove}>
                Approve
              </button>
            </>
          }
        >
          <p className="cell-sub" style={{ marginBottom: 12 }}>
            Approving <b>{approveFor.member_name}</b> for {humanize(approveFor.program_type)}. Assign a counselor (optional):
          </p>
          <select value={counselorId} onChange={(e) => setCounselorId(e.target.value)} style={{ width: "100%" }}>
            <option value="">— No counselor —</option>
            {(counselorsQ.data ?? []).map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </Modal>
      )}

      {viewId && <AppDetail id={viewId} onClose={() => setViewId(null)} onApprove={(a) => { setViewId(null); setApproveFor(a); setCounselorId(""); }} onReject={(id) => { setViewId(null); doReject(id); }} />}
    </>
  );
}

function AppDetail({
  id,
  onClose,
  onApprove,
  onReject,
}: {
  id: string;
  onClose: () => void;
  onApprove: (a: Application) => void;
  onReject: (id: string) => void;
}) {
  const q = useQuery<Application>({
    queryKey: ["admin", "application", id],
    queryFn: () => get<Application>(`/api/admin/applications/${id}`),
  });
  const a = q.data;
  const data = a?.application_data ?? {};

  return (
    <Modal
      title="Application Detail"
      wide
      onClose={onClose}
      footer={
        <>
          <button className="btn" onClick={onClose}>
            Close
          </button>
          {a?.status === "pending" && (
            <>
              <div className="spacer" />
              <button className="btn sm" style={{ color: "var(--danger)" }} onClick={() => onReject(id)}>
                Reject
              </button>
              <button className="btn primary sm" onClick={() => onApprove(a)}>
                Approve
              </button>
            </>
          )}
        </>
      }
    >
      {q.isLoading || !a ? (
        <div style={{ padding: 20 }}>
          <Spinner />
        </div>
      ) : (
        <>
          <div style={{ display: "flex", gap: 10, alignItems: "center", marginBottom: 14, flexWrap: "wrap" }}>
            <b>{a.member_name || "Member"}</b>
            {a.program_type === "credit_repair" ? <Badge tone="info">Credit Repair</Badge> : <Badge tone="muted">Fin. Counseling</Badge>}
            <StatusBadge value={a.status} />
            <span className="cell-sub">Applied {fmtDate(a.applied_at)}</span>
          </div>
          <div className="table-wrap">
            <table className="tbl">
              <tbody>
                {Object.entries(data).map(([k, v]) => (
                  <tr key={k}>
                    <td style={{ fontWeight: 500, whiteSpace: "nowrap" }}>{humanize(k)}</td>
                    <td>{Array.isArray(v) ? v.join(", ") : v == null || v === "" ? "—" : String(v)}</td>
                  </tr>
                ))}
                {Object.keys(data).length === 0 && (
                  <tr>
                    <td className="cell-sub">No additional application data.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </>
      )}
    </Modal>
  );
}

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { get } from "@/lib/api";
import { fmtDate } from "@/lib/format";
import type { MemberRow } from "@/lib/types";
import { Card, StatusBadge, Badge, Spinner, ErrorState } from "@/components/ui";
import { IconMembers } from "@/components/icons";
import { Modal } from "@/components/Modal";
import { useMemberActions } from "@/hooks/useMemberActions";
import MemberDrawer from "./MemberDrawer";

const BRANCHES = ["Army", "Navy", "Marine Corps", "Air Force", "Coast Guard", "Space Force", "National Guard", "Reserve"];
const STAGES = ["applied", "dd214_pending", "dd214_review", "approved", "active", "inactive", "graduated"];

function SearchIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
      <circle cx="11" cy="11" r="8" />
      <path d="m21 21-4.3-4.3" />
    </svg>
  );
}

export default function Members() {
  const [q, setQ] = useState("");
  const [branch, setBranch] = useState("");
  const [stage, setStage] = useState("");
  const [verified, setVerified] = useState("");
  const [openId, setOpenId] = useState<string | null>(null);
  const [pwFor, setPwFor] = useState<MemberRow | null>(null);
  const [pw, setPw] = useState("");

  const A = useMemberActions();
  const query = useQuery<MemberRow[]>({
    queryKey: ["admin", "members"],
    queryFn: () => get<MemberRow[]>("/api/admin/members"),
  });

  const rows = useMemo(() => {
    const all = query.data ?? [];
    const s = q.toLowerCase();
    return all.filter((m) => {
      const name = `${m.first_name ?? ""} ${m.last_name ?? ""} ${m.email}`.toLowerCase();
      return (
        (!s || name.includes(s)) &&
        (!branch || m.branch === branch) &&
        (!stage || m.pipeline_stage === stage) &&
        (!verified || String(!!m.verified) === verified)
      );
    });
  }, [query.data, q, branch, stage, verified]);

  if (query.isLoading) return <Spinner />;
  if (query.isError) return <ErrorState error={query.error} retry={() => query.refetch()} />;

  const nameOf = (m: MemberRow) => `${m.first_name ?? ""} ${m.last_name ?? ""}`.trim() || m.email;

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Members</h1>
          <p>Every registered veteran, their program stage, and verification status.</p>
        </div>
      </div>

      <div className="toolbar">
        <div className="search">
          <SearchIcon />
          <input placeholder="Search name or email…" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        <select value={branch} onChange={(e) => setBranch(e.target.value)}>
          <option value="">All branches</option>
          {BRANCHES.map((b) => (
            <option key={b}>{b}</option>
          ))}
        </select>
        <select value={stage} onChange={(e) => setStage(e.target.value)}>
          <option value="">All stages</option>
          {STAGES.map((s) => (
            <option key={s} value={s}>
              {s.replace(/_/g, " ")}
            </option>
          ))}
        </select>
        <select value={verified} onChange={(e) => setVerified(e.target.value)}>
          <option value="">Any status</option>
          <option value="true">Verified</option>
          <option value="false">Unverified</option>
        </select>
        <div className="spacer" />
        <span className="count-pill">{rows.length} members</span>
      </div>

      <Card>
        <div className="table-wrap">
          <table className="tbl">
            <thead>
              <tr>
                <th>Name</th>
                <th>Email</th>
                <th>Branch</th>
                <th>Stage</th>
                <th>DD-214</th>
                <th>Verified</th>
                <th>Joined</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 ? (
                <tr>
                  <td colSpan={8}>
                    <div className="empty">
                      <IconMembers style={{ width: 26, height: 26, opacity: 0.4 }} />
                      <div style={{ marginTop: 8 }}>No members match these filters.</div>
                    </div>
                  </td>
                </tr>
              ) : (
                rows.map((m) => (
                  <tr key={m.id} className="row-click" onClick={() => setOpenId(m.id)}>
                    <td className="cell-name">{nameOf(m)}</td>
                    <td className="cell-sub">{m.email}</td>
                    <td>{m.branch ? <Badge tone="muted">{m.branch}</Badge> : "—"}</td>
                    <td><StatusBadge value={m.pipeline_stage} /></td>
                    <td><StatusBadge value={m.dd214_status} /></td>
                    <td>{m.verified ? <Badge tone="ok">Yes</Badge> : <Badge tone="muted">No</Badge>}</td>
                    <td className="cell-sub">{fmtDate(m.created_at)}</td>
                    <td onClick={(e) => e.stopPropagation()} style={{ whiteSpace: "nowrap" }}>
                      {!m.verified && (
                        <button className="btn sm" style={{ marginRight: 6 }} onClick={() => A.verify(m.id)}>
                          Verify
                        </button>
                      )}
                      <button className="btn sm" style={{ marginRight: 6 }} onClick={() => { setPwFor(m); setPw(""); }}>
                        Set PW
                      </button>
                      {m.pipeline_stage !== "inactive" && (
                        <button className="btn sm" style={{ marginRight: 6 }} onClick={() => A.archive(m.id, nameOf(m))}>
                          Archive
                        </button>
                      )}
                      <button className="btn sm" style={{ color: "var(--danger)" }} onClick={() => A.remove(m.id, nameOf(m))}>
                        Delete
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </Card>

      {openId && <MemberDrawer memberId={openId} onClose={() => setOpenId(null)} />}

      {pwFor && (
        <Modal
          title="Set Member Password"
          onClose={() => setPwFor(null)}
          footer={
            <>
              <button className="btn" onClick={() => setPwFor(null)}>
                Cancel
              </button>
              <button
                className="btn primary"
                disabled={pw.trim().length < 6}
                onClick={() => A.setPassword(pwFor.id, pw.trim()).then((ok) => ok && setPwFor(null))}
              >
                Set Password
              </button>
            </>
          }
        >
          <p className="cell-sub" style={{ marginBottom: 12 }}>
            Setting a new password for <b>{nameOf(pwFor)}</b>. Minimum 6 characters.
          </p>
          <input type="text" value={pw} onChange={(e) => setPw(e.target.value)} placeholder="New password" style={{ width: "100%" }} autoFocus />
        </Modal>
      )}
    </>
  );
}

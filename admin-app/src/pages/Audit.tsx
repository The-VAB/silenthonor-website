import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { get } from "@/lib/api";
import { fmtTime, humanize } from "@/lib/format";
import type { AuditEntry } from "@/lib/types";
import { Card, Spinner, ErrorState } from "@/components/ui";

export default function Audit() {
  const [q, setQ] = useState("");
  const query = useQuery<AuditEntry[]>({
    queryKey: ["admin", "audit"],
    queryFn: () => get<AuditEntry[]>("/api/admin/audit-log"),
  });

  const rows = useMemo(() => {
    const all = query.data ?? [];
    const s = q.toLowerCase();
    const filtered = s
      ? all.filter(
          (l) =>
            (l.action ?? "").toLowerCase().includes(s) ||
            (l.user_email ?? "").toLowerCase().includes(s) ||
            (l.entity_type ?? "").toLowerCase().includes(s)
        )
      : all;
    return filtered.slice(0, 200);
  }, [query.data, q]);

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Audit Log</h1>
          <p>Every administrative action, most recent first (last 200 shown).</p>
        </div>
      </div>

      <div className="toolbar">
        <div className="search">
          <input placeholder="Search action, user, or entity…" value={q} onChange={(e) => setQ(e.target.value)} style={{ paddingLeft: 12 }} />
        </div>
        <div className="spacer" />
        <span className="count-pill">{rows.length} entries</span>
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
                  <th>Time</th>
                  <th>User</th>
                  <th>Action</th>
                  <th>Entity</th>
                  <th>IP</th>
                </tr>
              </thead>
              <tbody>
                {rows.length === 0 ? (
                  <tr>
                    <td colSpan={5}>
                      <div className="empty">No audit entries found.</div>
                    </td>
                  </tr>
                ) : (
                  rows.map((l, i) => (
                    <tr key={i}>
                      <td className="cell-sub" style={{ whiteSpace: "nowrap" }}>{fmtTime(l.timestamp)}</td>
                      <td>{l.user_email || "—"}</td>
                      <td>
                        <code style={{ fontSize: 11.5, background: "var(--muted-bg)", padding: "2px 7px", borderRadius: 5 }}>
                          {humanize(l.action)}
                        </code>
                      </td>
                      <td>
                        {l.entity_type || "—"}
                        {l.entity_id && <span className="cell-sub"> {l.entity_id.slice(-8)}</span>}
                      </td>
                      <td className="cell-sub">{l.ip_address || "—"}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </>
  );
}

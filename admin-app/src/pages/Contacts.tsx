import { useQuery, useQueryClient } from "@tanstack/react-query";
import { get, put, del } from "@/lib/api";
import { fmtDate } from "@/lib/format";
import type { Contact } from "@/lib/types";
import { Card, Badge, Spinner, ErrorState } from "@/components/ui";
import { useToast } from "@/components/toast";

export default function Contacts() {
  const toast = useToast();
  const qc = useQueryClient();
  const query = useQuery<Contact[]>({
    queryKey: ["admin", "contacts"],
    queryFn: () => get<Contact[]>("/api/admin/contacts"),
  });
  const refresh = () => qc.invalidateQueries({ queryKey: ["admin", "contacts"] });

  async function markResponded(c: Contact) {
    try {
      await put(`/api/admin/contacts/${c.id}`, { responded: true });
      refresh();
    } catch (e) {
      toast(e instanceof Error ? e.message : "Error", "error");
    }
  }
  async function remove(c: Contact) {
    if (!window.confirm("Delete this inquiry?")) return;
    try {
      await del(`/api/admin/contacts/${c.id}`);
      toast("Inquiry deleted", "success");
      refresh();
    } catch (e) {
      toast(e instanceof Error ? e.message : "Error", "error");
    }
  }

  const open = (query.data ?? []).filter((c) => !c.responded).length;

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Contacts</h1>
          <p>Inquiries from the public contact form. {open} awaiting a response.</p>
        </div>
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
                  <th>Name</th>
                  <th>Email</th>
                  <th>Topic</th>
                  <th>Message</th>
                  <th>Received</th>
                  <th>Status</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {(query.data ?? []).length === 0 ? (
                  <tr>
                    <td colSpan={7}>
                      <div className="empty">No inquiries yet.</div>
                    </td>
                  </tr>
                ) : (
                  query.data!.map((c) => (
                    <tr key={c.id}>
                      <td className="cell-name">{`${c.first_name ?? ""} ${c.last_name ?? ""}`.trim() || "—"}</td>
                      <td className="cell-sub">{c.email}</td>
                      <td>{c.topic || "—"}</td>
                      <td style={{ maxWidth: 280 }}>
                        <div style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={c.message}>
                          {c.message}
                        </div>
                      </td>
                      <td className="cell-sub">{fmtDate(c.created_at)}</td>
                      <td><Badge tone={c.responded ? "ok" : "warn"}>{c.responded ? "Responded" : "New"}</Badge></td>
                      <td style={{ whiteSpace: "nowrap" }}>
                        {!c.responded && (
                          <button className="btn sm" style={{ marginRight: 6 }} onClick={() => markResponded(c)}>
                            Mark Responded
                          </button>
                        )}
                        <button className="btn sm" style={{ color: "var(--danger)" }} onClick={() => remove(c)}>
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
      )}
    </>
  );
}

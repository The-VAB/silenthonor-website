import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { get, post, put, del } from "@/lib/api";
import { fmtDate } from "@/lib/format";
import type { Announcement } from "@/lib/types";
import { Card, Badge, Spinner, ErrorState } from "@/components/ui";
import { Modal } from "@/components/Modal";
import { useToast } from "@/components/toast";

const TYPE_TONE = { info: "info", success: "ok", warning: "warn" } as const;

interface Form {
  title: string;
  content: string;
  type: Announcement["type"];
  expires_at: string;
}
const EMPTY: Form = { title: "", content: "", type: "info", expires_at: "" };

export default function Announcements() {
  const [editing, setEditing] = useState<Announcement | null | undefined>(undefined);
  const [form, setForm] = useState<Form>(EMPTY);
  const toast = useToast();
  const qc = useQueryClient();

  const query = useQuery<Announcement[]>({
    queryKey: ["admin", "announcements"],
    queryFn: () => get<Announcement[]>("/api/admin/announcements"),
  });
  const refresh = () => qc.invalidateQueries({ queryKey: ["admin", "announcements"] });

  async function save() {
    if (!form.title.trim()) {
      toast("Title is required", "error");
      return;
    }
    const body = { title: form.title.trim(), content: form.content, type: form.type, expires_at: form.expires_at || null };
    try {
      if (editing) await put(`/api/admin/announcements/${editing.id}`, body);
      else await post("/api/admin/announcements", body);
      toast("Announcement saved", "success");
      setEditing(undefined);
      refresh();
    } catch (e) {
      toast(e instanceof Error ? e.message : "Error", "error");
    }
  }
  async function remove(a: Announcement) {
    if (!window.confirm(`Delete announcement "${a.title}"?`)) return;
    try {
      await del(`/api/admin/announcements/${a.id}`);
      toast("Deleted", "success");
      refresh();
    } catch (e) {
      toast(e instanceof Error ? e.message : "Error", "error");
    }
  }

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Announcements</h1>
          <p>Notices shown to members and staff in their portals.</p>
        </div>
        <button className="btn primary" onClick={() => { setForm(EMPTY); setEditing(null); }}>
          + New Announcement
        </button>
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
                  <th>Title</th>
                  <th>Type</th>
                  <th>Created</th>
                  <th>Expires</th>
                  <th>Status</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {(query.data ?? []).length === 0 ? (
                  <tr>
                    <td colSpan={6}>
                      <div className="empty">No announcements yet.</div>
                    </td>
                  </tr>
                ) : (
                  query.data!.map((a) => (
                    <tr key={a.id}>
                      <td className="cell-name">{a.title}</td>
                      <td><Badge tone={TYPE_TONE[a.type] ?? "muted"}>{a.type}</Badge></td>
                      <td className="cell-sub">{fmtDate(a.created_at)}</td>
                      <td className="cell-sub">{a.expires_at ? fmtDate(a.expires_at) : "Never"}</td>
                      <td><Badge tone={a.active ? "ok" : "muted"}>{a.active ? "Active" : "Inactive"}</Badge></td>
                      <td style={{ whiteSpace: "nowrap" }}>
                        <button className="btn sm" style={{ marginRight: 6 }} onClick={() => { setForm({ title: a.title, content: a.content ?? "", type: a.type, expires_at: a.expires_at ?? "" }); setEditing(a); }}>
                          Edit
                        </button>
                        <button className="btn sm" style={{ color: "var(--danger)" }} onClick={() => remove(a)}>
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

      {editing !== undefined && (
        <Modal
          title={editing ? "Edit Announcement" : "New Announcement"}
          onClose={() => setEditing(undefined)}
          footer={
            <>
              <button className="btn" onClick={() => setEditing(undefined)}>Cancel</button>
              <button className="btn primary" onClick={save}>Save</button>
            </>
          }
        >
          <div className="field-row">
            <div className="field-label">Title</div>
            <input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} style={{ width: "100%" }} />
          </div>
          <div className="form-grid-2">
            <div className="field-row">
              <div className="field-label">Type</div>
              <select value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value as Announcement["type"] })} style={{ width: "100%" }}>
                <option value="info">Info</option>
                <option value="success">Success</option>
                <option value="warning">Warning</option>
              </select>
            </div>
            <div className="field-row">
              <div className="field-label">Expires (optional)</div>
              <input type="date" value={form.expires_at} onChange={(e) => setForm({ ...form, expires_at: e.target.value })} style={{ width: "100%" }} />
            </div>
          </div>
          <div className="field-row">
            <div className="field-label">Message</div>
            <textarea value={form.content} onChange={(e) => setForm({ ...form, content: e.target.value })} rows={4} style={{ width: "100%" }} />
          </div>
        </Modal>
      )}
    </>
  );
}

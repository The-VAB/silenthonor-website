import { useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { get, post, put, del } from "@/lib/api";
import { fmtDate } from "@/lib/format";
import type { Knowledge as KB } from "@/lib/types";
import { Card, Badge, StatusBadge, Spinner, ErrorState } from "@/components/ui";
import { Modal } from "@/components/Modal";
import { useToast } from "@/components/toast";

interface Form {
  title: string;
  category: string;
  tags: string;
  visibility: KB["visibility"];
  status: KB["status"];
  body: string;
}
const EMPTY: Form = { title: "", category: "", tags: "", visibility: "staff_only", status: "draft", body: "" };

export default function Knowledge() {
  const [q, setQ] = useState("");
  const [vis, setVis] = useState("");
  const [stat, setStat] = useState("");
  const [editing, setEditing] = useState<KB | null | undefined>(undefined);
  const [form, setForm] = useState<Form>(EMPTY);
  const toast = useToast();
  const qc = useQueryClient();

  const query = useQuery<KB[]>({
    queryKey: ["admin", "knowledge"],
    queryFn: () => get<KB[]>("/api/admin/knowledge"),
  });
  const refresh = () => qc.invalidateQueries({ queryKey: ["admin", "knowledge"] });

  const rows = useMemo(() => {
    const all = query.data ?? [];
    const s = q.toLowerCase();
    return all.filter(
      (e) =>
        (!vis || e.visibility === vis) &&
        (!stat || e.status === stat) &&
        (!s || (e.title ?? "").toLowerCase().includes(s) || (e.body ?? "").toLowerCase().includes(s))
    );
  }, [query.data, q, vis, stat]);

  async function save() {
    if (!form.title.trim() || !form.body.trim()) {
      toast("Title and body are required", "error");
      return;
    }
    const body = {
      title: form.title.trim(),
      body: form.body.trim(),
      category: form.category.trim() || null,
      tags: form.tags.split(",").map((t) => t.trim()).filter(Boolean),
      visibility: form.visibility,
      status: form.status,
    };
    try {
      if (editing) await put(`/api/admin/knowledge/${editing.id}`, body);
      else await post("/api/admin/knowledge", body);
      toast("Entry saved", "success");
      setEditing(undefined);
      refresh();
    } catch (e) {
      toast(e instanceof Error ? e.message : "Error", "error");
    }
  }
  async function setStatus(e: KB, action: "publish" | "retire") {
    try {
      await post(`/api/admin/knowledge/${e.id}/${action}`);
      toast(action === "publish" ? "Published" : "Retired", "success");
      refresh();
    } catch (err) {
      toast(err instanceof Error ? err.message : "Error", "error");
    }
  }
  async function remove(e: KB) {
    if (!window.confirm("Delete this entry permanently? Consider Retire instead if it was ever published.")) return;
    try {
      await del(`/api/admin/knowledge/${e.id}`);
      toast("Deleted", "success");
      refresh();
    } catch (err) {
      toast(err instanceof Error ? err.message : "Error", "error");
    }
  }

  const warn = form.visibility === "member_visible" && form.status === "published";

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Knowledge Base</h1>
          <p>Playbooks and reference articles for staff — some published to members.</p>
        </div>
        <button className="btn primary" onClick={() => { setForm(EMPTY); setEditing(null); }}>
          + New Entry
        </button>
      </div>

      <div className="toolbar">
        <div className="search">
          <input placeholder="Search entries…" value={q} onChange={(e) => setQ(e.target.value)} style={{ paddingLeft: 12 }} />
        </div>
        <select value={vis} onChange={(e) => setVis(e.target.value)}>
          <option value="">All visibility</option>
          <option value="member_visible">Member-visible</option>
          <option value="staff_only">Staff-only</option>
        </select>
        <select value={stat} onChange={(e) => setStat(e.target.value)}>
          <option value="">All statuses</option>
          <option value="published">Published</option>
          <option value="draft">Draft</option>
          <option value="retired">Retired</option>
        </select>
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
                  <th>Title</th>
                  <th>Category</th>
                  <th>Visibility</th>
                  <th>Status</th>
                  <th>Updated</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {rows.length === 0 ? (
                  <tr>
                    <td colSpan={6}>
                      <div className="empty">No entries match.</div>
                    </td>
                  </tr>
                ) : (
                  rows.map((e) => (
                    <tr key={e.id}>
                      <td className="cell-name">{e.title}</td>
                      <td>{e.category || "—"}</td>
                      <td><Badge tone={e.visibility === "member_visible" ? "ok" : "muted"}>{e.visibility === "member_visible" ? "Member" : "Staff"}</Badge></td>
                      <td><StatusBadge value={e.status} /></td>
                      <td className="cell-sub">{fmtDate(e.updated_at)}</td>
                      <td style={{ whiteSpace: "nowrap" }}>
                        <button className="btn sm" style={{ marginRight: 6 }} onClick={() => { setForm({ title: e.title, category: e.category ?? "", tags: (e.tags ?? []).join(", "), visibility: e.visibility, status: e.status, body: e.body ?? "" }); setEditing(e); }}>
                          Edit
                        </button>
                        {e.status !== "published" && (
                          <button className="btn sm" style={{ marginRight: 6 }} onClick={() => setStatus(e, "publish")}>
                            Publish
                          </button>
                        )}
                        {e.status !== "retired" && (
                          <button className="btn sm" style={{ marginRight: 6 }} onClick={() => setStatus(e, "retire")}>
                            Retire
                          </button>
                        )}
                        <button className="btn sm" style={{ color: "var(--danger)" }} onClick={() => remove(e)}>
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
          title={editing ? "Edit Knowledge Entry" : "New Knowledge Entry"}
          wide
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
              <div className="field-label">Category</div>
              <input value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} style={{ width: "100%" }} />
            </div>
            <div className="field-row">
              <div className="field-label">Tags (comma-separated)</div>
              <input value={form.tags} onChange={(e) => setForm({ ...form, tags: e.target.value })} style={{ width: "100%" }} />
            </div>
            <div className="field-row">
              <div className="field-label">Visibility</div>
              <select value={form.visibility} onChange={(e) => setForm({ ...form, visibility: e.target.value as KB["visibility"] })} style={{ width: "100%" }}>
                <option value="staff_only">Staff-only</option>
                <option value="member_visible">Member-visible</option>
              </select>
            </div>
            <div className="field-row">
              <div className="field-label">Status</div>
              <select value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value as KB["status"] })} style={{ width: "100%" }}>
                <option value="draft">Draft</option>
                <option value="published">Published</option>
                <option value="retired">Retired</option>
              </select>
            </div>
          </div>
          {warn && (
            <div className="temp-pass" style={{ background: "var(--warn-bg)" }}>
              <div className="cell-sub" style={{ color: "var(--warn)", fontWeight: 600 }}>
                This entry will be visible to all members once saved.
              </div>
            </div>
          )}
          <div className="field-row" style={{ marginTop: 12 }}>
            <div className="field-label">Body</div>
            <textarea value={form.body} onChange={(e) => setForm({ ...form, body: e.target.value })} rows={8} style={{ width: "100%" }} />
          </div>
        </Modal>
      )}
    </>
  );
}

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { get, post, put } from "@/lib/api";
import { humanize } from "@/lib/format";
import type { StaffRow } from "@/lib/types";
import { Card, Badge, StatusBadge, Spinner, ErrorState } from "@/components/ui";
import { Modal } from "@/components/Modal";
import { useToast } from "@/components/toast";
import StaffDrawer from "./StaffDrawer";

interface StaffForm {
  first_name: string;
  last_name: string;
  email: string;
  role: string;
  title: string;
  credentials: string;
  bio: string;
  specialties: string;
  calendly_url: string;
}
const EMPTY: StaffForm = {
  first_name: "",
  last_name: "",
  email: "",
  role: "counselor",
  title: "",
  credentials: "",
  bio: "",
  specialties: "",
  calendly_url: "",
};

export default function Staff() {
  const [openId, setOpenId] = useState<string | null>(null);
  const [editing, setEditing] = useState<StaffRow | null | undefined>(undefined); // undefined=closed, null=new
  const [form, setForm] = useState<StaffForm>(EMPTY);
  const [tempPass, setTempPass] = useState<string | null>(null);
  const toast = useToast();
  const qc = useQueryClient();

  const query = useQuery<StaffRow[]>({
    queryKey: ["admin", "staff-list"],
    queryFn: () => get<StaffRow[]>("/api/admin/staff"),
  });

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["admin", "staff-list"] });
    qc.invalidateQueries({ queryKey: ["admin", "counselors"] });
  };

  function openNew() {
    setForm(EMPTY);
    setTempPass(null);
    setEditing(null);
  }
  function openEdit(s: StaffRow) {
    setForm({
      first_name: s.first_name ?? "",
      last_name: s.last_name ?? "",
      email: s.email ?? "",
      role: s.role ?? "counselor",
      title: s.title ?? "",
      credentials: s.credentials ?? "",
      bio: s.bio ?? "",
      specialties: (s.specialties ?? []).join(", "),
      calendly_url: s.calendly_url ?? "",
    });
    setTempPass(null);
    setEditing(s);
  }

  async function save() {
    if (!form.first_name.trim() || !form.last_name.trim() || !form.email.trim()) {
      toast("First name, last name, and email are required", "error");
      return;
    }
    const body = {
      first_name: form.first_name.trim(),
      last_name: form.last_name.trim(),
      email: form.email.trim(),
      role: form.role,
      title: form.title,
      credentials: form.credentials,
      bio: form.bio,
      specialties: form.specialties.split(",").map((x) => x.trim()).filter(Boolean),
      calendly_url: form.calendly_url.trim() || null,
    };
    try {
      if (editing) {
        await put(`/api/admin/staff/${editing.id}`, body);
        toast("Staff updated", "success");
        setEditing(undefined);
      } else {
        const res = await post<{ temp_password?: string }>("/api/admin/staff", body);
        if (res?.temp_password) {
          setTempPass(res.temp_password);
          toast("Staff account created — save the temp password", "success");
        } else {
          toast("Staff created", "success");
          setEditing(undefined);
        }
      }
      refresh();
    } catch (e) {
      toast(e instanceof Error ? e.message : "Error", "error");
    }
  }

  async function invite(s: StaffRow) {
    if (!window.confirm(`Send portal invite email to ${s.email}?`)) return;
    try {
      await post(`/api/admin/staff/${s.id}/invite`);
      toast(`Invite sent to ${s.email}`, "success");
    } catch (e) {
      toast(e instanceof Error ? e.message : "Failed to send invite", "error");
    }
  }

  async function toggleActive(s: StaffRow) {
    try {
      await put(`/api/admin/staff/${s.id}`, { active: !s.active });
      refresh();
    } catch (e) {
      toast(e instanceof Error ? e.message : "Error", "error");
    }
  }

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Staff &amp; Counselors</h1>
          <p>Team members, their roles, and counselor caseloads.</p>
        </div>
        <button className="btn primary" onClick={openNew}>
          + Add Staff
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
                  <th>Name</th>
                  <th>Role</th>
                  <th>Title</th>
                  <th>Email</th>
                  <th>Clients</th>
                  <th>Status</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {(query.data ?? []).length === 0 ? (
                  <tr>
                    <td colSpan={7}>
                      <div className="empty">No staff members yet.</div>
                    </td>
                  </tr>
                ) : (
                  query.data!.map((s) => (
                    <tr key={s.id} className="row-click" onClick={() => setOpenId(s.id)}>
                      <td className="cell-name">{s.name || `${s.first_name ?? ""} ${s.last_name ?? ""}`.trim() || s.email}</td>
                      <td><Badge tone={s.role === "admin" ? "danger" : "info"}>{humanize(s.role)}</Badge></td>
                      <td>{s.title || "—"}</td>
                      <td className="cell-sub">{s.email}</td>
                      <td className="tabnum">{s.client_count ?? 0}</td>
                      <td><StatusBadge value={s.active ? "active" : "inactive"} /></td>
                      <td onClick={(e) => e.stopPropagation()} style={{ whiteSpace: "nowrap" }}>
                        <button className="btn sm" style={{ marginRight: 6 }} onClick={() => openEdit(s)}>
                          Edit
                        </button>
                        <button className="btn sm" style={{ marginRight: 6 }} onClick={() => invite(s)}>
                          Invite
                        </button>
                        <button className="btn sm" style={{ color: s.active ? "var(--danger)" : "var(--ok)" }} onClick={() => toggleActive(s)}>
                          {s.active ? "Deactivate" : "Activate"}
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

      {openId && <StaffDrawer staffId={openId} onClose={() => setOpenId(null)} />}

      {editing !== undefined && (
        <Modal
          title={editing ? "Edit Staff Member" : "Add Staff Member"}
          wide
          onClose={() => setEditing(undefined)}
          footer={
            <>
              <button className="btn" onClick={() => setEditing(undefined)}>
                {tempPass ? "Done" : "Cancel"}
              </button>
              {!tempPass && (
                <button className="btn primary" onClick={save}>
                  {editing ? "Save Changes" : "Create Staff"}
                </button>
              )}
            </>
          }
        >
          <div className="form-grid-2">
            <div className="field-row">
              <div className="field-label">First Name</div>
              <input value={form.first_name} onChange={(e) => setForm({ ...form, first_name: e.target.value })} style={{ width: "100%" }} />
            </div>
            <div className="field-row">
              <div className="field-label">Last Name</div>
              <input value={form.last_name} onChange={(e) => setForm({ ...form, last_name: e.target.value })} style={{ width: "100%" }} />
            </div>
            <div className="field-row">
              <div className="field-label">Email</div>
              <input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} style={{ width: "100%" }} />
            </div>
            <div className="field-row">
              <div className="field-label">Role</div>
              <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })} style={{ width: "100%" }}>
                <option value="counselor">Counselor</option>
                <option value="admin">Admin</option>
              </select>
            </div>
            <div className="field-row">
              <div className="field-label">Title</div>
              <input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} style={{ width: "100%" }} />
            </div>
            <div className="field-row">
              <div className="field-label">Credentials</div>
              <input value={form.credentials} onChange={(e) => setForm({ ...form, credentials: e.target.value })} style={{ width: "100%" }} />
            </div>
          </div>
          <div className="field-row">
            <div className="field-label">Specialties (comma-separated)</div>
            <input value={form.specialties} onChange={(e) => setForm({ ...form, specialties: e.target.value })} style={{ width: "100%" }} />
          </div>
          <div className="field-row">
            <div className="field-label">Calendly URL</div>
            <input type="url" value={form.calendly_url} onChange={(e) => setForm({ ...form, calendly_url: e.target.value })} style={{ width: "100%" }} />
          </div>
          <div className="field-row">
            <div className="field-label">Bio</div>
            <textarea value={form.bio} onChange={(e) => setForm({ ...form, bio: e.target.value })} rows={3} style={{ width: "100%" }} />
          </div>
          {tempPass && (
            <div className="temp-pass">
              <div className="field-label" style={{ color: "var(--warn)" }}>Temporary Password — save this now</div>
              <code>{tempPass}</code>
              <div className="cell-sub" style={{ marginTop: 6 }}>
                Share it securely with the new staff member, or send them a portal invite. It won't be shown again.
              </div>
            </div>
          )}
        </Modal>
      )}
    </>
  );
}

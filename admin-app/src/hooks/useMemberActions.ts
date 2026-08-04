import { useQueryClient } from "@tanstack/react-query";
import { post, patch, put, del } from "@/lib/api";
import { useToast } from "@/components/toast";

/**
 * Shared member mutations used by the Members table, the detail drawer,
 * and the DD-214 review grid. Each refreshes the relevant caches + toasts.
 */
export function useMemberActions() {
  const qc = useQueryClient();
  const toast = useToast();

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["admin", "members"] });
    qc.invalidateQueries({ queryKey: ["admin", "analytics"] });
    qc.invalidateQueries({ queryKey: ["admin", "stats"] });
  };

  async function run<T>(fn: () => Promise<T>, ok: string): Promise<boolean> {
    try {
      await fn();
      toast(ok, "success");
      refresh();
      return true;
    } catch (e) {
      toast(e instanceof Error ? e.message : "Something went wrong", "error");
      return false;
    }
  }

  return {
    refreshMember: (id: string) => qc.invalidateQueries({ queryKey: ["admin", "member", id] }),

    verify: (id: string) =>
      run(() => post(`/api/admin/members/${id}/verify`, { status: "verified", notes: "Admin quick-verify" }), "Member verified"),

    setDd214: (id: string, status: "verified" | "rejected", cb?: () => void) =>
      run(() => post(`/api/admin/members/${id}/verify`, { status, notes: "" }), status === "verified" ? "DD-214 approved" : "DD-214 rejected").then((ok) => {
        if (ok) cb?.();
        return ok;
      }),

    manualApprove: (id: string, notes: string) =>
      run(() => post(`/api/admin/members/${id}/approve-dd214`, { notes }), "Member manually approved"),

    archive: (id: string, name: string) => {
      if (!window.confirm(`Archive ${name}? This marks them inactive and blocks login, but keeps all their data.`)) return Promise.resolve(false);
      return run(() => patch(`/api/admin/members/${id}/archive`), `${name} archived`);
    },

    remove: (id: string, name: string) => {
      if (!window.confirm(`PERMANENTLY DELETE ${name}? This removes the member and ALL their data. This cannot be undone.`)) return Promise.resolve(false);
      if (!window.confirm(`Final confirmation: delete ${name} forever?`)) return Promise.resolve(false);
      return run(() => del(`/api/admin/members/${id}`), `${name} permanently deleted`);
    },

    setPassword: (id: string, password: string) =>
      run(() => put(`/api/admin/members/${id}/password`, { password }), "Password updated"),

    setStage: (id: string, pipeline_type: string, stage: string, cb?: () => void) =>
      run(() => put(`/api/admin/members/${id}/stage`, { pipeline_type, stage }), "Stage updated").then((ok) => {
        if (ok) cb?.();
        return ok;
      }),

    saveOverview: (id: string, data: Record<string, unknown>) =>
      run(() => patch(`/api/admin/members/${id}`, data), "Member updated"),

    addNote: (id: string, content: string, cb?: () => void) =>
      run(() => post(`/api/admin/members/${id}/notes`, { content }), "Note added").then((ok) => {
        if (ok) cb?.();
        return ok;
      }),
  };
}

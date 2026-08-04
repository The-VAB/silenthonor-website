import { useLocation } from "react-router-dom";
import { post, goToLogin } from "@/lib/api";
import { titleFor } from "@/nav";
import { fullName, initials, type Me, type AdminStats } from "@/lib/types";
import { IconLogout } from "@/components/icons";

export default function Topbar({ me, stats }: { me: Me; stats?: AdminStats }) {
  const { pathname } = useLocation();

  async function logout() {
    try {
      await post("/api/auth/logout");
    } catch {
      /* ignore — cookie may already be gone */
    }
    goToLogin();
  }

  return (
    <header className="topbar">
      <div>
        <div className="tb-crumb">Admin</div>
        <div className="tb-title">{titleFor(pathname)}</div>
      </div>
      <div className="tb-spacer" />
      <div className="tb-mini">
        <div className="m">
          <b className="tabnum">{stats?.total_members ?? "—"}</b>
          <span>Members</span>
        </div>
        <div className="m">
          <b className="tabnum">{stats?.pending_verification ?? stats?.pending_dd214 ?? "—"}</b>
          <span>Pending</span>
        </div>
      </div>
      <div className="tb-user">
        <div className="avatar">{initials(me)}</div>
        <div className="u">
          <b>{fullName(me)}</b>
          <span>Administrator</span>
        </div>
        <button className="btn sm" style={{ marginLeft: 6 }} onClick={logout} title="Sign out">
          <IconLogout style={{ width: 15, height: 15 }} />
        </button>
      </div>
    </header>
  );
}

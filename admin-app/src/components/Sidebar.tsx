import { NavLink } from "react-router-dom";
import { NAV } from "@/nav";
import type { AdminStats } from "@/lib/types";

export default function Sidebar({ counts }: { counts?: AdminStats }) {
  return (
    <aside className="sidebar">
      <div className="sb-brand">
        <img src="../images/silent-honor-logo.png" alt="Silent Honor" />
        <div>
          <div className="bt">Silent Honor</div>
          <div className="bs">Admin Console</div>
        </div>
      </div>
      <nav className="sb-nav">
        {NAV.map((group) => (
          <div className="sb-group" key={group.label}>
            <div className="sb-group-label">{group.label}</div>
            {group.items.map((item) => {
              const Icon = item.icon;
              const n = item.badge ? counts?.[item.badge] : undefined;
              return (
                <NavLink
                  key={item.path}
                  to={item.path}
                  end={item.path === "/"}
                  className={({ isActive }) => "sb-link" + (isActive ? " active" : "")}
                >
                  <Icon />
                  <span>{item.label}</span>
                  {typeof n === "number" && n > 0 && <span className="count">{n}</span>}
                </NavLink>
              );
            })}
          </div>
        ))}
      </nav>
    </aside>
  );
}

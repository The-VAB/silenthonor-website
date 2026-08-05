import { Outlet } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import Sidebar from "./Sidebar";
import Topbar from "./Topbar";
import { get } from "@/lib/api";
import type { AdminStats, Me } from "@/lib/types";

export default function Shell({ me }: { me: Me }) {
  // Sidebar badges + topbar mini-stats. Cheap, refreshed periodically.
  const { data: stats } = useQuery<AdminStats>({
    queryKey: ["admin", "stats"],
    queryFn: () => get<AdminStats>("/api/admin/stats"),
    staleTime: 60 * 1000,
    refetchInterval: 2 * 60 * 1000,
  });

  return (
    <div className="shell">
      <Sidebar counts={stats} />
      <div className="main">
        <Topbar me={me} stats={stats} />
        <main className="content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

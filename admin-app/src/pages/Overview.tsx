import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from "recharts";
import { get } from "@/lib/api";
import type { Analytics } from "@/lib/types";
import { Card, Stat, Spinner, ErrorState, Empty } from "@/components/ui";
import { IconAlert } from "@/components/icons";

const GOLD = "#c9952a";

function Breakdown({ data, empty }: { data: Record<string, number>; empty: string }) {
  const rows = Object.entries(data || {}).sort((a, b) => b[1] - a[1]);
  const max = Math.max(1, ...rows.map(([, v]) => v));
  if (!rows.length) return <Empty>{empty}</Empty>;
  return (
    <div className="bars">
      {rows.map(([label, v]) => (
        <div className="bar-row" key={label}>
          <div className="bl" title={label}>
            {label}
          </div>
          <div className="bar-track">
            <div className="bar-fill" style={{ width: `${(v / max) * 100}%` }} />
          </div>
          <div className="bv tabnum">{v}</div>
        </div>
      ))}
    </div>
  );
}

export default function Overview() {
  const nav = useNavigate();
  const q = useQuery<Analytics>({
    queryKey: ["admin", "analytics"],
    queryFn: () => get<Analytics>("/api/admin/analytics"),
    staleTime: 60 * 1000,
  });

  if (q.isLoading) return <Spinner />;
  if (q.isError) return <ErrorState error={q.error} retry={() => q.refetch()} />;

  const a = q.data!;
  const k = a.kpis ?? ({} as Analytics["kpis"]);
  const growth = (a.monthly_members ?? []).map((m) => ({ month: m.month, count: m.count }));

  const actions = [
    {
      show: (k.pending_dd214 ?? 0) > 0,
      color: "var(--red)",
      title: `${k.pending_dd214} DD-214${k.pending_dd214 === 1 ? "" : "s"} awaiting review`,
      sub: "Verify service records to approve members",
      to: "/dd214",
    },
    {
      show: true,
      color: "var(--gold)",
      title: `${k.new_this_month ?? 0} new member${k.new_this_month === 1 ? "" : "s"} this month`,
      sub: "Review recent signups in the pipeline",
      to: "/pipeline",
    },
  ].filter((x) => x.show);

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Overview</h1>
          <p>Program health at a glance — members, verification, and growth.</p>
        </div>
      </div>

      <div className="stat-grid">
        <Stat label="Total Members" value={k.total_members ?? 0} accent="navy" meta="All registered veterans" />
        <Stat
          label="Verified"
          value={k.verified_members ?? 0}
          meta={
            k.total_members
              ? `${Math.round(((k.verified_members ?? 0) / k.total_members) * 100)}% of members`
              : "—"
          }
        />
        <Stat label="New This Month" value={k.new_this_month ?? 0} meta={<span className="up">↑ recent signups</span>} />
        <Stat label="DD-214 Pending" value={k.pending_dd214 ?? 0} accent="red" meta="Awaiting verification" />
        <Stat label="Active Courses" value={k.active_courses ?? 0} meta="Published curriculum" />
        <Stat label="Counselors" value={k.total_counselors ?? 0} meta="Coaching staff" />
      </div>

      <div className="grid main-side" style={{ marginBottom: 16 }}>
        <Card title="Membership Growth" sub="New members per month">
          <div className="card-pad">
            {growth.length ? (
              <div className="chart-box">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={growth} margin={{ top: 8, right: 8, bottom: 0, left: -18 }}>
                    <defs>
                      <linearGradient id="g" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor={GOLD} stopOpacity={0.35} />
                        <stop offset="100%" stopColor={GOLD} stopOpacity={0.02} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid stroke="var(--line)" vertical={false} />
                    <XAxis
                      dataKey="month"
                      tick={{ fontSize: 11, fill: "var(--ink-3)" }}
                      tickLine={false}
                      axisLine={{ stroke: "var(--line)" }}
                    />
                    <YAxis
                      allowDecimals={false}
                      tick={{ fontSize: 11, fill: "var(--ink-3)" }}
                      tickLine={false}
                      axisLine={false}
                      width={40}
                    />
                    <Tooltip
                      contentStyle={{
                        borderRadius: 10,
                        border: "1px solid var(--line)",
                        fontFamily: "var(--body)",
                        fontSize: 13,
                        boxShadow: "var(--shadow)",
                      }}
                    />
                    <Area
                      type="monotone"
                      dataKey="count"
                      name="New members"
                      stroke={GOLD}
                      strokeWidth={2.4}
                      fill="url(#g)"
                      dot={{ r: 3, fill: GOLD }}
                      activeDot={{ r: 5 }}
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <Empty>No growth data yet.</Empty>
            )}
          </div>
        </Card>

        <Card title="Action Required" sub="What needs you">
          <div className="card-pad">
            {actions.length ? (
              actions.map((x, i) => (
                <div
                  className="action-item"
                  key={i}
                  role="button"
                  tabIndex={0}
                  style={{ cursor: "pointer" }}
                  onClick={() => nav(x.to)}
                  onKeyDown={(e) => e.key === "Enter" && nav(x.to)}
                >
                  <div className="ico" style={{ background: x.color }}>
                    <IconAlert style={{ width: 18, height: 18 }} />
                  </div>
                  <div className="txt">
                    <b>{x.title}</b>
                    <span>{x.sub}</span>
                  </div>
                </div>
              ))
            ) : (
              <Empty>All clear — nothing needs review.</Empty>
            )}
          </div>
        </Card>
      </div>

      <div className="grid cols-3">
        <Card title="Pipeline Stage">
          <div className="card-pad">
            <Breakdown data={a.pipeline} empty="No members in pipeline." />
          </div>
        </Card>
        <Card title="By Branch">
          <div className="card-pad">
            <Breakdown data={a.branches} empty="No branch data." />
          </div>
        </Card>
        <Card title="DD-214 Status">
          <div className="card-pad">
            <Breakdown data={a.dd214} empty="No DD-214 records." />
          </div>
        </Card>
      </div>
    </>
  );
}

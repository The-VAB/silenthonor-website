import { useQuery } from "@tanstack/react-query";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
} from "recharts";
import { get } from "@/lib/api";
import { humanize } from "@/lib/format";
import type { Analytics } from "@/lib/types";
import { Card, Stat, Spinner, ErrorState, Empty } from "@/components/ui";

const GOLD = "#c9952a";
const NAVY = "#0c1322";
const BLUE = "#2563eb";
const GREEN = "#16a34a";
const PIE = ["#167c4a", "#c9952a", "#b91c1c", "#2563eb", "#8a94a6"];

const AXIS = { fontSize: 11, fill: "var(--ink-3)" } as const;
const TIP = { borderRadius: 10, border: "1px solid var(--line)", fontFamily: "var(--body)", fontSize: 13, boxShadow: "var(--shadow)" } as const;

function toData(map?: Record<string, number>) {
  return Object.entries(map ?? {}).map(([k, v]) => ({ name: humanize(k), value: v }));
}

function ChartCard({ title, children, empty }: { title: string; children: React.ReactNode; empty?: boolean }) {
  return (
    <Card title={title}>
      <div className="card-pad">
        <div className="chart-box">{empty ? <Empty>No data yet.</Empty> : <ResponsiveContainer width="100%" height="100%">{children as React.ReactElement}</ResponsiveContainer>}</div>
      </div>
    </Card>
  );
}

export default function Reports() {
  const q = useQuery<Analytics>({
    queryKey: ["admin", "analytics"],
    queryFn: () => get<Analytics>("/api/admin/analytics"),
    staleTime: 60 * 1000,
  });

  if (q.isLoading) return <Spinner />;
  if (q.isError) return <ErrorState error={q.error} retry={() => q.refetch()} />;

  const a = q.data!;
  const k = a.kpis;
  const growth = a.monthly_members ?? [];
  const branch = toData(a.branches);
  const cr = toData(a.cr_pipeline);
  const fc = toData(a.fc_pipeline);
  const dd = toData(a.dd214);

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Reports</h1>
          <p>Program impact and pipeline analytics.</p>
        </div>
      </div>

      <div className="stat-grid">
        <Stat label="Members Served" value={k.total_members ?? 0} accent="navy" />
        <Stat label="Verified" value={k.verified_members ?? 0} />
        <Stat label="New This Month" value={k.new_this_month ?? 0} />
        <Stat label="Pending DD-214" value={k.pending_dd214 ?? 0} accent="red" />
        <Stat label="Active Courses" value={k.active_courses ?? 0} />
        <Stat label="Counselors" value={k.total_counselors ?? 0} />
      </div>

      <div className="grid cols-2" style={{ marginBottom: 16 }}>
        <ChartCard title="Member Growth" empty={!growth.length}>
          <LineChart data={growth} margin={{ top: 8, right: 10, bottom: 0, left: -18 }}>
            <CartesianGrid stroke="var(--line)" vertical={false} />
            <XAxis dataKey="month" tick={AXIS} tickLine={false} axisLine={{ stroke: "var(--line)" }} />
            <YAxis allowDecimals={false} tick={AXIS} tickLine={false} axisLine={false} width={40} />
            <Tooltip contentStyle={TIP} />
            <Line type="monotone" dataKey="count" name="New members" stroke={GOLD} strokeWidth={2.4} dot={{ r: 3, fill: GOLD }} />
          </LineChart>
        </ChartCard>
        <ChartCard title="Branch of Service" empty={!branch.length}>
          <BarChart data={branch} margin={{ top: 8, right: 10, bottom: 0, left: -18 }}>
            <CartesianGrid stroke="var(--line)" vertical={false} />
            <XAxis dataKey="name" tick={AXIS} tickLine={false} axisLine={{ stroke: "var(--line)" }} interval={0} angle={-20} textAnchor="end" height={50} />
            <YAxis allowDecimals={false} tick={AXIS} tickLine={false} axisLine={false} width={40} />
            <Tooltip contentStyle={TIP} />
            <Bar dataKey="value" name="Members" fill={NAVY} radius={[4, 4, 0, 0]} />
          </BarChart>
        </ChartCard>
      </div>

      <div className="grid cols-2" style={{ marginBottom: 16 }}>
        <ChartCard title="Credit Repair Pipeline" empty={!cr.length}>
          <BarChart data={cr} margin={{ top: 8, right: 10, bottom: 0, left: -18 }}>
            <CartesianGrid stroke="var(--line)" vertical={false} />
            <XAxis dataKey="name" tick={AXIS} tickLine={false} axisLine={{ stroke: "var(--line)" }} interval={0} angle={-20} textAnchor="end" height={54} />
            <YAxis allowDecimals={false} tick={AXIS} tickLine={false} axisLine={false} width={40} />
            <Tooltip contentStyle={TIP} />
            <Bar dataKey="value" name="Members" fill={BLUE} radius={[4, 4, 0, 0]} />
          </BarChart>
        </ChartCard>
        <ChartCard title="Financial Counseling Pipeline" empty={!fc.length}>
          <BarChart data={fc} margin={{ top: 8, right: 10, bottom: 0, left: -18 }}>
            <CartesianGrid stroke="var(--line)" vertical={false} />
            <XAxis dataKey="name" tick={AXIS} tickLine={false} axisLine={{ stroke: "var(--line)" }} interval={0} angle={-20} textAnchor="end" height={54} />
            <YAxis allowDecimals={false} tick={AXIS} tickLine={false} axisLine={false} width={40} />
            <Tooltip contentStyle={TIP} />
            <Bar dataKey="value" name="Members" fill={GREEN} radius={[4, 4, 0, 0]} />
          </BarChart>
        </ChartCard>
      </div>

      <ChartCard title="DD-214 Status Breakdown" empty={!dd.length}>
        <PieChart>
          <Pie data={dd} dataKey="value" nameKey="name" cx="40%" cy="50%" innerRadius={55} outerRadius={90} paddingAngle={2}>
            {dd.map((_, i) => (
              <Cell key={i} fill={PIE[i % PIE.length]} />
            ))}
          </Pie>
          <Tooltip contentStyle={TIP} />
          <Legend layout="vertical" align="right" verticalAlign="middle" />
        </PieChart>
      </ChartCard>
    </>
  );
}

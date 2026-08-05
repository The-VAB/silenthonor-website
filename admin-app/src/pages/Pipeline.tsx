import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { get } from "@/lib/api";
import type { PipelineData } from "@/lib/types";
import { Spinner, ErrorState, Badge } from "@/components/ui";
import { useMemberActions } from "@/hooks/useMemberActions";
import MemberDrawer from "./MemberDrawer";

interface PipeConfig {
  key: string;
  label: string;
  dataKey: string;
  stages: string[];
  labels: Record<string, string>;
}
const CONFIGS: PipeConfig[] = [
  {
    key: "onboarding",
    label: "Onboarding",
    dataKey: "onboarding",
    stages: ["applied", "dd214_pending", "dd214_review", "approved", "active", "inactive", "graduated"],
    labels: { applied: "Applied", dd214_pending: "DD-214 Pending", dd214_review: "DD-214 Review", approved: "Approved", active: "Active", inactive: "Inactive", graduated: "Graduated" },
  },
  {
    key: "credit_repair",
    label: "Credit Repair",
    dataKey: "credit_repair",
    stages: ["cr_waitlist", "cr_consultation", "cr_documents", "cr_dispute_1", "cr_dispute_2", "cr_dispute_3", "cr_monitoring", "cr_complete"],
    labels: { cr_waitlist: "Waitlist", cr_consultation: "Consultation", cr_documents: "Documents", cr_dispute_1: "Dispute Rd 1", cr_dispute_2: "Dispute Rd 2", cr_dispute_3: "Dispute Rd 3", cr_monitoring: "Monitoring", cr_complete: "Complete" },
  },
  {
    key: "financial_counseling",
    label: "Financial Counseling",
    dataKey: "financial_counseling",
    stages: ["fc_waitlist", "fc_consultation", "fc_documents", "fc_gameplan", "fc_working", "fc_complete"],
    labels: { fc_waitlist: "Waitlist", fc_consultation: "Consultation", fc_documents: "Documents", fc_gameplan: "Game Plan", fc_working: "Working Plan", fc_complete: "Complete" },
  },
];

function daysAgo(v?: string) {
  if (!v) return "";
  const d = Math.floor((Date.now() - new Date(v).getTime()) / 86400000);
  if (isNaN(d)) return "";
  return d <= 0 ? "today" : d === 1 ? "1 day" : `${d} days`;
}

export default function Pipeline() {
  const [cfgKey, setCfgKey] = useState("onboarding");
  const [openId, setOpenId] = useState<string | null>(null);
  const [dragId, setDragId] = useState<string | null>(null);
  const [overStage, setOverStage] = useState<string | null>(null);
  const A = useMemberActions();
  const qc = useQueryClient();

  const cfg = CONFIGS.find((c) => c.key === cfgKey)!;
  const query = useQuery<PipelineData>({
    queryKey: ["admin", "pipeline"],
    queryFn: () => get<PipelineData>("/api/admin/pipeline"),
  });

  async function drop(stage: string) {
    setOverStage(null);
    const id = dragId;
    setDragId(null);
    if (!id) return;
    await A.setStage(id, cfg.dataKey, stage);
    qc.invalidateQueries({ queryKey: ["admin", "pipeline"] });
  }

  const stageData = query.data?.[cfg.dataKey] ?? {};

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Pipeline</h1>
          <p>Drag members between stages to update their progress.</p>
        </div>
      </div>

      <div className="seg-tabs">
        {CONFIGS.map((c) => (
          <button key={c.key} className={"seg-tab" + (c.key === cfgKey ? " active" : "")} onClick={() => setCfgKey(c.key)}>
            {c.label}
          </button>
        ))}
      </div>

      {query.isLoading ? (
        <Spinner />
      ) : query.isError ? (
        <ErrorState error={query.error} retry={() => query.refetch()} />
      ) : (
        <div className="kanban">
          {cfg.stages.map((stage) => {
            const members = stageData[stage] ?? [];
            return (
              <div
                key={stage}
                className={"kanban-col" + (overStage === stage ? " over" : "")}
                onDragOver={(e) => { e.preventDefault(); setOverStage(stage); }}
                onDragLeave={() => setOverStage((s) => (s === stage ? null : s))}
                onDrop={() => drop(stage)}
              >
                <div className="kanban-head">
                  <span className="kanban-title">{cfg.labels[stage] ?? stage}</span>
                  <span className="kanban-count">{members.length}</span>
                </div>
                <div className="kanban-cards">
                  {members.map((m) => (
                    <div
                      key={m.id}
                      className="kanban-card"
                      draggable
                      onDragStart={() => setDragId(m.id)}
                      onDragEnd={() => { setDragId(null); setOverStage(null); }}
                      onClick={() => setOpenId(m.id)}
                    >
                      <div className="kanban-card-name">{m.name || m.email}</div>
                      <div className="kanban-card-meta">
                        {m.branch && <Badge tone="muted">{m.branch}</Badge>}
                        <span className="cell-sub">{daysAgo(m.created_at)}</span>
                      </div>
                    </div>
                  ))}
                  {members.length === 0 && <div className="kanban-empty">Drop here</div>}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {openId && <MemberDrawer memberId={openId} onClose={() => setOpenId(null)} />}
    </>
  );
}

import { useMemo, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { get, post, put } from "@/lib/api";
import type { AssistantStatus, AssistantAction, MemberRow, MemberFull, Analytics, AdminStats } from "@/lib/types";
import { Card, Badge, Spinner, ErrorState } from "@/components/ui";
import { IconAssistant } from "@/components/icons";
import { useToast } from "@/components/toast";

interface Turn {
  role: "user" | "assistant";
  content: string; // display text (action block stripped)
  action?: AssistantAction | null;
  done?: boolean;
}

// Pull a single ```sh-action {json}``` block out of a reply, if present.
function parseAction(reply: string): { text: string; action: AssistantAction | null } {
  const m = reply.match(/```sh-action\s*([\s\S]*?)```/);
  if (!m) return { text: reply.trim(), action: null };
  let action: AssistantAction | null = null;
  try {
    action = JSON.parse(m[1].trim());
  } catch {
    action = null;
  }
  const text = reply.replace(m[0], "").trim();
  return { text, action };
}

function actionPreview(a: AssistantAction): string {
  if (a.type === "send_message") return a.body ?? "";
  if (a.type === "create_announcement") return `${a.title ?? ""}\n\n${a.content ?? ""}`.trim();
  if (a.type === "set_stage") return `${a.pipeline_type ?? ""} → ${a.stage ?? ""}`;
  return JSON.stringify(a, null, 1);
}

export default function Assistant() {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [memberId, setMemberId] = useState<string | null>(null);
  const [memberSearch, setMemberSearch] = useState("");
  const [pickerOpen, setPickerOpen] = useState(false);
  const bodyRef = useRef<HTMLDivElement>(null);
  const toast = useToast();
  const qc = useQueryClient();

  const statusQ = useQuery<AssistantStatus>({
    queryKey: ["admin", "assistant-status"],
    queryFn: () => get<AssistantStatus>("/api/admin/assistant/status"),
    retry: false,
  });

  // Context sources (attached to each message so the assistant can answer from data).
  const analyticsQ = useQuery<Analytics>({ queryKey: ["admin", "analytics"], queryFn: () => get("/api/admin/analytics"), staleTime: 60_000, enabled: !!statusQ.data?.enabled });
  const statsQ = useQuery<AdminStats>({ queryKey: ["admin", "stats"], queryFn: () => get("/api/admin/stats"), staleTime: 60_000, enabled: !!statusQ.data?.enabled });
  const membersQ = useQuery<MemberRow[]>({ queryKey: ["admin", "members"], queryFn: () => get("/api/admin/members"), enabled: pickerOpen });
  const memberFullQ = useQuery<MemberFull>({ queryKey: ["admin", "member", memberId], queryFn: () => get(`/api/admin/members/${memberId}/full`), enabled: !!memberId });

  const selectedMember = memberFullQ.data;
  const memberName = selectedMember ? `${selectedMember.first_name ?? ""} ${selectedMember.last_name ?? ""}`.trim() || selectedMember.email : "";

  const filteredMembers = useMemo(() => {
    const all = membersQ.data ?? [];
    const s = memberSearch.toLowerCase();
    return (s ? all.filter((m) => `${m.first_name ?? ""} ${m.last_name ?? ""} ${m.email}`.toLowerCase().includes(s)) : all).slice(0, 8);
  }, [membersQ.data, memberSearch]);

  function buildContext() {
    const ctx: Record<string, unknown> = {};
    if (analyticsQ.data) ctx.analytics = analyticsQ.data;
    if (statsQ.data) ctx.stats = statsQ.data;
    if (selectedMember) ctx.member = selectedMember;
    return Object.keys(ctx).length ? ctx : null;
  }

  async function send(text: string) {
    const msg = text.trim();
    if (!msg || sending) return;
    const history = turns.map((t) => ({ role: t.role, content: t.content }));
    setTurns((t) => [...t, { role: "user", content: msg }]);
    setInput("");
    setSending(true);
    try {
      const res = await post<{ reply: string }>("/api/admin/assistant", { message: msg, history, context: buildContext() });
      const { text: reply, action } = parseAction(res.reply ?? "");
      setTurns((t) => [...t, { role: "assistant", content: reply || "(no response)", action }]);
    } catch (e) {
      setTurns((t) => [...t, { role: "assistant", content: `⚠️ ${e instanceof Error ? e.message : "Something went wrong."}` }]);
    } finally {
      setSending(false);
      requestAnimationFrame(() => bodyRef.current?.scrollTo(0, bodyRef.current.scrollHeight));
    }
  }

  async function runAction(idx: number, a: AssistantAction) {
    try {
      if (a.type === "send_message") {
        if (!a.member_id || !a.body) throw new Error("Missing member or message body.");
        await post("/api/messages", { to_user_id: a.member_id, content: a.body });
      } else if (a.type === "set_stage") {
        if (!a.member_id || !a.stage) throw new Error("Missing member or stage.");
        await put(`/api/admin/members/${a.member_id}/stage`, { pipeline_type: a.pipeline_type ?? "onboarding", stage: a.stage });
        qc.invalidateQueries({ queryKey: ["admin", "members"] });
      } else if (a.type === "create_announcement") {
        await post("/api/admin/announcements", { title: a.title, content: a.content, type: a.kind ?? "info" });
        qc.invalidateQueries({ queryKey: ["admin", "announcements"] });
      } else {
        throw new Error(`Unknown action type: ${a.type}`);
      }
      toast("Done", "success");
      setTurns((t) => t.map((turn, i) => (i === idx ? { ...turn, done: true } : turn)));
    } catch (e) {
      toast(e instanceof Error ? e.message : "Action failed", "error");
    }
  }

  if (statusQ.isLoading) return <Spinner />;
  if (statusQ.isError) return <ErrorState error={statusQ.error} retry={() => statusQ.refetch()} />;

  // Dormant: backend flag off (or no API key configured yet).
  if (!statusQ.data?.enabled) {
    return (
      <>
        <div className="page-head">
          <div>
            <h1>Assistant</h1>
            <p>An AI copilot for running the platform.</p>
          </div>
        </div>
        <Card>
          <div className="asst-dormant">
            <div className="box">
              <Badge tone="warn">Coming soon</Badge>
              <h2 style={{ fontSize: 22, textTransform: "uppercase", margin: "12px 0 8px" }}>Assistant is not turned on yet</h2>
              <p style={{ color: "var(--ink-2)", lineHeight: 1.6 }}>
                Once enabled, the assistant will help you <b>draft</b> member messages, announcements, and knowledge
                articles; <b>answer</b> operational questions from live data ("who's awaiting DD-214 review?", "summarize
                this member"); and <b>propose actions</b> you approve with one click. It stays dark until an Anthropic API
                key is set and the feature flag is switched on.
              </p>
            </div>
          </div>
        </Card>
      </>
    );
  }

  const chips = [
    { label: "Draft a welcome message", prompt: memberId ? `Draft a warm welcome message to ${memberName}.` : "Draft a warm welcome message for a newly approved member." },
    ...(memberId ? [{ label: "Summarize this member", prompt: `Summarize ${memberName}'s case and suggest the next best action.` }] : []),
    { label: "How's the pipeline?", prompt: "Give me a quick read on the pipeline — where are members concentrated and who needs attention?" },
    { label: "Draft an announcement", prompt: "Draft a short announcement letting members know about a new course." },
  ];

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Assistant</h1>
          <p>Draft, ask, and propose — grounded in your live data. You approve every action.</p>
        </div>
      </div>

      <div className="asst">
        <div className="asst-ctx">
          <span className="lbl">Context</span>
          <span className="ctx-chip">Program analytics</span>
          {memberId ? (
            <span className="ctx-chip">
              {memberName || "Member"} <button onClick={() => setMemberId(null)} aria-label="Remove">×</button>
            </span>
          ) : (
            <button className="btn sm" onClick={() => setPickerOpen((v) => !v)}>+ Attach member</button>
          )}
          {pickerOpen && !memberId && (
            <div style={{ flexBasis: "100%", marginTop: 8 }}>
              <input placeholder="Search members to attach…" value={memberSearch} onChange={(e) => setMemberSearch(e.target.value)} style={{ width: "100%" }} autoFocus />
              <div style={{ marginTop: 6, display: "flex", flexDirection: "column", gap: 4 }}>
                {filteredMembers.map((m) => (
                  <button key={m.id} className="asst-chip" style={{ textAlign: "left" }} onClick={() => { setMemberId(m.id); setPickerOpen(false); setMemberSearch(""); }}>
                    {`${m.first_name ?? ""} ${m.last_name ?? ""}`.trim() || m.email} · <span className="cell-sub">{m.email}</span>
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="asst-body" ref={bodyRef}>
          {turns.length === 0 ? (
            <div className="asst-empty">
              <IconAssistant style={{ width: 30, height: 30, opacity: 0.5 }} />
              <h3>How can I help?</h3>
              <p>Ask me to draft something, answer a question about your members, or propose an action to run.</p>
              <div className="asst-chips">
                {chips.map((c) => (
                  <button key={c.label} className="asst-chip" onClick={() => send(c.prompt)}>{c.label}</button>
                ))}
              </div>
            </div>
          ) : (
            turns.map((t, i) => (
              <div key={i} style={{ display: "contents" }}>
                <div className={"bubble " + (t.role === "user" ? "mine" : "assistant theirs")}>{t.content}</div>
                {t.action && (
                  <div className={"action-card" + (t.done ? " done" : "")}>
                    <div className="ac-kind">{t.done ? "✓ Done" : "Proposed action"}</div>
                    <div className="ac-label">{t.action.label || t.action.type}</div>
                    {actionPreview(t.action) && <div className="ac-preview">{actionPreview(t.action)}</div>}
                    {!t.done && (
                      <div className="ac-acts">
                        <button className="btn primary sm" onClick={() => runAction(i, t.action!)}>Confirm &amp; run</button>
                        <button className="btn sm" onClick={() => setTurns((x) => x.map((tt, j) => (j === i ? { ...tt, action: null } : tt)))}>Dismiss</button>
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))
          )}
          {sending && <div className="asst-typing">Assistant is thinking…</div>}
        </div>

        <div className="asst-compose">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(input); } }}
            placeholder="Ask the assistant, or describe what to draft…"
          />
          <button className="btn primary" onClick={() => send(input)} disabled={!input.trim() || sending}>Send</button>
        </div>
      </div>
    </>
  );
}

import { useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { get, post } from "@/lib/api";
import { fmtTime } from "@/lib/format";
import type { Message, MsgUser } from "@/lib/types";
import { useMe } from "@/auth/useMe";
import { Spinner, ErrorState, Empty } from "@/components/ui";
import { useToast } from "@/components/toast";

interface Convo {
  member: MsgUser;
  last_message: string;
  last_time: string;
  unread: number;
}

export default function Messages() {
  const [activeId, setActiveId] = useState<string | null>(null);
  const [reply, setReply] = useState("");
  const toast = useToast();
  const qc = useQueryClient();
  const meQ = useMe();
  const adminId = meQ.data?.id;

  const query = useQuery<Message[]>({
    queryKey: ["admin", "messages"],
    queryFn: () => get<Message[]>("/api/messages/admin/all"),
    refetchInterval: 30 * 1000,
  });

  const convos = useMemo<Convo[]>(() => {
    const msgs = query.data ?? [];
    const map = new Map<string, Convo>();
    for (const m of msgs) {
      const mine = m.from_user.id === adminId;
      const other = mine ? m.to_user : m.from_user;
      const prev = map.get(other.id);
      if (!prev || new Date(m.created_at ?? 0) > new Date(prev.last_time)) {
        map.set(other.id, {
          member: other,
          last_message: m.content,
          last_time: m.created_at ?? "",
          unread: prev?.unread ?? 0,
        });
      }
      if (!m.read && m.to_user.id === adminId) {
        const c = map.get(other.id);
        if (c) c.unread += 1;
      }
    }
    return [...map.values()].sort((a, b) => new Date(b.last_time).getTime() - new Date(a.last_time).getTime());
  }, [query.data, adminId]);

  const thread = useMemo(() => {
    if (!activeId) return [];
    return (query.data ?? [])
      .filter((m) => (m.from_user.id === adminId && m.to_user.id === activeId) || (m.from_user.id === activeId && m.to_user.id === adminId))
      .sort((a, b) => new Date(a.created_at ?? 0).getTime() - new Date(b.created_at ?? 0).getTime());
  }, [query.data, activeId, adminId]);

  const activeMember = convos.find((c) => c.member.id === activeId)?.member;

  async function send() {
    if (!reply.trim() || !activeId) return;
    try {
      await post("/api/messages", { to_user_id: activeId, content: reply.trim() });
      setReply("");
      qc.invalidateQueries({ queryKey: ["admin", "messages"] });
    } catch (e) {
      toast(e instanceof Error ? e.message : "Failed to send", "error");
    }
  }

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Messages</h1>
          <p>Direct conversations with members.</p>
        </div>
      </div>

      {query.isLoading ? (
        <Spinner />
      ) : query.isError ? (
        <ErrorState error={query.error} retry={() => query.refetch()} />
      ) : (
        <div className="msg-wrap">
          <div className="convo-list">
            {convos.length === 0 ? (
              <Empty>No messages yet.</Empty>
            ) : (
              convos.map((c) => (
                <div key={c.member.id} className={"convo-item" + (activeId === c.member.id ? " active" : "")} onClick={() => setActiveId(c.member.id)}>
                  <div className="convo-avatar">{(c.member.name || c.member.email || "?")[0].toUpperCase()}</div>
                  <div className="convo-info">
                    <div className="convo-name">{c.member.name || c.member.email}</div>
                    <div className="convo-preview">{c.last_message}</div>
                  </div>
                  <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 4 }}>
                    <div className="cell-sub" style={{ fontSize: 11 }}>{fmtTime(c.last_time)}</div>
                    {c.unread > 0 && <div className="convo-unread">{c.unread}</div>}
                  </div>
                </div>
              ))
            )}
          </div>

          {activeId ? (
            <div className="thread">
              <div className="thread-head">{activeMember?.name || activeMember?.email || "Conversation"}</div>
              <div className="thread-body">
                {thread.length === 0 ? (
                  <Empty>No messages yet.</Empty>
                ) : (
                  thread.map((m, i) => {
                    const mine = m.from_user.id === adminId;
                    return (
                      <div key={i} className={"bubble " + (mine ? "mine" : "theirs")}>
                        {!mine && <div className="who">{m.from_user.name || m.from_user.email}</div>}
                        <div>{m.content}</div>
                        <div className="when">{fmtTime(m.created_at)}</div>
                      </div>
                    );
                  })
                )}
              </div>
              <div className="thread-compose">
                <input
                  value={reply}
                  onChange={(e) => setReply(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }}
                  placeholder="Type a reply…"
                  style={{ flex: 1 }}
                />
                <button className="btn primary" onClick={send} disabled={!reply.trim()}>
                  Send
                </button>
              </div>
            </div>
          ) : (
            <div className="thread-empty">Select a conversation</div>
          )}
        </div>
      )}
    </>
  );
}

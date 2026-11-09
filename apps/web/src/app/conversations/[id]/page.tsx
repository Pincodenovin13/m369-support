"use client";

import { useEffect, useState, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import { useAuth } from "@/hooks/use-auth";
import { DashboardShell } from "@/components/dashboard-shell";
import { Loading, ErrorState, Badge } from "@/components/ui";
import { conversationApi, messageApi, ApiError, type ConversationOut, type MessageOut, type PaginatedResponse } from "@/lib/api-client";

export default function ConversationDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const { user, agency, loading: authLoading, error: authError, refresh } = useAuth();
  const [conversation, setConversation] = useState<ConversationOut | null>(null);
  const [messages, setMessages] = useState<MessageOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reply, setReply] = useState("");
  const [sending, setSending] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!user || !params.id) return;
    setLoading(true);
    Promise.all([
      conversationApi.get(params.id),
      messageApi.list(params.id, { limit: 100 }),
    ])
      .then(([conv, msgs]) => {
        setConversation(conv);
        setMessages((msgs as PaginatedResponse<MessageOut>).items);
        setLoading(false);
      })
      .catch((err) => {
        if (err instanceof ApiError && err.status === 404) {
          router.replace("/conversations");
          return;
        }
        setError(err instanceof Error ? err.message : "Failed to load conversation");
        setLoading(false);
      });
  }, [user, params.id, router]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function handleSend(e: React.FormEvent) {
    e.preventDefault();
    if (!reply.trim() || sending || !conversation) return;
    setSending(true);
    try {
      const msg = await messageApi.send({ conversation_id: conversation.id, content: reply.trim(), is_internal: false });
      setMessages((prev) => [...prev, msg]);
      setReply("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to send message");
    } finally {
      setSending(false);
    }
  }

  async function handleStatusChange(newStatus: ConversationOut["status"]) {
    if (!conversation) return;
    try {
      const updated = await conversationApi.update(conversation.id, { status: newStatus });
      setConversation(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update status");
    }
  }

  if (authLoading || loading) return <Loading label="Loading conversation..." />;
  if (authError) return <ErrorState message={authError} onRetry={refresh} />;
  if (error) return <ErrorState message={error} />;
  if (!user || !agency || !conversation) return <Loading />;

  return (
    <DashboardShell user={user} agency={agency}>
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-gray-900">{conversation.subject || "(no subject)"}</h1>
          <p className="text-xs text-gray-500">Conversation {conversation.id}</p>
        </div>
        <div className="flex items-center gap-2">
          <Badge status={conversation.status} />
          <select
            value={conversation.status}
            onChange={(e) => handleStatusChange(e.target.value as ConversationOut["status"])}
            className="text-xs border border-gray-300 rounded-md px-2 py-1"
          >
            <option value="open">Open</option>
            <option value="pending">Pending</option>
            <option value="resolved">Resolved</option>
            <option value="closed">Closed</option>
          </select>
        </div>
      </div>

      <div className="bg-white rounded-lg border border-gray-200 flex flex-col" style={{ height: "60vh" }}>
        <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
          {messages.length === 0 ? (
            <p className="text-sm text-gray-500 text-center py-8">No messages yet. Send the first reply below.</p>
          ) : (
            messages.map((m) => (
              <div
                key={m.id}
                className={`flex ${m.sender_type === "agent" ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`max-w-xs px-3 py-2 rounded-lg text-sm ${
                    m.sender_type === "agent"
                      ? "bg-brand-500 text-white"
                      : m.sender_type === "system"
                        ? "bg-gray-100 text-gray-600 italic"
                        : "bg-gray-200 text-gray-900"
                  }`}
                >
                  <div className="whitespace-pre-wrap break-words">{m.content}</div>
                  <div className={`text-xs mt-1 ${m.sender_type === "agent" ? "text-brand-100" : "text-gray-500"}`}>
                    {new Date(m.created_at).toLocaleTimeString()} · {m.sender_type}{m.is_internal ? " · Internal note" : ""}
                  </div>
                </div>
              </div>
            ))
          )}
          <div ref={messagesEndRef} />
        </div>
        <form onSubmit={handleSend} className="border-t border-gray-200 px-4 py-3 flex gap-2">
          <input
            type="text"
            value={reply}
            onChange={(e) => setReply(e.target.value)}
            placeholder="Type a reply..."
            disabled={sending}
            className="flex-1 px-3 py-2 text-sm border border-gray-300 rounded-md focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500 disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={sending || !reply.trim()}
            className="px-4 py-2 bg-brand-500 text-white text-sm font-medium rounded-md hover:bg-brand-600 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {sending ? "Sending..." : "Send"}
          </button>
        </form>
      </div>
    </DashboardShell>
  );
}

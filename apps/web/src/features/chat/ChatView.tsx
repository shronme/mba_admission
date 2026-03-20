"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  createChatThread,
  fetchChatMessages,
  getApiBaseUrl,
  type ChatMessageDto,
} from "@/lib/api";

type LocalMessage = ChatMessageDto & { _local?: boolean };

function makeLocalId() {
  // crypto.randomUUID is supported in modern browsers.
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `local_${Math.random().toString(16).slice(2)}`;
}

export function ChatView({ sessionToken }: { sessionToken?: string | null }) {
  const base = getApiBaseUrl();
  const [threadId, setThreadId] = useState<string | null>(null);
  const [messages, setMessages] = useState<LocalMessage[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [input, setInput] = useState("");

  const listRef = useRef<HTMLDivElement | null>(null);

  const authHeader = useMemo(() => {
    return sessionToken ? { Authorization: `Bearer ${sessionToken}` } : undefined;
  }, [sessionToken]);

  const loadMessages = useCallback(
    async (id: string) => {
      const out = await fetchChatMessages(id, sessionToken ?? null);
      setMessages(out as LocalMessage[]);
    },
    [sessionToken],
  );

  const ensureThread = useCallback(async () => {
    if (!base) return;
    if (threadId) return;
    const created = await createChatThread(sessionToken ?? null);
    setThreadId(created.id);
  }, [base, sessionToken, threadId]);

  useEffect(() => {
    void ensureThread().catch((e) => setError(String(e)));
  }, [ensureThread]);

  useEffect(() => {
    if (!threadId) return;
    void loadMessages(threadId).catch((e) => setError(String(e)));
  }, [threadId, loadMessages]);

  useEffect(() => {
    // Keep the transcript pinned to bottom while streaming.
    if (!listRef.current) return;
    listRef.current.scrollTop = listRef.current.scrollHeight;
  }, [messages, busy]);

  const send = useCallback(async () => {
    if (!base || !threadId) return;
    const trimmed = input.trim();
    if (!trimmed || busy) return;

    setError(null);
    setBusy(true);
    setInput("");

    const userMsg: LocalMessage = {
      id: makeLocalId(),
      role: "user",
      content: trimmed,
      _local: true,
    };
    const assistantMsgId = makeLocalId();
    const assistantPlaceholder: LocalMessage = {
      id: assistantMsgId,
      role: "assistant",
      content: "",
      _local: true,
    };

    setMessages((prev) => [...prev, userMsg, assistantPlaceholder]);

    try {
      const res = await fetch(
        `${base}/chat/threads/${encodeURIComponent(threadId)}/messages/stream`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(authHeader || {}),
          },
          body: JSON.stringify({ content: trimmed }),
        },
      );

      if (!res.ok) {
        const text = await res.text();
        throw new Error(`Stream failed: ${res.status} ${text}`);
      }
      if (!res.body) throw new Error("No response body for stream");

      const reader = res.body.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });
        if (!chunk) continue;

        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantMsgId
              ? {
                  ...m,
                  content: m.content + chunk,
                }
              : m,
          ),
        );
      }

      // Refresh from DB so roles/status match canonical state.
      await loadMessages(threadId);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }, [authHeader, base, input, loadMessages, threadId, busy]);

  if (!base) {
    return (
      <div className="flex h-full items-center justify-center rounded-lg border border-neutral-200 bg-white p-6 text-sm text-neutral-500">
        Set <code className="rounded bg-neutral-100 px-1">NEXT_PUBLIC_API_URL</code>.
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-neutral-200 px-4 py-3">
        <div className="text-sm font-semibold text-neutral-900">
          Admissions Chat
        </div>
        <div className="mt-0.5 text-xs text-neutral-500">
          Upload relevant documents, then tell us your goals. The assistant will
          stay within admissions/help topics.
        </div>
      </div>

      <div
        ref={listRef}
        className="flex-1 overflow-auto px-4 py-4"
        aria-live="polite"
      >
        {messages.length === 0 ? (
          <div className="text-sm text-neutral-500">
            Starting intake…
          </div>
        ) : (
          <div className="space-y-4">
            {messages.map((m) => {
              const isUser = m.role === "user";
              return (
                <div
                  key={m.id}
                  className={isUser ? "flex justify-end" : "flex justify-start"}
                >
                  <div
                    className={
                      isUser
                        ? "max-w-[85%] rounded-2xl rounded-br-sm bg-neutral-900 px-4 py-3 text-sm text-white"
                        : "max-w-[85%] rounded-2xl rounded-bl-sm bg-neutral-100 px-4 py-3 text-sm text-neutral-900"
                    }
                  >
                    {m.content || (isUser ? " " : "…")}
                  </div>
                </div>
              );
            })}
          </div>
        )}
        {busy && (
          <div className="mt-3 text-xs text-neutral-500">
            Generating response…
          </div>
        )}
      </div>

      {error && (
        <div className="px-4 pb-3">
          <div className="rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-900">
            {error}
          </div>
        </div>
      )}

      <div className="border-t border-neutral-200 px-4 py-3">
        <div className="flex items-end gap-3">
          <div className="flex-1">
            <label className="sr-only" htmlFor="chatInput">
              Message
            </label>
            <textarea
              id="chatInput"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Type your message…"
              className="min-h-[44px] w-full resize-none rounded-md border border-neutral-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-neutral-500 focus:outline-none focus:ring-1 focus:ring-neutral-500"
              disabled={busy}
            />
          </div>
          <button
            type="button"
            onClick={() => void send()}
            disabled={busy}
            className="rounded-md bg-neutral-900 px-4 py-2 text-sm font-medium text-white shadow hover:bg-neutral-800 disabled:opacity-50"
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
}


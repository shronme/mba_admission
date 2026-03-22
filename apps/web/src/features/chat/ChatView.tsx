"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import {
  createChatThread,
  fetchCandidateProfile,
  fetchChatMessages,
  getApiBaseUrl,
  type ChatMessageDto,
} from "@/lib/api";
import { STAGES } from "@/components/StageProgressBar";

type LocalMessage = ChatMessageDto & { _local?: boolean };

function makeLocalId() {
  // crypto.randomUUID is supported in modern browsers.
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `local_${Math.random().toString(16).slice(2)}`;
}

export function ChatView({
  sessionToken,
  currentStage = 1,
  onProfileUpdate,
  lastUploadedAt,
}: {
  sessionToken?: string | null;
  currentStage?: number;
  onProfileUpdate?: (intakeComplete: boolean) => void;
  lastUploadedAt?: number;
}) {
  const base = getApiBaseUrl();
  const [threadId, setThreadId] = useState<string | null>(null);
  const [messages, setMessages] = useState<LocalMessage[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [intakeComplete, setIntakeComplete] = useState(false);
  const [intakeScore, setIntakeScore] = useState(0);

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

  const refreshIntakeProgress = useCallback(async () => {
    if (!sessionToken) return;
    try {
      const cand = await fetchCandidateProfile(sessionToken);
      const profile = cand.profile;
      const complete = profile?.profile_complete ?? false;
      setIntakeComplete(complete);
      setIntakeScore(profile?.completeness_score ?? 0);
      onProfileUpdate?.(complete);
    } catch {
      // silently ignore — progress bar just won't update
    }
  }, [sessionToken, onProfileUpdate]);

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
    void refreshIntakeProgress();
  }, [threadId, loadMessages, refreshIntakeProgress]);

  // Poll for new messages and intake progress every 5 s.
  useEffect(() => {
    if (!threadId || busy) return;
    const id = setInterval(() => {
      void loadMessages(threadId).catch(() => {});
      void refreshIntakeProgress();
    }, 5000);
    return () => clearInterval(id);
  }, [threadId, busy, loadMessages, refreshIntakeProgress]);

  // After a file upload, poll every 2 s for up to 30 s so the Celery
  // notification appears promptly without waiting for the 5 s interval.
  useEffect(() => {
    if (!threadId || !lastUploadedAt) return;
    const deadline = lastUploadedAt + 30_000;
    const id = setInterval(() => {
      if (Date.now() > deadline) {
        clearInterval(id);
        return;
      }
      void loadMessages(threadId).catch(() => {});
    }, 2000);
    return () => clearInterval(id);
  }, [threadId, lastUploadedAt, loadMessages]);

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
      void refreshIntakeProgress();
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

  const stageName = STAGES[Math.max(0, Math.min(currentStage - 1, STAGES.length - 1))].name;

  return (
    <div className="flex h-full flex-col">
      {/* Chat panel header */}
      <div className="flex items-center justify-between border-b border-neutral-200 px-4 py-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold text-neutral-900">
              Advising Session
            </span>
            <span className="rounded-full bg-indigo-50 px-2 py-0.5 text-[10px] font-semibold text-indigo-600">
              {stageName}
            </span>
          </div>
          <div className="mt-0.5 text-[11px] text-neutral-400">
            Upload documents on the right, then chat here about your goals.
          </div>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-full bg-emerald-400" />
          <span className="text-[11px] text-neutral-400">
            {intakeComplete ? "Profile complete" : "Active"}
          </span>
        </div>
      </div>

      {/* Profile completeness bar */}
      <div className="border-b border-neutral-100 px-4 py-2">
        <div className="mb-1 flex items-center justify-between">
          <span className="text-[11px] text-neutral-400">
            {intakeComplete ? "Profile complete" : `Profile ${intakeScore}% complete`}
          </span>
          {intakeComplete && (
            <span className="text-[11px] font-semibold text-emerald-600">
              ✓ Ready for research
            </span>
          )}
        </div>
        <div className="h-1 w-full overflow-hidden rounded-full bg-neutral-100">
          <div
            className={[
              "h-full rounded-full transition-all duration-700",
              intakeComplete
                ? "bg-emerald-500"
                : intakeScore >= 75
                  ? "bg-indigo-500"
                  : intakeScore >= 40
                    ? "bg-indigo-400"
                    : "bg-neutral-300",
            ].join(" ")}
            style={{ width: `${Math.min(100, Math.max(0, intakeScore))}%` }}
          />
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
                    {isUser ? (
                      m.content || " "
                    ) : m.content ? (
                      <ReactMarkdown
                        remarkPlugins={[remarkGfm]}
                        components={{
                          p: ({ children }) => (
                            <p className="mb-2 last:mb-0">{children}</p>
                          ),
                          strong: ({ children }) => (
                            <strong className="font-semibold">{children}</strong>
                          ),
                          em: ({ children }) => (
                            <em className="italic text-neutral-600">{children}</em>
                          ),
                          ul: ({ children }) => (
                            <ul className="mb-2 ml-4 list-disc space-y-1 last:mb-0">{children}</ul>
                          ),
                          ol: ({ children }) => (
                            <ol className="mb-2 ml-4 list-decimal space-y-1 last:mb-0">{children}</ol>
                          ),
                          li: ({ children }) => (
                            <li className="leading-snug">{children}</li>
                          ),
                          code: ({ children }) => (
                            <code className="rounded bg-neutral-200 px-1 py-0.5 text-xs">{children}</code>
                          ),
                          hr: () => <hr className="my-2 border-neutral-300" />,
                        }}
                      >
                        {m.content}
                      </ReactMarkdown>
                    ) : (
                      "…"
                    )}
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

      <div className="border-t border-neutral-200 px-4 pb-2 pt-3">
        <div className="flex items-end gap-3">
          <div className="flex-1">
            <label className="sr-only" htmlFor="chatInput">
              Message
            </label>
            <textarea
              id="chatInput"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  void send();
                }
              }}
              placeholder="Tell me about yourself, your goals, or ask anything about the admissions process…"
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
        <p className="mt-1.5 text-[10px] text-neutral-400">
          Press <kbd className="rounded bg-neutral-100 px-1 font-mono">Enter</kbd> to send ·{" "}
          <kbd className="rounded bg-neutral-100 px-1 font-mono">Shift+Enter</kbd> for new line
        </p>
      </div>
    </div>
  );
}


"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

import { getApiBaseUrl } from "@/lib/api";
import { ArtifactDownloadCard } from "@/components/ArtifactDownloadCard";

const mdComponents: Components = {
  p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
  strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
  em: ({ children }) => <em className="italic">{children}</em>,
  ul: ({ children }) => <ul className="mb-2 ml-4 list-disc space-y-1">{children}</ul>,
  ol: ({ children }) => <ol className="mb-2 ml-4 list-decimal space-y-1">{children}</ol>,
  li: ({ children }) => <li>{children}</li>,
  h1: ({ children }) => <h1 className="mb-1 text-base font-bold">{children}</h1>,
  h2: ({ children }) => <h2 className="mb-1 text-sm font-bold">{children}</h2>,
  h3: ({ children }) => <h3 className="mb-1 text-sm font-semibold">{children}</h3>,
  code: ({ children }) => <code className="rounded bg-neutral-100 px-1 py-0.5 text-xs font-mono">{children}</code>,
};

type ChatMessageUi = {
  id: string;
  role: "user" | "assistant";
  content: string;
  extra?: Record<string, unknown>;
  created_at?: string | null;
};

function extractArtifactFromText(text: string): {
  artifact_id: string;
  artifact_type: "cv_draft" | "essay_draft";
  title: string;
  school_name: string;
  download_url: string;
} | null {
  const t = text || "";
  const m = t.match(
    /(\/api)?\/artifacts\/([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})\/download/,
  );
  if (!m) return null;
  const id = m[2];
  const lower = t.toLowerCase();
  const idx = lower.indexOf(m[0].toLowerCase());
  const windowStart = Math.max(0, idx - 80);
  const windowEnd = Math.min(lower.length, idx + 80);
  const context = lower.slice(windowStart, windowEnd);

  // Heuristic: if we can’t infer type confidently, don’t render a misleading card.
  const inferredType: "cv_draft" | "essay_draft" | null = (() => {
    if (/\bessay\b/.test(context) || /\bapplication\b/.test(context) || /\bprompt\b/.test(context)) {
      return "essay_draft";
    }
    if (/\bcv\b/.test(context) || /\bresume\b/.test(context) || /\br[ée]sum[ée]\b/.test(context)) {
      return "cv_draft";
    }
    return null;
  })();

  if (!inferredType) return null;
  return {
    artifact_id: id,
    artifact_type: inferredType,
    title: "",
    school_name: "",
    // Normalize to same-origin API proxy path for the browser.
    download_url: `/api/artifacts/${id}/download`,
  };
}

export interface StreamingChatProps {
  /** Bearer token for API auth. */
  sessionToken: string;
  /** ID of the chat thread to load and stream into. */
  threadId: string;
  /** Optional placeholder text for the text input. */
  inputPlaceholder?: string;
  /**
   * Optional value to pre-fill the input field (e.g. from a quick-action chip).
   * The component will populate the input but will NOT auto-submit.
   */
  prefillValue?: string;
  /**
   * Called after the component has consumed prefillValue into its input state,
   * so the parent can clear its own state and avoid re-triggering.
   */
  onPrefillConsumed?: () => void;
  onSendingChange?: (sending: boolean) => void;
  onHistoryLoaded?: (messages: ChatMessageUi[]) => void;
  /** Optional className applied to the root container element. */
  className?: string;
  /** Initials to render inside the user-avatar circle (e.g. "MO"). Falls back to a dot. */
  userInitials?: string;
  /** Label shown below AI messages. Defaults to "The Advisor". */
  assistantLabel?: string;
}

function formatMessageTime(iso: string | null | undefined): string {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return "";
    return d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  } catch {
    return "";
  }
}

function SparkleIcon({ className }: { className?: string }) {
  // Material Symbols "auto_awesome" as inline SVG so we don't need to load the
  // Material Symbols font across the app just for the advisor avatar.
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="currentColor"
      aria-hidden
    >
      <path d="M12 2.5l2.04 5.46L19.5 10l-5.46 2.04L12 17.5l-2.04-5.46L4.5 10l5.46-2.04L12 2.5zm7 11l.94 2.56L22.5 17l-2.56.94L19 20.5l-.94-2.56L15.5 17l2.56-.94L19 13.5zM5 14l.7 1.8L7.5 16.5l-1.8.7L5 19l-.7-1.8L2.5 16.5l1.8-.7L5 14z" />
    </svg>
  );
}

function SendIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor" aria-hidden>
      <path d="M3.4 20.6l17.45-7.48a1.22 1.22 0 000-2.24L3.4 3.4A1.22 1.22 0 001.74 4.9l1.96 5.9a1 1 0 00.81.68l7.55 1.02a.2.2 0 010 .4l-7.55 1.02a1 1 0 00-.81.68l-1.96 5.9a1.22 1.22 0 001.66 1.5z" />
    </svg>
  );
}

function asChatMessages(data: unknown): ChatMessageUi[] {
  if (!data || typeof data !== "object") return [];
  const obj = data as Record<string, unknown>;
  const arr = Array.isArray(obj.messages) ? obj.messages : [];
  const out: ChatMessageUi[] = [];
  for (const raw of arr) {
    if (!raw || typeof raw !== "object") continue;
    const m = raw as Record<string, unknown>;
    const role = String(m.role ?? "");
    if (role !== "user" && role !== "assistant") continue;
    const content = typeof m.content === "string" ? m.content : "";
    out.push({
      id: typeof m.id === "string" && m.id ? m.id : `${role}-${out.length}`,
      role,
      content,
      extra: typeof m.extra === "object" && m.extra !== null && !Array.isArray(m.extra) ? (m.extra as Record<string, unknown>) : undefined,
      created_at: typeof m.created_at === "string" ? m.created_at : null,
    });
  }
  return out;
}

export function StreamingChat({
  sessionToken,
  threadId,
  inputPlaceholder,
  prefillValue,
  onPrefillConsumed,
  onSendingChange,
  onHistoryLoaded,
  className,
  userInitials,
  assistantLabel,
}: StreamingChatProps): JSX.Element {
  const AdvisorLabel = assistantLabel ?? "The Advisor";
  const userBadge = (userInitials ?? "").trim().slice(0, 2).toUpperCase();
  const [messages, setMessages] = useState<ChatMessageUi[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(true);
  const [sending, setSending] = useState(false);
  const [streamingText, setStreamingText] = useState("");
  const [streamingArtifact, setStreamingArtifact] = useState<{
    artifact_id: string;
    artifact_type: "cv_draft" | "essay_draft";
    title: string;
    school_name: string;
    download_url: string;
  } | null>(null);
  const [ndjsonThinking, setNdjsonThinking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [input, setInput] = useState("");

  const abortRef = useRef<AbortController | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  // Stabilize parent-supplied callbacks via refs so they don't invalidate
  // effects/callbacks every render. If we depend on them directly, a parent
  // re-render (e.g. from setHasUserMessages) would re-run loadHistory and,
  // worse, trigger the history effect's cleanup — which aborts the in-flight
  // stream request.
  const onHistoryLoadedRef = useRef(onHistoryLoaded);
  useEffect(() => { onHistoryLoadedRef.current = onHistoryLoaded; }, [onHistoryLoaded]);
  const onSendingChangeRef = useRef(onSendingChange);
  useEffect(() => { onSendingChangeRef.current = onSendingChange; }, [onSendingChange]);
  const onPrefillConsumedRef = useRef(onPrefillConsumed);
  useEffect(() => { onPrefillConsumedRef.current = onPrefillConsumed; }, [onPrefillConsumed]);

  const apiRoot = useMemo(() => {
    const root = getApiBaseUrl();
    if (!root) throw new Error("NEXT_PUBLIC_API_URL is not set");
    return root;
  }, []);

  const loadHistory = useCallback(async () => {
    setError(null);
    setLoadingHistory(true);
    try {
      const res = await fetch(
        `${apiRoot}/chat/threads/${encodeURIComponent(threadId)}/messages`,
        {
          method: "GET",
          cache: "no-store",
          headers: { Authorization: `Bearer ${sessionToken}` },
        },
      );
      const text = await res.text();
      if (!res.ok) {
        throw new Error(`GET /chat/threads/${threadId}/messages failed: ${res.status} ${text}`);
      }
      const data = text ? (JSON.parse(text) as unknown) : {};
      const parsed = asChatMessages(data);
      setMessages(parsed);
      onHistoryLoadedRef.current?.(parsed);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoadingHistory(false);
    }
  }, [apiRoot, sessionToken, threadId]);

  // Load history once per (threadId, sessionToken). On unmount / thread
  // change, abort any in-flight stream so we don't leak a reader.
  useEffect(() => {
    void loadHistory();
    return () => {
      abortRef.current?.abort();
    };
  }, [loadHistory]);

  useEffect(() => {
    if (!prefillValue) return;
    setInput(prefillValue);
    onPrefillConsumedRef.current?.();
    // Only respond to changes; parent should clear prefillValue after callback.
  }, [prefillValue]);

  useEffect(() => {
    if (!scrollRef.current) return;
    scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages, streamingText, loadingHistory]);

  const submit = useCallback(async () => {
    const trimmed = input.trim();
    if (!trimmed || sending) return;

    setSending(true);
    onSendingChangeRef.current?.(true);
    setError(null);
    setStreamingText("");
    setStreamingArtifact(null);
    setNdjsonThinking(false);

    // Optimistic user bubble + in-progress assistant bubble.
    const optimisticUser: ChatMessageUi = {
      id: `user-${Date.now()}`,
      role: "user",
      content: trimmed,
      created_at: null,
    };
    setMessages((prev) => [...prev, optimisticUser]);
    setInput("");

    abortRef.current?.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;

    try {
      const res = await fetch(
        `${apiRoot}/chat/threads/${encodeURIComponent(threadId)}/messages/stream`,
        {
          method: "POST",
          cache: "no-store",
          headers: {
            Authorization: `Bearer ${sessionToken}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ content: trimmed }),
          signal: ctrl.signal,
        },
      );
      if (!res.ok) {
        const text = await res.text();
        throw new Error(`POST /chat/threads/${threadId}/messages/stream failed: ${res.status} ${text}`);
      }
      if (!res.body) throw new Error("Streaming response body missing");

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let acc = "";
      let lastArtifact: {
        artifact_id: string;
        artifact_type: "cv_draft" | "essay_draft";
        title: string;
        school_name: string;
        download_url: string;
      } | null = null;
      const ct = res.headers.get("content-type") ?? "";
      const isNdjson = ct.includes("application/x-ndjson");
      if (isNdjson) setNdjsonThinking(true);

      let buf = "";
      // eslint-disable-next-line no-constant-condition
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        if (!value) continue;
        const chunk = decoder.decode(value, { stream: true });
        if (!chunk) continue;

        if (!isNdjson) {
          acc += chunk;
          setStreamingText(acc);
          continue;
        }

        buf += chunk;
        const lines = buf.split("\n");
        buf = lines.pop() ?? "";
        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed) continue;
          let evt: any;
          try {
            evt = JSON.parse(trimmed);
          } catch {
            continue;
          }
          if (evt?.type === "text_chunk") {
            const v = typeof evt.value === "string" ? evt.value : "";
            if (v) {
              acc += v;
              setNdjsonThinking(false);
              setStreamingText(acc);
            }
          } else if (evt?.type === "artifact") {
            if (typeof evt.artifact_id === "string" && typeof evt.download_url === "string") {
              lastArtifact = {
                artifact_id: evt.artifact_id,
                artifact_type: evt.artifact_type === "essay_draft" ? "essay_draft" : "cv_draft",
                title: typeof evt.title === "string" ? evt.title : "",
                school_name: typeof evt.school_name === "string" ? evt.school_name : "",
                download_url: evt.download_url,
              };
              setStreamingArtifact(lastArtifact);
            }
          } else if (evt?.type === "error") {
            const msg = typeof evt.message === "string" ? evt.message : "Unknown error";
            setError(msg);
            setNdjsonThinking(false);
          }
        }
      }

      // Finalize assistant bubble and refresh persisted history (best-effort).
      const finalAssistant: ChatMessageUi = {
        id: `assistant-${Date.now()}`,
        role: "assistant",
        content: acc.trimEnd(),
        extra: lastArtifact
          ? {
              artifact_id: lastArtifact.artifact_id,
              artifact_type: lastArtifact.artifact_type,
              title: lastArtifact.title,
              school_name: lastArtifact.school_name,
              download_url: lastArtifact.download_url,
            }
          : undefined,
        created_at: null,
      };
      setStreamingText("");
      setStreamingArtifact(null);
      setNdjsonThinking(false);
      setMessages((prev) => [...prev, finalAssistant]);
      void loadHistory();
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      // Keep partial text (if any) and show inline error.
      setError(msg);
    } finally {
      setSending(false);
      onSendingChangeRef.current?.(false);
    }
  }, [apiRoot, input, loadHistory, sending, sessionToken, threadId]);

  const disabled = sending || loadingHistory;

  const assistantBubbleClass =
    "rounded-2xl rounded-tl-none bg-surface-card p-5 text-on-surface leading-relaxed shadow-[0px_1px_2px_rgba(25,28,29,0.04)]";
  const userBubbleClass =
    "rounded-2xl rounded-tr-none bg-brand-900 p-5 leading-relaxed text-white shadow-[0px_4px_12px_rgba(4,22,39,0.12)] whitespace-pre-wrap";
  const timestampClass =
    "text-[10px] font-bold uppercase tracking-widest text-neutral-400";

  return (
    <div
      className={[
        "flex min-h-[560px] max-h-[78vh] flex-col overflow-hidden rounded-2xl bg-surface-low shadow-ambient",
        className ?? "",
      ]
        .filter(Boolean)
        .join(" ")}
    >
      <div
        ref={scrollRef}
        className="chat-scroll flex-1 overflow-y-auto px-5 py-6 lg:px-10 lg:py-8"
        aria-live="polite"
      >
        {loadingHistory ? (
          <div className="text-sm text-neutral-500">Loading conversation…</div>
        ) : messages.length === 0 && !streamingText && !ndjsonThinking ? (
          <div className="text-sm text-neutral-500">No messages yet.</div>
        ) : (
          <div className="space-y-8">
            {messages.map((m) => {
              const time = formatMessageTime(m.created_at);
              if (m.role === "user") {
                return (
                  <div key={m.id} className="ml-auto flex max-w-2xl flex-row-reverse gap-4">
                    <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center overflow-hidden rounded-full bg-brand-200 text-xs font-semibold text-brand-900">
                      {userBadge || "·"}
                    </div>
                    <div className="space-y-2 text-right">
                      <div className={userBubbleClass}>{m.content}</div>
                      <span className={`${timestampClass} mr-2`}>
                        Sent by You{time ? ` · ${time}` : ""}
                      </span>
                    </div>
                  </div>
                );
              }
              const extra = (m.extra && typeof m.extra === "object" ? m.extra : null) as
                | Record<string, unknown>
                | null;
              const hasArtifact =
                !!extra &&
                typeof extra.artifact_id === "string" &&
                typeof extra.artifact_type === "string" &&
                typeof extra.download_url === "string";
              const textArtifact = !hasArtifact ? extractArtifactFromText(m.content) : null;
              return (
                <div key={m.id} className="flex max-w-2xl gap-4">
                  <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full bg-brand-800">
                    <SparkleIcon className="h-5 w-5 text-accent" />
                  </div>
                  <div className="space-y-2">
                    <div className={assistantBubbleClass}>
                      <ReactMarkdown remarkPlugins={[remarkGfm]} components={mdComponents}>
                        {m.content}
                      </ReactMarkdown>
                      {hasArtifact && extra ? (
                        <ArtifactDownloadCard
                          artifactId={String(extra.artifact_id)}
                          artifactType={
                            extra.artifact_type === "essay_draft" ? "essay_draft" : "cv_draft"
                          }
                          title={String(extra.title ?? "")}
                          schoolName={String(extra.school_name ?? "")}
                          downloadUrl={String(extra.download_url)}
                        />
                      ) : textArtifact ? (
                        <ArtifactDownloadCard
                          artifactId={textArtifact.artifact_id}
                          artifactType={textArtifact.artifact_type}
                          title={textArtifact.title}
                          schoolName={textArtifact.school_name}
                          downloadUrl={textArtifact.download_url}
                        />
                      ) : null}
                    </div>
                    <span className={`${timestampClass} ml-2`}>
                      Sent by {AdvisorLabel}
                      {time ? ` · ${time}` : ""}
                    </span>
                  </div>
                </div>
              );
            })}

            {streamingText ? (
              <div className="flex max-w-2xl gap-4">
                <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full bg-brand-800">
                  <SparkleIcon className="h-5 w-5 text-accent" />
                </div>
                <div className="space-y-2">
                  <div className={assistantBubbleClass}>
                    <ReactMarkdown remarkPlugins={[remarkGfm]} components={mdComponents}>
                      {streamingText}
                    </ReactMarkdown>
                    {/*
                      Robust fallback: if the backend didn't emit an artifact event and the
                      model printed a download URL as plain text, still render the card.
                    */}
                    {!streamingArtifact ? (() => {
                      const fallback = extractArtifactFromText(streamingText);
                      if (!fallback) return null;
                      return (
                        <ArtifactDownloadCard
                          artifactId={fallback.artifact_id}
                          artifactType={fallback.artifact_type}
                          title={fallback.title}
                          schoolName={fallback.school_name}
                          downloadUrl={fallback.download_url}
                        />
                      );
                    })() : null}
                    {streamingArtifact ? (
                      <ArtifactDownloadCard
                        artifactId={streamingArtifact.artifact_id}
                        artifactType={streamingArtifact.artifact_type}
                        title={streamingArtifact.title}
                        schoolName={streamingArtifact.school_name}
                        downloadUrl={streamingArtifact.download_url}
                      />
                    ) : null}
                  </div>
                </div>
              </div>
            ) : ndjsonThinking ? (
              <div className="flex max-w-2xl gap-4">
                <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full bg-brand-800">
                  <SparkleIcon className="h-5 w-5 text-accent" />
                </div>
                <div className={assistantBubbleClass}>
                  <span className="inline-flex items-center gap-2 text-sm text-neutral-500">
                    <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-accent" />
                    {AdvisorLabel} is thinking…
                  </span>
                </div>
              </div>
            ) : null}
          </div>
        )}
      </div>

      <div className="border-t border-surface-high bg-surface-card px-5 py-5 lg:px-10 lg:py-6">
        <div className="mx-auto flex w-full max-w-4xl items-end gap-4">
          <div className="relative flex-1">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  void submit();
                }
              }}
              placeholder={inputPlaceholder ?? "Type your message…"}
              rows={1}
              className="min-h-[56px] w-full resize-none rounded-xl bg-surface-highest px-4 py-4 pr-12 text-sm text-on-surface placeholder:text-neutral-500 transition-all focus:outline-none focus:ring-1 focus:ring-accent disabled:opacity-60"
              disabled={disabled}
            />
          </div>
          <button
            type="button"
            onClick={() => void submit()}
            disabled={disabled || input.trim().length === 0}
            aria-label={sending ? "Sending" : "Send message"}
            className="flex h-14 w-14 shrink-0 items-center justify-center rounded-xl bg-brand-900 text-white shadow-lg transition-all hover:opacity-90 active:scale-95 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {sending ? (
              <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-white/40 border-t-white" />
            ) : (
              <SendIcon className="h-5 w-5" />
            )}
          </button>
        </div>

        {error ? (
          <div className="mx-auto mt-4 max-w-4xl rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
            {error}
          </div>
        ) : null}
      </div>
    </div>
  );
}


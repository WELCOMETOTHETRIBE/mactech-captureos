"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

type Phase = "idle" | "streaming" | "complete" | "error";

type StreamEvent =
  | { type: "delta"; text: string }
  | {
      type: "complete";
      draft_id: string;
      version: number;
      model?: string | null;
      input_tokens?: number | null;
      output_tokens?: number | null;
    }
  | { type: "error"; message?: string };

/**
 * Generic SSE consumer used by both draft-streaming entry points
 * (opp-detail "Draft response" + draft-detail "Regenerate"). Extracted
 * here so the same parser/reducer logic doesn't duplicate.
 */
async function* consumeSSE(
  response: Response
): AsyncGenerator<StreamEvent, void, void> {
  if (!response.body) return;
  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let idx: number;
    while ((idx = buffer.indexOf("\n\n")) !== -1) {
      const block = buffer.slice(0, idx).trim();
      buffer = buffer.slice(idx + 2);
      if (!block) continue;
      const dataStr = block
        .split("\n")
        .filter((l) => l.startsWith("data: "))
        .map((l) => l.slice(6))
        .join("\n");
      if (!dataStr) continue;
      try {
        yield JSON.parse(dataStr) as StreamEvent;
      } catch {
        // skip malformed
      }
    }
  }
}

/* ─── Initial draft generation (opp detail page) ───────────────────── */

export function StreamingDraftButton({
  opportunityId,
  hasExistingDrafts,
  recommended
}: {
  opportunityId: string;
  hasExistingDrafts: boolean;
  recommended: boolean;
}) {
  const [phase, setPhase] = useState<Phase>("idle");
  const [content, setContent] = useState<string>("");
  const [errorMessage, setErrorMessage] = useState<string>("");
  const [tokenCount, setTokenCount] = useState<number>(0);
  const abortRef = useRef<AbortController | null>(null);
  const router = useRouter();
  const customRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    return () => abortRef.current?.abort();
  }, []);

  async function generate() {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setPhase("streaming");
    setContent("");
    setErrorMessage("");
    setTokenCount(0);

    const customInstructions = customRef.current?.value.trim() || null;

    try {
      const res = await fetch(
        `/opportunities/${opportunityId}/draft-stream`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            custom_instructions: customInstructions,
            max_tokens: 4000
          }),
          signal: controller.signal
        }
      );
      if (!res.ok) {
        let detail = `request failed (${res.status})`;
        try {
          const j = (await res.json()) as { error?: string };
          if (j.error) detail = j.error;
        } catch {}
        setPhase("error");
        setErrorMessage(detail);
        return;
      }
      let accumulated = "";
      for await (const ev of consumeSSE(res)) {
        if (ev.type === "delta") {
          accumulated += ev.text;
          setContent(accumulated);
          setTokenCount((c) => c + 1);
        } else if (ev.type === "error") {
          setPhase("error");
          setErrorMessage(ev.message ?? "stream error");
          return;
        } else if (ev.type === "complete") {
          setPhase("complete");
          // Wait a half second so the user can see "complete!" then nav.
          setTimeout(() => {
            router.push(`/drafts/${ev.draft_id}`);
          }, 600);
          return;
        }
      }
      if (phase === "streaming") {
        setPhase("error");
        setErrorMessage("stream ended unexpectedly");
      }
    } catch (err) {
      if ((err as Error).name === "AbortError") return;
      setPhase("error");
      setErrorMessage(
        err instanceof Error ? err.message : "unexpected error"
      );
    }
  }

  if (phase === "streaming" || phase === "complete" || phase === "error") {
    return (
      <DraftStreamPanel
        phase={phase}
        content={content}
        errorMessage={errorMessage}
        tokenCount={tokenCount}
        onCancel={() => {
          abortRef.current?.abort();
          setPhase("idle");
          setContent("");
          setErrorMessage("");
        }}
      />
    );
  }

  return (
    <div className="space-y-3">
      {hasExistingDrafts ? null : (
        <textarea
          ref={customRef}
          rows={2}
          placeholder="Custom instructions (optional). e.g. Lead with cybersecurity past performance. Tone: formal."
          className="w-full rounded-md border border-neutral-300 px-3 py-2 text-xs shadow-sm focus:border-brand-500 focus:outline-none"
        />
      )}
      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={generate}
          className={
            recommended
              ? "rounded-md border border-brand-700 bg-brand-700 px-4 py-2 text-sm font-medium text-white hover:bg-brand-800"
              : "rounded-md border border-neutral-300 px-4 py-2 text-sm font-medium hover:border-neutral-500"
          }
        >
          {hasExistingDrafts ? "+ Generate new version" : "Draft response →"}
        </button>
        <span className="text-[11px] text-neutral-400">
          Streams live. Saved on completion. Uses Claude Sonnet 4.6.
        </span>
      </div>
    </div>
  );
}

/* ─── Regenerate (draft detail page) ────────────────────────────────── */

export function StreamingRegeneratePanel({
  draftId,
  initialInstructions,
  nextVersion
}: {
  draftId: string;
  initialInstructions: string | null;
  nextVersion: number;
}) {
  const [phase, setPhase] = useState<Phase>("idle");
  const [content, setContent] = useState<string>("");
  const [errorMessage, setErrorMessage] = useState<string>("");
  const [tokenCount, setTokenCount] = useState<number>(0);
  const abortRef = useRef<AbortController | null>(null);
  const router = useRouter();
  const instructionsRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    return () => abortRef.current?.abort();
  }, []);

  async function regenerate() {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setPhase("streaming");
    setContent("");
    setErrorMessage("");
    setTokenCount(0);

    const customInstructions = instructionsRef.current?.value.trim() || null;

    try {
      const res = await fetch(`/drafts/${draftId}/regenerate-stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          custom_instructions: customInstructions,
          max_tokens: 4000
        }),
        signal: controller.signal
      });
      if (!res.ok) {
        let detail = `request failed (${res.status})`;
        try {
          const j = (await res.json()) as { error?: string };
          if (j.error) detail = j.error;
        } catch {}
        setPhase("error");
        setErrorMessage(detail);
        return;
      }
      let accumulated = "";
      for await (const ev of consumeSSE(res)) {
        if (ev.type === "delta") {
          accumulated += ev.text;
          setContent(accumulated);
          setTokenCount((c) => c + 1);
        } else if (ev.type === "error") {
          setPhase("error");
          setErrorMessage(ev.message ?? "stream error");
          return;
        } else if (ev.type === "complete") {
          setPhase("complete");
          setTimeout(() => {
            router.push(`/drafts/${ev.draft_id}`);
          }, 600);
          return;
        }
      }
      if (phase === "streaming") {
        setPhase("error");
        setErrorMessage("stream ended unexpectedly");
      }
    } catch (err) {
      if ((err as Error).name === "AbortError") return;
      setPhase("error");
      setErrorMessage(
        err instanceof Error ? err.message : "unexpected error"
      );
    }
  }

  if (phase === "streaming" || phase === "complete" || phase === "error") {
    return (
      <DraftStreamPanel
        phase={phase}
        content={content}
        errorMessage={errorMessage}
        tokenCount={tokenCount}
        onCancel={() => {
          abortRef.current?.abort();
          setPhase("idle");
          setContent("");
          setErrorMessage("");
        }}
      />
    );
  }

  return (
    <div className="space-y-2">
      <textarea
        ref={instructionsRef}
        rows={5}
        defaultValue={initialInstructions ?? ""}
        placeholder="e.g. Lead with our cybersecurity past performance. Emphasize CMMC L2 readiness. Tone: more formal."
        className="w-full rounded-md border border-neutral-300 px-2 py-2 text-xs shadow-sm focus:border-brand-500 focus:outline-none"
      />
      <button
        type="button"
        onClick={regenerate}
        className="w-full rounded-md border border-neutral-900 bg-neutral-900 px-3 py-2 text-xs font-medium text-white hover:bg-neutral-800"
      >
        Generate v{nextVersion} →
      </button>
      <p className="text-[10px] text-neutral-400">
        Streams live. Page redirects to the new version on completion.
      </p>
    </div>
  );
}

/* ─── Shared streaming panel ────────────────────────────────────────── */

function DraftStreamPanel({
  phase,
  content,
  errorMessage,
  tokenCount,
  onCancel
}: {
  phase: Phase;
  content: string;
  errorMessage: string;
  tokenCount: number;
  onCancel: () => void;
}) {
  return (
    <div className="rounded-md border border-brand-200 bg-brand-50 p-4">
      <div className="flex items-baseline justify-between gap-3">
        <p className="text-[11px] uppercase tracking-wide text-brand-700">
          {phase === "streaming"
            ? "Drafting…"
            : phase === "complete"
            ? "Draft complete — redirecting"
            : "Draft failed"}
        </p>
        {phase === "streaming" && (
          <button
            type="button"
            onClick={onCancel}
            className="text-[10px] text-neutral-500 hover:text-neutral-800"
          >
            cancel
          </button>
        )}
        {phase === "error" && (
          <button
            type="button"
            onClick={onCancel}
            className="text-[10px] text-neutral-500 hover:text-neutral-800"
          >
            try again
          </button>
        )}
      </div>

      {phase === "error" ? (
        <p className="mt-3 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-900">
          <span className="font-medium">Stream failed.</span>{" "}
          {errorMessage || "Unknown error."}
        </p>
      ) : (
        <>
          <p className="mt-2 text-[11px] text-neutral-500 tabular-nums">
            {tokenCount} chunks received · streaming live
          </p>
          <pre className="mt-3 max-h-96 overflow-y-auto whitespace-pre-wrap rounded-md border border-brand-200 bg-white p-3 font-sans text-xs leading-relaxed text-neutral-800">
            {content || (
              <span className="italic text-neutral-400">
                Composing draft…
              </span>
            )}
            {phase === "streaming" && (
              <span
                aria-hidden
                className="ml-1 inline-block h-3 w-1 animate-pulse bg-brand-700 align-middle"
              />
            )}
          </pre>
          {phase === "complete" && (
            <p className="mt-3 text-[11px] text-neutral-500">
              Saved. Opening editor…
            </p>
          )}
        </>
      )}
    </div>
  );
}

"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

const STARTER_LABELS: Record<string, string> = {
  should_we_pursue: "Should we pursue this?",
  incumbent: "Who's the likely incumbent?",
  win_probability: "What's our win probability?",
  must_haves: "What are the must-haves?",
  teaming: "Should we prime, sub, or team?"
};

const STARTER_ORDER = [
  "should_we_pursue",
  "incumbent",
  "win_probability",
  "must_haves",
  "teaming"
];

type Phase = "idle" | "streaming" | "complete" | "error";

export function AskStreamingPanel({
  opportunityId
}: {
  opportunityId: string;
}) {
  const [phase, setPhase] = useState<Phase>("idle");
  const [questionShown, setQuestionShown] = useState<string>("");
  const [answer, setAnswer] = useState<string>("");
  const [errorMessage, setErrorMessage] = useState<string>("");
  const inputRef = useRef<HTMLInputElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const router = useRouter();

  // Cancel any in-flight stream on unmount.
  useEffect(() => {
    return () => abortRef.current?.abort();
  }, []);

  async function startStream(payload: {
    question: string;
    starter_kind: string | null;
    displayQuestion: string;
  }) {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setPhase("streaming");
    setQuestionShown(payload.displayQuestion);
    setAnswer("");
    setErrorMessage("");

    try {
      const res = await fetch(
        `/opportunities/${opportunityId}/ask-stream`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            question: payload.question,
            starter_kind: payload.starter_kind
          }),
          signal: controller.signal
        }
      );
      if (!res.ok || !res.body) {
        let detail = `request failed (${res.status})`;
        try {
          const j = (await res.json()) as { error?: string };
          if (j.error) detail = j.error;
        } catch {
          // ignore
        }
        setPhase("error");
        setErrorMessage(detail);
        return;
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";
      let accumulated = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        // Parse SSE: split by double-newline delimiter.
        let idx: number;
        while ((idx = buffer.indexOf("\n\n")) !== -1) {
          const eventBlock = buffer.slice(0, idx).trim();
          buffer = buffer.slice(idx + 2);
          if (!eventBlock) continue;
          // Each block may have multiple `data: ` lines per SSE spec; we
          // only emit single-line data on the server, but be tolerant.
          const dataLines = eventBlock
            .split("\n")
            .filter((l) => l.startsWith("data: "))
            .map((l) => l.slice(6));
          if (dataLines.length === 0) continue;
          const dataStr = dataLines.join("\n");
          let parsed: { type: string; text?: string; message?: string };
          try {
            parsed = JSON.parse(dataStr);
          } catch {
            continue;
          }
          if (parsed.type === "delta" && parsed.text) {
            accumulated += parsed.text;
            setAnswer(accumulated);
          } else if (parsed.type === "error") {
            setPhase("error");
            setErrorMessage(parsed.message ?? "stream error");
            return;
          } else if (parsed.type === "complete") {
            setPhase("complete");
            // Refresh the page so the persisted question appears in the
            // history list rendered by the server component.
            router.refresh();
            return;
          }
        }
      }
      // Stream ended without a complete event.
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

  function onStarter(kind: string) {
    startStream({
      question: STARTER_LABELS[kind] ?? kind,
      starter_kind: kind,
      displayQuestion: STARTER_LABELS[kind] ?? kind
    });
  }

  function onFreeformSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const q = inputRef.current?.value.trim();
    if (!q) return;
    startStream({ question: q, starter_kind: null, displayQuestion: q });
    if (inputRef.current) inputRef.current.value = "";
  }

  function reset() {
    abortRef.current?.abort();
    setPhase("idle");
    setQuestionShown("");
    setAnswer("");
    setErrorMessage("");
  }

  const inFlight = phase === "streaming";

  return (
    <div>
      <div className="flex flex-wrap gap-2">
        {STARTER_ORDER.map((kind) => (
          <button
            key={kind}
            type="button"
            disabled={inFlight}
            onClick={() => onStarter(kind)}
            className="rounded-md border border-neutral-300 bg-white px-3 py-1.5 text-xs font-medium text-neutral-700 transition-colors hover:border-brand-500 hover:text-brand-800 disabled:opacity-50"
          >
            {STARTER_LABELS[kind] ?? kind}
          </button>
        ))}
      </div>

      <form
        onSubmit={onFreeformSubmit}
        className="mt-3 flex flex-wrap items-stretch gap-2"
      >
        <input
          ref={inputRef}
          type="text"
          name="question"
          placeholder="Or type your own question…"
          disabled={inFlight}
          maxLength={1000}
          className="min-w-0 flex-1 rounded-md border border-neutral-300 px-3 py-2 text-sm shadow-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500 disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={inFlight}
          className="rounded-md border border-brand-700 bg-brand-700 px-4 py-2 text-sm font-medium text-white hover:bg-brand-800 disabled:opacity-50"
        >
          {inFlight ? "Streaming…" : "Ask →"}
        </button>
      </form>

      <p className="mt-2 text-[11px] text-neutral-500">
        Live streaming. The answer appears as Claude writes it.
      </p>

      {/* Live answer panel */}
      {(inFlight || phase === "complete" || phase === "error") && (
        <div className="mt-5 rounded-md border border-neutral-200 bg-neutral-50 p-4">
          <div className="flex items-baseline justify-between gap-3">
            <p className="text-sm font-medium text-neutral-800">
              <span className="text-brand-700">Q.</span> {questionShown}
            </p>
            <button
              type="button"
              onClick={reset}
              className="text-[10px] text-neutral-400 hover:text-neutral-700"
              title="Clear and ask another"
            >
              clear
            </button>
          </div>
          {phase === "error" ? (
            <p className="mt-2 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-900">
              <span className="font-medium">Stream failed.</span>{" "}
              {errorMessage || "Unknown error."}
            </p>
          ) : (
            <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-neutral-800">
              <span className="text-brand-700">A.</span>{" "}
              {answer || (
                <span className="italic text-neutral-400">
                  Composing answer…
                </span>
              )}
              {inFlight && (
                <span
                  aria-hidden
                  className="ml-1 inline-block h-3 w-1 animate-pulse bg-brand-700 align-middle"
                />
              )}
            </p>
          )}
          {phase === "complete" && (
            <p className="mt-2 text-[11px] text-neutral-500">
              Saved to history below.
            </p>
          )}
        </div>
      )}
    </div>
  );
}

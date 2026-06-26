"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

const COMPONENTS = [
  "Army",
  "Navy",
  "Air Force",
  "DLA",
  "DARPA",
  "SOCOM",
  "Other"
] as const;

type Depth = "scaffold" | "standard" | "complete";
type SourceKind = "text" | "url" | "pdf";

type Attachment = {
  name: string;
  text: string;
  kind: string;
  truncated: boolean;
};

type DecodedFile = {
  name: string;
  kind: string;
  text: string;
  char_count: number;
  truncated: boolean;
};

type Phase =
  | { kind: "form" }
  | { kind: "streaming" }
  | { kind: "done"; submissionId: string | null }
  | { kind: "error"; message: string };

type ProgressEvent =
  | { type: "phase_start"; phase: string; label: string }
  | { type: "delta"; phase: string; text: string }
  | {
      type: "file_written";
      phase: string;
      path: string;
      bytes: number;
    }
  | { type: "phase_complete"; phase: string; duration_ms: number }
  | { type: "error"; message: string }
  | {
      type: "final";
      submission_id: string;
      output_dir: string;
      file_count: number;
      verify_flags: string[];
      model: string | null;
      input_tokens: number | null;
      output_tokens: number | null;
    };

type PhaseRow = {
  key: string;
  label: string;
  status: "running" | "done" | "errored";
  durationMs?: number;
  charCount: number;
  files: { path: string; bytes: number }[];
};

const SCAFFOLD_HELP =
  "Vol 1 cover sheet + DSIP cheat sheet only. ~10 min.";
const STANDARD_HELP =
  "All 7 volumes + supporting docs + audit files. Markdown. ~20–40 min.";
const COMPLETE_HELP =
  "Same as Standard. PDF/Excel/DOCX rendering is deferred — flagged in output.";

export type SBIRRunnerInitial = {
  topicNumber?: string;
  topicTitle?: string | null;
  component?: (typeof COMPONENTS)[number];
  topicPayload?: string;
  topicCloseDate?: string | null;
  sourceKind?: SourceKind;
};

export function SBIRRunner({ initial }: { initial?: SBIRRunnerInitial } = {}) {
  const router = useRouter();
  const [phase, setPhase] = useState<Phase>({ kind: "form" });
  const [progress, setProgress] = useState<PhaseRow[]>([]);
  const [verifyFlags, setVerifyFlags] = useState<string[]>([]);
  const [outputDir, setOutputDir] = useState<string>("");
  const [submissionId, setSubmissionId] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  // Form state — pre-filled when the user lands here via /sbir/submit?topic_id=…
  const [topicNumber, setTopicNumber] = useState(initial?.topicNumber ?? "");
  const [topicTitle, setTopicTitle] = useState(initial?.topicTitle ?? "");
  const [component, setComponent] = useState<(typeof COMPONENTS)[number]>(
    initial?.component ?? "DLA"
  );
  const [sourceKind, setSourceKind] = useState<SourceKind>(
    initial?.sourceKind ?? "text"
  );
  const [topicPayload, setTopicPayload] = useState(initial?.topicPayload ?? "");
  const [topicCloseDate, setTopicCloseDate] = useState(
    initial?.topicCloseDate ?? ""
  );
  const [synergy, setSynergy] = useState("");
  const [sister, setSister] = useState("");
  const [resourceLinks, setResourceLinks] = useState("");
  const [specialInstructions, setSpecialInstructions] = useState("");
  const [depth, setDepth] = useState<Depth>("scaffold");
  const [attachments, setAttachments] = useState<Attachment[]>([]);

  // Per-control upload state.
  const [topicPdfStatus, setTopicPdfStatus] = useState<
    | { kind: "idle" }
    | { kind: "uploading"; name: string }
    | { kind: "ready"; name: string; chars: number; truncated: boolean }
    | { kind: "error"; message: string }
  >({ kind: "idle" });
  const [attachUploading, setAttachUploading] = useState<string | null>(null);
  const [attachError, setAttachError] = useState<string | null>(null);
  const topicPdfInputRef = useRef<HTMLInputElement>(null);
  const attachInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => () => abortRef.current?.abort(), []);

  async function decodeFile(file: File): Promise<DecodedFile> {
    const fd = new FormData();
    fd.append("file", file);
    const res = await fetch("/sbir/decode-file", {
      method: "POST",
      body: fd
    });
    if (!res.ok) {
      let detail = `decode failed (${res.status})`;
      try {
        const j = (await res.json()) as { detail?: string; error?: string };
        if (j.detail) detail = j.detail;
        else if (j.error) detail = j.error;
      } catch {
        // ignore
      }
      throw new Error(detail);
    }
    return (await res.json()) as DecodedFile;
  }

  async function onTopicPdfChosen(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setTopicPdfStatus({ kind: "uploading", name: file.name });
    try {
      const decoded = await decodeFile(file);
      setTopicPayload(decoded.text);
      setTopicPdfStatus({
        kind: "ready",
        name: decoded.name,
        chars: decoded.char_count,
        truncated: decoded.truncated
      });
    } catch (err) {
      setTopicPdfStatus({
        kind: "error",
        message: err instanceof Error ? err.message : "decode failed"
      });
    } finally {
      // Reset the input so the same file can be re-picked after clearing.
      if (topicPdfInputRef.current) topicPdfInputRef.current.value = "";
    }
  }

  function clearTopicPdf() {
    setTopicPdfStatus({ kind: "idle" });
    setTopicPayload("");
  }

  async function onAttachmentsChosen(
    e: React.ChangeEvent<HTMLInputElement>
  ) {
    const files = Array.from(e.target.files ?? []);
    if (!files.length) return;
    setAttachError(null);
    for (const file of files) {
      // Skip duplicates by filename.
      if (attachments.some((a) => a.name === file.name)) continue;
      setAttachUploading(file.name);
      try {
        const decoded = await decodeFile(file);
        setAttachments((prev) => [
          ...prev,
          {
            name: decoded.name,
            text: decoded.text,
            kind: decoded.kind,
            truncated: decoded.truncated
          }
        ]);
      } catch (err) {
        setAttachError(
          `${file.name}: ${err instanceof Error ? err.message : "decode failed"}`
        );
        break;
      }
    }
    setAttachUploading(null);
    if (attachInputRef.current) attachInputRef.current.value = "";
  }

  function removeAttachment(name: string) {
    setAttachments((prev) => prev.filter((a) => a.name !== name));
  }

  function updatePhase(key: string, patch: Partial<PhaseRow>) {
    setProgress((rows) =>
      rows.map((r) => (r.key === key ? { ...r, ...patch } : r))
    );
  }

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (phase.kind === "streaming") return;

    const sisterList = sister
      .split("\n")
      .map((s) => s.trim())
      .filter(Boolean);
    const linksList = resourceLinks
      .split("\n")
      .map((s) => s.trim())
      .filter(Boolean);

    const body = {
      topic_number: topicNumber.trim(),
      topic_title: topicTitle.trim() || null,
      component,
      topic_source_kind: sourceKind,
      topic_payload: topicPayload,
      topic_close_date: topicCloseDate.trim() || null,
      synergy_hypothesis: synergy,
      attachments: attachments.map((a) => ({ name: a.name, text: a.text })),
      resource_links: linksList,
      sister_proposals: sisterList,
      special_instructions: specialInstructions.trim() || null,
      depth
    };

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setProgress([]);
    setVerifyFlags([]);
    setOutputDir("");
    setSubmissionId(null);
    setPhase({ kind: "streaming" });

    let res: Response;
    try {
      res = await fetch("/sbir/generate-stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        signal: controller.signal
      });
    } catch (err) {
      if ((err as Error).name === "AbortError") return;
      setPhase({
        kind: "error",
        message: err instanceof Error ? err.message : "network error"
      });
      return;
    }
    if (!res.ok || !res.body) {
      let detail = `request failed (${res.status})`;
      try {
        const j = (await res.json()) as { error?: string; detail?: string };
        if (j.error) detail = j.error;
        else if (j.detail) detail = j.detail;
      } catch {
        // ignore
      }
      setPhase({ kind: "error", message: detail });
      return;
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";

    while (true) {
      let chunk: ReadableStreamReadResult<Uint8Array>;
      try {
        chunk = await reader.read();
      } catch (err) {
        if ((err as Error).name === "AbortError") return;
        setPhase({
          kind: "error",
          message: err instanceof Error ? err.message : "stream read error"
        });
        return;
      }
      if (chunk.done) break;
      buffer += decoder.decode(chunk.value, { stream: true });

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
        let evt: ProgressEvent;
        try {
          evt = JSON.parse(dataStr) as ProgressEvent;
        } catch {
          continue;
        }
        if (evt.type === "phase_start") {
          setProgress((rows) => [
            ...rows.filter((r) => r.key !== evt.phase),
            {
              key: evt.phase,
              label: evt.label,
              status: "running",
              charCount: 0,
              files: []
            }
          ]);
        } else if (evt.type === "delta") {
          setProgress((rows) =>
            rows.map((r) =>
              r.key === evt.phase
                ? { ...r, charCount: r.charCount + evt.text.length }
                : r
            )
          );
        } else if (evt.type === "file_written") {
          setProgress((rows) =>
            rows.map((r) =>
              r.key === evt.phase
                ? {
                    ...r,
                    files: [...r.files, { path: evt.path, bytes: evt.bytes }]
                  }
                : r
            )
          );
        } else if (evt.type === "phase_complete") {
          updatePhase(evt.phase, {
            status: "done",
            durationMs: evt.duration_ms
          });
        } else if (evt.type === "error") {
          setPhase({ kind: "error", message: evt.message });
          return;
        } else if (evt.type === "final") {
          setOutputDir(evt.output_dir);
          setVerifyFlags(evt.verify_flags);
          setSubmissionId(evt.submission_id);
          setPhase({ kind: "done", submissionId: evt.submission_id });
          router.refresh();
          return;
        }
      }
    }
    setPhase({ kind: "error", message: "stream ended unexpectedly" });
  }

  function reset() {
    abortRef.current?.abort();
    setPhase({ kind: "form" });
    setProgress([]);
    setVerifyFlags([]);
    setOutputDir("");
    setSubmissionId(null);
  }

  const streaming = phase.kind === "streaming";
  const formDisabled = streaming;

  // PDF source tab disables the textarea (text comes from the upload);
  // text/URL keep it editable.
  const payloadEditable = sourceKind !== "pdf";

  return (
    <section className="rounded-md border border-border bg-card">
      <form onSubmit={onSubmit} className="divide-y divide-border">
        {/* ─── Section: Topic ─── */}
        <FormSection
          title="Topic"
          subtitle="Identify the SBIR announcement and paste its text or upload the PDF."
        >
          <div className="grid gap-4 md:grid-cols-2">
            <Field label="Topic number" required>
              <input
                type="text"
                value={topicNumber}
                onChange={(e) => setTopicNumber(e.target.value)}
                placeholder="DLA26BZ02-NV007"
                maxLength={64}
                required
                disabled={formDisabled}
                className={inputCls}
              />
            </Field>
            <Field label="Topic title (optional)">
              <input
                type="text"
                value={topicTitle}
                onChange={(e) => setTopicTitle(e.target.value)}
                maxLength={512}
                disabled={formDisabled}
                className={inputCls}
              />
            </Field>
            <Field label="Component" required>
              <select
                value={component}
                onChange={(e) =>
                  setComponent(e.target.value as (typeof COMPONENTS)[number])
                }
                disabled={formDisabled}
                className={inputCls}
              >
                {COMPONENTS.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Topic close date (ET)">
              <input
                type="text"
                value={topicCloseDate}
                onChange={(e) => setTopicCloseDate(e.target.value)}
                placeholder="2026-07-15 14:00 ET"
                maxLength={64}
                disabled={formDisabled}
                className={inputCls}
              />
            </Field>
          </div>

          <Field
            label="Topic source"
            hint="Paste the topic text, supply the announcement URL, or upload the topic PDF."
            className="mt-4"
          >
            <div className="mb-2 flex flex-wrap items-center gap-2 text-xs">
              {(["text", "url", "pdf"] as const).map((k) => (
                <button
                  key={k}
                  type="button"
                  onClick={() => {
                    setSourceKind(k);
                    if (k !== "pdf") setTopicPdfStatus({ kind: "idle" });
                  }}
                  disabled={formDisabled}
                  className={
                    "rounded-md border px-3 py-1 transition-colors " +
                    (sourceKind === k
                      ? "border-primary bg-primary/10 text-primary"
                      : "border-border bg-background text-foreground hover:border-foreground/30")
                  }
                >
                  {k.toUpperCase()}
                </button>
              ))}
              {sourceKind === "pdf" && (
                <div className="ml-auto flex items-center gap-2">
                  <input
                    ref={topicPdfInputRef}
                    type="file"
                    accept=".pdf,application/pdf"
                    onChange={onTopicPdfChosen}
                    disabled={formDisabled || topicPdfStatus.kind === "uploading"}
                    className="hidden"
                    id="topic-pdf-input"
                  />
                  <label
                    htmlFor="topic-pdf-input"
                    className={
                      "cursor-pointer rounded-md border border-border bg-background px-3 py-1 text-xs hover:border-foreground/30 " +
                      (formDisabled || topicPdfStatus.kind === "uploading"
                        ? "opacity-50"
                        : "")
                    }
                  >
                    {topicPdfStatus.kind === "uploading"
                      ? "Decoding…"
                      : topicPdfStatus.kind === "ready"
                        ? "Replace PDF"
                        : "Choose PDF"}
                  </label>
                  {topicPdfStatus.kind === "ready" && (
                    <button
                      type="button"
                      onClick={clearTopicPdf}
                      className="text-xs text-muted-foreground hover:text-foreground"
                    >
                      clear
                    </button>
                  )}
                </div>
              )}
            </div>

            {sourceKind === "pdf" && topicPdfStatus.kind === "ready" && (
              <p className="mb-2 text-[11px] text-muted-foreground">
                <span className="font-medium text-foreground">
                  {topicPdfStatus.name}
                </span>{" "}
                · {topicPdfStatus.chars.toLocaleString()} chars decoded
                {topicPdfStatus.truncated && " (truncated)"}
              </p>
            )}
            {sourceKind === "pdf" && topicPdfStatus.kind === "error" && (
              <p className="mb-2 text-[11px] text-destructive">
                {topicPdfStatus.message}
              </p>
            )}

            <textarea
              value={topicPayload}
              onChange={(e) => setTopicPayload(e.target.value)}
              minLength={10}
              required
              rows={sourceKind === "pdf" ? 4 : 6}
              disabled={formDisabled || !payloadEditable}
              readOnly={!payloadEditable}
              placeholder={
                sourceKind === "url"
                  ? "https://www.dodsbirsttr.mil/topics-app/#/topic-details/…"
                  : sourceKind === "pdf"
                    ? "Upload a PDF above; decoded text appears here."
                    : "Paste the topic announcement text here…"
              }
              className={textareaCls + (!payloadEditable ? " bg-muted/40" : "")}
            />
          </Field>
        </FormSection>

        {/* ─── Section: Synergy ─── */}
        <FormSection
          title="Synergy"
          subtitle="Tell the engine how this topic fits MacTech. It will validate the hypothesis against the topic and refine or reject if the fit is weak."
        >
          <Field label="Synergy hypothesis" required>
            <textarea
              value={synergy}
              onChange={(e) => setSynergy(e.target.value)}
              minLength={10}
              maxLength={8000}
              required
              rows={5}
              disabled={formDisabled}
              className={textareaCls}
              placeholder="e.g. 'This RMF documentation-grading topic is a direct fit for Codex RMF-AIR — the four-agent pipeline already grades 800-171 SSP language for completeness, corroboration, and consistency…'"
            />
          </Field>
        </FormSection>

        {/* ─── Section: Disclosures & context ─── */}
        <FormSection
          title="Disclosures & context"
          subtitle="Sister-proposal disclosures (BAA §3.5) are required. Attachments and links sharpen the engine's grounding."
        >
          <div className="grid gap-4 md:grid-cols-2">
            <Field
              label="Sister proposals"
              hint="One per line — every other pending federal proposal in this solicitation cycle."
            >
              <textarea
                value={sister}
                onChange={(e) => setSister(e.target.value)}
                rows={3}
                disabled={formDisabled}
                className={textareaCls}
                placeholder="DLA26BZ02-NV005 — Continuous CMMC L2 evidence&#10;DLA26BZ02-NV006 — Pentest validation"
              />
            </Field>
            <Field
              label="Resource links"
              hint="One URL per line — GitHub repos, deployed products, public standards."
            >
              <textarea
                value={resourceLinks}
                onChange={(e) => setResourceLinks(e.target.value)}
                rows={3}
                disabled={formDisabled}
                className={textareaCls}
                placeholder="https://github.com/mactech/trust-codex&#10;https://capture.mactechsolutionsllc.com"
              />
            </Field>
          </div>

          <Field
            label="Attachments"
            hint="PDF or text (txt / md / json / yaml / csv). Decoded and sent inline to the engine. Each capped at 200,000 chars."
            className="mt-4"
          >
            <div className="space-y-2">
              <div className="flex flex-wrap items-center gap-2">
                <input
                  ref={attachInputRef}
                  type="file"
                  multiple
                  accept=".pdf,.txt,.md,.markdown,.json,.yaml,.yml,.csv,.tsv,.log"
                  onChange={onAttachmentsChosen}
                  disabled={formDisabled || attachUploading !== null}
                  className="hidden"
                  id="attach-input"
                />
                <label
                  htmlFor="attach-input"
                  className={
                    "cursor-pointer rounded-md border border-border bg-background px-3 py-1.5 text-xs hover:border-foreground/30 " +
                    (formDisabled || attachUploading
                      ? "opacity-50"
                      : "")
                  }
                >
                  {attachUploading ? `Decoding ${attachUploading}…` : "Add files"}
                </label>
                {attachments.length > 0 && (
                  <span className="text-[11px] text-muted-foreground">
                    {attachments.length} attached
                  </span>
                )}
              </div>
              {attachError && (
                <p className="text-[11px] text-destructive">{attachError}</p>
              )}
              {attachments.length > 0 && (
                <ul className="space-y-1">
                  {attachments.map((a) => (
                    <li
                      key={a.name}
                      className="flex items-center justify-between gap-3 rounded-md border border-border bg-background px-3 py-1.5 text-xs"
                    >
                      <span className="min-w-0 truncate">
                        <span className="text-muted-foreground">[{a.kind}]</span>{" "}
                        <span className="text-foreground">{a.name}</span>
                        <span className="ml-2 text-muted-foreground">
                          {a.text.length.toLocaleString()} chars
                          {a.truncated && " (truncated)"}
                        </span>
                      </span>
                      <button
                        type="button"
                        onClick={() => removeAttachment(a.name)}
                        disabled={formDisabled}
                        className="text-muted-foreground hover:text-destructive"
                      >
                        remove
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </Field>

          <Field
            label="Special instructions"
            hint="Overrides — e.g. 'PI = Brian', 'drop the subcontract', 'use Trust Codex as primary platform'."
            className="mt-4"
          >
            <textarea
              value={specialInstructions}
              onChange={(e) => setSpecialInstructions(e.target.value)}
              maxLength={4000}
              rows={3}
              disabled={formDisabled}
              className={textareaCls}
            />
          </Field>
        </FormSection>

        {/* ─── Section: Generate ─── */}
        <FormSection
          title="Generate"
          subtitle="Pick a depth. The engine streams progress and writes artifacts to disk as it goes."
        >
          <div className="grid gap-2 md:grid-cols-3">
            <DepthCard
              value="scaffold"
              current={depth}
              label="Scaffold"
              help={SCAFFOLD_HELP}
              onChange={setDepth}
              disabled={formDisabled}
            />
            <DepthCard
              value="standard"
              current={depth}
              label="Standard"
              help={STANDARD_HELP}
              onChange={setDepth}
              disabled={formDisabled}
            />
            <DepthCard
              value="complete"
              current={depth}
              label="Complete"
              help={COMPLETE_HELP}
              onChange={setDepth}
              disabled={formDisabled}
            />
          </div>
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <button
              type="submit"
              disabled={formDisabled}
              className="rounded-md border border-primary bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-50"
            >
              {streaming ? "Generating…" : "Generate submission package"}
            </button>
            {(phase.kind === "done" || phase.kind === "error") && (
              <button
                type="button"
                onClick={reset}
                className="text-xs text-muted-foreground hover:underline"
              >
                Reset form
              </button>
            )}
            {phase.kind === "error" && (
              <span className="text-xs text-destructive">{phase.message}</span>
            )}
          </div>
        </FormSection>
      </form>

      {(streaming || phase.kind === "done" || progress.length > 0) && (
        <div className="space-y-3 border-t border-border p-5">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
            Run progress
          </h3>
          {outputDir && (
            <p className="text-xs text-muted-foreground">
              Writing to{" "}
              <code className="rounded bg-muted px-1.5 py-0.5">{outputDir}</code>
            </p>
          )}
          <ul className="space-y-2">
            {progress.map((p) => (
              <li
                key={p.key}
                className="rounded-md border border-border bg-background p-3"
              >
                <div className="flex items-baseline justify-between gap-3">
                  <p className="text-sm font-medium text-foreground">
                    <StatusDot status={p.status} /> {p.label}
                  </p>
                  <p className="text-xs text-muted-foreground tabular-nums">
                    {p.charCount > 0 && (
                      <>
                        {p.charCount.toLocaleString()} chars
                        {p.durationMs
                          ? ` · ${(p.durationMs / 1000).toFixed(1)}s`
                          : ""}
                      </>
                    )}
                  </p>
                </div>
                {p.files.length > 0 && (
                  <ul className="mt-2 space-y-1 text-xs">
                    {p.files.map((f) => (
                      <li key={f.path} className="flex justify-between gap-3">
                        <span className="text-foreground">
                          {submissionId ? (
                            <a
                              href={`/sbir/submissions/${submissionId}/files/${f.path}`}
                              className="text-primary hover:underline"
                            >
                              {f.path}
                            </a>
                          ) : (
                            f.path
                          )}
                        </span>
                        <span className="text-muted-foreground tabular-nums">
                          {f.bytes.toLocaleString()} bytes
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </li>
            ))}
          </ul>

          {verifyFlags.length > 0 && (
            <div className="rounded-md border border-warning/40 bg-warning/10 p-3">
              <p className="text-sm font-medium text-foreground">
                Verify flags — resolve before DSIP certification
              </p>
              <ul className="mt-1 list-disc space-y-1 pl-5 text-xs text-foreground">
                {verifyFlags.map((f) => (
                  <li key={f}>{f}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </section>
  );
}

function FormSection({
  title,
  subtitle,
  children
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="p-5">
      <div className="mb-4">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-primary">
          {title}
        </h3>
        {subtitle && (
          <p className="mt-1 text-xs text-muted-foreground">{subtitle}</p>
        )}
      </div>
      {children}
    </div>
  );
}

function Field({
  label,
  hint,
  required,
  className,
  children
}: {
  label: string;
  hint?: string;
  required?: boolean;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <div className={"flex flex-col gap-1 " + (className ?? "")}>
      <label className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
        {label}
        {required && <span className="ml-1 text-destructive">*</span>}
      </label>
      {children}
      {hint && <p className="text-[11px] text-muted-foreground">{hint}</p>}
    </div>
  );
}

function DepthCard({
  value,
  current,
  label,
  help,
  onChange,
  disabled
}: {
  value: Depth;
  current: Depth;
  label: string;
  help: string;
  onChange: (d: Depth) => void;
  disabled?: boolean;
}) {
  const active = value === current;
  return (
    <button
      type="button"
      onClick={() => onChange(value)}
      disabled={disabled}
      className={
        "rounded-md border p-3 text-left transition-colors " +
        (active
          ? "border-primary bg-primary/10"
          : "border-border bg-background hover:border-foreground/30")
      }
    >
      <p
        className={
          "text-sm font-medium " +
          (active ? "text-primary" : "text-foreground")
        }
      >
        {label}
      </p>
      <p className="mt-1 text-xs text-muted-foreground">{help}</p>
    </button>
  );
}

function StatusDot({
  status
}: {
  status: "running" | "done" | "errored";
}) {
  const cls =
    status === "running"
      ? "bg-blue-500 animate-pulse"
      : status === "done"
        ? "bg-green-600"
        : "bg-destructive";
  return (
    <span
      aria-hidden
      className={"mr-2 inline-block h-2 w-2 rounded-full align-middle " + cls}
    />
  );
}

const inputCls =
  "rounded-md border border-border bg-background px-3 py-2 text-sm shadow-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary disabled:opacity-50";
const textareaCls = inputCls + " font-mono leading-relaxed";

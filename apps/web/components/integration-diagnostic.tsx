import { Badge, Card, fmtDate } from "@/components/ui";
import type { IntegrationStatusOut } from "@/lib/api";

type Props = {
  status: IntegrationStatusOut | null;
  fetchError?: string | null;
  triggerAction: () => Promise<void>;
};

/**
 * Diagnostic card replacing the generic "check back tomorrow" empty
 * state. Surfaces the actual reason data is missing — no token, run
 * failed, run skipped, run succeeded but ingest yielded nothing — and
 * a Retry button that fires the kick task on demand.
 */
export function IntegrationDiagnostic({
  status,
  fetchError,
  triggerAction,
}: Props) {
  if (!status) {
    return (
      <Card title="Diagnostic — integration status unavailable">
        <div className="rounded-md border border-red-200 bg-red-50 p-3">
          <p className="text-sm font-medium text-red-900">
            The API returned an error fetching integration status.
          </p>
          {fetchError && (
            <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap rounded border border-red-200 bg-white p-2 font-mono text-[11px] text-red-800">
              {fetchError}
            </pre>
          )}
          <p className="mt-2 text-[11px] text-red-800">
            Most likely causes:
          </p>
          <ul className="mt-1 list-disc pl-5 text-[11px] text-red-800">
            <li>
              Latest deploy hasn&rsquo;t completed yet — check{" "}
              <code className="rounded bg-red-100 px-1">
                railway status --service api
              </code>
              .
            </li>
            <li>
              Alembic migration failed during boot — check{" "}
              <code className="rounded bg-red-100 px-1">
                railway logs --service api
              </code>{" "}
              for an exception.
            </li>
            <li>
              Database connection issue (DATABASE_URL stale or unreachable).
            </li>
          </ul>
        </div>
      </Card>
    );
  }

  const { last_run, api_token_set, label, description, schedule, api_token_var } =
    status;

  // Resolve the headline diagnosis.
  let headline: string;
  let body: React.ReactNode;
  let tone: "red" | "amber" | "neutral" | "blue" = "neutral";

  if (!api_token_set && (!last_run || last_run.apify_status === "SKIPPED")) {
    tone = "red";
    headline = `${api_token_var} not set on the API service`;
    body = (
      <>
        <p className="text-sm text-neutral-700">
          The {label.toLowerCase()} worker no-ops every run because{" "}
          <code className="rounded bg-neutral-100 px-1">{api_token_var}</code>{" "}
          isn&rsquo;t in the environment. Set it on the Railway workers
          service (and the API service if you want this banner to flip
          green) and trigger a run below to verify.
        </p>
        <p className="mt-2 text-[11px] text-neutral-500">
          Beat schedule: {schedule}.
        </p>
      </>
    );
  } else if (last_run?.apify_status === "SKIPPED") {
    tone = "amber";
    headline = "Last run was skipped by the worker";
    body = (
      <>
        <p className="text-sm text-neutral-700">
          The worker recorded a skip on{" "}
          {last_run.received_at ? fmtDate(last_run.received_at) : "?"}.
          Reason: <em>{last_run.ingest_error ?? "unknown"}</em>.
        </p>
      </>
    );
  } else if (last_run?.apify_status && last_run.apify_status !== "SUCCEEDED") {
    tone = "red";
    headline = `Last Apify run ${last_run.apify_status}`;
    body = (
      <>
        <p className="text-sm text-neutral-700">
          Apify reported status{" "}
          <code className="rounded bg-neutral-100 px-1">
            {last_run.apify_status}
          </code>{" "}
          on {last_run.received_at ? fmtDate(last_run.received_at) : "?"}.
          {last_run.ingest_error ? (
            <>
              {" "}
              Error: <em>{last_run.ingest_error}</em>.
            </>
          ) : null}
        </p>
      </>
    );
  } else if (last_run && (last_run.items_count ?? 0) === 0) {
    tone = "amber";
    headline = "Last run succeeded but extracted no records";
    body = (
      <>
        <p className="text-sm text-neutral-700">
          Apify finished cleanly on{" "}
          {last_run.received_at ? fmtDate(last_run.received_at) : "?"} but
          the LLM extractor returned zero {label.toLowerCase()}. The seed
          URLs may have changed shape — check the worker logs and the
          forecast hub URLs in the worker source.
        </p>
        {last_run.ingest_error && (
          <p className="mt-1 text-[11px] text-neutral-500">
            Note: {last_run.ingest_error}
          </p>
        )}
      </>
    );
  } else if (last_run && (last_run.items_count ?? 0) > 0) {
    tone = "blue";
    headline = "Last run succeeded";
    body = (
      <p className="text-sm text-neutral-700">
        {last_run.items_count?.toLocaleString()} dataset records ingested
        on {last_run.received_at ? fmtDate(last_run.received_at) : "?"}.
        The view above filters to opportunities matching your NAICS or
        upcoming dates — try removing those filters if you expected
        more.
      </p>
    );
  } else {
    // No run on file ever.
    tone = "amber";
    headline = "No runs on file yet";
    body = (
      <p className="text-sm text-neutral-700">
        The worker has not yet recorded a kick. The next scheduled beat is{" "}
        {schedule}, or you can trigger one now to verify the pipeline.
      </p>
    );
  }

  return (
    <Card
      title={`Diagnostic — ${label}`}
      trailing={
        api_token_set ? (
          <Badge tone="green">{api_token_var} set</Badge>
        ) : (
          <Badge tone="red">{api_token_var} missing</Badge>
        )
      }
    >
      <div
        className={
          tone === "red"
            ? "rounded-md border border-red-200 bg-red-50 p-3"
            : tone === "amber"
            ? "rounded-md border border-amber-200 bg-amber-50 p-3"
            : tone === "blue"
            ? "rounded-md border border-blue-200 bg-blue-50 p-3"
            : "rounded-md border border-neutral-200 bg-neutral-50 p-3"
        }
      >
        <p className="text-sm font-medium text-neutral-900">{headline}</p>
        <div className="mt-1">{body}</div>
      </div>

      <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-neutral-100 pt-3">
        <p className="text-[11px] text-neutral-500">{description}</p>
        <form action={triggerAction}>
          <button
            type="submit"
            className="rounded-md border border-neutral-900 bg-neutral-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-neutral-800"
          >
            Trigger run now →
          </button>
        </form>
      </div>
    </Card>
  );
}

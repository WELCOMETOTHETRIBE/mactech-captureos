import Link from "next/link";
import { apiFetch } from "@/lib/api";
import {
  Badge,
  EmptyState,
  LinkButton,
  PageHeader,
  fmtDate
} from "@/components/ui";
import { SBIRTopicsRefreshButton } from "@/components/sbir-topics-refresh";

export const dynamic = "force-dynamic";

type SBIRTopicListItem = {
  id: string;
  source: string;
  topic_number: string;
  title: string | null;
  component: string | null;
  program: string | null;
  phase: string | null;
  status: string;
  close_date: string | null;
  url: string | null;
};

type SBIRTopicListResponse = {
  total: number;
  items: SBIRTopicListItem[];
};

const STATUS_TONE: Record<
  string,
  "neutral" | "blue" | "green" | "amber" | "red"
> = {
  prerelease: "amber",
  open: "green",
  closed: "neutral",
  unknown: "neutral"
};

const STATUSES = ["all", "open", "prerelease", "closed"] as const;
type StatusFilter = (typeof STATUSES)[number];
const COMPONENTS = [
  "all",
  "Army",
  "Navy",
  "Air Force",
  "DLA",
  "DARPA",
  "SOCOM",
  "Space Force",
  "MDA",
  "OSD",
  "Other"
] as const;
type ComponentFilter = (typeof COMPONENTS)[number];
const PROGRAMS = ["all", "SBIR", "STTR"] as const;
type ProgramFilter = (typeof PROGRAMS)[number];

function coerceStatus(v: string | undefined): StatusFilter {
  return v && (STATUSES as readonly string[]).includes(v)
    ? (v as StatusFilter)
    : "open";
}
function coerceComponent(v: string | undefined): ComponentFilter {
  return v && (COMPONENTS as readonly string[]).includes(v)
    ? (v as ComponentFilter)
    : "all";
}
function coerceProgram(v: string | undefined): ProgramFilter {
  return v && (PROGRAMS as readonly string[]).includes(v)
    ? (v as ProgramFilter)
    : "all";
}

function buildQuery(params: {
  status: StatusFilter;
  component: ComponentFilter;
  program: ProgramFilter;
  q?: string;
}) {
  const usp = new URLSearchParams();
  if (params.status !== "all") usp.set("status", params.status);
  if (params.component !== "all") usp.set("component", params.component);
  if (params.program !== "all") usp.set("program", params.program);
  if (params.q?.trim()) usp.set("q", params.q.trim());
  return usp.toString();
}

export default async function SBIRTopicsPage({
  searchParams
}: {
  searchParams: Promise<{
    status?: string;
    component?: string;
    program?: string;
    q?: string;
  }>;
}) {
  const sp = await searchParams;
  const filters = {
    status: coerceStatus(sp.status),
    component: coerceComponent(sp.component),
    program: coerceProgram(sp.program),
    q: sp.q
  };

  const apiQuery = buildQuery(filters);
  let data: SBIRTopicListResponse = { total: 0, items: [] };
  try {
    data = await apiFetch<SBIRTopicListResponse>(
      `/sbir/topics${apiQuery ? `?${apiQuery}` : ""}`
    );
  } catch (err) {
    console.error("Failed to load /sbir/topics", err);
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="SBIR · Topics"
        title="SBIR/STTR topic finder"
        subtitle={
          <>
            Open DoD SBIR and STTR topics scraped from DSIP, SBIR.gov, and
            component portals. Click <em>Use this topic</em> to pre-fill the
            submitter with the topic number, title, component, and close date.
          </>
        }
        trailing={<SBIRTopicsRefreshButton />}
      />

      <section className="rounded-md border border-border bg-card p-4">
        <form className="grid gap-3 md:grid-cols-4">
          <FilterRow label="Status" name="status" options={STATUSES} current={filters.status} />
          <FilterRow
            label="Component"
            name="component"
            options={COMPONENTS}
            current={filters.component}
          />
          <FilterRow
            label="Program"
            name="program"
            options={PROGRAMS}
            current={filters.program}
          />
          <div className="flex flex-col gap-1">
            <label className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
              Search
            </label>
            <div className="flex gap-2">
              <input
                type="text"
                name="q"
                defaultValue={filters.q ?? ""}
                placeholder="topic number, title, keyword…"
                className="min-w-0 flex-1 rounded-md border border-border bg-background px-3 py-2 text-sm shadow-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
              />
              <button
                type="submit"
                className="rounded-md border border-primary bg-primary px-3 py-2 text-xs font-medium text-primary-foreground hover:opacity-90"
              >
                Search
              </button>
            </div>
          </div>
        </form>
      </section>

      <section className="space-y-3">
        <div className="flex items-baseline justify-between">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
            {data.total === 0
              ? "No topics found"
              : `${data.total} topic${data.total === 1 ? "" : "s"}`}
          </h2>
          {data.total > 0 && (
            <p className="text-xs text-muted-foreground">
              Sorted by soonest close date.
            </p>
          )}
        </div>

        {data.items.length === 0 ? (
          <EmptyState
            title="No topics yet."
            body={
              filters.status !== "open" ||
              filters.component !== "all" ||
              filters.program !== "all" ||
              !!filters.q
                ? "Try widening the filters above. If the topic feed has never been refreshed, click 'Refresh feed' to kick the Apify ingest."
                : "The topic feed is empty. Click 'Refresh feed' to kick the Apify ingest — first run takes 5–10 minutes."
            }
            action={
              <LinkButton href="/sbir/submit" variant="primary">
                Submit without a topic →
              </LinkButton>
            }
          />
        ) : (
          <ul className="space-y-2">
            {data.items.map((t) => (
              <li
                key={t.id}
                className="flex flex-wrap items-baseline justify-between gap-3 rounded-md border border-border bg-card p-4"
              >
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone={STATUS_TONE[t.status] ?? "neutral"}>
                      {t.status}
                    </Badge>
                    <span className="font-medium text-foreground">
                      {t.topic_number}
                    </span>
                    {t.component && (
                      <span className="text-xs text-muted-foreground">
                        {t.component}
                      </span>
                    )}
                    {t.program && (
                      <span className="text-xs text-muted-foreground">
                        · {t.program}
                        {t.phase ? ` Phase ${t.phase}` : ""}
                      </span>
                    )}
                    <span className="ml-1 text-[10px] uppercase tracking-wide text-muted-foreground">
                      {t.source}
                    </span>
                  </div>
                  {t.title && (
                    <p className="mt-1 text-sm text-foreground">{t.title}</p>
                  )}
                  {t.url && (
                    <a
                      href={t.url}
                      target="_blank"
                      rel="noreferrer noopener"
                      className="mt-1 inline-block max-w-full truncate text-[11px] text-muted-foreground hover:text-foreground hover:underline"
                    >
                      {t.url}
                    </a>
                  )}
                </div>
                <div className="flex flex-col items-end gap-1 text-xs text-muted-foreground">
                  {t.close_date && (
                    <p>
                      closes <span className="text-foreground">{fmtDate(t.close_date)}</span>
                    </p>
                  )}
                  <Link
                    href={`/sbir/submit?topic_id=${t.id}`}
                    className="rounded-md border border-primary bg-primary/10 px-3 py-1 text-xs font-medium text-primary hover:bg-primary/20"
                  >
                    Use this topic →
                  </Link>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

function FilterRow<T extends readonly string[]>({
  label,
  name,
  options,
  current
}: {
  label: string;
  name: string;
  options: T;
  current: T[number];
}) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </label>
      <select
        name={name}
        defaultValue={current}
        className="rounded-md border border-border bg-background px-3 py-2 text-sm shadow-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
      >
        {options.map((o) => (
          <option key={o} value={o}>
            {o}
          </option>
        ))}
      </select>
    </div>
  );
}

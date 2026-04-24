# Apify Strategy — MacTech CaptureOS

## 1. The frame

MacTech already integrates SAM.gov Opportunities, Entity Management, and Exclusions directly via REST. USASpending and FPDS-NG come for free (no auth, well-documented, stable). So the honest question is: why pay Apify a cent?

Apify earns its place by attacking the surface area that REST APIs don't cover: agency forecast pages that publish pre-solicitation intent in HTML and PDF (DoD OSBP, VA, DHS, GSA OSDBU, service-branch SBO pages), DLA DIBBS for commodity RFQs, GSA eBuy post-Schedule task orders, FedConnect, industry-day announcements buried on .mil subdomains, SEC EDGAR filings that telegraph incumbent distress, and LinkedIn signals on departing program managers. None of this is available through SAM.gov. All of it is structured enough to scrape and unstructured enough that building bespoke scrapers in-house would consume Phase 1 entirely.

**Strategic thesis:** Apify is the sealed ingest edge for public-but-unstructured GovCon signal — everything that lives outside `api.sam.gov` and `api.usaspending.gov` but materially shifts whether MacTech wins or loses a contract.

The phrase **sealed ingest edge** is operationally specific. Apify is SOC 2 Type II and GDPR-compliant, but it is **not** FedRAMP, not GovCloud, and carries no CMMC attestation. That means: Apify only ever touches public data on the way *in*. Scraped artifacts land in Apify Datasets briefly, get pulled into MacTech Postgres via webhook, then nothing proprietary, nothing tenant-owned, and nothing CUI-marked ever flows back through Apify. Pursuits, capability statements, draft proposals, compliance matrices, and customer-tenant data live in MacTech's CMMC-aligned stack (Railway today, GovCloud later) and stay there. Apify is upstream of the moat, never inside it.

This framing also resolves a second question: Apify is not a substitute for our direct SAM.gov client; it's a complement. Direct REST stays primary for the data SAM.gov serves authoritatively. Apify covers the gaps and the long tail.

## 2. The integration topology

Apify sits at the perimeter, on the public-data side of the MacTech security boundary. It runs Actors on schedules or on demand, deposits results into Apify Datasets, and pings MacTech via webhooks. MacTech's FastAPI app receives those webhooks, validates them, enqueues a Celery task to pull dataset items via `apify-client`, normalizes the payload into Postgres, and triggers downstream LLM enrichment through the existing `AnthropicAPIClient`. Nothing pushes from MacTech outward into Apify except Actor input parameters (search terms, NAICS codes, date windows — none of which are sensitive).

```
┌─────────────────── Public internet ───────────────────┐
│                                                       │
│   SAM.gov forecasts │ DLA DIBBS │ Agency .mil pages   │
│   GSA eBuy │ FedConnect │ SEC EDGAR │ LinkedIn (read) │
│                          │                            │
│                          ▼                            │
│              ┌──────────────────────┐                 │
│              │   Apify Platform     │                 │
│              │   (sealed edge,      │                 │
│              │    public data only) │                 │
│              │                      │                 │
│              │  Store Actors  ◀──┐  │                 │
│              │  Custom Actors    │  │ schedules       │
│              │   (apify push)    │  │ + webhooks      │
│              │  Standby Actors ──┘  │                 │
│              │                      │                 │
│              │  Datasets (transit)  │                 │
│              └─────────┬────────────┘                 │
│                        │  webhook (RUN.SUCCEEDED)     │
└────────────────────────┼──────────────────────────────┘
                         │
   === MacTech security boundary (CMMC L2 aligned) ===
                         │
                         ▼
              ┌──────────────────────┐
              │  FastAPI webhook     │
              │  /webhooks/apify     │   HMAC verify
              └─────────┬────────────┘
                        │ enqueue
                        ▼
              ┌──────────────────────┐
              │  Celery worker       │
              │  pulls dataset items │
              │  via apify-client    │
              └─────────┬────────────┘
                        │ upsert
                        ▼
              ┌──────────────────────┐
              │  Postgres 18 + pgvec │
              │  opportunities_raw,  │
              │  forecasts_raw,      │
              │  incumbent_signals,  │
              │  agency_events       │
              └─────────┬────────────┘
                        │
                        ▼
              ┌──────────────────────┐
              │  AnthropicAPIClient  │
              │  scoring + summary   │
              └──────────────────────┘
```

**Primitive-to-purpose mapping:**

- **Actor (scheduled run):** nightly or hourly polls of agency forecast pages, DIBBS, EDGAR. Cron-driven via Apify Schedules.
- **Dataset:** transit buffer only. We pull items within minutes of run completion and treat Apify Datasets as ephemeral; MacTech Postgres is the source of truth.
- **Webhook (RUN.SUCCEEDED / RUN.FAILED):** the only push from Apify into MacTech. Failed runs alert Sentry; succeeded runs trigger ingest.
- **Standby Actor:** warm HTTP endpoints for interactive lookups during a pursuit-qualify session (e.g., "fetch this agency's last 10 industry days for vehicle X"). Sub-second latency vs. cold-start.
- **MCP Server (Apify-hosted):** exposes any Apify Actor as a Claude tool, used by the four founders during ad-hoc capture work in Claude Code or Claude Desktop. Read-only by default.
- **Private Actor (`apify push`):** MacTech-built parsers for sources where no Store actor is trustworthy enough — primarily agency-forecast pages and DIBBS-PDF extraction.

**What never touches Apify:** opportunity scoring outputs, capability library content, founder identities beyond NAICS, draft proposal language, compliance matrices, customer tenant data, any document marked FOUO/CUI/PROPIN/ITAR, anything originating from a customer's secure document ingest, and any prompt that would echo back proprietary capability language.

## 3. The killer apps

Seven Apify-powered capabilities, ordered by Phase 1 → Phase 4 strategic weight. Each one earns its place against the test: does this help MacTech win a contract, or would a DIB customer pay for it?

---

### 3.1 Agency Forecast Sweep

**What it does:** Nightly scrape of agency forecast and procurement-intent pages that don't post to SAM.gov until 30–180 days later, sometimes never. Captures DoD OSBP forecasts, VA forecast (FBO replacement), DHS APFS, GSA OSDBU, Air Force AFLCMC industry days, Army PEO C3T, and NIWC Atlantic/Pacific calendars. Normalizes into a `forecasts_raw` table with NAICS, est. value, period of performance, set-aside intent, and POC.

**Founder + when:** All four. Fires nightly 0200 ET; surfaces in the 0600 ET digest as a *"Coming to SAM.gov in 60–180 days"* section, separate from active opportunities.

**Actor(s):** MacTech custom private Actor per agency (`apify push`). Forecast pages are too idiosyncratic and too important for our recompete posture to depend on a Store actor that may stop being maintained or hit the Oct 2026 rental-pricing sunset. One Actor per agency; ~10 agencies in Phase 1 expanding to ~25.

**Integration pattern:** Schedule (cron) → Actor run → Dataset → webhook to `/webhooks/apify/forecast` → Celery `ingest_forecast_run` task → upsert by `(agency, forecast_id)` → Voyage embedding → Anthropic scoring with same scoring config as opportunities.

**Cost:** ~10 Actors, each ~30s @ 1GB = 0.0083 CU/run × 30 days = ~2.5 CU/Actor/month × 10 = ~25 CU = ~$6/mo at Scale tier. No proxy needed for most .gov pages.

**Phase:** Phase 1 (Week 4 stretch) for top 3 agencies; Phase 2 for full 10.

**ROI thesis:** A 90-day head start on a $2M opportunity is worth more than every other capability on this list combined. Forecasts are the single highest-leverage public-data signal in GovCon and SAM.gov doesn't carry them.

---

### 3.2 DIBBS RFQ Capture

**What it does:** Continuous (every 4 hours) capture of DLA DIBBS RFQs filtered by FSC/NSN ranges relevant to MacTech's adjacency (test equipment, calibration items, IT commodities). Pulls quote response deadline, quantity, delivery, and PDF attachment URLs.

**Founder + when:** Brian (metrology FSCs) and James (IT commodity NSNs). Fires on ingest; surfaces in a dedicated DIBBS panel separate from main pursuit board because the volume and velocity are different.

**Actor(s):** Start with `parseforge/dibbs-rfq-scraper` for Phase 1 to validate the funnel; budget a private Actor build by end of Phase 2 to remove third-party dependency before Oct 2026 sunset.

**Integration pattern:** 4-hourly schedule → Dataset → webhook → Celery → `dibbs_rfqs` table. PDF attachment URLs queued for the document-parse pipeline once Phase 3 ships.

**Cost:** parseforge actor ~$1–$3/1k RFQs depending on filter breadth. Realistic Phase 1 volume: ~500 matched RFQs/mo = ~$1.50/mo + ~3 CU compute = ~$2/mo all-in.

**Phase:** Phase 1 (Week 4) on Store actor; Phase 2 (Week 6) cut over to private Actor.

**ROI thesis:** Brian's funnel is otherwise too narrow for the SAM.gov-only feed. DIBBS broadens his weekly opportunity count from ~2 to ~15+ and is the most likely path to his first independent win.

---

### 3.3 Incumbent Distress Signals

**What it does:** Monitors SEC EDGAR (10-K, 10-Q, 8-K) for the top 200 federal contractors, plus their LinkedIn company pages for layoff announcements and Glassdoor sentiment shifts. Surfaces signals like "incumbent X reported a $40M loss on this contract segment," "incumbent Y just laid off 12% of their federal services group," "key program manager Z left incumbent A 60 days ago." Cross-joined against `opportunities_raw.incumbent_uei` (populated from USASpending) so signals attach to specific recompetes.

**Founder + when:** All four, but weighted toward Patrick and James whose target opportunities are most often recompetes. Fires weekly Sunday 1800 ET; surfaces as a "Recompete Risk Watch" panel in Monday digest.

**Actor(s):** SEC EDGAR — one of the existing Store EDGAR scrapers (8-K + 10-Q with AI summary variants); validate before committing. LinkedIn — `harvestapi/linkedin-profile-search` for departed-PM detection ($0.10/page + $0.004/profile), strictly read-only.

**Integration pattern:** Weekly schedule → Dataset → webhook → Celery → `incumbent_signals` table keyed by UEI + signal type + observed_at. Anthropic enrichment generates the "why this matters for the recompete" paragraph.

**Cost:** EDGAR ~5 CU/week = ~$5/mo. LinkedIn ~200 company pages/week + ~50 profile fetches = ~$2.50/week = ~$10/mo. Total ~$15/mo.

**Phase:** Phase 2 (Week 7).

**ROI thesis:** Recompete win-rates jump dramatically when the challenger arrives knowing the incumbent is bleeding. This is the single capability most likely to differentiate MacTech CaptureOS from GovWin.

---

### 3.4 Capture-Time Standby Lookups (MCP-exposed)

**What it does:** A Standby Actor exposing low-latency HTTP endpoints for interactive use during a pursuit-qualify session: "give me this agency's last 10 industry days," "list all SEWP V task orders awarded in the last 90 days for NAICS 541512," "fetch the POC's prior CO history from FPDS." Wrapped through Apify's first-party MCP server so the four founders can invoke them as tools directly from Claude Code or Claude Desktop while drafting capture plans.

**Founder + when:** All four. Fires on demand during pursuit-qualify and pink-team review.

**Actor(s):** MacTech custom private Standby Actor for the composite lookups; `apify/apify-mcp-server` (hosted, OAuth) as the gateway.

**Integration pattern:** Founder invokes tool in Claude Code → Apify MCP server routes to Standby Actor → results return inline in chat. Notable: results do **not** flow into Postgres — this is read-only ad-hoc intel, not pipeline.

**Cost:** Standby idle is near-zero on Scale tier; active lookups <$0.01 each. Realistic 50 lookups/founder/week = ~$8/mo.

**Phase:** Phase 2 (Week 8) once the founders are doing real capture in the tool.

**ROI thesis:** Capture velocity. A founder mid-conversation with a teaming partner can pull authoritative public data into the chat in seconds without breaking flow. This is the capability most likely to make CaptureOS feel native to the way the founders actually work.

---

### 3.5 GSA eBuy + FedConnect Sweep

**What it does:** Captures Schedule task orders posted to GSA eBuy (visible only after Schedule award) and FedConnect-only solicitations. These are both significant blind spots for SAM.gov-only pipelines.

**Founder + when:** James (Schedule-eligible IT/cloud task orders). Fires twice daily 0700 and 1500 ET.

**Actor(s):** MacTech custom private Actors. No Store actor we'd trust for eBuy given the auth-walled nature of the source; FedConnect similarly idiosyncratic. These two are post-MacTech-Schedule-award capability so this work is correctly Phase 3+ unless MacTech accelerates Schedule pursuit.

**Integration pattern:** Authenticated session via stored credentials in Apify Key-Value Store (encrypted) → schedule → Dataset → webhook → `task_orders_raw` table.

**Cost:** ~10 CU/mo = ~$2.50/mo + minimal proxy.

**Phase:** Phase 3, conditional on MacTech Schedule.

**ROI thesis:** Once MacTech is on Schedule, eBuy is where the real recurring revenue lives. Without this capability the Schedule itself is half-utilized.

---

### 3.6 Industry Day + Pre-Sol Calendar

**What it does:** Aggregates announced industry days, pre-solicitation conferences, and "meet the buyer" events across DoD OSBP, NIWC, AFCEA, AFFIRM, and target-agency calendars. Cross-references with founders' assigned NAICS to flag attendance candidates 14–60 days out.

**Founder + when:** All four. Fires daily 0500 ET; surfaces in digest "Where to be" section.

**Actor(s):** Combination of `apify/website-content-crawler` (official, well-maintained) for crawl + a thin private Actor for parse normalization.

**Integration pattern:** Daily schedule → website-content-crawler → webhook → Celery LLM-extract event metadata → `agency_events` table → digest renderer.

**Cost:** website-content-crawler is well-priced; ~5 CU/mo = ~$1.25/mo. LLM extract dominates: ~$3/mo Anthropic.

**Phase:** Phase 2 (Week 6).

**ROI thesis:** Industry-day attendance is the single strongest predictor of bid/no-bid intel quality. Showing up to two events MacTech would otherwise miss pays for a year of CaptureOS several times over.

---

### 3.7 Teaming Partner Footprint

**What it does:** For any opportunity scored ≥70, runs a one-shot enrichment that maps the small-business landscape eligible to team on it: SDVOSB/HUBZone/8a/WOSB primes and subs in the relevant NAICS who have history with the target agency. Pulls from USASpending sub-award data (direct API) plus LinkedIn company-page presence checks via Apify for currency confirmation.

**Founder + when:** Whichever founder is auto-assigned the pursuit. Fires once at pursuit-qualify stage.

**Actor(s):** `harvestapi/linkedin-profile-search` for company-page existence + employee count signal. USASpending portion is direct REST, no Apify.

**Integration pattern:** On-demand Actor run triggered by Celery from the pursuit-qualify lifecycle hook → small Dataset → pulled inline (sync if <60s, otherwise async with webhook) → enriches `pursuits` table teaming candidates.

**Cost:** ~$0.05 per qualified pursuit. At MacTech volume of ~20 qualified pursuits/mo = ~$1/mo.

**Phase:** Phase 3 (Week 11).

**ROI thesis:** Teaming is how MacTech gets into the $5M–$20M opportunity range as a sub before primeing on its own. A 30-second teaming-partner shortlist beats a 4-hour LinkedIn rabbit hole.

---

## 4. What NOT to do

- **No CUI through Apify, ever.** Apify is not FedRAMP, not CMMC-attested. Any document with FOUO/CUI/PROPIN/ITAR markings, any customer-uploaded artifact, any draft proposal, and any prompt embedding capability statements stays inside MacTech's boundary. The webhook receiver explicitly rejects payloads that match a CUI-marker regex on inbound text fields and Sentry-alerts.
- **No automated LinkedIn outreach.** LinkedIn read-only signal extraction is acceptable as decision support. LinkedIn-driven automated messaging, connection requests, or InMail sequences from the platform is not — both ToS-violating and brand-suicidal for a veteran-owned compliance firm. Any future outreach is human-initiated, in a human's own LinkedIn session, informed by but not executed by the platform.
- **No third-party Actor as a single point of failure.** Every Store actor we depend on must have either (a) a private MacTech-built equivalent in backlog or (b) a documented fallback to direct REST or human review. The Oct 1 2026 rental-pricing sunset is an existential risk for any unattended dependency.
- **No agency-PDF ingestion through Apify when the PDF is plausibly marked.** Industry-day slides, draft RFP packages, and Q&A documents frequently carry FOUO markings even on public sites. Pull the PDF URL via Apify, but fetch the PDF itself with a MacTech-side worker so it never sits in Apify Storage.
- **No reliance on rental-priced Actors past Q1 2026.** Audit every Store actor we use against the Apr 1 2026 freeze; cut over or replace before that date.
- **No proprietary scoring logic in private Actors.** Private Actors do extraction and normalization only — no scoring weights, no founder-NAICS routing logic, no MacTech-specific intelligence. Apify is multitenant infrastructure and our scoring config is a competitive moat.

## 5. Phased rollout

| Phase | Capability | Actor(s) | Integration point | Est. monthly cost |
|---|---|---|---|---|
| 1 (Wk 4) | Agency Forecast Sweep (top 3) | Private — DoD OSBP, VA, DHS | Celery `ingest_forecast_run` | ~$3 |
| 1 (Wk 4) | DIBBS RFQ Capture | `parseforge/dibbs-rfq-scraper` | Celery `ingest_dibbs_rfq` | ~$2 |
| 2 (Wk 6) | Industry Day + Pre-Sol Calendar | `apify/website-content-crawler` + private parser | Celery `ingest_agency_event` | ~$5 |
| 2 (Wk 6) | Forecast Sweep expand to 10 agencies | 7 add'l private Actors | same | +~$3 |
| 2 (Wk 7) | Incumbent Distress Signals | EDGAR Store actor + `harvestapi/linkedin-profile-search` | Celery `ingest_incumbent_signal` | ~$15 |
| 2 (Wk 8) | Capture-Time Standby Lookups (MCP) | Private Standby + `apify/apify-mcp-server` | Direct from Claude Code; no Postgres | ~$8 |
| 3 (Wk 11) | Teaming Partner Footprint | `harvestapi/linkedin-profile-search` | Pursuit-qualify hook | ~$1 |
| 3 (cond.) | GSA eBuy + FedConnect | Private — both | Celery `ingest_task_order` | ~$3 |
| 2 (Wk 6) | Cut DIBBS over to private Actor | Private DIBBS parser | replaces `parseforge` | swap |

**Capabilities that MUST be MacTech-private:** Agency Forecast Sweep (every agency), DIBBS (cutover by Wk 6), GSA eBuy, FedConnect, Standby Lookups. The pattern: anything operationally load-bearing in our digest, anything authenticated, anything whose disappearance would degrade founder workflow within 24 hours.

**Capabilities that can stay on Store actors:** SEC EDGAR (mature, multiple alternatives, low switching cost), LinkedIn search (vendor concentration but high quality), website-content-crawler (Apify first-party, no sunset risk), Apify MCP server (Apify first-party).

## 6. Tooling decisions

- **Python client.** Use `apify-client` (sync in Celery tasks, async in FastAPI handlers). Custom HTTP buys nothing; the SDK handles retry, pagination, and dataset iteration correctly.
- **Webhook receiver:** new FastAPI endpoint `POST /webhooks/apify/{capability}` under a dedicated router, HMAC-verified using the shared secret stored in Railway env. The endpoint validates, persists a raw `apify_runs` audit row, then enqueues a Celery task — it does not pull dataset items inline. This keeps the webhook fast and the heavy lifting in workers where retries are first-class.
- **API token storage:** Railway env var `APIFY_API_TOKEN` (production) and `.env` for local dev. Webhook secret as `APIFY_WEBHOOK_SECRET`. Never logged, never serialized into payloads.
- **First-party MCP server for Claude Code:** **Yes, adopt.** Zero glue code, OAuth handshake handled by Apify, lets the four founders use Claude Code as a research surface during capture work without us building tool-binding infrastructure. Lock to read-only Actor invocations in Phase 1; expand selectively. The Standby Lookups capability (3.4) is the production form of this; Claude Code MCP is the developer/founder form.
- **n8n vs. Make vs. direct:** **Direct integration.** Phase 1 has four founders and a small engineering surface; n8n/Make adds a control-plane dependency that doesn't justify itself until we have customers building their own pipelines. Revisit n8n in Phase 4 as a customer-facing extensibility option (DIB primes will want to wire CaptureOS into their existing automation).

## 7. Cost + risk model

**Phase 1 (Weeks 1–4, 4 founders):** $5–$15/mo expected, $25/mo worst-case. Forecast Sweep + DIBBS only. Compute dominated; per-result negligible. Recommend **Starter $29/mo plan** sized comfortably.

**Phase 2 (Weeks 5–8):** $35–$60/mo expected, $90/mo worst-case. Adds incumbent signals (LinkedIn is the largest line item), industry days, and full forecast sweep across 10 agencies. Recommend **Scale $199/mo plan** for the included $25 CU/mo headroom and lower per-CU rate.

**Phase 4 (external beta, ~25 paying tenants):** $400–$900/mo expected, $2,000/mo worst-case. Each tenant runs their own scoped DIBBS/eBuy/forecast sweeps; LinkedIn enrichment is the cost-blow-up vector. Per-tenant budget guardrail enforced at app layer, billed through tenant subscription.

**Three biggest cost-blow-up scenarios:**

1. **LinkedIn-driven incumbent signal volume scales linearly with watched contractors.** Capping the watch list at top-200 federal contractors is the discipline; without it, expanding to "every prime in the database" multiplies cost 10–50x.
2. **Misconfigured forecast sweep scrapes the same agency 20x/day.** A bad cron or a runaway retry could chew a Phase 1 month's budget in an afternoon. Mitigation: per-Actor concurrency cap of 1 + per-Actor monthly CU budget enforced via Apify's Spend Limit setting.
3. **Per-result Store actors during Apify's pricing sunset.** Rental-priced actors get more expensive or disappear between Apr 1 2026 and Oct 1 2026. Cost can spike unpredictably if vendors rush to repackage as pay-per-event.

**Budget guardrail recommendation:** mirror the $75/mo Anthropic alert pattern. Set Apify account-level **soft cap at $50/mo for Phase 1** and **$150/mo for Phase 2**, with email alerts at 50% / 80% / 100%. Phase 4 moves to per-tenant budgets attached to subscription tier and a $1,500/mo platform-level hard cap.

## 8. Open questions for the founders

- Is MacTech willing to publish intel in customer-facing digests that includes LinkedIn-sourced signals we cannot fully attribute (e.g., "incumbent appears to have laid off ~12% of their federal services group based on LinkedIn headcount delta")? If yes, with what disclaimer language?
- Are we prepared to commit engineering time in Phase 1 Week 4 to build private Actors for the top 3 agency forecast pages, or do we accept Phase 2 slip and start with a Store actor?
- The Sources Sought drafter (Phase 3) — must it run entirely inside MacTech infra against Anthropic API, or is it acceptable to run it through a private Standby Actor with prompt caching for latency? (Standby is faster and cheaper but adds Apify to the prompt path.)
- For the top-200 incumbent watch list, who curates it and how often? Quarterly review by Patrick + James, or auto-populated from USASpending top awardees?
- Are we comfortable storing GSA eBuy and FedConnect credentials in Apify Key-Value Store (encrypted at rest, SOC 2) for Phase 3, or do we require those credentials never leave MacTech infra (which means building those scrapers as MacTech-internal workers, not Apify Actors)?
- Veteran-owned brand voice: any LinkedIn read activity from MacTech-attributable Apify proxy IPs could in theory be observed by the targets. Are we comfortable with that operational footprint, or do we want to route exclusively through Apify residential proxies to anonymize?
- Phase 4 customer pricing model: do we charge for Apify pass-through cost line-itemed, or absorb it into tier pricing and accept margin compression on LinkedIn-heavy customers?
- Cutover deadline for rental-priced Actors: do we want a hard internal deadline of Mar 1 2026 (one month before freeze) or are we comfortable cutting closer to Apr 1?
- Should we build an Apify MCP whitelist of approved Actors that the founders can invoke from Claude Code, or trust the founders to use judgment on the open Actor catalog?
- For Phase 6 intelligence data products and the newsletter: do we treat Apify-sourced signals as redistributable in commercial reports, or do we re-derive them through direct sources before publication to avoid redistribution-license ambiguity?

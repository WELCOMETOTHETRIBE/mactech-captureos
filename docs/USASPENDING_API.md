# USASpending.gov API — Integration Brief

Practical notes for MacTech CaptureOS. Grounded in live calls on 2026-04-24. Complements `docs/SAM_GOV_API.md`.

The full endpoint catalog lists ~180 routes. MacTech uses ~10 of them. This doc covers those 10.

---

## 1. Why we use USASpending alongside SAM.gov

SAM Contract Awards and USASpending both surface federal contract awards drawn ultimately from FPDS-NG. Their differences are operationally significant.

| Capability | SAM Contract Awards | USASpending |
|---|---|---|
| **Contracts** | ✓ | ✓ |
| **Grants / loans / direct payments / other assistance** | — | ✓ |
| **Subawards** (sub-prime relationships) | — | ✓ — *only path to teaming intel* |
| **IDV task-order tree** (SEWP, ITES, GSA Schedules) | partial | ✓ — *purpose-built endpoint* |
| **Recipient profile + parent/child hierarchy** | partial | ✓ — *richer* |
| **Auth** | API key | **None** — fully public |
| **Daily call cap** | 1,000 / day | none documented (be polite) |
| **DoD 90-day visibility veil** | yes (for personal keys) | no |
| **Earliest data** | varies | 2007-10-01 (synchronous search); 2000-10-01 via bulk download |
| **Update lag** | near-real-time | days (depends on agency reporting cadence) |
| **Date format** | `MM/DD/YYYY` | ISO `YYYY-MM-DD` |
| **Range syntax** | `[low,high]` in query string | nested JSON object in POST body |
| **Modification-level granularity** | ✓ | ✓ |
| **Authoritative for "latest action"** | ✓ | — *uses snapshot loads* |

**Decision rule:** For incremental ingestion of recent awards, prefer SAM Contract Awards (faster, narrower payload, no veil compensation needed for civilian agencies). For teaming graphs, IDV trees, recipient deep-dives, and any DoD intelligence newer than 90 days that we can't get through SAM, use USASpending.

The two should be cross-validated. If USASpending and SAM disagree on an award's current end date, SAM is fresher; if they disagree on subaward structure, USASpending is the only signal.

---

## 2. Auth and call discipline

- **No API key.** No bearer token, no header, no query param.
- **No documented rate limit.** USASpending publishes "reasonable use" guidance in their tutorial. In practice, throttle the client to 1 request/second with jittered backoff.
- **Throttle anyway.** Hammer-the-API behavior risks IP-level blocking with no recourse mechanism, given there's no account to negotiate against.
- **Be a good citizen.** Cache aggressively (most lookups don't change daily), respect any 429s with exponential backoff, identify yourself in `User-Agent` (`MacTechCaptureOS/0.1 (+https://www.mactechsolutionsllc.com)`).

---

## 3. The endpoints MacTech uses

### 3.1 `POST /api/v2/search/spending_by_award/` — *the workhorse*

Primary search across all awards. The single most-used endpoint.

**Body:**
```json
{
  "filters": {
    "naics_codes": ["541519"],
    "agencies": [{"type": "awarding", "tier": "toptier", "name": "Department of Veterans Affairs"}],
    "time_period": [{"start_date": "2024-04-24", "end_date": "2026-04-24"}],
    "award_type_codes": ["A","B","C","D"],
    "award_amounts": [{"lower_bound": 100000}],
    "place_of_performance_locations": [],
    "recipient_search_text": [],
    "recipient_type_names": ["service_disabled_veteran_owned_business"]
  },
  "fields": [
    "Award ID", "Recipient Name", "Recipient UEI",
    "Award Amount", "Period of Performance Start Date",
    "Period of Performance Current End Date",
    "Description", "Awarding Agency", "Awarding Sub Agency",
    "Contract Award Type", "NAICS", "PSC"
  ],
  "page": 1,
  "limit": 25,
  "sort": "Period of Performance Current End Date",
  "order": "desc"
}
```

**Response shape:**
```json
{
  "spending_level": "awards",
  "limit": 3,
  "results": [
    {
      "internal_id": 347651074,
      "Award ID": "VA11817F1888",
      "Recipient Name": "DELL FEDERAL SYSTEMS L.P",
      "Recipient UEI": "N1C5QLNPJLS4",
      "Award Amount": 1730532626.58,
      "Description": "...",
      "generated_internal_id": "CONT_AWD_VA11817F1888_3600_GS35F0884P_4730"
    }
  ],
  "page_metadata": {
    "page": 1,
    "hasNext": true,
    "last_record_unique_id": 280478561,
    "last_record_sort_value": "36S79720F0009"
  },
  "messages": ["..."]
}
```

**Notes:**
- `generated_internal_id` is the durable identifier — use it as the upsert key, not `Award ID`. Format: `CONT_AWD_<piid>_<agency>_<idv_piid>_<idv_agency>` for contracts; different prefix for grants/loans.
- `messages` carries API-level warnings (date-window caps, deprecations). Log these.
- `page_metadata` switches to **cursor-based pagination after page 10**. Subsequent pages must pass `last_record_unique_id` and `last_record_sort_value` from the prior response. Don't try to deep-paginate by `page` number alone past 10.
- Filter validation is strict — `agencies[].name` must match the toptier-agency canonical name. Use `/api/v2/references/toptier_agencies/` to enumerate valid names.

**Verified live (2026-04-24):** VA + NAICS 541519 + last 24mo returned 3 hits (Four Points Tech, Dell Federal Systems $1.7B, Cellco/Verizon).

### 3.2 `POST /api/v2/recipient/` — find a recipient's USASpending hash

Recipient detail endpoints below take a USASpending-internal hash, **not** the SAM UEI. To go UEI → hash, search:

**Body:**
```json
{"keyword": "DH TECHNOLOGIES", "order": "desc", "sort": "amount", "limit": 3, "page": 1}
```

`keyword` matches against name OR UEI.

**Response per result:**
```json
{
  "id": "3b8298c2-5bfd-7fc4-bb07-ad4c20d92543-C",
  "name": "DH TECHNOLOGIES, INC.",
  "uei": "NKC2AB3ESFP5",
  "duns": null,
  "amount": 138919967,
  "recipient_level": "C"
}
```

**The `id` is `<uuid>-<level>` where level is one of:**
- `C` — child entity (the operating company; usually what you want)
- `P` — parent entity (rolled-up parent UEI)
- `R` — recipient-only (entity has no parent/child distinction)

A single UEI typically appears as both `-C` and `-P` rows when an entity is its own ultimate parent. Take `-C` for the operating-entity profile; take `-P` for parent-rolled-up financials.

### 3.3 `GET /api/v2/recipient/duns/<HASH>/` — full recipient profile

Despite the path saying `/duns/`, it accepts the USASpending hash from §3.2.

**Returned fields:** `name`, `uei`, `duns`, `parent_name`, `parent_uei`, `recipient_level`, `business_types[]` (e.g., `["service_disabled_veteran_owned_business", "small_business"]`), `total_amounts.{contract_amount, assistance_amount, transactions}`, `location.{address_line1, city, state_code, country_code, ...}`, `alternate_names[]`.

Use this to compose the "About this incumbent" panel on the pursuit detail page.

### 3.4 `POST /api/v2/subawards/` — teaming intelligence

Returns the subawards underneath a prime award. **The only public path to sub-prime relationships** — SAM Contract Awards does not surface this.

**Body:**
```json
{"award_id": "CONT_AWD_VA11817F1888_3600_GS35F0884P_4730", "limit": 25}
```

Pass the `generated_internal_id` from §3.1 as `award_id`.

**Use case for MacTech:** when scoring an opportunity, run §3.1 to identify the incumbent prime, then §3.4 to get the *list of subs already on the work*. Those subs become the immediate teaming-partner candidates if MacTech bids the recompete.

### 3.5 IDV awards — `POST /api/v2/idvs/awards/` and `POST /api/v2/idvs/funding/`

For Indefinite Delivery Vehicles (SEWP V, ITES-SW2, GSA 2GIT, NETCENTS task orders). Returns the full task-order tree under a vehicle.

**Body for `idvs/awards/`:**
```json
{"award_id": "CONT_IDV_NNG15SC70B_8000", "type": "child", "limit": 25}
```

`type` values:
- `child` — direct task orders under this IDV
- `grandchild` — task orders under child IDVs (for nested vehicles)

**Why this matters for MacTech:** James's sweet spot is $500k–$5M task orders on existing vehicles. Without IDV-tree awareness, those task orders look like isolated awards in a search; with it, MacTech can see the full $X-billion vehicle, who's winning the task orders, and which are recompetes vs. fresh issues. **This is the difference between "we missed a SEWP V task order" and "we knew about this task order class three months ago and positioned for it."**

### 3.6 `GET /api/v2/awards/<AWARD_ID>/` — single-award deep dive

Pass `generated_internal_id` (e.g., `CONT_AWD_VA11817F1888_...`). Returns the full award record including funding hierarchy, period of performance, parent IDV reference, all modifications, transaction list, executive compensation, and place of performance.

Use this for the pursuit-detail "Incumbent contract" panel — one call gets everything.

### 3.7 References (no-auth metadata)

| Endpoint | Use |
|---|---|
| `GET /api/v2/references/toptier_agencies/` | Canonical agency-name list for `agencies` filter |
| `GET /api/v2/references/naics/<NAICS_CODE>/` | NAICS hierarchy + spending stats by code |
| `GET /api/v2/references/agency/<AGENCY_ID>/` | Basic agency metadata |
| `GET /api/v2/references/award_types/` | Award type code dictionary (the A/B/C/D... map) |

Cache these aggressively — the data turns over only on government re-orgs.

### 3.8 Bulk and deferred endpoints (Phase 2+)

- `POST /api/v2/bulk_download/awards/` — generates a zip with all awards matching a filter set. Use for initial historical backfill across all 20 NAICS × all target agencies. Yields a download URL within minutes.
- `GET /api/v2/bulk_download/status/<JOB_ID>/` — poll for completion.
- `POST /api/v2/download/contract/` — single-contract zip with all transactions and modifications.

Defer until incremental ingest is stable.

---

## 4. Filter object reference (the shared schema)

All `POST /search/...` and `POST /disaster/...` endpoints accept the same filter shape (subset depending on endpoint):

```json
{
  "keywords": ["network operations"],
  "time_period": [{"start_date": "YYYY-MM-DD", "end_date": "YYYY-MM-DD", "date_type": "action_date"}],
  "place_of_performance_scope": "domestic",
  "place_of_performance_locations": [{"country": "USA", "state": "VA"}],
  "agencies": [
    {"type": "awarding|funding", "tier": "toptier|subtier", "name": "..."}
  ],
  "recipient_search_text": ["..."],
  "recipient_scope": "domestic",
  "recipient_locations": [],
  "recipient_type_names": [
    "service_disabled_veteran_owned_business",
    "small_business",
    "veteran_owned_business",
    "minority_owned_business",
    "woman_owned_business"
  ],
  "award_type_codes": ["A","B","C","D"],
  "award_ids": [],
  "award_amounts": [{"lower_bound": 100000, "upper_bound": 10000000}],
  "naics_codes": ["541519", "541512"],
  "psc_codes": ["D316"],
  "contract_pricing_type_codes": ["J"],
  "set_aside_type_codes": ["SDVOSBC"],
  "extent_competed_type_codes": ["A","B","C","D","E","F","G"],
  "tas_codes": [],
  "def_codes": []
}
```

`date_type` values: `action_date` (when the action was taken), `last_modified_date`, `date_signed`, `new_awards_only`. Default is `action_date`.

---

## 5. Award type codes

| Code | Meaning |
|---|---|
| `A` | BPA Call |
| `B` | Purchase Order |
| `C` | Delivery Order |
| `D` | Definitive Contract |
| `IDV_A` | Government-Wide Acquisition Contract (GWAC) |
| `IDV_B` | Indefinite Delivery Contract (IDC) |
| `IDV_B_A` | IDC — Indefinite Delivery / Indefinite Quantity |
| `IDV_B_B` | IDC — Indefinite Delivery / Definite Quantity |
| `IDV_B_C` | IDC — Indefinite Delivery / Requirements |
| `IDV_C` | Federal Supply Schedule (FSS / GSA Schedule) |
| `IDV_D` | BOA — Basic Ordering Agreement |
| `IDV_E` | BPA — Blanket Purchase Agreement |
| `02–11` | Various assistance / grant / loan codes (not used by MacTech) |

For MacTech's contract-only pipeline, filter to `["A","B","C","D"]` for transaction-level work and `["IDV_A","IDV_B","IDV_C","IDV_D","IDV_E", ...]` for vehicle-level work.

---

## 6. The chained workflows MacTech runs

### Chain 1 — Incumbent detection (alternative path to SAM Contract Awards)
SAM Opportunity → §3.1 spending_by_award filtered by NAICS + awarding agency + last 24 mo + `award_type_codes=["A","B","C","D"]`, sorted by `Period of Performance Current End Date` desc → top result whose end-date straddles or precedes the new opp's posted date is the incumbent. Persist `(incumbent_uei, incumbent_recipient_hash, incumbent_award_generated_id)`.

**When to use this over SAM Contract Awards Chain 2:** when the target opportunity is at a DoD agency and was awarded fewer than 90 days ago — SAM Contract Awards veils that data for our personal key tier; USASpending does not.

### Chain 2 — Recipient deep-dive (incumbent → profile)
§3.2 with `keyword=<incumbent_uei>` → take `id` of the `-C` entity → §3.3 for full profile → drives the "About this incumbent" panel and feeds Apify's incumbent-distress signal worker (per `docs/APIFY_STRATEGY.md` §3.3).

### Chain 3 — Teaming graph
§3.1 to find the prime award → use `generated_internal_id` → §3.4 subawards → list of all subs on the prime contract → cross-reference each sub UEI against MacTech's teaming-partner allowlist + SAM Exclusions → ranked teaming candidates for the recompete pursuit.

### Chain 4 — Vehicle awareness (James's lane)
For each MacTech-relevant IDV (SEWP V, ITES-SW2, NETCENTS, GSA 2GIT, Schedule 70):
1. §3.1 with `award_type_codes=["IDV_A","IDV_B","IDV_C"]` + agency filter to find the IDV's `generated_internal_id`.
2. §3.5 `idvs/awards/` with that ID + `type=child` → all current task orders under the vehicle.
3. Surface in the dashboard "Vehicle Pulse" panel with task-order counts, dollar volume, and which primes are winning each task-order class.

### Chain 5 — Recompete radar (alternative to SAM Contract Awards)
§3.1 with NAICS filter + `time_period.date_type=action_date` + `award_amounts.lower_bound=100000`, sorted by `Period of Performance Current End Date` ascending, filter rows where end date is in next 12 months. Same goal as SAM Contract Awards Chain 3 — runs as backup when SAM rate budget is tight, since USASpending has no daily cap.

---

## 7. Implementation notes for Phase 1 Week 3

- **Client:** `httpx.AsyncClient` with `tenacity` retry; `User-Agent: MacTechCaptureOS/0.1` set on every request.
- **Polite throttle:** `asyncio.Semaphore(1)` + 1 request/second cap, backoff on 429 with exponential jitter (cap 60s).
- **Pagination:**
  - First 10 pages: increment `page`.
  - Page 11+: pass `last_record_unique_id` and `last_record_sort_value` from prior response. Implement a single `paginate(filter_body, sort_field)` helper that handles both modes.
- **Idempotent upserts:** key on `generated_internal_id` (the `CONT_AWD_*` durable string), not on `internal_id` (which can drift between snapshots).
- **Date format awareness:** USASpending takes ISO `YYYY-MM-DD`. SAM takes `MM/DD/YYYY`. Wrap your filter builders with explicit date converters; do not pass user-input dates through unchanged.
- **Cross-source recipient join:** `Recipient UEI` field from §3.1 is the clean join key against SAM's `awardeeUEIInformation.uniqueEntityId`. Both sources use the 12-character SAM UEI; USASpending's hash is internal-only, never mix it with SAM data.
- **Messages logging:** persist the `messages[]` from every response into a small `usaspending_messages` table for review. Most are date-window deprecation warnings, but new ones occasionally carry breaking-change notice.
- **Bulk download for backfill:** for the initial 5-year MacTech-NAICS backfill across target agencies, use `bulk_download/awards/` with `request.filters` matching our scoring scope. Single zip beats 50,000 paginated calls.
- **DoD freshness rule:** when a SAM-side incumbent lookup returns null and the opp is DoD-affiliated, fall through to USASpending (no veil). Worker code path:
  ```
  incumbent = sam_contract_awards.find_incumbent(opp)
  if incumbent is None and opp.is_dod():
      incumbent = usaspending.find_incumbent(opp)
  ```
- **No CUI ever flows out.** USASpending is read-only and we don't push anything to it. The compliance posture is the same as SAM.gov — public read, no upload.
- **`award_type_codes` defaults:** Phase 1 always includes `["A","B","C","D"]`. Add IDV codes only when querying for vehicle-tree work (Chain 4).
- **Earliest synchronous date:** **2007-10-01.** For backfills older than that, use the bulk download path (which goes back to 2000-10-01).

---

## 8. SerpAPI sidebar (where it complements USASpending + SAM)

SerpAPI handles the open-web augmentation that neither USASpending nor SAM carries: contracting-officer LinkedIn presence, agency industry-day announcements, incumbent-company news/financial-distress signals, and brand monitoring. Implementation lives in `packages/integrations/serpapi/` (Phase 2). Key in `.env` and Railway env. **Verified working 2026-04-24** — query for "NIWC Atlantic industry day 2026" returned the 2026 Navy Information Warfare Industry Day on AFCEA's site plus an SAM.gov IWRP industry-day notice. Cache results 7 days; never use for automated outbound; human-reviewed only per `docs/POSITIONING.md`.

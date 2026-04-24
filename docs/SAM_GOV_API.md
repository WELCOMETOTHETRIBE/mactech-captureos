# SAM.gov API — Integration Brief

Practical notes for MacTech CaptureOS. Grounded in live calls against MacTech's production key on 2026-04-24. Complements `docs/DATA_SOURCES.md`.

---

## 1. The two "styles" — what they actually are

SAM.gov publishes **two different APIs that both carry the word "Opportunities"** in their names. They look similar, serve opposite audiences, and require different credentials. Don't mix them up.

### Style A — Get Opportunities Public API *(this is what MacTech uses)*

**What it is:** Read-only REST search across all published federal contract opportunities. Buyers publish via Style B; vendors (us) search via Style A.

**Audience:** Vendors, BD teams, researchers, analytics platforms. Us.

**Endpoint:** `GET https://api.sam.gov/opportunities/v2/search`
**Alpha / sandbox:** `GET https://api-alpha.sam.gov/opportunities/v2/search`
**Method:** GET only.
**Auth:** public API key as `api_key=...` query param.
**Rate limit (observed/documented):** ~1,000 req/day for non-federal registered users; 10/day unauthenticated; 10,000/day for federal system accounts. Rate-limit header behavior is undocumented, so we cap ourselves client-side.
**Key docs:** [open.gsa.gov/api/get-opportunities-public-api](https://open.gsa.gov/api/get-opportunities-public-api/)

**Required query params:**
- `api_key`
- `postedFrom` — `MM/dd/yyyy` (NOT ISO 8601)
- `postedTo` — `MM/dd/yyyy`, max 1-year range

**Useful optional params:**

| Param | Meaning | Example |
|---|---|---|
| `ncode` | NAICS code (up to 6 digits) | `541519` |
| `typeOfSetAside` | Set-aside code | `SDVOSBC`, `SDVOSBS`, `VSA`, `VSS`, `SBA`, `SBP`, `SB`, `8A`, `WOSB`, `HZC`, etc. |
| `ptype` | Procurement/notice type | `o` Solicitation, `p` Presolicitation, `r` Sources Sought, `s` Special Notice, `k` Combined Synopsis, `a` Award, `u` Justification, `g` Sale of Surplus |
| `limit` | Records per page, 0–1000 (default 1) | `1000` |
| `offset` | Page index (default 0) | `0` |
| `deptname`, `orgKey`, `organizationName` | Agency filters | `DEPARTMENT OF THE NAVY` |
| `state`, `zip` | Place-of-performance filters | `VA`, `22060` |
| `rdlfrom`, `rdlto` | Response deadline window (MM/dd/yyyy, ≤1yr) | |
| `solnum` | Solicitation number | |
| `noticeid` | Fetch one specific notice | |
| `title` | Title substring | |

**Response top-level:**
```
{
  "totalRecords": int,
  "limit": int,
  "offset": int,
  "opportunitiesData": [ { ... } ],
  "links": [ { "rel": "self", "href": "..." } ]
}
```

**Per-opportunity fields** (verified in our test calls):
`noticeId`, `title`, `solicitationNumber`, `fullParentPathName`, `fullParentPathCode`, `postedDate`, `type`, `baseType`, `archiveType`, `archiveDate`, `typeOfSetAsideDescription`, `typeOfSetAside`, `responseDeadLine`, `naicsCode`, `naicsCodes[]`, `classificationCode`, `active`, `award` *(only on Award notices — includes `date`, `number`, `amount`, `awardee.{name, location, ueiSAM, cageCode}`)*, `pointOfContact[]`, `description` *(this is a URL, not text — see below)*, `organizationType`, `officeAddress`, `placeOfPerformance`, `additionalInfoLink`, `uiLink`, `links[]`, `resourceLinks`.

### Style B — Opportunity Management API *(NOT for MacTech)*

**What it is:** Full CRUD — contracting officers create, amend, publish, cancel, and archive opportunities through this API.

**Audience:** Federal contracting officers, COR/COTR staff, procurement systems.

**Endpoints:** `/opportunities/{v1|v2|v3}/create`, `/publish/{opportunityId}`, `/update/{opportunityId}`, `/search`, `/{opportunityId}`, `/delete/...`, plus resource/attachment management and vendor list access.

**HTTP methods:** `POST`, `PATCH`, `GET`, `DELETE`.

**Auth:** Federal SAM.gov **system account** + authorized IP allowlist + separate API key. Can't be obtained without a `.gov` or `.mil` email, and issuance is gated.

**Docs:** [open.gsa.gov/api/opportunities-api](https://open.gsa.gov/api/opportunities-api/)

**Why it matters to us:** zero. We do not publish opportunities; we react to them. It's listed here so the next developer doesn't accidentally try to use its `POST /create` endpoint when all they wanted was `GET /search`.

---

## 2. The chained fetches — there is no single "give me everything" call

Style A's search response does **not** include the full SOW / PWS / Section L/M text. Instead, each record gives us a `description` field that is **itself a URL** pointing at a separate endpoint:

```
GET https://api.sam.gov/prod/opportunities/v1/noticedesc?noticeid=<noticeId>&api_key=<key>
```

That endpoint returns `{"description": "..."}`. In practice the text is often just `"See attachment"` — the real SOW lives in a PDF or DOCX attached to the opportunity, retrievable via `resourceLinks[]` on the search record.

**What that means for our ingestion pipeline:**

1. **Search worker** hits `/opportunities/v2/search`, upserts everything into `opportunities_raw`. (One API call per NAICS per polling interval.)
2. **Description worker** walks new rows and fetches the `noticedesc` endpoint, stores the text in `opportunities_raw.description_text` (add this column in Week 2).
3. **Attachment worker** (Week 9) walks `resourceLinks[]`, downloads PDFs/DOCX, parses with pdfplumber/python-docx, stores parsed text on the `documents` table.

Budgeting: for ~500 NAICS-matched opps/week, that's ~500 search calls + ~500 description calls + N attachment downloads. Well under the 1,000/day cap because we batch by NAICS, not by record.

---

## 3. Siblings in the SAM.gov ecosystem (all same auth, separate endpoints)

Same API key works across all of these — these are not "styles" of the Opportunities API, but adjacent APIs we use for enrichment.

| Name | URL | What we use it for |
|---|---|---|
| Entity Management | `GET https://api.sam.gov/entity-information/v3/entities?ueiSAM=...` | Soliciting office details, teaming-partner verification, competitor UEI lookups. **Verified working.** |
| Exclusions | `GET https://api.sam.gov/entity-information/v4/exclusions?ueiSAM=...` | Pre-submit debarment screen. Gates pursuit stage "Submit". |
| Contract Awards | `GET https://api.sam.gov/contract-awards/v1/search` | Historical awards (parallel to USASpending). Use USASpending as primary, Contract Awards as fallback/cross-check. |
| Notice Description | `GET https://api.sam.gov/prod/opportunities/v1/noticedesc?noticeid=...` | Full opp description (chained from Search — see §2). |

---

## 4. Bulk data path (different delivery mechanism, not a different API)

The REST search API returns **metadata** only. For full historical or full-description data without burning per-call budget, SAM publishes bulk dumps at:

- **Active opportunities:** https://sam.gov/data-services?domain=Contract%20Opportunities%2Fdatagov
- **Archived:** https://sam.gov/data-services?domain=Contract%20Opportunities%2FArchived%20Data

These are CSV/JSON files downloaded manually (or via scheduled `curl`) — not a REST API. Not needed for Phase 1. Revisit if our rate-limit budget gets tight when we add Voyage embeddings against the full description corpus in Phase 2.

---

## 5. MacTech profile query — confirmed working

On 2026-04-24 with MacTech's key:

```bash
curl -sS "https://api.sam.gov/opportunities/v2/search?api_key=$SAM_API_KEY\
&postedFrom=03/25/2026&postedTo=04/24/2026\
&ncode=541519&typeOfSetAside=SDVOSBC&limit=3"
```

Returned **14 records** — all real Navy / VA / civilian cyber opportunities. Example hits:

- Combined Synopsis/Solicitation — "DB10 — VA Long Beach Real Time Location System" (SDVOSBC, NAICS 541519)
- Solicitation — "Camunda Enterprise Software Licensing" (SDVOSBC, NAICS 541519)
- Award Notice — "VISN 5 Video Surveillance and Physical Access" (SDVOSBC, NAICS 541519, awardee CAGE 6XKC9)

Set-aside counts for NAICS 541519 Jan–Apr 2026 with MacTech's allowlist:

| Set-aside | Count |
|---|---|
| SDVOSBC | 17 |
| SDVOSBS | 1 |
| VSA | 3 |
| VSS | 0 |
| SBA | 25 |
| SBP | 1 |
| SB | 0 |

Pool is healthy for daily digests on just the security pillar's primary NAICS. Patrick's threshold at 70 across five NAICS should yield comfortably more than 5 candidates/day for the morning digest.

---

## 6. Implementation notes for Week 2

- **Paginate defensively.** Client loops `offset` by `limit` until `offset >= totalRecords` OR no records returned.
- **Batch by NAICS, not by opportunity.** One search call per NAICS per polling tick — 20 NAICS × 12 calls/day = 240/day. Well under the 1000/day cap.
- **Idempotent upsert on `noticeId`.** It is the documented primary key across all of SAM.gov's opp-related APIs, including the `noticeid` query param on every sibling endpoint.
- **Store `raw_payload` as JSONB.** The API schema gains fields without warning. We persist the full response and project columns on read.
- **Backoff on HTTP 429.** Documented rate limits exist but SAM.gov does not return `Retry-After`. Use exponential backoff with jitter, max 60s.
- **Date window discipline.** `postedFrom`/`postedTo` must be MM/dd/yyyy, max 1-year window. On backfill, chunk the year into quarters.
- **Phase 1 does not need the attachment pipeline.** Week 2 stops at search + description text. Attachments come in Phase 1 Week 9 per `docs/ROADMAP.md`.

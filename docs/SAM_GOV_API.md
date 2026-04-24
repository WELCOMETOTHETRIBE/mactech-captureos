# SAM.gov API — Integration Brief

Practical notes for MacTech CaptureOS. Grounded in live calls against MacTech's production key on 2026-04-24. Complements `docs/DATA_SOURCES.md`.

---

## 1. The two API styles MacTech consumes

SAM.gov publishes ~ten REST APIs. Two of them carry MacTech's whole pipeline. Treat the rest (Entity Management, Exclusions) as enrichment helpers, not primary feeds.

| | **Style A — Get Opportunities Public API** | **Style B — Contract Awards API** |
|---|---|---|
| **What it carries** | Active solicitations, presolicitations, sources sought, combined synopses, special notices, award notices for *new* opportunities. The forward-looking pipeline. | Historical contract awards and indefinite-delivery vehicles (BPAs, IDIQs). The backward-looking record of what was bought from whom and when. |
| **Endpoint** | `GET https://api.sam.gov/opportunities/v2/search` | `GET https://api.sam.gov/contract-awards/v1/search` |
| **Alpha/sandbox** | `api-alpha.sam.gov/opportunities/v2/search` | `api-alpha.sam.gov/contract-awards/v1/search` |
| **Auth** | `api_key=` query param | `api_key=` query param |
| **Required params** | `postedFrom`, `postedTo` (MM/dd/yyyy, ≤1yr range) | At least one filter; commonly `lastModifiedDate` or `dateSigned` |
| **Date range cap** | 1 year per call | 1 year per call |
| **Default page size** | 1 | 10 |
| **Max page size (`limit`)** | 1000 | 100 |
| **Pagination cap** | (none documented) | `offset × limit ≤ 400,000` synchronous |
| **Async extract** | No | Yes — `format=json\|csv` up to 1M records, optional email delivery |
| **Multi-value param syntax** | Single value per param | Tilde-separated, max 100 (e.g. `naicsCode=541519~541512~518210`) |
| **Range syntax** | N/A | `[low,high]` for dates and dollars |
| **Forbidden chars in values** | None documented | `& \| { } ^ \\` — return HTTP 400 |
| **What it answers for MacTech** | "What just got posted that we should pursue?" | "Who already has work like this — and when does their contract end?" |

**The single most important workflow** uses both: Style A surfaces a new opportunity → Style B finds the most recent matching award (NAICS + agency, contract not yet expired) → that's the incumbent. Style A alone misses everything that matters about a recompete; Style B alone misses what's actually being procured right now. **MacTech's scoring engine reads from both and the morning digest joins them.**

**What we do NOT use:** the **Opportunity Management API** (`api.sam.gov/opportunities/{v1\|v2\|v3}/create\|publish\|update`) — that's CRUD for federal contracting officers publishing opportunities, gated by federal `.gov`/`.mil` system accounts and IP allowlists. We're consumers, not publishers.

---

## 2. Style A — Get Opportunities Public API

**Docs:** [open.gsa.gov/api/get-opportunities-public-api](https://open.gsa.gov/api/get-opportunities-public-api/)

### Required & most-used params

| Param | Example | Notes |
|---|---|---|
| `api_key` | `SAM-...` | Required |
| `postedFrom` | `04/01/2026` | MM/dd/yyyy required; max 1-year span with `postedTo` |
| `postedTo` | `04/24/2026` | Inclusive |
| `limit` | `1000` | Default 1, max 1000 |
| `offset` | `0` | 0-indexed |
| `ncode` | `541519` | NAICS, 6-digit max |
| `typeOfSetAside` | `SDVOSBC` | See full enum below |
| `ptype` | `o`, `r`, `k` | Notice type — see enum |
| `state`, `zip` | `VA`, `22060` | Place of performance |
| `organizationName` | `DEPARTMENT OF THE NAVY` | Replaces deprecated `deptname` / `subtier` |
| `rdlfrom` / `rdlto` | `04/01/2026` | Response deadline window, ≤1yr |
| `solnum`, `noticeid`, `title` | | Direct lookups |
| `status` | `active`, `inactive`, `archived`, `cancelled`, `deleted` | (marked "Coming Soon" in docs but works) |

### Procurement type codes (`ptype`)

| Code | Meaning |
|---|---|
| `r` | Sources Sought |
| `p` | Presolicitation |
| `o` | Solicitation |
| `k` | Combined Synopsis/Solicitation |
| `s` | Special Notice |
| `a` | Award Notice |
| `u` | Justification (J&A) |
| `g` | Sale of Surplus Property |
| `i` | Intent to Bundle Requirements (DoD-Funded) |

**Retired codes:** `f` (Foreign Government Standard), `l` (Fair Opportunity / Limited Sources).

### Set-aside codes (`typeOfSetAside`) — full list

| Code | Description |
|---|---|
| `SBA` | Total Small Business Set-Aside (FAR 19.5) |
| `SBP` | Partial Small Business Set-Aside (FAR 19.5) |
| `8A` | 8(a) Set-Aside (FAR 19.8) |
| `8AN` | 8(a) Sole Source (FAR 19.8) |
| `HZC` | HUBZone Set-Aside |
| `HZS` | HUBZone Sole Source (FAR 19.13) |
| `SDVOSBC` | SDVOSB Set-Aside |
| `SDVOSBS` | SDVOSB Sole Source (FAR 19.14) |
| `WOSB` | WOSB Program Set-Aside |
| `WOSBSS` | WOSB Sole Source (FAR 19.15) |
| `EDWOSB` | EDWOSB Program Set-Aside |
| `EDWOSBSS` | EDWOSB Sole Source (FAR 19.15) |
| `LAS` | Local Area Set-Aside (FAR 26.2) |
| `IEE` | Indian Economic Enterprise Set-Aside (DoI) |
| `ISBEE` | Indian Small Business Economic Enterprise Set-Aside |
| `BICiv` | Buy Indian Set-Aside (HHS Indian Health Services) |
| `VSA` | VA Veteran-Owned Small Business Set-Aside |
| `VSS` | VA Veteran-Owned Sole Source |

MacTech's allowlist (per `config/mactech_tenant_defaults.yml`): `SDVOSBC, SDVOSBS, VSA, VSS, SBA, SBP, SB`. Excluded: `8A, 8AN, HZC, HZS, WOSB, EDWOSB`.

### Response shape (top level)

```json
{
  "totalRecords": 14,
  "limit": 3,
  "offset": 0,
  "opportunitiesData": [ { ... } ],
  "links": [ { "rel": "self", "href": "..." } ]
}
```

### Per-opportunity fields (verified live)

`noticeId`, `title`, `solicitationNumber`, `fullParentPathName`, `fullParentPathCode`, `postedDate`, `type`, `baseType`, `archiveType`, `archiveDate`, `typeOfSetAsideDescription`, `typeOfSetAside`, `responseDeadLine`, `naicsCode`, `naicsCodes[]`, `classificationCode`, `active`, `award` *(only on Award notices — `date`, `number`, `amount`, `awardee.{name, location, ueiSAM, cageCode}`)*, `pointOfContact[]`, `description` *(this is a URL, not text — see §4)*, `organizationType`, `officeAddress`, `placeOfPerformance`, `additionalInfoLink`, `uiLink`, `links[]`, `resourceLinks[]`.

---

## 3. Style B — Contract Awards API

**Docs:** [open.gsa.gov/api/contract-awards](https://open.gsa.gov/api/contract-awards/)

### Required & most-used params

| Param | Example | Purpose |
|---|---|---|
| `api_key` | `SAM-...` | Required |
| `dateSigned` | `[01/01/2026,04/24/2026]` | When the contract action was signed; range syntax `[low,high]` |
| `lastModifiedDate` | `[04/01/2026,04/24/2026]` | Best for incremental ingestion (when SAM.gov last touched the record) |
| `naicsCode` | `541519` or `541519~541512~518210~541513` | Up to 100 tilde-separated |
| `awardOrIDV` | `Award` or `IDV` | Separates contracts from indefinite-delivery vehicles |
| `awardOrIDVTypeCode` / `Name` | `B` / `PURCHASE ORDER`, `DELIVERY ORDER`, `BPA CALL`, etc. | Action-type filter |
| `contractingDepartmentName` | `VETERANS AFFAIRS` | Substring match against agency |
| `fundingDepartmentName` | `DEFENSE` | Funding source (≠ contracting org for transferred funds) |
| `awardeeUniqueEntityId` | `NKC2AB3ESFP5` (or `~` list) | Recipient lookup |
| `ultimateParentUniqueEntityId` | | Parent company portfolio |
| `dollarsObligated` | `[100000,99999999]` | Single action obligation |
| `totalDollarsObligated` | `[1000000,99999999]` | Aggregate across mods |
| `ulitmateCompletionDate` *(sic — typo is in the API)* | `[04/24/2026,04/24/2027]` | Recompete-window radar |
| `currentCompletionDate` | (range) | The award's currently-set end date |
| `typeOfSetAsideCode` | `SDVOSBC` | Same enum as Opportunities |
| `extentCompetedCode` | `B`, `C`, etc. | "NOT COMPETED" / "FULL AND OPEN" / etc. — useful for sole-source spotting |
| `productOrServiceCode` | `D316` | PSC (a.k.a. FSC) |
| `placeOfPerformStateCode` | `VA` | |
| `fiscalYear` | `2024` | |
| `piid` / `modificationNumber` | | Direct contract lookup |
| `q` | free text | Full-text search |
| `limit` | `100` | Default 10, max 100 |
| `offset` | `0` | `offset × limit ≤ 400,000` |
| `includeSections` | `contractId,coreData,awardDetails,awardeeData,nasaSpecific` | Field-projection. Omit to get all sections |
| `format` | `json` or `csv` | Triggers async extract (up to 1M records) |
| `emailId` | `Yes` | Pair with `format` to email a download link |
| `piidAggregation` | `yes` | Roll up an IDV's task orders into one summary |
| `deletedStatus` | `yes` | Returns contracts deleted in last 6 months only |

### Response shape (top level)

```json
{
  "totalRecords": 922,
  "limit": 3,
  "offset": 0,
  "awardSummary": [ { ... } ]
}
```

### Per-award structure (deeply nested)

```
awardSummary[i]:
  contractId.{ piid, modificationNumber, transactionNumber, subtier, referencedIDV* , reasonForModification }
  coreData.{
    awardOrIDV, awardOrIDVType,
    federalOrganization.contractingInformation.{ contractingDepartment, contractingSubtier, contractingOffice },
    federalOrganization.fundingInformation.{ fundingDepartment, fundingSubtier, fundingOffice, foreignFunding },
    productOrServiceInformation.{ principalNAICSCode, productOrServiceCode, ... },
    competitionInformation,
    principalPlaceOfPerformance,
    legislativeMandates,
    acquisitionData
  }
  awardDetails.{
    dates.{ dateSigned, periodOfPerformanceStartDate, currentCompletionDate, ultimateCompletionDate, lastDateToOrder, fiscalYear },
    dollars.{ actionObligation, baseDollarsObligated, baseAndExercisedOptionsValue, baseAndAllOptionsValue, ... },
    totalContractDollars.{ totalActionObligation, totalBaseAndExercisedOptionsValue, totalBaseAndAllOptionsValue },
    awardeeData.{
      awardeeHeader.{ awardeeName, legalBusinessName, doingBusinessAsName, ... },
      awardeeUEIInformation.{ uniqueEntityId, cageCode, awardeeUltimateParentUniqueEntityId, awardeeUltimateParentName, awardeeImmediateParentUEI/Name (unrevealed only) },
      awardeeLocation.{ streetAddress1, city, state, zip, country, congressionalDistrict, ... },
      awardeeBusinessTypes.{ ... },
      socioEconomicData.{ smallBusiness, veteranOwnedBusiness, serviceDisabledVeteranOwnedBusiness, isMinorityOwnedBusiness, womenOwnedBusiness, ... },
      certifications.{ sbaCertified8aProgramParticipant, sbaCertifiedHubZoneFirm, sbaCertifiedSmallDisadvantagedBusiness, sbaCertifiedWomenOwnedSmallBusiness, ... },
      organizationFactors,
      lineOfBusiness,
      relationshipWithFederalGovernment
    },
    nasaSpecificData (NASA contracts only),
    transactionData.{ status, version, createdBy, createdDate, lastModifiedBy, lastModifiedDate, approvedBy, approvedDate, closedBy, closedDate, closedStatus }
  }
  oldContractId[]
```

### Revealed vs. unrevealed data — the DoD 90-day rule

Two visibility tiers, controlled by your API key's role:

| Data class | Personal (us) | DoD federal system account |
|---|---|---|
| Civilian agency contracts | ✓ | ✓ |
| DoD contracts ≥90 days old | ✓ | ✓ |
| **DoD contracts <90 days old** | ✗ | ✓ |
| **Awardee parent UEI/name** | ✗ (only ultimate parent) | ✓ |

For MacTech in Phase 1 this means: **DoD recompete intel from the Contract Awards API runs on a 90-day delay.** Compensate by using the Opportunities API's Award Notices (`ptype=a`), which surface DoD awards immediately, and reconcile downstream once Contract Awards catches up.

### Verified test calls (2026-04-24)

```
NAICS 541519 + VA + last 90 days        →  922 contracts
DH Technologies UEI, last 24 months      →  1,458 contracts
NAICS 541519/541512/518210/541513,
    contracts ending 4/26 to 4/27,
    obligated > $100k                    →  recompete radar working
```

---

## 4. The chained fetches MacTech actually runs

### Chain 1 — Opportunity ingest with full description (Style A → Style A)

Style A's search returns a `description` field that is **a URL, not text**. The full description lives at:
```
GET https://api.sam.gov/prod/opportunities/v1/noticedesc?noticeid=<noticeId>&api_key=<key>
```
Returns `{"description": "..."}`. Often the body is `"See attachment"` and the real SOW is in `resourceLinks[]` PDFs/DOCX.

### Chain 2 — Incumbent detection (Style A → Style B) — *the one that matters*

Workflow:
1. Style A returns a new opp on NAICS 541519 + VA + SDVOSBC (Patrick's profile).
2. Style B query: `naicsCode=541519&contractingDepartmentName=VETERANS AFFAIRS&typeOfSetAsideCode=SDVOSBC&dateSigned=[<24mo ago>,<today>]&ulitmateCompletionDate=[<today>,<today+24mo>]`.
3. Top result by `dateSigned DESC` whose `currentCompletionDate` straddles or precedes the new opp's posted date is the incumbent.
4. Persist `(opportunity_id, incumbent_uei, incumbent_legal_name, incumbent_contract_piid, incumbent_end_date)` into `opportunities_enriched`.
5. Run Style B again with `awardeeUniqueEntityId=<uei>` for portfolio context — feeds the "Why this matters" paragraph.

This chain is the difference between a digest that says *"new VA opp posted"* and one that says *"new VA opp posted; incumbent is DH Technologies whose contract ends in 11 months and they just lost a similar Navy recompete"* — the kind of intel a captured BD team writes the proposal off of.

### Chain 3 — Recompete radar (Style B alone, scheduled)

Daily Celery job: `naicsCode=<MacTech 20>&ulitmateCompletionDate=[<today>,<today+12mo>]&dollarsObligated=[100000,inf]`. Persist hits in a `recompete_watch` table; surface in Monday rollup digest as "20 contracts in your NAICS expire in the next 12 months."

### Chain 4 — Pre-submit exclusions (Style B → Exclusions API)

Before pursuit advances to "Submit", iterate every UEI in the proposal team and call `api.sam.gov/entity-information/v4/exclusions?ueiSAM=<uei>`. Block on any active exclusion.

---

## 5. Sibling APIs (same key, narrower roles)

| API | URL | What we use it for |
|---|---|---|
| Entity Management | `GET https://api.sam.gov/entity-information/v3/entities?ueiSAM=...` | Soliciting-office details, teaming-partner verification, competitor lookup. **Verified working.** |
| Exclusions | `GET https://api.sam.gov/entity-information/v4/exclusions?ueiSAM=...` | Pre-submit debarment screen — gates the "Submit" stage transition |
| Notice Description | `GET https://api.sam.gov/prod/opportunities/v1/noticedesc?noticeid=...` | Full opp description text (Chain 1) |

### Bulk data path

The REST APIs return metadata. For full historical or full-description harvesting without burning per-call budget, SAM publishes bulk dumps at:
- Active: https://sam.gov/data-services?domain=Contract%20Opportunities%2Fdatagov
- Archived: https://sam.gov/data-services?domain=Contract%20Opportunities%2FArchived%20Data

CSV/JSON files downloaded manually or via cron — not a REST API. Not needed for Phase 1.

---

## 6. Rate limits — both styles

| User class | Daily limit |
|---|---|
| Non-federal, no role | 10 / day |
| Non-federal with role *(MacTech)* | 1,000 / day |
| Federal user (personal key) | 1,000 / day |
| Non-federal system account | 1,000 / day |
| Federal system account | 10,000 / day |

Limits are **per-API per-day**, not aggregated. Opportunities and Contract Awards each get their own 1,000/day budget at MacTech's tier. Total addressable budget at Phase 1: ~2,000 calls/day across both styles plus more for siblings.

**Budget plan at Phase 1 volume (4 founders, 20 NAICS):**

| Source | Cadence | Calls/day |
|---|---|---|
| Opportunities — incremental search by NAICS | 12× per day × 20 NAICS, batched | ~30 |
| Opportunities — `noticedesc` chained fetches | once per new record | ~50 |
| Contract Awards — incumbent detection | once per new opp | ~50 |
| Contract Awards — daily recompete radar | 1× per day × 4 NAICS clusters | ~5 |
| Entity / Exclusions | on-demand at pursuit-stage transitions | ~10 |
| **Total** | | **~145 / day** |

Comfortably under the 1,000/day per-API cap. Headroom for the digest + ad-hoc queries.

---

## 7. Implementation notes for Phase 1 Week 2

- **Use `httpx.AsyncClient` with `tenacity`** for both Style A and Style B clients. Single shared rate-limit semaphore per API (tokens regenerate at 1000/day each).
- **`curl -g`/Python equivalent** — never let URL globbing eat the `[range,range]` syntax. Use `httpx`'s `params={...}` or pre-encode brackets as `%5B`/`%5D`.
- **Forbidden chars** — Style B rejects `& | { } ^ \` in any value. Validator at boundary; reject early.
- **Multi-NAICS efficiency** — batch with `~`-separated lists (max 100) on Style B, but Style A only takes one `ncode` per call. Phase 1 fan-out is one Style A call per NAICS.
- **Idempotent upserts:**
  - Style A: `(source='sam_gov', source_id=noticeId)`.
  - Style B: `(source='sam_gov_awards', source_id=piid + '|' + modificationNumber)` — one row per modification, not per contract.
- **Pagination discipline:** Style A loops `offset += limit` until `offset >= totalRecords`. Style B has the additional `offset × limit ≤ 400,000` synchronous cap — for any window producing more than that, switch to `format=csv` async extract.
- **`includeSections` discipline on Style B** — fetching all sections is a heavy payload. For incumbent detection, `includeSections=contractId,awardDetails` is enough. For full enrichment, add `coreData,awardeeData`.
- **Date-window discipline:** both APIs cap at 1 year. For 30-day backfills, single window. For multi-year competitor portfolio, chunk into 12-month windows in code.
- **Incremental ingestion:** Style A use `postedFrom = last_successful_run`. Style B use `lastModifiedDate = [last_successful_run, today]` — `lastModifiedDate` catches modifications and corrections to existing awards, which `dateSigned` does not.
- **`raw_payload jsonb`** — both APIs evolve; persist full responses.
- **DoD 90-day veil compensation:** when scoring DoD opps, allow Style B incumbent enrichment to be `null` for the first 90 days; reconcile via a daily "fill in DoD incumbents" job that re-queries any opp whose `incumbent_uei` is null and posted_date is older than 95 days.
- **Exponential backoff on 429** — neither API documents `Retry-After`. Use jittered exponential backoff capped at 60s.

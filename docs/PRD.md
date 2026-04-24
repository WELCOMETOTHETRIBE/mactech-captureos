# Product Requirements — MacTech CaptureOS

## 1. Vision

An AI-native GovCon revenue operations platform that turns public federal contracting data into won contracts — first for MacTech Solutions (internal BD engine), then for DIB contractors as SaaS.

## 2. Why now

Incumbents (Deltek GovWin IQ $15k+/yr, Bloomberg Government, HigherGov) sell data access. None of them sell *outcomes*. The 2026 unlock is LLM-powered automation of the capture workflow itself — compliance matrix generation, Sources Sought drafting, proposal shred-outs, incumbent intelligence — built natively into the pipeline rather than bolted on.

## 3. Users

### 3.1 Primary users (internal, Year 1)

The four MacTech founders. Each has a pillar and a NAICS footprint. When an opportunity arrives, the system auto-routes based on NAICS match → pillar assignment.

| Founder | Pillar | Primary NAICS they own |
|---|---|---|
| Patrick Caruso | Security | 541519, 541512, 541513, 518210 |
| James Adams | Infrastructure | 518210, 541330, 541512, 541513 |
| Brian MacDonald | Quality | 541380, 541614, 541611 |
| John Milso | Governance | 541110, 541611, 541618, 541199 |

### 3.2 Secondary users (external, Year 2+)

- **Solo SDVOSB / small-business primes** — $199/mo tier, opportunity feed + basic pipeline
- **Small primes 5–50 employees** — $599/mo tier, full pipeline + AI drafting + intel
- **Mid-market primes 50–500 employees** — $1,499/mo tier, multi-user, API, compliance automation
- **Large primes / PE-backed** — $5k–$25k/mo, white-glove, custom NAICS tuning, managed capture
- **Standalone CMMC buyers** — $5k–$25k engagement + optional monitoring retainer (cross-sell into CaptureOS)

## 4. Revenue lines

### 4.1 Line Zero — MacTech direct wins (Months 0–∞)
The tool is our own BD engine. Every opportunity scored, pursued, and won by MacTech is Revenue Line Zero. Year 1 target: $1M+ in MacTech contract revenue attributable to platform-surfaced opportunities.

### 4.2 Line 1 — Managed Capture + CMMC services (Month 1)
Human-delivered, tool-augmented. Our experts run a client's capture pipeline and/or prepare their CMMC artifacts.
- Pricing: $15k–$40k/mo retainers OR $10k–$50k fixed-scope engagements
- Year 1 target: $150k–$400k

### 4.3 Line 2 — CaptureOS SaaS (Month 6)
Self-serve platform, 4 tiers (see 3.2).
- Year 1 target: $50k ARR (10–20 paid customers, mostly at $199–$599 tiers)

### 4.4 Line 3 — CMMC Readiness Engine (Month 9)
Control tracking across 110 NIST 800-171 controls, evidence management, POA&M generator, audit-ready export bundles. Sold standalone or as a CaptureOS add-on.
- Pricing: $5k–$25k one-time engagement + $500–$2k/mo monitoring
- Year 1 target: $100k–$300k

### 4.5 Line 4 — Intelligence Data Products (Year 2)
Structured reports and newsletters from the data lake we accumulate. "Top 100 DIB entrants to CMMC L2," "Q3 Navy recompete forecast," etc.
- Pricing: $500–$5,000 per report, $99–$499/mo subs
- Target market: PE firms, large primes, recruiters, agencies

## 5. Feature list by tier

### 5.1 Scout ($199/mo) — Opportunity awareness
- Opportunity feed filtered by NAICS, set-aside, keyword, agency, value range
- Email / SMS alerts for scored matches above user threshold
- Saved searches (up to 10)
- Basic incumbent info (who won the prior contract, ceiling value, expiration)
- Single user
- 30-day history

### 5.2 Capture ($599/mo) — Pursuit management
Everything in Scout, plus:
- Full capture pipeline (Lead → Qualify → Pursue → Propose → Submit → Won/Lost)
- AI-generated opportunity summaries ("Why this matters" paragraphs)
- Sources Sought auto-drafter (first pass, human-edited)
- Capability statement library (reusable across pursuits)
- Past performance matrix
- 5 users
- 1-year history

### 5.3 Prime ($1,499/mo) — Team + automation
Everything in Capture, plus:
- Unlimited users
- AI-generated compliance matrices from solicitation docs (Section L/M parse → requirements tracker)
- AI-assisted proposal shred-outs
- Teaming partner marketplace (match primes ↔ subs)
- Agency forecast tracking (via Apify scraping layer)
- API access (read-only, rate-limited)
- Full history

### 5.4 Enterprise ($5k–$25k/mo, custom)
- White-glove onboarding
- Custom NAICS and agency tuning
- Dedicated success manager
- SAML SSO
- Audit log export
- Managed capture services bundled
- SLA

## 6. Critical user journeys

### 6.1 MacTech internal — "Patrick wakes up to a new opportunity"
1. Overnight ingestion pulls 200 new SAM.gov opportunities
2. Scoring engine runs: NAICS match × keyword density × set-aside fit × ceiling sanity × incumbent weakness
3. 3 score above Patrick's threshold (set at 75)
4. At 7am ET, Patrick receives an email digest: 3 opps, each with: AI "Why this matters" paragraph, incumbent info, filing deadlines, matching capability statements
5. Patrick clicks into one → opportunity detail page shows full SOW, auto-parsed requirements, suggested teaming partners, historical wins in similar scope
6. Patrick moves it to "Qualify" in the pipeline
7. System drafts a Sources Sought response using the SOW + MacTech's capability library
8. Patrick edits and submits via the agency's mechanism

### 6.2 External customer — "DIB prime onboards to Scout"
1. User signs up via Clerk (SSO or email)
2. Onboarding wizard: enters their NAICS codes, preferred agencies, set-aside eligibility, keyword alerts
3. System backfills their feed with the last 30 days of relevant opportunities
4. First email digest lands next morning

### 6.3 CMMC Readiness Engine — "New customer buys standalone"
1. CISO at DIB contractor purchases engagement ($15k)
2. Kickoff call with MacTech team (delivered by Patrick and/or Brian)
3. Customer uploads current documentation; system auto-maps evidence to 110 controls
4. Gap analysis report generated; POA&M drafted
5. Customer enters monthly monitoring retainer ($1k/mo) for continuous posture tracking

## 7. Non-functional requirements

### 7.1 Security / Compliance
- Encryption at rest (AES-256) and in transit (TLS 1.3)
- Multi-tenant isolation via PostgreSQL RLS + application-level tenant scoping
- Audit log for every data access and mutation (append-only table)
- CMMC L2 / NIST 800-171 alignment from day one
- SOC 2 Type I internal readiness (already claimed on MacTech's site)
- Eventual FedRAMP Moderate when revenue justifies (Year 2–3)
- No customer PII beyond what's needed for auth and billing
- Automatic secret rotation for API keys stored in-platform

### 7.2 Performance
- Opportunity feed load: p95 < 500ms
- Scoring run for 1k opportunities: < 60s
- AI-drafted Sources Sought: < 45s from click to draft
- SAM.gov ingestion: every 2 hours during business days, every 6 hours off-hours

### 7.3 Reliability
- 99.5% uptime target Year 1 (≈3.5 hours downtime/mo)
- Daily automated DB backups, 30-day retention
- Queue-based ingestion so API outages don't break the feed
- Circuit breakers on every external API client

### 7.4 Observability
- Sentry for error tracking
- PostHog for product analytics (feature adoption, funnel conversion)
- Better Stack (or similar) for uptime monitoring
- Structured JSON logging with correlation IDs

## 8. Out of scope (explicit non-goals for MVP)

- State & local (SLED) opportunities — federal only for Year 1
- Grants — Year 2
- Real-time collaboration on proposal drafts — use Google Docs integration for v1
- Mobile app — responsive web only
- White-label / reseller offering — Year 2+
- Integrations with Deltek Costpoint / Unanet — Year 2
- Automated proposal submission via agency portals — human-in-the-loop always

## 9. Success metrics

### 9.1 Internal (Line Zero)
- # opportunities surfaced by the tool per week
- # opportunities advanced past "Qualify" per month
- # contracts won per quarter
- $ of contract revenue attributed to platform-surfaced opportunities

### 9.2 External (SaaS + services)
- MRR / ARR
- Net revenue retention
- Free trial → paid conversion
- Time-to-first-value (sign-up → first useful alert)
- NPS from DIB customers
- Churn

## 10. Competitive positioning (short form)

| Competitor | Price | What they do well | Where we beat them |
|---|---|---|---|
| Deltek GovWin IQ | $15k+/yr | Deepest data, integrations with Costpoint | AI-native workflow, 10× cheaper entry, modern UX |
| Bloomberg Government | $5k–$15k/yr | Policy + news, big-picture intel | Purpose-built for capture, not news |
| HigherGov | $500–$2k/mo | Modern UX, growing fast | Deeper AI, compliance integration, SDVOSB-first positioning |
| GovTribe | $100–$500/mo | Cheap, clean UX | Richer intel layer, full pipeline, CMMC |
| USASpending.gov (free) | $0 | Public truth source | We sit on top and add intelligence |

**Our wedge:** We are the *only* GovCon tool built by active GovCon contractors. Every feature is field-tested by our own BD team.

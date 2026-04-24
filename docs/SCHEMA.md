# Database Schema — MacTech CaptureOS

PostgreSQL 16 with extensions: `pgvector`, `pg_trgm`, `uuid-ossp`, `pgcrypto`.

Multi-tenant model: public reference data is shared; domain data is tenant-scoped with RLS.

---

## Naming conventions

- Tables: `snake_case`, plural (`opportunities`, `pursuits`)
- Primary keys: `id UUID DEFAULT gen_random_uuid()`
- Tenant columns: `tenant_id UUID NOT NULL REFERENCES tenants(id)`
- Timestamps: `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`, `updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`
- Soft delete: `deleted_at TIMESTAMPTZ NULL`
- Source data columns suffix: `_raw` for unmodified API payloads

---

## Shared (public) tables

### `tenants`
```sql
CREATE TABLE tenants (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug            TEXT UNIQUE NOT NULL,
    name            TEXT NOT NULL,
    plan            TEXT NOT NULL DEFAULT 'scout',  -- scout|capture|prime|enterprise|internal
    uei             TEXT,
    cage_code       TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```
Tenant 1 = MacTech Solutions LLC (seeded on first migration).

### `users`
```sql
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    clerk_user_id   TEXT UNIQUE NOT NULL,
    email           TEXT NOT NULL,
    full_name       TEXT,
    role            TEXT NOT NULL DEFAULT 'member',  -- owner|admin|member|viewer
    founder_id      UUID NULL REFERENCES founders(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_users_tenant ON users(tenant_id);
```

### `founders` (seeded from data/founders.json — MacTech-specific but kept here for schema simplicity)
```sql
CREATE TABLE founders (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug            TEXT UNIQUE NOT NULL,   -- brian-macdonald, etc.
    full_name       TEXT NOT NULL,
    title           TEXT NOT NULL,
    pillar          TEXT NOT NULL,          -- quality|security|infrastructure|governance
    bio             TEXT,
    areas_of_expertise JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### `naics_codes`
```sql
CREATE TABLE naics_codes (
    code            TEXT PRIMARY KEY,        -- e.g., '541519'
    title           TEXT NOT NULL,
    description     TEXT,
    size_standard   TEXT,                    -- e.g., '$34M', '500 employees'
    mactech_tier    TEXT,                    -- 'primary' | 'secondary' | NULL
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### `founder_naics_matrix`
```sql
CREATE TABLE founder_naics_matrix (
    founder_id      UUID NOT NULL REFERENCES founders(id),
    naics_code      TEXT NOT NULL REFERENCES naics_codes(code),
    affinity        INTEGER NOT NULL DEFAULT 1,  -- 1 = claimed, future: weighted 1-5
    PRIMARY KEY (founder_id, naics_code)
);
CREATE INDEX idx_fnm_naics ON founder_naics_matrix(naics_code);
```

### `opportunities_raw`
```sql
CREATE TABLE opportunities_raw (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source              TEXT NOT NULL,           -- 'sam_gov' | 'dibbs' | 'fedconnect' | ...
    source_id           TEXT NOT NULL,           -- noticeId for sam_gov
    notice_type         TEXT,                    -- 'Sources Sought' | 'Solicitation' | ...
    title               TEXT NOT NULL,
    description         TEXT,
    solicitation_number TEXT,
    agency              TEXT,
    subagency           TEXT,
    office              TEXT,
    naics_code          TEXT REFERENCES naics_codes(code),
    set_aside           TEXT,
    estimated_value_low NUMERIC,
    estimated_value_high NUMERIC,
    posted_at           TIMESTAMPTZ,
    response_deadline   TIMESTAMPTZ,
    place_of_performance JSONB,
    raw_payload         JSONB NOT NULL,          -- full API response
    embedding           vector(1024),            -- Voyage voyage-3 default
    hash                TEXT,                    -- SHA256 of normalized payload for change detection
    ingested_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (source, source_id)
);
CREATE INDEX idx_opp_naics ON opportunities_raw(naics_code);
CREATE INDEX idx_opp_agency ON opportunities_raw(agency);
CREATE INDEX idx_opp_posted ON opportunities_raw(posted_at DESC);
CREATE INDEX idx_opp_setaside ON opportunities_raw(set_aside);
CREATE INDEX idx_opp_description_trgm ON opportunities_raw USING gin (description gin_trgm_ops);
CREATE INDEX idx_opp_embedding ON opportunities_raw USING ivfflat (embedding vector_cosine_ops);
```

### `opportunities_enriched`
```sql
CREATE TABLE opportunities_enriched (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    opportunity_id      UUID NOT NULL UNIQUE REFERENCES opportunities_raw(id),
    incumbent_uei       TEXT,
    incumbent_name      TEXT,
    incumbent_contract_id TEXT,
    incumbent_end_date  DATE,
    requirements        JSONB,                   -- parsed from SOW/PWS if available
    naics_match_notes   TEXT,
    enriched_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### `awards_history`
```sql
CREATE TABLE awards_history (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source              TEXT NOT NULL,           -- 'usaspending' | 'fpds'
    award_id            TEXT NOT NULL,           -- PIID or USASpending award_id
    piid                TEXT,
    recipient_uei       TEXT,
    recipient_name      TEXT,
    awarding_agency     TEXT,
    awarding_subagency  TEXT,
    naics_code          TEXT REFERENCES naics_codes(code),
    award_type          TEXT,                    -- 'BPA' | 'Contract' | 'Task Order' | ...
    obligated_amount    NUMERIC,
    base_and_all_options_value NUMERIC,
    period_of_performance_start DATE,
    period_of_performance_current_end DATE,
    period_of_performance_potential_end DATE,
    description         TEXT,
    raw_payload         JSONB,
    ingested_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (source, award_id)
);
CREATE INDEX idx_award_recipient ON awards_history(recipient_uei);
CREATE INDEX idx_award_naics_agency ON awards_history(naics_code, awarding_agency);
CREATE INDEX idx_award_end_date ON awards_history(period_of_performance_current_end);
```

### `entities`
```sql
CREATE TABLE entities (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    uei             TEXT UNIQUE NOT NULL,
    cage_code       TEXT,
    legal_name      TEXT NOT NULL,
    dba_name        TEXT,
    registration_status TEXT,                    -- 'A' | 'E' | ...
    entity_type     TEXT,
    business_types  JSONB,                       -- ['SDVOSB','SBA 8(a)',...]
    physical_address JSONB,
    primary_naics   TEXT REFERENCES naics_codes(code),
    small_business_statuses JSONB,               -- from SBA DSBS
    raw_sam_payload JSONB,
    raw_sba_payload JSONB,
    last_refreshed_at TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_entities_name_trgm ON entities USING gin (legal_name gin_trgm_ops);
```

### `exclusions_cache`
```sql
CREATE TABLE exclusions_cache (
    uei             TEXT PRIMARY KEY,
    is_excluded     BOOLEAN NOT NULL,
    exclusion_details JSONB,
    checked_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### `agency_forecasts`
```sql
CREATE TABLE agency_forecasts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_url      TEXT NOT NULL,
    agency          TEXT NOT NULL,
    subagency       TEXT,
    office          TEXT,
    title           TEXT NOT NULL,
    description     TEXT,
    estimated_value NUMERIC,
    estimated_solicitation_date DATE,
    estimated_award_date DATE,
    naics_code      TEXT REFERENCES naics_codes(code),
    set_aside       TEXT,
    contract_vehicle TEXT,
    raw_payload     JSONB,
    scraped_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    embedding       vector(1024)
);
CREATE INDEX idx_forecast_naics ON agency_forecasts(naics_code);
CREATE INDEX idx_forecast_dates ON agency_forecasts(estimated_solicitation_date);
```

---

## Tenant-scoped tables (RLS enforced)

Every tenant-scoped table:
```sql
ALTER TABLE <table> ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON <table>
    USING (tenant_id = current_setting('app.tenant_id')::uuid);
```

### `saved_searches`
```sql
CREATE TABLE saved_searches (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    user_id         UUID REFERENCES users(id),
    name            TEXT NOT NULL,
    filters         JSONB NOT NULL,              -- {naics:[],agencies:[],setAsides:[],keywords:[],...}
    alert_threshold INTEGER NOT NULL DEFAULT 70, -- send alerts when score >= this
    alert_channels  JSONB NOT NULL DEFAULT '["email"]'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### `opportunity_scores`
```sql
CREATE TABLE opportunity_scores (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    opportunity_id  UUID NOT NULL REFERENCES opportunities_raw(id),
    score           INTEGER NOT NULL,            -- 0-100
    score_breakdown JSONB NOT NULL,              -- {naics_match:20,keyword:30,...}
    assigned_founder_id UUID REFERENCES founders(id),
    why_it_matters  TEXT,                        -- LLM-generated paragraph
    scored_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (tenant_id, opportunity_id)
);
CREATE INDEX idx_scores_tenant_score ON opportunity_scores(tenant_id, score DESC);
```

### `pursuits` (the capture pipeline)
```sql
CREATE TABLE pursuits (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    opportunity_id  UUID REFERENCES opportunities_raw(id),
    forecast_id     UUID REFERENCES agency_forecasts(id),
    custom_title    TEXT,                        -- for pursuits not tied to a public opp
    stage           TEXT NOT NULL DEFAULT 'lead',-- lead|qualify|pursue|propose|submit|won|lost
    owner_user_id   UUID REFERENCES users(id),
    pwin            INTEGER,                     -- probability of win 0-100 (user set)
    bid_no_bid_decision TEXT,                    -- bid|no_bid|undecided
    notes           TEXT,
    proposal_due_at TIMESTAMPTZ,
    submitted_at    TIMESTAMPTZ,
    closed_at       TIMESTAMPTZ,
    outcome         TEXT,                        -- won|lost|no_bid
    award_value     NUMERIC,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_pursuits_tenant_stage ON pursuits(tenant_id, stage);
```

### `pursuit_events` (audit trail per pursuit)
```sql
CREATE TABLE pursuit_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    pursuit_id      UUID NOT NULL REFERENCES pursuits(id),
    actor_user_id   UUID REFERENCES users(id),
    event_type      TEXT NOT NULL,               -- stage_changed|note_added|document_attached|...
    payload         JSONB,
    occurred_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### `capability_statements`
```sql
CREATE TABLE capability_statements (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    title           TEXT NOT NULL,
    summary         TEXT NOT NULL,
    keywords        TEXT[],
    related_naics   TEXT[],
    related_founders JSONB,                      -- [{founder_id, role}]
    artifact_s3_key TEXT,                        -- optional: uploaded PDF
    embedding       vector(1024),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_capstmt_embedding ON capability_statements USING ivfflat (embedding vector_cosine_ops);
```

### `past_performance`
```sql
CREATE TABLE past_performance (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    contract_piid   TEXT,
    customer        TEXT NOT NULL,
    title           TEXT NOT NULL,
    period_start    DATE,
    period_end      DATE,
    value           NUMERIC,
    role            TEXT,                        -- prime|sub
    description     TEXT NOT NULL,
    outcomes        TEXT,
    cpars_rating    TEXT,
    reference_name  TEXT,
    reference_email TEXT,
    embedding       vector(1024),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### `documents` (solicitation docs, draft responses, proposal artifacts)
```sql
CREATE TABLE documents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    pursuit_id      UUID REFERENCES pursuits(id),
    doc_type        TEXT NOT NULL,               -- solicitation|sow|pws|draft_response|compliance_matrix|capability_statement|other
    name            TEXT NOT NULL,
    mime_type       TEXT,
    s3_key          TEXT NOT NULL,
    size_bytes      BIGINT,
    parsed_content  TEXT,                        -- extracted text
    parse_status    TEXT DEFAULT 'pending',      -- pending|parsed|failed
    uploaded_by     UUID REFERENCES users(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_docs_pursuit ON documents(pursuit_id);
```

### `compliance_matrices`
```sql
CREATE TABLE compliance_matrices (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    pursuit_id      UUID NOT NULL REFERENCES pursuits(id),
    source_document_id UUID REFERENCES documents(id),
    requirements    JSONB NOT NULL,              -- [{section, requirement, response_location, owner, status}]
    status          TEXT NOT NULL DEFAULT 'draft',
    generated_by    TEXT,                        -- 'ai' | 'human'
    llm_version     TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### `teaming_partners` (the marketplace)
```sql
CREATE TABLE teaming_partners (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    entity_id       UUID REFERENCES entities(id),
    relationship_type TEXT NOT NULL,             -- prime_we_sub_to|sub_we_prime_for|evaluated|declined
    status          TEXT NOT NULL DEFAULT 'active',
    primary_contact_name TEXT,
    primary_contact_email TEXT,
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### `notifications`
```sql
CREATE TABLE notifications (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    user_id         UUID NOT NULL REFERENCES users(id),
    channel         TEXT NOT NULL,               -- email|sms|slack|in_app
    subject         TEXT,
    body            TEXT,
    payload         JSONB,
    sent_at         TIMESTAMPTZ,
    read_at         TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

## CMMC Readiness tables (Product Line 3, ships Month 9)

### `cmmc_assessments`
```sql
CREATE TABLE cmmc_assessments (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    scope           TEXT NOT NULL,
    target_level    INTEGER NOT NULL,            -- 1|2|3
    status          TEXT NOT NULL DEFAULT 'in_progress',
    started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at    TIMESTAMPTZ
);
```

### `cmmc_controls` (catalog — shared reference)
```sql
CREATE TABLE cmmc_controls (
    id              TEXT PRIMARY KEY,            -- e.g., 'AC.L2-3.1.1'
    family          TEXT NOT NULL,
    level           INTEGER NOT NULL,
    title           TEXT NOT NULL,
    requirement_text TEXT NOT NULL,
    discussion      TEXT,
    nist_800_171_ref TEXT
);
```

### `cmmc_control_status` (tenant-scoped)
```sql
CREATE TABLE cmmc_control_status (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    assessment_id   UUID NOT NULL REFERENCES cmmc_assessments(id),
    control_id      TEXT NOT NULL REFERENCES cmmc_controls(id),
    implementation_status TEXT NOT NULL,         -- implemented|partial|not_implemented|na
    evidence_notes  TEXT,
    last_reviewed_at TIMESTAMPTZ,
    reviewer_user_id UUID REFERENCES users(id),
    UNIQUE (tenant_id, assessment_id, control_id)
);
```

### `cmmc_evidence`
```sql
CREATE TABLE cmmc_evidence (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    control_id      TEXT NOT NULL REFERENCES cmmc_controls(id),
    document_id     UUID REFERENCES documents(id),
    summary         TEXT NOT NULL,
    metadata        JSONB,                       -- evidence-type, date, author, etc.
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### `cmmc_poam`
```sql
CREATE TABLE cmmc_poam (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    assessment_id   UUID NOT NULL REFERENCES cmmc_assessments(id),
    control_id      TEXT NOT NULL REFERENCES cmmc_controls(id),
    weakness        TEXT NOT NULL,
    mitigation_plan TEXT,
    target_date     DATE,
    owner           TEXT,
    status          TEXT NOT NULL DEFAULT 'open',
    closed_at       TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

## Audit & operational tables

### `audit_log` (append-only, all tenants)
```sql
CREATE TABLE audit_log (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       UUID,
    actor_user_id   UUID,
    action          TEXT NOT NULL,
    target_table    TEXT,
    target_id       UUID,
    before_state    JSONB,
    after_state     JSONB,
    ip_address      INET,
    user_agent      TEXT,
    occurred_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_audit_tenant_time ON audit_log(tenant_id, occurred_at DESC);
```

### `external_credentials` (customer-supplied API keys, encrypted)
```sql
CREATE TABLE external_credentials (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    service         TEXT NOT NULL,               -- 'sam_gov' | 'docusign' | ...
    ciphertext      BYTEA NOT NULL,              -- KMS-encrypted
    key_version     INTEGER NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    rotated_at      TIMESTAMPTZ,
    UNIQUE (tenant_id, service)
);
```

### `llm_calls` (operational log for AI cost + replay)
```sql
CREATE TABLE llm_calls (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID,
    provider        TEXT NOT NULL,               -- 'anthropic' | 'openai' | 'voyage'
    model           TEXT NOT NULL,
    prompt_hash     TEXT NOT NULL,
    prompt_version  TEXT,
    input_tokens    INTEGER,
    output_tokens   INTEGER,
    cost_usd        NUMERIC(10,4),
    latency_ms      INTEGER,
    cached          BOOLEAN NOT NULL DEFAULT FALSE,
    purpose         TEXT,                        -- 'scoring' | 'why_it_matters' | 'compliance_matrix' | ...
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_llm_tenant_time ON llm_calls(tenant_id, created_at DESC);
```

---

## Scoring algorithm (implemented in `packages/intelligence/scoring.py`)

Score = weighted sum, 0–100:

| Component | Weight | Notes |
|---|---|---|
| NAICS match | 25 | 25 if exact primary, 15 if secondary, 5 if embedding-similar, 0 otherwise |
| Keyword density | 20 | Tenant's saved keywords found in title + description |
| Set-aside fit | 15 | 15 if SDVOSB match (or tenant's cert), 8 if small biz, 0 if unrestricted |
| Value sanity | 10 | 10 if within tenant's historical win range, scaled otherwise |
| Incumbent weakness | 15 | 15 if incumbent is small, recompete, or losing contracts elsewhere; 5 baseline |
| Founder availability | 10 | 10 if matched founder's pillar has capacity (future: pulls from load model) |
| Freshness | 5 | 5 if posted < 48h ago, declines linearly to 0 at 30 days |

Future v2: bring in embedding similarity to past wins.

---

## Seeding

On first migration, seed:
1. Tenants: MacTech (tenant_id fixed from env `MACTECH_TENANT_ID`)
2. Founders from `data/founders.json`
3. NAICS codes from `data/naics_matrix.json`
4. `founder_naics_matrix` from same file
5. CMMC controls from NIST 800-171 R3 reference (import once L3 scope is ready — Phase 3)

# Agent Architecture — MacTech CaptureOS

This document describes the Claude Agent SDK-based execution model that powers the AI layer of CaptureOS. Read this alongside `ARCHITECTURE.md` — they're complementary.

## Why this exists

The naive architecture for an LLM-powered platform is: web app → Anthropic API → response. That works, but it's expensive at scale and underuses what's actually available from Anthropic's tooling.

The Claude Agent SDK (formerly Claude Code SDK) provides:
- Headless, programmatic invocation of Claude with full tool access (filesystem, bash, MCP servers)
- Structured JSON output conforming to user-defined schemas
- Session persistence — multi-turn reasoning across separate invocations
- Project-level behavioral context via `CLAUDE.md`
- First-class support for CI/CD, cron, webhook-triggered, and long-running workflows
- Billing against the running user's Claude subscription OR an API key, depending on environment

For MacTech's internal use (Revenue Line Zero), this is transformative: a flat Claude Max subscription covers effectively unlimited internal AI operations. For external SaaS customers (Revenue Lines 2–3), customer usage must be billed appropriately via either BYO-API-key or platform-metered billing.

**Reference docs:**
- Agent SDK overview: https://docs.claude.com/en/docs/agent-sdk
- Headless mode / CLI reference: `claude -p --help`

## Terms-of-service boundary (read carefully)

From Anthropic's Agent SDK commercial terms:

> Unless previously approved, Anthropic does not allow third-party developers to offer claude.ai login or rate limits for their products, including agents built on the Claude Agent SDK.

**What this means for CaptureOS:**

| Scenario | Allowed? | Auth path |
|---|---|---|
| MacTech founders running agents against MacTech's own data | ✅ | MacTech's Claude subscription (via SDK) |
| MacTech delivering a managed service using CaptureOS internally | ✅ | MacTech's subscription |
| MacTech reselling SaaS that routes customer queries through MacTech's subscription | ❌ | Must be customer-billed |
| Customer brings their own Anthropic API key, CaptureOS uses it for their queries | ✅ | Customer API key |
| CaptureOS charges customer in their tier, routes their queries through CaptureOS's Anthropic commercial API with per-tenant metering | ✅ | Platform commercial API |

Implementation: see `Billing & execution modes` below.

## Execution modes

CaptureOS supports three AI execution modes. The platform's LLM client abstraction (`packages/intelligence/llm/client.py`) routes every AI call based on tenant configuration.

### Mode A — Agent SDK on subscription (internal, MacTech only)

**When:** Every AI call on behalf of tenant `mactech` (tenant #1).

**How:** 
- Agent SDK installed on the API host, authenticated against MacTech's Claude subscription (one-time login via `claude login`).
- LLM client spawns agent processes via `claude -p` or uses the Python SDK.
- Cost: flat subscription ($100–$200/mo depending on plan).

**Constraint:** Subscription rate limits apply. For normal internal operations at 4 founder scale this is comfortable. Monitor with operational metrics.

### Mode B — BYO API Key (external, lower tiers)

**When:** Tenant has provided their own Anthropic API key via settings.

**How:**
- Key stored encrypted in `external_credentials` table (per `SCHEMA.md`).
- LLM client swaps the credential on the underlying Anthropic SDK call for queries belonging to that tenant.
- Cost: flows directly to customer; platform has zero marginal cost.

**Default for:** Scout ($199/mo) and Capture ($599/mo) tiers.

### Mode C — Platform commercial API (external, higher tiers)

**When:** Tenant is on Prime ($1,499/mo) or Enterprise.

**How:**
- LLM client uses platform Anthropic commercial API key (not subscription).
- Per-call cost tracked in `llm_calls` table with `tenant_id` for usage-based billing reconciliation and margin monitoring.
- Cost: platform pays Anthropic, priced into tier.

**Default for:** Prime and Enterprise tiers.

## The LLM client abstraction

`packages/intelligence/llm/client.py` exposes a single interface:

```python
class LLMClient(Protocol):
    async def invoke(
        self,
        prompt: str,
        *,
        tenant_id: UUID,
        purpose: str,                    # 'scoring' | 'why_it_matters' | 'compliance_matrix' | ...
        complexity: Literal['fast', 'smart', 'deep'] = 'smart',
        schema: type[BaseModel] | None = None,
        session_id: str | None = None,   # for multi-turn
        tools: list[str] | None = None,  # for agent mode: e.g., ['Read', 'Bash', 'mcp__captureos_db']
    ) -> LLMResponse: ...
```

Implementations:
- `AgentSDKClient` — uses `claude -p` subprocess or Python SDK bindings
- `AnthropicAPIClient` — uses Anthropic commercial API
- `OpenAIFallbackClient` — backup provider

Routing logic in `LLMClientRouter.get_client(tenant)`:
1. If `tenant_id == MACTECH_TENANT_ID` → `AgentSDKClient`
2. Elif tenant has valid `external_credentials.anthropic_api_key` → `AnthropicAPIClient` with tenant's key
3. Else (Prime/Enterprise tier) → `AnthropicAPIClient` with platform key

## MCP servers — the data and tool layer

MCP (Model Context Protocol) servers are how we expose CaptureOS capabilities to agent sessions.

### MCPs we build in-house

1. **`mcp-captureos-db`** — Read-only access to the CaptureOS Postgres DB with tenant scoping enforced. Tools:
   - `query_opportunities(filters)` → list[Opportunity]
   - `query_awards_history(filters)` → list[Award]
   - `get_pursuit(pursuit_id)` → Pursuit (with tenant check)
   - `list_capability_statements()` → list[CapabilityStatement]
   - `list_past_performance()` → list[PastPerformance]

2. **`mcp-sam-gov`** — Typed wrapper around SAM.gov APIs. Tools:
   - `search_opportunities(naics, set_aside, ...)` → list[Opportunity]
   - `get_entity(uei)` → Entity
   - `check_exclusion(uei)` → ExclusionStatus

3. **`mcp-usaspending`** — USASpending / FPDS access. Tools:
   - `search_awards(recipient, agency, naics, ...)` → list[Award]
   - `get_incumbent(naics, agency, poc_end_after)` → Award | None

4. **`mcp-captureos-docs`** — Document operations. Tools:
   - `read_parsed_content(document_id)` → str
   - `attach_draft(pursuit_id, content, doc_type)` → Document

### Server-side vs agent-side MCPs

- **Server-side MCPs** are long-running HTTP services the agents connect to. Use for anything multi-tenant or expensive to initialize.
- **Agent-side MCPs** (`createSdkMcpServer`) are defined inside a single agent invocation. Use for one-off tools that don't need to be shared.

## Triggering patterns

Six ways agents fire in CaptureOS. Pick the pattern by job characteristics.

### 1. Scheduled (cron)
Longest-running and highest-volume jobs. Triggered by Celery Beat.

**Examples:** Morning digest (6am ET), ingestion sweeps, weekly capture report.

**Pattern:**
```python
@celery.task
def morning_digest():
    for tenant in tenants_with_digest_enabled():
        client = LLMClientRouter.get_client(tenant)
        response = asyncio.run(client.invoke(
            prompt=build_morning_digest_prompt(tenant),
            tenant_id=tenant.id,
            purpose='morning_digest',
            complexity='smart',
            schema=MorningDigestSchema,
            tools=['mcp__captureos_db', 'Read'],
        ))
        send_digest_email(tenant, response.parsed)
```

### 2. Event-driven (internal events)
Fired by domain events on the internal event bus.

**Examples:** `opportunity.ingested` → enrichment; `pursuit.stage_changed` → next-action suggestions.

### 3. User-triggered (button click in UI)
Interactive, need fast feedback.

**Examples:** "Draft Sources Sought response," "Generate compliance matrix," "Suggest teaming partners."

**Pattern:** UI posts to API, API enqueues job, worker invokes agent, result persisted, UI polls or uses SSE.

### 4. Webhook-triggered (external events)
A third-party service tells us to do something.

**Examples:** Clerk user signup hook → onboarding agent; future Stripe webhook → entitlement adjustment.

### 5. Chain (agent output triggers next agent)
Output of agent A is the input of agent B.

**Example:** Solicitation upload → parse agent → matrix generator agent → draft response agent. Each step is a separate invocation with `--resume <session_id>` preserving context.

### 6. Interactive (founder uses `claude` directly on the repo)
The 4 founders can open Claude Code against the production repo for ad-hoc queries, with MCPs configured.

**Example:** Brian at his desk asks "show me all pursuits in Qualify stage that touch 541380 and have no attached capability statement yet." The agent reads the DB via MCP and answers.

## Structured outputs — the contract

Every agent invocation that feeds another system returns JSON matching a Pydantic schema. No free-text → DB write paths.

Schemas live in `packages/intelligence/schemas/`:

```python
class OpportunityScore(BaseModel):
    score: int = Field(ge=0, le=100)
    breakdown: dict[str, int]
    why_it_matters: str = Field(max_length=600)
    assigned_founder_slug: str | None
    confidence: Literal['low', 'medium', 'high']

class ComplianceMatrix(BaseModel):
    requirements: list[Requirement]
    estimated_proposal_pages: int
    sections_identified: list[Section]
    risks_flagged: list[str]

class SourcesSoughtDraft(BaseModel):
    company_overview: str
    capability_alignment: str
    past_performance_summary: str
    proposed_approach: str
    points_of_contact: list[POC]
    word_count: int
```

Invocations specify the schema; the SDK enforces structure via `--output-format json --json-schema <schema>`.

## Session persistence strategy

Agent sessions can be resumed via `--resume <session_id>`. Use this to avoid rebuilding context on each turn.

**Rule:** Create a session per *logical work unit*, reuse across related invocations.

Examples:
- One session per `pursuit_id` — every AI action on that pursuit resumes the same session; context accumulates naturally.
- One session per `daily_digest_run_id` — scoring run reuses context across all opportunities.
- **Do not** use one session across all tenants or all pursuits — context pollution, data leakage risk.

Session IDs stored on `pursuits.agent_session_id` and `opportunity_scores.agent_session_id` columns.

`--no-session-persistence` used for pure stateless calls (e.g., "score this opportunity in isolation").

## Cost model

| Mode | Typical monthly cost | Who pays | When to use |
|---|---|---|---|
| Agent SDK on subscription | $100–$200 flat | MacTech | All Tenant #1 (MacTech) ops |
| BYO API key | Variable | Customer | Scout + Capture tiers |
| Platform commercial API | 10–20% of MRR | MacTech, priced in | Prime + Enterprise tiers |

Cost monitoring in `llm_calls` table. Weekly review: any tenant whose LLM cost exceeds 40% of their tier fee is a red flag — we may need to raise prices or add caching.

## Caching — the non-negotiable

Agent invocations are expensive in both money and wall-time even on subscription. Every LLM call goes through a Redis cache with a configurable TTL.

Cache key: SHA256 of (prompt_version + prompt_inputs_hash + model + schema_name + tenant_id).

TTL by purpose:
- Scoring, "why it matters": 14 days (opportunities don't change often)
- Compliance matrix: indefinite until solicitation doc changes
- Sources Sought draft: not cached (intentionally fresh each time)

## Testing strategy

Agents are non-deterministic. Standard approach:

1. **Contract tests** — validate output matches schema, contains required fields. Run on every CI.
2. **Golden fixtures** — curated set of real opportunities with expected score ranges. Alerts if drift exceeds threshold.
3. **Replay harness** — every `llm_calls` entry logs the prompt+response. Regression tests can replay old prompts against new prompts to measure delta.
4. **Shadow runs** — when a prompt is changed, run both old and new prompts in parallel for 48 hours, diff outputs, ship if delta acceptable.

## Security

- Agent processes run with minimal permissions. Default `--permission-mode acceptEdits` is forbidden for any tenant-scoped job; use explicit `--allowedTools`.
- MCP servers enforce tenant isolation; agents cannot cross tenant boundaries even with bash access.
- Agent processes write to ephemeral scratch directories; no persistent filesystem access by default.
- Every agent invocation logged with purpose, tenant, prompt hash, and result hash in `llm_calls`.

## Phased rollout

**Phase 1 (Weeks 1–4):** `AnthropicAPIClient` with a single platform API key. All MacTech internal traffic routes through it. `LLMClient` protocol and `LLMClientRouter` are built to the design in this document, but `AgentSDKClient` is a stub that raises `NotImplementedError`. Mode A is deferred — see rationale below.

**Phase 2 (Weeks 5–12):** Add MCP servers. Workflows that need DB or document access invoke MCP-backed tools through the Anthropic API's tool-use interface, not through Agent SDK.

**Phase 4 (Month 6):** Add BYO-key path. Tenant-supplied `external_credentials.anthropic_api_key` routes through `AnthropicAPIClient` with the tenant's key instead of the platform key. Ship Scout + Capture tiers.

**Phase 5+ (Month 9+):** Revisit Mode A (Agent SDK on subscription) only if one of the following triggers hits: (a) MacTech-only platform-API spend exceeds $300/mo sustained, or (b) Prime/Enterprise customer volume makes the per-call → flat-rate arbitrage material. At that point, build the Agent SDK proxy as a dedicated service — do **not** resurrect shared-volume `~/.claude/` approaches, which are fragile across multi-replica worker fleets.

### Why Mode A is deferred in Phase 1

Agent SDK subscription auth (`claude login`) writes credentials to `~/.claude/` on the host where the login happened. Celery workers on Fly.io or Railway run multi-replica, with containers cycling in and out — machine-local credentials break. Making them work across replicas requires either a shared volume (operationally fragile, subject to race conditions on token refresh) or a dedicated Agent SDK RPC service (2–3 weeks of infrastructure). At MacTech's Phase 1 scale — ~200–500 opportunities scored per week, ~20 why_it_matters paragraphs, ~4 compliance matrices, ~6 Sources Sought drafts per month — platform-API spend with Haiku-for-scoring + Sonnet-for-drafting + Redis caching is $15–$40/mo. Not worth the infra cost to avoid.

Guardrail: set a billing alert at $75/mo on the Anthropic console. If sustained spend approaches $300/mo, revisit.

Founders running `claude` interactively on their own laptops are a different path and are unaffected by this decision.

## References

- Claude Agent SDK docs: https://docs.claude.com/en/docs/agent-sdk
- Headless mode guide: https://code.claude.com/docs/en/headless
- MCP spec: https://modelcontextprotocol.io
- Claude Code CLAUDE.md conventions: https://docs.claude.com/en/docs/claude-code/memory

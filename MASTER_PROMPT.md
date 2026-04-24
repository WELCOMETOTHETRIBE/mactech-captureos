# MASTER PROMPT — Paste this into Claude Code

**How to use this file:**

1. Download `mactech-captureos-bootstrap.zip` and extract it into a new empty directory.
2. Open a terminal in that directory and run `claude` to start Claude Code.
3. Copy everything between the ```=== prompt ===``` markers below and paste it as your first message.

---

```=== prompt ===

You are working on MacTech CaptureOS, an AI-native GovCon revenue operations platform for defense contractors. I'm one of the four founding members of MacTech Solutions LLC (SDVOSB, veteran-owned). You are the sole engineering agent on this project; I'm non-technical and relying on you for implementation judgment.

Before you write any code or run any commands, do the following in order:

1. Read /CLAUDE.md end to end. It is your always-on operating context.
2. Read /docs/MACTECH_PLAYBOOK.md in full — this is Phase 1's governing spec and the most important document in the repo for the work we're doing now.
3. Read /README.md, /docs/PRD.md, /docs/ARCHITECTURE.md, /docs/AGENT_ARCHITECTURE.md, /docs/DATA_SOURCES.md, /docs/SCHEMA.md, /docs/ROADMAP.md, /docs/POSITIONING.md. Skim for structure; you'll come back to each as you build.
4. Read /data/founders.json, /data/naics_matrix.json, and /config/mactech_tenant_defaults.yml so you understand who the four pillar founders are, which NAICS codes we're targeting, and how the MacTech tenant is configured.
5. Read /docs/PROGRESS.md to see the last session's state.

Once you've read those, report back to me with:

- A one-paragraph summary of what you understand MacTech CaptureOS to be (so I can correct your framing if it drifts).
- Your three biggest open questions or ambiguities before we start building.
- Your proposed first commit: what files you'd create, in what order, and what you'd demonstrate at the end of it.

Do NOT start coding yet. Wait for my response to your questions.

Critical architectural note you must absorb from AGENT_ARCHITECTURE.md:

- The AI layer uses the Claude Agent SDK (not the Anthropic commercial API) for all MacTech internal operations. This runs on the founder's Claude subscription, not per-call API billing. Only external SaaS customers (Year 2+) use the commercial API or BYO-key paths.
- This is a deliberate architectural choice, not a cost optimization. It enables richer agent capabilities: filesystem access, bash execution, MCP tool integration, session persistence, structured JSON outputs — all of which we use.
- Build the LLM abstraction (packages/intelligence/llm/client.py) with three implementations from day one: AgentSDKClient (Mode A), AnthropicAPIClient (Modes B and C), and a stub for OpenAIFallbackClient. In Phase 1 only Mode A is wired up, but the abstraction exists.

Critical product-scope note you must absorb from MACTECH_PLAYBOOK.md:

- Phase 1 is MacTech's internal capture weapon, not a generic SaaS demo. Every feature, API call, dashboard panel, and scheduled job in Phase 1 must map to one of the 4 founders' actual capture workflows described in the playbook.
- The success criterion for Phase 1 is: "At 6am ET on a Tuesday, all four MacTech founders receive a real email listing 3–5 real, scored, recently-posted opportunities they should actually consider pursuing." If we can't deliver that, Phase 1 isn't done.
- Multi-tenancy exists in the architecture (RLS, tenant scoping) because it's cheaper to build right the first time than retrofit. But we are not onboarding external customers in Phase 1. No sign-up flow, no billing integration, no marketing page. Just MacTech's 4 founders using the product to win contracts.
- When PRD.md or ROADMAP.md mentions an external-customer feature that isn't needed yet, defer it. When MACTECH_PLAYBOOK.md prescribes a specific detail for a founder's workflow, build that detail.

Operating agreement (restated from CLAUDE.md, for emphasis):

- Ship a demoable increment every 3–5 working sessions. If something is too big to demo in that window, decompose it.
- Prefer small, reviewable commits over sweeping refactors.
- Ask clarifying questions early. It is always cheaper than rebuilding.
- Write tests for business logic (scoring, ingestion, compliance matrix generation). Target >=70% coverage on packages/intelligence and packages/integrations.
- Multi-tenant isolation is a non-negotiable correctness property. Two layers: PostgreSQL RLS + application-level tenant scoping. Every tenant-scoped query must be verified.
- CMMC 2.0 Level 2 alignment from day one. We are selling to DIB contractors handling CUI. Encryption at rest, encryption in transit, audit logging, hard tenant isolation — these are baseline, not features.
- Never put production secrets in code. Only .env.example files are committed.
- Never invent API endpoints or fields. If SAM.gov / USASpending / etc. docs are unclear, ask me and I'll check the source.
- Update /docs/PROGRESS.md at the end of every working session: what shipped, what's half-done, what's blocked, what's next.
- When you hit a tradeoff (library choice, architecture fork, cost-vs-simplicity), surface it briefly with a recommendation. Don't silently choose and don't bikeshed.

Style expectations:

- Sober, plainspoken voice in all code comments, commit messages, and docs. No hype, no emoji in product UI.
- Python: type hints everywhere, ruff for linting, black for formatting.
- TypeScript: strict mode, no `any` in business logic.
- SQL: lowercase keywords, explicit column lists (never SELECT *).
- Prompts used by the AI layer live in packages/intelligence/prompts/ with version tags. Prompt changes are PRs.

Context on me (the human):

- I'm one of four co-founders. The other three are Brian (Quality), Patrick (Security), James (Infrastructure), John (Governance) — see /data/founders.json.
- I can read code but I'm not the implementer. Assume I need occasional plain-English explanations for tradeoffs and architectural choices.
- My primary success metric is Revenue Line Zero: contracts MacTech wins because of this tool. Ship features that directly support identifying, scoring, and pursuing federal opportunities first. Everything else is secondary.

Start by confirming you've read the project context. Then ask your three questions.

```

---

## Prerequisites you'll want set up before the first real build session

You can start without some of these — Claude Code will stub anything missing — but having them ready accelerates Phase 1 substantially.

1. **Claude subscription (Pro or Max)** — this is what powers the Agent SDK for internal work. Pro is enough to start; Max makes sense once you have steady daily usage. Log in via `claude login` after installing Claude Code.

2. **SAM.gov API key** — free. Register at https://sam.gov → Profile → Account Details → Request API Key. Usually approved within 1 business day. Put it in `.env` as `SAM_API_KEY`.

3. **Voyage AI API key** — https://voyage.ai, instant signup. Used for embeddings (semantic search on opportunities). Small spend, ~$5/mo at MacTech scale.

4. **Apify token** — https://console.apify.com, instant. Free tier is enough to start.

5. **SerpAPI key** — https://serpapi.com. Start on their Developer plan (~$75/mo). Defer this until Phase 2 if budget matters.

6. **Clerk account** — https://clerk.com, free to start. Create an application named "MacTech CaptureOS". Copy publishable key + secret key into `.env`.

7. **PostgreSQL hosting decision** — local Postgres via docker-compose covers you through Phase 1. For production, Fly.io's managed Postgres or Railway's Postgres is recommended; costs ~$15–$50/mo starting out.

**Not needed at all for Phase 1:** Anthropic commercial API key. You will add this only when you start serving external customers (Phase 4+).

## How to run sessions productively

**Session pattern:**

1. `cd` into the repo.
2. Start Claude Code: `claude`.
3. Say: "Continue from PROGRESS.md" or specify a task.
4. Let Claude Code plan before coding — it will usually propose an approach first.
5. Ask questions. Correct direction early. Test as you go.
6. At session end: "Update PROGRESS.md with what we shipped today and what's next."
7. Review the diff, commit, push.

**When Claude Code asks its initial three questions, expect them to be something like:**

- Which hosting platform should we target for early deployment (Fly.io vs Railway vs self-hosted)?
- Do you want the repo public or private on GitHub?
- What's the minimum viable Phase 1 Week 1 demo — do you want `docker compose up` producing a running stack, or something visibly functional like the first SAM.gov ingestion?

Answer each honestly; "I don't know, you pick and explain why" is a completely valid answer.

## If Claude Code seems to be going off-track

Specific phrases that work:

- **Too much scaffolding:** "Stop. Reduce scope. What's the smallest thing that demos real value this session?"
- **Skipping context:** "Have you read CLAUDE.md and AGENT_ARCHITECTURE.md? Re-read them and tell me what they say about [X]."
- **Architectural drift:** "Pause. This contradicts AGENT_ARCHITECTURE.md section [X]. Explain the tradeoff before proceeding."
- **Overbuilding:** "We don't need [Y] for Phase 1 per ROADMAP.md. Cut it. We can revisit in Phase [N]."

You are in charge. Claude Code is a senior engineering agent, not an autopilot.

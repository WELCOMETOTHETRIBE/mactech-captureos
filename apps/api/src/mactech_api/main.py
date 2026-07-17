from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from mactech_db import async_session_factory
from sqlalchemy import text

from mactech_api.routes.agency_intel import router as agency_intel_router
from mactech_api.routes.amendments import router as amendments_router
from mactech_api.routes.ask import router as ask_router
from mactech_api.routes.bid_invites import router as bid_invites_router
from mactech_api.routes.brief import router as brief_router
from mactech_api.routes.capture import router as capture_router
from mactech_api.routes.capture_package import router as capture_package_router
from mactech_api.routes.cyber import router as cyber_router
from mactech_api.routes.cyber_scope import router as cyber_scope_router
from mactech_api.routes.cyber_scope_downstream import router as cyber_scope_downstream_router
from mactech_api.routes.cyber_scope_intelligence import router as cyber_scope_intelligence_router
from mactech_api.routes.drafts import router as drafts_router
from mactech_api.routes.eligibility import router as eligibility_router
from mactech_api.routes.events import router as events_router
from mactech_api.routes.explain import router as explain_router
from mactech_api.routes.forecasts import router as forecasts_router
from mactech_api.routes.founders import router as founders_router
from mactech_api.routes.integrations import router as integrations_router
from mactech_api.routes.library import router as library_router
from mactech_api.routes.library_import import router as library_import_router
from mactech_api.routes.me import router as me_router
from mactech_api.routes.onboarding import router as onboarding_router
from mactech_api.routes.opportunities import router as opportunities_router
from mactech_api.routes.past_performance import router as past_performance_router
from mactech_api.routes.pursuit_links import router as pursuit_links_router
from mactech_api.routes.pursuits import router as pursuits_router
from mactech_api.routes.sbir import router as sbir_router
from mactech_api.routes.search import router as search_router
from mactech_api.routes.settings import router as settings_router
from mactech_api.routes.solicitation import router as solicitation_router
from mactech_api.routes.teaming_partners import router as teaming_partners_router
from mactech_api.routes.web_mentions import router as web_mentions_router
from mactech_api.routes.webhooks import router as webhooks_router
from mactech_api.settings import settings

app = FastAPI(
    title="MacTech CaptureOS API",
    version="0.1.0",
    description="The operating system for defense contractors.",
)

_origins = [o.strip() for o in settings.cors_allow_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(me_router)
app.include_router(opportunities_router)
app.include_router(library_router)
app.include_router(settings_router)
app.include_router(pursuits_router)
app.include_router(pursuit_links_router)
app.include_router(past_performance_router)
app.include_router(teaming_partners_router)
app.include_router(drafts_router)
app.include_router(explain_router)
app.include_router(ask_router)
app.include_router(brief_router)
app.include_router(agency_intel_router)
app.include_router(search_router)
app.include_router(library_import_router)
app.include_router(onboarding_router)
app.include_router(founders_router)
app.include_router(web_mentions_router)
app.include_router(webhooks_router)
app.include_router(bid_invites_router)
app.include_router(events_router)
app.include_router(forecasts_router)
app.include_router(solicitation_router)
app.include_router(amendments_router)
app.include_router(eligibility_router)
app.include_router(integrations_router)
app.include_router(cyber_router)
app.include_router(cyber_scope_router)
app.include_router(cyber_scope_downstream_router)
app.include_router(cyber_scope_intelligence_router)
app.include_router(capture_package_router)
app.include_router(capture_router)
app.include_router(sbir_router)


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def root() -> str:
    return _LANDING_HTML


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok", "environment": settings.environment}


@app.get("/readyz")
async def readyz() -> dict[str, str]:
    session_factory = async_session_factory()
    async with session_factory() as session:
        await session.execute(text("select 1"))
    return {"status": "ready"}


_LANDING_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>MacTech CaptureOS</title>
<style>
  :root{--fg:#111;--mute:#555;--line:#e5e5e5;--accent:#1a3a5c;--bg:#fafafa}
  *{box-sizing:border-box}
  body{margin:0;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;background:var(--bg);color:var(--fg);line-height:1.5}
  main{max-width:720px;margin:0 auto;padding:64px 24px}
  .eyebrow{font-size:12px;letter-spacing:.12em;text-transform:uppercase;color:var(--mute);margin:0 0 8px}
  h1{font-size:28px;font-weight:600;margin:0 0 8px;letter-spacing:-0.01em}
  .tagline{color:var(--mute);margin:0 0 32px;font-size:16px}
  .card{border:1px solid var(--line);background:#fff;border-radius:6px;padding:20px 24px;margin:0 0 16px}
  .card h2{font-size:14px;font-weight:600;margin:0 0 12px;letter-spacing:.04em;text-transform:uppercase;color:var(--mute)}
  dl{margin:0;display:grid;grid-template-columns:140px 1fr;row-gap:8px;column-gap:16px;font-size:14px}
  dt{color:var(--mute)}
  dd{margin:0}
  a{color:var(--accent);text-decoration:none;border-bottom:1px solid var(--accent)}
  a:hover{opacity:0.7}
  .status-ok{display:inline-block;width:8px;height:8px;border-radius:50%;background:#2d8f4e;margin-right:6px;vertical-align:middle}
  footer{color:var(--mute);font-size:12px;margin-top:32px}
  code{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:13px;background:#f0f0f0;padding:1px 6px;border-radius:3px}
</style>
</head>
<body>
<main>
  <p class="eyebrow">MacTech CaptureOS</p>
  <h1>The operating system for defense contractors.</h1>
  <p class="tagline">Identify, win, and stay eligible for federal work.</p>

  <div class="card">
    <h2>Service</h2>
    <dl>
      <dt>API</dt><dd><span class="status-ok"></span>mactech-api &middot; v0.1.0</dd>
      <dt>Environment</dt><dd>production</dd>
      <dt>Phase</dt><dd>1 / Week 1 &mdash; skeleton + MacTech tenant seeded</dd>
      <dt>Dashboard</dt><dd>ships Phase 2 Week 5</dd>
    </dl>
  </div>

  <div class="card">
    <h2>Endpoints</h2>
    <dl>
      <dt>Health</dt><dd><a href="/healthz">/healthz</a></dd>
      <dt>Readiness</dt><dd><a href="/readyz">/readyz</a> <span style="color:var(--mute)">&mdash; verifies Postgres</span></dd>
      <dt>API docs</dt><dd><a href="/docs">/docs</a> &middot; <a href="/redoc">/redoc</a></dd>
      <dt>OpenAPI</dt><dd><a href="/openapi.json">/openapi.json</a></dd>
    </dl>
  </div>

  <footer>
    MacTech Solutions LLC &middot; SDVOSB-certified &middot; Veteran-Owned<br>
    <a href="https://www.mactechsolutionsllc.com">mactechsolutionsllc.com</a>
  </footer>
</main>
</body>
</html>"""

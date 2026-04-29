# MacTech Identity audit integration

CaptureOS API forwards audit events to the central
[MacTech Identity Command Center](https://www.suite.mactechsolutionsllc.com)
via its `/api/audit/ingest` endpoint.

## Required env vars

| Variable | Purpose |
| --- | --- |
| `MACTECH_IDENTITY_BASE_URL` | Defaults to `https://www.suite.mactechsolutionsllc.com`. Override only for staging. |
| `MACTECH_AUDIT_INGEST_API_KEY` | Bearer key shared with the central hub. Server-side only. |

## What is sent automatically

`mactech_api.auth.get_request_context` fires one `capture.session.opened`
event per Clerk user per process per hour, throttled in memory. Per-process
state is not shared across replicas, so worst case you see N events per
hour per user where N = replica count. Acceptable noise for a session
signal.

The event is dispatched as `asyncio.create_task(send_audit_log(...))`
so the request never waits for the hub. Errors inside `send_audit_log`
are logged via `logging.warning` and never raised — a hub outage cannot
break CaptureOS auth.

## How to log a custom event

```python
from mactech_api.mactech_audit_client import send_audit_log

await send_audit_log({
    "appKey": "capture",
    "eventType": "capture.opportunity.submitted",
    "eventCategory": "capture",
    "severity": "info",
    "action": f"Submitted opportunity #{opportunity_id} to bid review",
    "customerOrgClerkId": ctx.claims.tenant_org_id,
    "actorClerkUserId": ctx.claims.sub,
    "actorEmail": ctx.user.email,
    "resourceType": "opportunity",
    "resourceId": str(opportunity_id),
    "metadata": {"naics": "541512", "agency": "DoD"},
})
```

The full surface lives in
`apps/api/src/mactech_api/mactech_audit_client.py`. The server-side
payload schema is enforced by the central hub
(`mactech-suite-platform/lib/validations/audit.ts`).

## Python workers

The same client works from the workers package since it only depends on
`httpx` (already in capture's deps). Import from
`mactech_api.mactech_audit_client` if running inside the API process, or
copy the file into `apps/workers/src/...` if you want the workers package
to depend on it directly without a cross-package import.

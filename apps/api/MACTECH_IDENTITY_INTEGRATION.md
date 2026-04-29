# MacTech Identity Command Center — JIT tenant + user provisioning

CaptureOS API now reads the central
[MacTech Identity Command Center](https://www.suite.mactechsolutionsllc.com)
on every authenticated request to JIT-provision Tenants and Users
when they don't yet exist locally.

## What changed

`apps/api/src/mactech_api/auth.py > _resolve_tenant_and_user` previously:

  1. Looked up `Tenant` by `claims.tenant_org_id`. **Refused 403** if
     none existed.
  2. Looked up `User` by `claims.sub`. JIT-created if missing under the
     existing tenant.

After this change:

  1. Tenant lookup as before.
  2. **NEW** — If no Tenant exists for that Clerk org id, asks the ICC
     whether the Clerk user has access to `capture` via that org. On
     a hit, JIT-creates the Tenant from the ICC org metadata (name,
     slug derived from the Clerk org id, clerk_org_id link). On a
     miss, returns the same 403 with a clearer message that points
     the operator at the central admin.
  3. User lookup + JIT create as before, but the new user's `role` is
     now mapped from the central role: `customer_owner → owner`,
     `customer_admin → admin`, everything else → `member`. Internal
     MacTech operators always become `owner`.

## Required env vars (already set on this service)

| Variable | Purpose |
| --- | --- |
| `MACTECH_IDENTITY_BASE_URL` | https://www.suite.mactechsolutionsllc.com |
| `MACTECH_AUDIT_INGEST_API_KEY` | Bearer key shared with the central hub |

The same key is reused for both the audit forwarder and the identity
check. Mint per-app keys in the central admin once the legacy env-var
key is rotated out.

## Failure mode

If the ICC is unreachable during a JIT-tenant lookup, the function
falls back to refusing 403 (since we can't safely create a tenant
without the ICC's say-so). Users with existing Tenants + Users are
unaffected. Fail-closed for tenant creation, fail-open for everything
else (since existing users keep working without ever hitting the ICC).

## Effect

To onboard a new customer org to capture:

  - Create the customer org in the central admin UI (this auto-creates
    the Clerk org, since we wired that earlier).
  - Set `capture` to enabled in the customer org's product
    entitlements.
  - Add the user to that org via the central admin UI.

When the user signs in to capture for the first time, capture
JIT-creates the local Tenant + User rows from ICC metadata, sets
the user's role from the ICC role, and the request proceeds.

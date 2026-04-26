# Clerk operations runbook

Identity for all four MacTech apps (Capture, Codex, Training, Quality) lives in a single Clerk instance. One sign-in covers all four.

- **Instance:** `ins_3CpKgTpccZN0TC5dZeBFLUbVMfk` (development tier — pre-production, free)
- **Org:** `org_3CpMVyinL6o6SydBwIPaz188MWk` ("MacTech Solutions")
- **Dashboard:** https://dashboard.clerk.com (switch env to "Development" — that's where ours lives until we promote to a prod instance)
- **Frontend API:** `helped-chimp-72.clerk.accounts.dev`

## Adding someone

```bash
# From the captureos repo root
export CLERK_SECRET_KEY=$(railway variables --service mactech-web --kv | grep '^CLERK_SECRET_KEY=' | cut -d= -f2-)

node scripts/clerk.mjs invite jon@mactechsolutionsllc.com           # member
node scripts/clerk.mjs invite jon@mactechsolutionsllc.com --role admin
```

What happens:
- If they don't exist in Clerk yet → email invitation sent. They click the link, set a password (or sign in with Google), and land in the app they were invited to.
- If they already exist (e.g. signed in to one app) → they're added to the MacTech org with the requested role.

Once they're in the MacTech org, they can sign in to all four apps with the same credentials. Each app's auth shim adopts their existing user row by email on first sign-in (or JIT-creates a new row).

## Removing someone

```bash
node scripts/clerk.mjs deactivate brian@mactechsolutionsllc.com   # ban + revoke all sessions
```

Their existing rows in each app's DB are kept (so document authorship, audit trails, etc. stay intact). They just can't sign in anywhere.

## Force sign-out (without removing)

```bash
node scripts/clerk.mjs revoke patrick@mactechsolutionsllc.com
```

## Snapshot of who has access

```bash
node scripts/clerk.mjs list                    # all members
node scripts/clerk.mjs list --role admin       # just admins
node scripts/clerk.mjs audit                   # adds the per-app DB queries you can run to verify Clerk ↔ local-user linkage
```

## What's set on the Clerk instance

| Setting | Value | Where it's set |
|---|---|---|
| Application name | MacTech | API (`PATCH /v1/instance`) |
| Support email | support@mactechsolutionsllc.com | API |
| Allowed origins | capture / codex / training / quality + localhost | API |
| Restricted mode | ON (no public sign-ups) | Dashboard → Configure → Restrictions |
| Allowed Google OAuth | Default Clerk shared OAuth (dev mode) | Dashboard |

## Per-app sign-out destinations

Each app's sign-out (top-right menu) sends users to `/sign-in` of that app, NOT the Clerk-hosted page. So the user always stays in MacTech-branded UX.

## When to promote to a Clerk Production instance

The current development instance has limits:
- 5 members per org maximum
- Clerk-hosted dev domain (`*.clerk.accounts.dev`) for the Frontend API
- "Development keys" warning banner in the browser console

Promote when any of these is true:
1. You need >5 members in the MacTech org (or any future customer org)
2. You want a custom Clerk Frontend API domain (e.g. `clerk.mactechsolutionsllc.com`) — required for clean cross-subdomain SSO via shared cookie
3. You want to use your own Google Cloud OAuth client (recommended before customer onboarding)
4. You're going to sit for SOC 2 or any audit — prod instance gets you Clerk's enterprise SLA + audit log retention

Promotion is a few hours of work: create a prod Clerk instance, configure custom domain, migrate users (Clerk has a one-click prod-clone tool), update env vars on all 4 Railway services, redeploy.

## Things still done in the dashboard (no API)

- Application **logo** upload
- Email/SMS **template themes** (colors, fonts in transactional emails)
- **Google OAuth** provider config (Google Cloud client ID/secret for production)
- **JWT template** creation and editing
- **Custom Clerk domain** (DNS verification flow)

For everything else, prefer `scripts/clerk.mjs` over the dashboard.

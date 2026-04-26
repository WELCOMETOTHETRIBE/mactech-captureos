# Clerk Production Migration Runbook

Status: **kicked off — waiting on three manual steps from Patrick before automated cutover.**

We're moving from Clerk's Development instance (`pk_test_…`, `helped-chimp-72.clerk.accounts.dev`) to a Clerk Production instance with a custom Frontend API at `clerk.mactechsolutionsllc.com`. Why we care:

- Removes the orange **"Development mode"** banner on every sign-in page
- Removes the **5-member-per-org** dev cap
- Enables real **cross-subdomain SSO via shared cookie** (one sign-in covers all 4 apps with no extra round-trips)
- Required before any external SOC 2 / CMMC audit prep that names Clerk as the IdP

## Your three manual steps (only you can do these)

### 1. Create the Production instance in Clerk dashboard
1. https://dashboard.clerk.com → **Personal workspace → My Application**
2. Top-left environment dropdown → click **"+ Production"** (or "Promote to production")
3. Confirm. Clerk clones your dev settings (auth strategies, restricted mode, allowed origins, JWT templates) into the new instance.
4. **Copy the new keys** from API Keys page:
   - `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_live_…`
   - `CLERK_SECRET_KEY=sk_live_…`
5. **Copy the new MacTech org id** from Organizations tab — it'll be a fresh `org_…` (not the dev one).

### 2. Add DNS records for `clerk.mactechsolutionsllc.com`
Clerk's dashboard will show you 5 CNAME records when you set the production Frontend API domain. Add them in your domain registrar (Cloudflare / Route53 / wherever `mactechsolutionsllc.com` is hosted).

DNS propagation typically takes **15 min to 24 hours**. Clerk's dashboard will say "Verified" when ready.

### 3. Set up Google Cloud OAuth client for production
Dev mode used Clerk's shared OAuth app. Prod needs your own:
1. https://console.cloud.google.com → Create project (or reuse one) → **APIs & Services → Credentials → Create OAuth 2.0 Client ID**
2. Application type: **Web application**
3. Authorized redirect URI: paste the one Clerk's dashboard shows (it'll be `https://clerk.mactechsolutionsllc.com/v1/oauth_callback` or similar)
4. Copy the **Client ID + Client Secret** → paste into Clerk dashboard → **User & authentication → Social Connections → Google**
5. Click **Verify** in Clerk

## What I run, in order, once you give me the keys

Pre-staged in `scripts/`:

```bash
# 1. Migrate users + the MacTech org from dev to prod (preserves bcrypt hashes)
CLERK_DEV_SECRET_KEY=sk_test_… \
CLERK_PROD_SECRET_KEY=sk_live_… \
CLERK_DEV_ORG_ID=org_3CpMVyinL6o6SydBwIPaz188MWk \
CLERK_PROD_ORG_ID=org_…<new prod org> \
node scripts/clerk-prod-migrate.mjs --dry-run    # always start with --dry-run
# review the plan, then re-run without --dry-run

# 2. Flip Railway env vars on all 5 services + trigger redeploys
PROD_PUBLISHABLE_KEY=pk_live_… \
PROD_SECRET_KEY=sk_live_… \
bash scripts/clerk-prod-cutover.sh

# 3. Re-link the local "MacTech" org row in each of the 4 app DBs
#    + clear stale clerk_user_id values so the auth shim adopts by email
psql "$CAPTURE_DB"  -f scripts/clerk-prod-relink.sql -v prod_org_id=org_…
psql "$CODEX_DB"    -f scripts/clerk-prod-relink.sql -v prod_org_id=org_…
psql "$TRAINING_DB" -f scripts/clerk-prod-relink.sql -v prod_org_id=org_…
psql "$QMS_DB"      -f scripts/clerk-prod-relink.sql -v prod_org_id=org_…
```

After step 3, every founder signs in once on each app. The auth shim adopts their existing local `users` row by email, stamps the new prod `clerk_user_id`, and they're back to normal — no data loss, no role reset.

## Rollback plan

If anything goes sideways during step 2:
- Re-run `clerk-prod-cutover.sh` with the original `pk_test_` / `sk_test_` values
- Re-run `clerk-prod-relink.sql` with the dev org id (`org_3CpMVyinL6o6SydBwIPaz188MWk`)
- All four apps are back on the dev instance within ~5 min

The dev instance stays alive after the migration — it doesn't get deleted. So rollback is always possible until you choose to retire dev.

## Cost note

Clerk Production starts free for the first 10k MAU. We're at ~25 across all four apps. No new spend triggered by this migration.

## What stays unchanged

- App code — none of the 4 repos need any code change. Only env vars.
- The `mactech-clerk` CLI (`scripts/clerk.mjs`) — same Backend API, just point `CLERK_SECRET_KEY` at the new prod key.
- Brand panels, footers, sign-in design — all unchanged.

## When you're ready

Send me:
1. `pk_live_…` (publishable)
2. `sk_live_…` (secret)
3. The new MacTech org id from prod
4. Confirmation that DNS shows "Verified" in Clerk's dashboard
5. Confirmation that Google OAuth shows "Verified" in Clerk's dashboard

I'll fire the 3-script sequence above, watch the deploys, and verify each app comes up clean.

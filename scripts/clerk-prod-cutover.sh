#!/usr/bin/env bash
# Flip all 5 Railway services from Clerk dev keys to prod keys.
# Run AFTER scripts/clerk-prod-migrate.mjs has migrated users + org.
#
# Required env (export them before running, or pass inline):
#   PROD_PUBLISHABLE_KEY=pk_live_…
#   PROD_SECRET_KEY=sk_live_…

set -euo pipefail

: "${PROD_PUBLISHABLE_KEY:?Set PROD_PUBLISHABLE_KEY=pk_live_…}"
: "${PROD_SECRET_KEY:?Set PROD_SECRET_KEY=sk_live_…}"

# (project-id, service-name) pairs.
SERVICES=(
  "captureOS:mactech-web:644284bd-ab31-41cd-89ae-fc3ce0c8a705:b5587be1-7c74-44eb-a7ad-a71766f80693"
  "codex:CMMC:::"
  "training:MacTech_Training:203f29bc-93bc-499e-bd29-38c0dc0bc5bd:c737c7f9-fc0a-48de-a6b1-c6fb0dfc3185"
  "QMS:QMS:d5aba872-4779-48c8-8d9f-574e4151316f:c89fd086-5d87-4908-b423-454628f17cfa"
)

# Capture's FastAPI back-end also reads CLERK_SECRET_KEY for JWT verification.
# We update it too so backend tokens validate against the prod JWKS.
SERVICES+=("captureOS:mactech-api:644284bd-ab31-41cd-89ae-fc3ce0c8a705:b5587be1-7c74-44eb-a7ad-a71766f80693")

for entry in "${SERVICES[@]}"; do
  IFS=':' read -r LABEL SVC PROJECT ENV <<< "$entry"
  echo "=== $LABEL ($SVC) ==="
  if [ -n "$PROJECT" ]; then
    railway link --project "$PROJECT" --environment "$ENV" >/dev/null 2>&1 || true
  fi

  # Vite frontend (QMS) uses VITE_CLERK_PUBLISHABLE_KEY; the others use NEXT_PUBLIC_*.
  if [ "$SVC" = "QMS" ]; then
    railway variables --service "$SVC" \
      --set "VITE_CLERK_PUBLISHABLE_KEY=$PROD_PUBLISHABLE_KEY" \
      --set "CLERK_SECRET_KEY=$PROD_SECRET_KEY" \
      --skip-deploys
  else
    railway variables --service "$SVC" \
      --set "NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=$PROD_PUBLISHABLE_KEY" \
      --set "CLERK_SECRET_KEY=$PROD_SECRET_KEY" \
      --skip-deploys
  fi

  railway redeploy --service "$SVC" --yes
done

echo
echo "All services flipped to prod keys + redeploy queued."
echo "Watch deploys: \`railway deployment list --service <SVC>\`"

#!/usr/bin/env node
/**
 * Migrate users + the MacTech org from a Clerk Development instance to
 * a Clerk Production instance.
 *
 * Run AFTER you've created the prod instance in Clerk dashboard and
 * have the new keys + the new MacTech org id.
 *
 *   CLERK_DEV_SECRET_KEY=sk_test_…  \
 *   CLERK_PROD_SECRET_KEY=sk_live_… \
 *   CLERK_DEV_ORG_ID=org_3CpMVy…    \
 *   CLERK_PROD_ORG_ID=org_…         \
 *   node scripts/clerk-prod-migrate.mjs [--dry-run]
 *
 * What it does (idempotent):
 *   1. List every user in the dev instance.
 *   2. For each, look up by email in prod. If found, skip. If not, create
 *      in prod preserving the bcrypt hash via passwordDigest+passwordHasher,
 *      external_id pointing back to the local DB user.id, and the prior
 *      first/last name.
 *   3. Add each migrated user to the prod MacTech org with the same role
 *      they had in dev (org:admin / org:member).
 *
 * What it does NOT do (handle separately):
 *   • Update Railway env vars on the 5 services — `scripts/clerk-prod-cutover.sh`
 *   • Update each app's local DB row to link the NEW prod org id —
 *     `scripts/clerk-prod-relink.sql` (run against each prod Postgres)
 *
 * Zero deps — Node 18+ built-in fetch.
 */

const DEV = process.env.CLERK_DEV_SECRET_KEY
const PROD = process.env.CLERK_PROD_SECRET_KEY
const DEV_ORG = process.env.CLERK_DEV_ORG_ID
const PROD_ORG = process.env.CLERK_PROD_ORG_ID
const DRY = process.argv.includes('--dry-run')

if (!DEV || !PROD || !DEV_ORG || !PROD_ORG) {
  console.error('Required env: CLERK_DEV_SECRET_KEY, CLERK_PROD_SECRET_KEY, CLERK_DEV_ORG_ID, CLERK_PROD_ORG_ID')
  process.exit(1)
}

const API = 'https://api.clerk.com/v1'

async function call(key, path, init = {}) {
  const res = await fetch(`${API}${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${key}`,
      'Content-Type': 'application/json',
      ...(init.headers ?? {}),
    },
  })
  const text = await res.text()
  let body
  try { body = text ? JSON.parse(text) : null } catch { body = text }
  if (!res.ok) {
    const err = body?.errors?.[0]?.long_message || body?.errors?.[0]?.message || text || `HTTP ${res.status}`
    throw new Error(`${res.status} ${path}: ${err}`)
  }
  return body
}

async function listAllOrgMembers(key, orgId) {
  const out = []
  let offset = 0
  // Clerk paginates at 100 max.
  while (true) {
    const page = await call(key, `/organizations/${orgId}/memberships?limit=100&offset=${offset}`)
    const items = page?.data ?? []
    out.push(...items)
    if (items.length < 100) break
    offset += 100
  }
  return out
}

async function getUser(key, userId) {
  return call(key, `/users/${userId}`)
}

async function findProdUserByEmail(email) {
  const data = await call(PROD, `/users?email_address=${encodeURIComponent(email)}`)
  return Array.isArray(data) ? data[0] : data?.data?.[0] ?? null
}

async function main() {
  console.log(`[plan] dev org ${DEV_ORG} -> prod org ${PROD_ORG}${DRY ? ' (dry-run)' : ''}`)

  const memberships = await listAllOrgMembers(DEV, DEV_ORG)
  console.log(`[plan] ${memberships.length} dev memberships to process`)

  let created = 0
  let linked = 0
  let alreadyMember = 0
  let failed = 0

  for (const m of memberships) {
    const devUserId = m.public_user_data?.user_id
    const role = m.role // org:admin | org:member
    const identifier = m.public_user_data?.identifier
    if (!devUserId) { failed++; continue }

    let devUser
    try {
      devUser = await getUser(DEV, devUserId)
    } catch (e) {
      console.warn(`[skip] could not fetch dev user ${devUserId} (${identifier}): ${e.message}`)
      failed++
      continue
    }

    const email = devUser?.email_addresses?.find((e) => e.id === devUser.primary_email_address_id)?.email_address
      ?? devUser?.email_addresses?.[0]?.email_address
      ?? null

    if (!email) {
      console.warn(`[skip] dev user ${devUserId} has no email`)
      failed++
      continue
    }

    let prodUser = await findProdUserByEmail(email)

    if (!prodUser) {
      const payload = {
        email_address: [email],
        first_name: devUser.first_name ?? undefined,
        last_name: devUser.last_name ?? undefined,
        external_id: devUser.external_id ?? undefined,
        skip_password_checks: true,
        ...(devUser.password_enabled
          ? {
              // Bring over the bcrypt hash if Clerk stored one in dev.
              // (Users who only ever signed in with Google won't have one;
              // they'll just sign in with Google again on prod.)
              password_digest: devUser.password_digest ?? undefined,
              password_hasher: devUser.password_digest ? 'bcrypt' : undefined,
            }
          : {}),
      }
      // Strip undefined fields the API rejects.
      Object.keys(payload).forEach((k) => payload[k] === undefined && delete payload[k])

      if (DRY) {
        console.log(`[would create] ${email} (role ${role})`)
        created++
      } else {
        try {
          prodUser = await call(PROD, `/users`, { method: 'POST', body: JSON.stringify(payload) })
          created++
          console.log(`[created] ${email} -> ${prodUser.id}`)
        } catch (e) {
          console.error(`[FAIL create] ${email}: ${e.message}`)
          failed++
          continue
        }
      }
    } else {
      linked++
      console.log(`[linked] ${email} already exists in prod -> ${prodUser.id}`)
    }

    // Add to prod MacTech org with the same role.
    if (!DRY && prodUser?.id) {
      try {
        await call(PROD, `/organizations/${PROD_ORG}/memberships`, {
          method: 'POST',
          body: JSON.stringify({ user_id: prodUser.id, role }),
        })
      } catch (e) {
        if (/already a member|already exists/i.test(e.message)) {
          alreadyMember++
        } else {
          console.warn(`[org membership warning] ${email}: ${e.message}`)
        }
      }
    }
  }

  console.log(`\n[done] created: ${created}  linked-existing: ${linked}  already-in-org: ${alreadyMember}  failed: ${failed}`)
  if (DRY) console.log('[dry-run] no writes performed')
}

main().catch((e) => {
  console.error(e)
  process.exit(1)
})

#!/usr/bin/env node
/**
 * mactech-clerk — operational CLI for the MacTech Clerk instance.
 *
 *   node scripts/clerk.mjs invite     <email> [--role admin|member]
 *   node scripts/clerk.mjs list       [--role admin|member]
 *   node scripts/clerk.mjs deactivate <email>     (ban + revoke all sessions)
 *   node scripts/clerk.mjs revoke     <email>     (revoke all sessions, keep account)
 *   node scripts/clerk.mjs audit                  (org membership snapshot)
 *
 * Env: CLERK_SECRET_KEY (required), MACTECH_CLERK_ORG_ID (optional, defaults
 * to the prod MacTech org).
 *
 * Zero deps — uses Node 18+ built-in fetch. Run from anywhere with Node 18+.
 */

const KEY = process.env.CLERK_SECRET_KEY
const ORG_ID = process.env.MACTECH_CLERK_ORG_ID ?? 'org_3CpMVyinL6o6SydBwIPaz188MWk'
const API = 'https://api.clerk.com/v1'

if (!KEY) {
  console.error('CLERK_SECRET_KEY not set. Pull it from any Railway service: `railway variables --service mactech-web --kv | grep CLERK_SECRET_KEY`')
  process.exit(1)
}

async function clerk(path, init = {}) {
  const res = await fetch(`${API}${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${KEY}`,
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

const argFlag = (name) => {
  const idx = process.argv.indexOf(`--${name}`)
  return idx >= 0 ? process.argv[idx + 1] : null
}

async function findUserByEmail(email) {
  const data = await clerk(`/users?email_address=${encodeURIComponent(email)}`)
  return Array.isArray(data) ? data[0] : data?.data?.[0] ?? null
}

async function cmdInvite(email) {
  if (!email) throw new Error('email required')
  const role = (argFlag('role') || 'member').toLowerCase()
  const clerkRole = role === 'admin' ? 'org:admin' : 'org:member'

  const existing = await findUserByEmail(email)
  if (existing) {
    try {
      await clerk(`/organizations/${ORG_ID}/memberships`, {
        method: 'POST',
        body: JSON.stringify({ user_id: existing.id, role: clerkRole }),
      })
      console.log(`✓ existing user ${email} added to MacTech org as ${clerkRole}`)
    } catch (e) {
      if (/already a member/i.test(e.message)) {
        console.log(`• ${email} is already in the MacTech org`)
      } else throw e
    }
    return
  }

  const inv = await clerk(`/organizations/${ORG_ID}/invitations`, {
    method: 'POST',
    body: JSON.stringify({
      email_address: email,
      role: clerkRole,
      inviter_user_id: null,
      redirect_url: 'https://capture.mactechsolutionsllc.com/sign-in',
    }),
  })
  console.log(`✓ invitation sent to ${email} (id ${inv.id}, role ${clerkRole}). They'll receive an email from Clerk.`)
}

async function cmdList() {
  const filter = argFlag('role')
  const data = await clerk(`/organizations/${ORG_ID}/memberships?limit=100`)
  const rows = (data?.data ?? []).map((m) => ({
    email: m.public_user_data?.identifier,
    role: m.role,
    user_id: m.public_user_data?.user_id,
  }))
  const out = filter ? rows.filter((r) => r.role.endsWith(filter.toLowerCase())) : rows
  console.log(`\nMacTech org — ${out.length} member${out.length === 1 ? '' : 's'}\n`)
  for (const r of out) console.log(`  ${r.email.padEnd(40)} ${r.role.padEnd(14)} ${r.user_id}`)
  console.log()
}

async function cmdDeactivate(email) {
  if (!email) throw new Error('email required')
  const u = await findUserByEmail(email)
  if (!u) throw new Error(`no Clerk user with email ${email}`)
  await clerk(`/users/${u.id}/ban`, { method: 'POST' })
  const sessions = await clerk(`/sessions?user_id=${u.id}&status=active`)
  for (const s of sessions?.data ?? []) {
    await clerk(`/sessions/${s.id}/revoke`, { method: 'POST' })
  }
  console.log(`✓ ${email} banned + ${sessions?.data?.length ?? 0} active session(s) revoked`)
}

async function cmdRevoke(email) {
  if (!email) throw new Error('email required')
  const u = await findUserByEmail(email)
  if (!u) throw new Error(`no Clerk user with email ${email}`)
  const sessions = await clerk(`/sessions?user_id=${u.id}&status=active`)
  for (const s of sessions?.data ?? []) {
    await clerk(`/sessions/${s.id}/revoke`, { method: 'POST' })
  }
  console.log(`✓ revoked ${sessions?.data?.length ?? 0} active session(s) for ${email}`)
}

async function cmdAudit() {
  await cmdList()
  console.log('Per-app DB linkage:')
  console.log('  capture:  SELECT email FROM users WHERE clerk_user_id IS NOT NULL;')
  console.log('  codex:    SELECT email FROM users WHERE clerk_user_id IS NOT NULL;')
  console.log('  training: SELECT email FROM "User" WHERE "clerkUserId" IS NOT NULL;')
  console.log('  qms:      SELECT email FROM users WHERE clerk_user_id IS NOT NULL;')
  console.log('\nRun those against each Railway Postgres to confirm Clerk → local user mapping.\n')
}

const [, , cmd, arg] = process.argv
const handlers = {
  invite: cmdInvite,
  list: cmdList,
  deactivate: cmdDeactivate,
  revoke: cmdRevoke,
  audit: cmdAudit,
}
const handler = handlers[cmd]
if (!handler) {
  console.error('Usage: clerk.mjs <invite|list|deactivate|revoke|audit> [args]')
  process.exit(1)
}
handler(arg).catch((e) => {
  console.error(`Error: ${e.message}`)
  process.exit(1)
})

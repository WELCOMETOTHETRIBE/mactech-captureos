-- Re-link each app's local "MacTech" org row to the new Clerk PROD org id.
-- Run separately against each app's prod Postgres after the prod instance
-- exists and you have the new org id.
--
-- Replace :prod_org_id with the new Clerk org id (e.g. org_3D…live…).
--
-- Capture (mactech-captureos):
UPDATE tenants
   SET clerk_org_id = ':prod_org_id'
 WHERE slug = 'mactech';
--
-- Codex (CMMC control plane):
UPDATE organizations
   SET clerk_org_id = ':prod_org_id'
 WHERE slug = 'mactech-solutions-llc';
--
-- Training (MacTech_Training):
UPDATE "Organization"
   SET "clerkOrgId" = ':prod_org_id'
 WHERE slug = 'demo';
--
-- QMS:
UPDATE organizations
   SET clerk_org_id = ':prod_org_id'
 WHERE slug = 'primary';
--
-- Also: clear stale clerkUserId values across all 4 apps so the auth shim
-- adopts users by email on first prod sign-in instead of trying to match
-- the old dev-instance user_id (which no longer exists).
--
-- Capture:
UPDATE users SET clerk_user_id = NULL;
-- Codex:
UPDATE users SET clerk_user_id = NULL;
-- Training:
UPDATE "User" SET "clerkUserId" = NULL;
-- QMS:
UPDATE users SET clerk_user_id = NULL;

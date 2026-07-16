"""Project a Suite capability profile onto a founder (ADR-0003 phase 5).

The member fills their profile in once, in bizops, from a resume they confirm
field-by-field. This projects the parts of it this app has a home for onto the
founder record, so nobody maintains the same person by hand in two systems.

**The link is the Clerk user id, and it already exists.** `users.clerk_user_id`
is set from the token's `sub` at sign-in and `users.founder_id` already records
which founder that person is; the Suite keys the same human by
`UserProfile.clerkUserId` (unique). So the chain is
`users.clerk_user_id -> Suite profile` and `users.founder_id -> founder`, using
only identifiers both systems already store. No column was added for this, there
is nothing to backfill, and no email is ever matched — an email match is the one
mechanism that could have attached one person's clearance to another's card.

A user with no `founder_id`, or a founder with no user, is simply skipped:
ordinary, not an error.

**What this owns, and what it must never touch.**

Synced (bizops is authoritative):
    founders.title  <- headline
    founders.bio    <- summary
    founder_naics_matrix rows  <- the member's confirmed NAICS codes

Never written here — this app owns them, and a resume cannot produce them:
    founder_naics_matrix.affinity   (hand-tuned routing weight)
    founders.pillar / full_name / email / digest settings
    any NAICS pair a human added that the profile does not mention

That last one is the important one and it is the easy thing to get wrong. The
obvious implementation — delete this founder's matrix rows and re-insert from
the profile — would silently replace curated capture intelligence with an LLM's
read of a PDF. The registry encodes *why* a code fits and who it routes to; the
profile encodes what one person's resume defends. They are different claims, and
the resume's silence on a code is not evidence against it. So the write is
**additive on the join**: new pairs are inserted, existing pairs are left
completely alone, and nothing is ever deleted.

Consequence, accepted: a code the member *removes* from their profile stays on
the founder until a human removes it here. That asymmetry is deliberate —
un-routing someone from work they were curated into should be a human's
decision, not a side effect of a resume re-upload.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from mactech_db.models.founder import Founder, FounderNaicsMatrix
from mactech_db.models.naics import NaicsCode
from mactech_db.models.user import User
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from mactech_api.mactech_profile_client import MemberProfile, fetch_member_profile

logger = logging.getLogger("mactech_profile_sync")

# Affinity given to a code the member's own profile supports but nobody has
# tuned yet. Matches the column's server_default: a synced code should start
# exactly as neutral as a hand-added one, not louder.
DEFAULT_AFFINITY = 1


@dataclass(frozen=True)
class SyncPlan:
    """What a sync *would* do. Pure — no session, no I/O.

    Split out so the rules are testable directly (this repo has no Postgres
    harness; see apps/api/tests/test_bid_invite_unseen.py). It is also the
    thing `--dry-run` prints, so what a reviewer reads is literally what the
    writer will execute.
    """

    title: str | None
    bio: str | None
    naics_to_add: tuple[str, ...]
    naics_skipped_unknown: tuple[str, ...]
    naics_already_present: tuple[str, ...]

    @property
    def changes_anything(self) -> bool:
        return self.title is not None or self.bio is not None or bool(self.naics_to_add)


def plan_founder_sync(
    *,
    current_title: str | None,
    current_bio: str | None,
    existing_codes: set[str],
    known_codes: set[str],
    profile: MemberProfile,
) -> SyncPlan:
    """Decide what to change. Never decides to remove anything.

    `title`/`bio` are None when there is nothing to do — either the profile is
    silent or the founder already matches. A member who has not written a
    headline must not blank a title someone typed here: an empty profile field
    is absence of a claim, not a claim of absence.

    NAICS is partitioned, never replaced:
      - already present -> left alone (it may carry a hand-tuned affinity)
      - not in this app's curated naics_codes -> skipped and reported, never
        auto-created; the FK would reject it and inventing a row would put an
        uncurated code in a curated table
      - otherwise -> added

    A code on the founder that the profile does not mention is *not* in any
    bucket, because nothing here removes it. The resume's silence is not
    evidence against a human's judgement.
    """

    title = profile.headline if (profile.headline and current_title != profile.headline) else None
    bio = profile.summary if (profile.summary and current_bio != profile.summary) else None

    to_add: list[str] = []
    skipped: list[str] = []
    already: list[str] = []
    for code in profile.naics_codes:
        if code in existing_codes:
            already.append(code)
        elif code not in known_codes:
            skipped.append(code)
        else:
            to_add.append(code)

    return SyncPlan(
        title=title,
        bio=bio,
        naics_to_add=tuple(to_add),
        naics_skipped_unknown=tuple(skipped),
        naics_already_present=tuple(already),
    )


@dataclass(frozen=True)
class SyncResult:
    founder_id: str
    linked: bool
    profile_found: bool
    title_updated: bool
    bio_updated: bool
    naics_added: tuple[str, ...]
    naics_skipped_unknown: tuple[str, ...]
    naics_already_present: tuple[str, ...]

    @property
    def changed(self) -> bool:
        return self.title_updated or self.bio_updated or bool(self.naics_added)


async def sync_founder_from_profile(
    session: AsyncSession,
    user: User,
    founder: Founder,
    *,
    profile: MemberProfile | None = None,
    dry_run: bool = False,
) -> SyncResult:
    """Bring one founder in line with the Suite profile of the user who is it.

    `user` supplies the identity (its `clerk_user_id`); `founder` is the record
    that identity already points at via `users.founder_id`. Pass `profile` to
    skip the fetch. `dry_run` computes without writing — the sync reports what
    it *would* do before it earns the right to do it.
    """

    empty = SyncResult(
        founder_id=str(founder.id),
        linked=user.clerk_user_id is not None,
        profile_found=False,
        title_updated=False,
        bio_updated=False,
        naics_added=(),
        naics_skipped_unknown=(),
        naics_already_present=(),
    )

    if not user.clerk_user_id:
        # A user row without a Clerk id has never signed in. Ordinary.
        return empty

    resolved = (
        profile if profile is not None else await fetch_member_profile(user.clerk_user_id)
    )
    if resolved is None:
        # No profile yet, or the Hub is unreachable. Both mean: leave the
        # founder exactly as it is. The client deliberately does not let us
        # tell these apart, because the right response is the same.
        return empty

    existing_rows = (
        (
            await session.execute(
                select(FounderNaicsMatrix.naics_code).where(
                    FounderNaicsMatrix.founder_id == founder.id
                )
            )
        )
        .scalars()
        .all()
    )

    # founder_naics_matrix.naics_code is a FK to naics_codes.code. This app's
    # table is curated (size standards, mactech_tier) and holds no guarantee of
    # covering every Census code the writer validated against.
    known = (
        set(
            (
                await session.execute(
                    select(NaicsCode.code).where(NaicsCode.code.in_(resolved.naics_codes))
                )
            )
            .scalars()
            .all()
        )
        if resolved.naics_codes
        else set()
    )

    plan = plan_founder_sync(
        current_title=founder.title,
        current_bio=founder.bio,
        existing_codes=set(existing_rows),
        known_codes=known,
        profile=resolved,
    )

    result = SyncResult(
        founder_id=str(founder.id),
        linked=True,
        profile_found=True,
        title_updated=plan.title is not None,
        bio_updated=plan.bio is not None,
        naics_added=plan.naics_to_add,
        naics_skipped_unknown=plan.naics_skipped_unknown,
        naics_already_present=plan.naics_already_present,
    )

    if dry_run:
        return result

    if plan.title is not None:
        founder.title = plan.title
    if plan.bio is not None:
        founder.bio = plan.bio

    if plan.naics_to_add:
        # ON CONFLICT DO NOTHING, not upsert: a pair that already exists carries
        # a hand-tuned affinity, and this sync has no business restating it.
        await session.execute(
            pg_insert(FounderNaicsMatrix)
            .values(
                [
                    {
                        "founder_id": founder.id,
                        "naics_code": code,
                        "affinity": DEFAULT_AFFINITY,
                    }
                    for code in plan.naics_to_add
                ]
            )
            .on_conflict_do_nothing(index_elements=["founder_id", "naics_code"])
        )

    if plan.naics_skipped_unknown:
        logger.warning(
            "[mactech-profile-sync] founder=%s codes not in naics_codes, skipped: %s",
            founder.id,
            ", ".join(plan.naics_skipped_unknown),
        )

    return result


async def sync_tenant_founders(
    session: AsyncSession,
    tenant_id: str,
    *,
    dry_run: bool = False,
) -> list[SyncResult]:
    """Sync every founder in one tenant that a signed-in user is linked to.

    Driven from `users`, not `founders`: the identity is what the Suite can
    resolve, and `users.founder_id` is what says whose card to update. A founder
    nobody has signed in as is skipped — there is no identity to ask about.
    """

    rows = (
        await session.execute(
            select(User, Founder)
            .join(Founder, Founder.id == User.founder_id)
            .where(
                User.tenant_id == tenant_id,
                User.founder_id.is_not(None),
                User.clerk_user_id.is_not(None),
            )
        )
    ).all()

    results = []
    for user, founder in rows:
        results.append(await sync_founder_from_profile(session, user, founder, dry_run=dry_run))
    return results

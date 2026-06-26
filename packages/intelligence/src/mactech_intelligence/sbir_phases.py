"""Per-phase user-message builders for the SBIR Submission Engine.

The system prompt (sbir-submission-engine.md) is global and carries all
the rules, constants, and overclaim guardrails. Each phase is one Claude
call whose USER message is a tight, focused brief — "do this phase, here
are the inputs and prior outputs, produce only the file content for X".

Keeping the phase logic here (separate from `sbir_submission_engine.py`,
the orchestrator) means the orchestrator stays a thin pipeline and each
phase's contract is read on a single screen.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VolumeSpec:
    """One Phase 5 sub-call — produce one volume file."""

    key: str  # used for phase event label
    relpath: str  # output file path inside workspace
    label: str  # human-readable phase label
    brief: str  # what to produce


# Phase 5 fans out across many files. Each entry produces one markdown
# artifact via its own streaming call. Ordering matters: earlier files
# become context for later ones (Vol 1 informs the Vol 2 abstract reuse,
# etc.) via the orchestrator's "prior outputs" payload.
VOLUME_SPECS: list[VolumeSpec] = [
    VolumeSpec(
        key="volume_1",
        relpath="volume-1-cover-sheet.md",
        label="Volume 1 — Cover sheet",
        brief=(
            "Produce the complete contents of `volume-1-cover-sheet.md` per the "
            "engine spec. Include the DSIP header field table, Technical Abstract "
            "(≤ 3,000 chars, character count at bottom), Anticipated Benefits "
            "abstract (≤ 3,000 chars, character count at bottom), Keywords "
            "(max 8, comma-separated), Proprietary page numbers field, and "
            "submitter notes. No emojis. No markdown code fences. The output "
            "IS the file content — do not preamble it."
        ),
    ),
    VolumeSpec(
        key="dsip_cheat_sheet",
        relpath="dsip-cheat-sheet.md",
        label="DSIP cheat sheet",
        brief=(
            "Produce the complete contents of `dsip-cheat-sheet.md` per the "
            "engine spec — paste-ready field-by-field walk for every DSIP form "
            "page including the 17 Vol I Proposal Certification yes/no questions "
            "with answers tailored to this proposal, Vol III cost fields in "
            "DSIP-required format (`100000.00` no commas), Vol IV CCR answer, "
            "Vol VII Foreign Disclosures answers. Output IS the file."
        ),
    ),
    VolumeSpec(
        key="volume_2",
        relpath="volume-2-technical.md",
        label="Volume 2 — Technical",
        brief=(
            "Produce the complete contents of `volume-2-technical.md` per the "
            "engine spec — all 12 BAA §3.7(c) sections in order, restrictive "
            "legend on first page, PI primary-employment certification block in "
            "§7, sister-proposal disclosure in §11.3, SBIR Data Rights assertions "
            "in §12. Output IS the file."
        ),
    ),
    VolumeSpec(
        key="volume_3",
        relpath="volume-3-cost.md",
        label="Volume 3 — Cost",
        brief=(
            "Produce the complete contents of `volume-3-cost.md` per the engine "
            "spec — cost summary landing exactly on the topic ceiling, POW table "
            "(MacTech ≥ 66.67%), Direct Labor detail, PI primary-employment "
            "certification, Travel/Materials/ODC, Subcontracts, cost narrative, "
            "Bluevine payment info, certifications. Show the Python cost-math "
            "verification at the end as a fenced block. Output IS the file."
        ),
    ),
    VolumeSpec(
        key="volume_4",
        relpath="volume-4-commercialization-report.md",
        label="Volume 4 — Commercialization Report",
        brief=(
            "Produce the complete contents of `volume-4-commercialization-report.md` "
            "per the engine spec — firm profile, zero prior SBIR/STTR awards, N/A "
            "commercialization-of-prior-work, sister-proposal disclosure table, "
            "commercialization strategy, SDVOSB socioeconomic dimension, required "
            "certifications. Output IS the file."
        ),
    ),
    VolumeSpec(
        key="volume_5_readme",
        relpath="volume-5-supporting/README.md",
        label="Volume 5 — Supporting (index)",
        brief=(
            "Produce `volume-5-supporting/README.md` — index of attachments and "
            "DSIP Vol V upload-slot guidance per the engine spec. Output IS the file."
        ),
    ),
    VolumeSpec(
        key="volume_5_pi_cv",
        relpath="volume-5-supporting/01-pi-cv.md",
        label="Volume 5 — PI CV",
        brief=(
            "Produce `volume-5-supporting/01-pi-cv.md` — the PI's CV with "
            "clearance, primary-employment certification, education, "
            "certifications, employment history, role on this Phase I, time "
            "commitment. Use only the PI personnel record from CONSTANTS or the "
            "user override. Output IS the file."
        ),
    ),
    VolumeSpec(
        key="volume_5_co_bio",
        relpath="volume-5-supporting/01b-bio-macdonald.md",
        label="Volume 5 — Brian MacDonald bio",
        brief=(
            "Produce `volume-5-supporting/01b-bio-macdonald.md` — Brian MacDonald "
            "biography (Founder, SDV basis, Corporate Official) per CONSTANTS. "
            "Output IS the file."
        ),
    ),
    VolumeSpec(
        key="volume_5_james_bio",
        relpath="volume-5-supporting/01c-bio-james-adams.md",
        label="Volume 5 — James Adams bio",
        brief=(
            "Produce `volume-5-supporting/01c-bio-james-adams.md` — James Adams "
            "biography (Quality, Configuration, Corpus Lead) per CONSTANTS. "
            "Output IS the file."
        ),
    ),
    VolumeSpec(
        key="volume_5_bibliography",
        relpath="volume-5-supporting/02-bibliography.md",
        label="Volume 5 — Bibliography",
        brief=(
            "Produce `volume-5-supporting/02-bibliography.md` — references cited "
            "in Vol 2. Include ONLY sources you can verify from inputs (topic PDF "
            "references, user-supplied attachments, public standard documents "
            "such as NIST/DFARS/FAR explicitly cited). Do not invent citations. "
            "If no verifiable sources exist, write a one-line note saying so. "
            "Output IS the file."
        ),
    ),
    VolumeSpec(
        key="volume_6",
        relpath="volume-6-fwa.md",
        label="Volume 6 — FWA",
        brief=(
            "Produce `volume-6-fwa.md` per the engine spec — firm-level FWA "
            "training note + verification checklist. Output IS the file."
        ),
    ),
    VolumeSpec(
        key="volume_7",
        relpath="volume-7-foreign-disclosures.md",
        label="Volume 7 — Foreign disclosures",
        brief=(
            "Produce `volume-7-foreign-disclosures.md` per the engine spec — "
            "form scaffold with clean all-No answers (SDVOSB, no foreign "
            "affiliations). Output IS the file."
        ),
    ),
    VolumeSpec(
        key="email_to_brian",
        relpath="email-to-brian.md",
        label="Email to Corporate Official",
        brief=(
            "Produce `email-to-brian.md` — draft email to Brian MacDonald telling "
            "him what to do in DSIP (log in, complete firm-level forms one-time, "
            "answer No on Vol IV question, certify). Include all firm data he "
            "might need and the deadline in ET. Output IS the file."
        ),
    ),
    VolumeSpec(
        key="readme",
        relpath="README.md",
        label="Package README",
        brief=(
            "Produce `README.md` for the submission package — topic, proposer, "
            "PI, Corporate Official, Phase, close date, inventory of files in "
            "this directory, DSIP certification instructions for the Corporate "
            "Official, sister-proposal disclosure summary. Output IS the file."
        ),
    ),
]

# Scaffold depth produces only these (engine spec: Vol 1 + DSIP cheat sheet).
SCAFFOLD_VOLUME_KEYS = {"volume_1", "dsip_cheat_sheet"}


def build_intake_user_message(input_summary: str) -> str:
    return (
        "PHASE 0 — INTAKE VALIDATION.\n\n"
        "Validate the following inputs against the engine's Phase 0 checks "
        "(all required inputs present, topic close date in future, no duplicate "
        "submission). Reply with EXACTLY ONE LINE:\n"
        "  VALIDATION_OK\n"
        "or\n"
        "  HALT: <one-sentence reason>\n\n"
        "Do not write any other content. Do not produce a file. Inputs follow.\n\n"
        f"{input_summary}\n"
    )


def build_topic_extract_user_message(
    input_summary: str, topic_payload: str
) -> str:
    return (
        "PHASE 1 — TOPIC ANALYSIS.\n\n"
        "Extract the topic facts per the engine spec and produce the COMPLETE "
        "contents of `topic-extract.md`. Include: topic number (canonical form), "
        "topic title, component instructions reference, ITAR/EAR language "
        "(verbatim if present), Phase I ceiling + duration, Phase I deliverables "
        "(verbatim list), Phase II scope + ceiling, Phase III dual-use, topic "
        "references (numbered), Technology Areas / Modernization Priorities / "
        "Keywords, Projected CMMC Level Requirement, TPOC. Use `⚠️ VERIFY:` "
        "for any required field that is genuinely absent from the topic text. "
        "The output IS the file content — do not preamble it.\n\n"
        f"--- INPUTS ---\n{input_summary}\n\n"
        f"--- TOPIC SOURCE TEXT ---\n{topic_payload}\n"
    )


def build_synergy_user_message(
    input_summary: str, topic_extract: str, synergy_hypothesis: str
) -> str:
    return (
        "PHASE 2 — FIRM-FIT + SYNERGY VALIDATION.\n\n"
        "Compare the user's synergy hypothesis against the topic requirements. "
        "Select the primary MacTech platform from the inventory. Produce the "
        "COMPLETE contents of `synergy-assessment.md` including: validated "
        "synergy framing (accept/refine/reject with reasoning), selected primary "
        "platform, Phase I work IS / IS NOT boundary statement, differentiators "
        "(only if substantiable; otherwise generic). The output IS the file.\n\n"
        f"--- USER SYNERGY HYPOTHESIS ---\n{synergy_hypothesis}\n\n"
        f"--- TOPIC EXTRACT ---\n{topic_extract}\n\n"
        f"--- INPUTS ---\n{input_summary}\n"
    )


def build_strategy_user_message(
    input_summary: str, topic_extract: str, synergy_assessment: str
) -> str:
    return (
        "PHASE 3 — STRATEGY AND STRUCTURE.\n\n"
        "Produce the COMPLETE contents of `strategy.md` covering: PI selection "
        "(with primary-employment validation), Key Personnel, labor allocation "
        "split (hours + dollars per person + per task), subcontract decision "
        "(T7 Independent Assessor or none), cost build line-by-line landing "
        "exactly on the topic ceiling with MacTech POW ≥ 66.67% (show the "
        "Python verification at the end as a fenced block), and synergy "
        "positioning. The output IS the file.\n\n"
        f"--- INPUTS ---\n{input_summary}\n\n"
        f"--- TOPIC EXTRACT ---\n{topic_extract}\n\n"
        f"--- SYNERGY ASSESSMENT ---\n{synergy_assessment}\n"
    )


def build_overclaim_user_message(
    input_summary: str,
    topic_extract: str,
    synergy_assessment: str,
    strategy: str,
) -> str:
    return (
        "PHASE 4 — OVERCLAIM AUDIT.\n\n"
        "Run the overclaim sweep against the inputs and the planned proposal "
        "content described in the prior phase outputs. For each claim category "
        "the engine spec lists, decide KEEP / DROP / FLAG and explain. Produce "
        "the COMPLETE contents of `overclaim-audit.md`. The output IS the file.\n\n"
        f"--- INPUTS ---\n{input_summary}\n\n"
        f"--- TOPIC EXTRACT ---\n{topic_extract}\n\n"
        f"--- SYNERGY ASSESSMENT ---\n{synergy_assessment}\n\n"
        f"--- STRATEGY ---\n{strategy}\n"
    )


def build_volume_user_message(spec: VolumeSpec, context: str) -> str:
    return (
        f"PHASE 5 — {spec.label.upper()}.\n\n"
        f"{spec.brief}\n\n"
        f"--- PRIOR PHASE OUTPUTS AND INPUTS ---\n{context}\n"
    )


def build_consistency_user_message(generated_files_payload: str) -> str:
    return (
        "PHASE 6 — CROSS-ARTIFACT CONSISTENCY SWEEP.\n\n"
        "Run the consistency checks the engine spec defines (topic number "
        "identical in all volumes; proposal title consistent across Vol 1 and "
        "Vol 2; dollar values reconcile to the ceiling; POW math = 100%; PI "
        "name and title consistent; sister proposals disclosed identically in "
        "Vol 2 §11.3 and Vol 4 §4; no leftover [BRACKETED] tokens other than "
        "`⚠️ VERIFY:` flags; no cross-contamination from prior topic platforms). "
        "Produce the COMPLETE contents of `inconsistency-report.md`. If "
        "everything reconciles, say so explicitly with a checklist of what was "
        "verified. The output IS the file.\n\n"
        f"--- GENERATED FILES ---\n{generated_files_payload}\n"
    )


def build_preflight_user_message(
    input_summary: str, verify_flags: list[str]
) -> str:
    flag_block = (
        "\n".join(f"- {f}" for f in verify_flags) if verify_flags else "(none)"
    )
    return (
        "PHASE 7 — PRE-FLIGHT CHECKLIST.\n\n"
        "Produce the COMPLETE contents of `preflight.md` covering the items "
        "the engine spec lists (firm registrations, CMMC SPRS status check, "
        "FWA training, DCAA attestation, bank info, all `⚠️ VERIFY:` flags "
        "resolved, sister-proposal disclosure confirmed, partner LOS sent/"
        "returned, DSIP firm forms completed, hours-to-deadline buffer "
        "target). Pre-populate the `⚠️ VERIFY:` section with the flags below. "
        "The output IS the file.\n\n"
        f"--- INPUTS ---\n{input_summary}\n\n"
        f"--- VERIFY FLAGS COLLECTED SO FAR ---\n{flag_block}\n"
    )

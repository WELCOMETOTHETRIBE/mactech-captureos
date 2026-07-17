"""Classify a procurement document before scope analysis.

Deterministic heuristics over filename + a text sample. Filename signals are
strong (SAM attachments are usually named "PWS.pdf", "Section L.pdf",
"Wage Determination.pdf"); text signals catch the untitled ones. Returns one of
``DOC_CLASSES``; ``other`` when nothing matches.
"""

from __future__ import annotations

import re

DOC_CLASSES = (
    "solicitation",
    "statement_of_work",
    "performance_work_statement",
    "scope_of_work",
    "specifications",
    "ufgs_specification",
    "drawing_index",
    "design_criteria",
    "section_l",
    "section_m",
    "clauses",
    "wage_determination",
    "amendment",
    "qa",
    "sources_sought",
    "capability_questionnaire",
    "bidder_list",
    "subcontracting_plan",
    "project_schedule",
    "cost_or_pricing",
    "past_performance_questionnaire",
    "security_classification_guide",
    "cdrl",
    "other",
)

# (doc_class, filename_regex, text_regex). First match wins; order = priority.
_RULES: list[tuple[str, re.Pattern[str] | None, re.Pattern[str] | None]] = [
    (
        "amendment",
        re.compile(r"amend|modification|\bmod\b", re.I),
        re.compile(r"amendment\s+(no|number|#)|SF\s?30", re.I),
    ),
    (
        "performance_work_statement",
        re.compile(r"\bpws\b|performance.?work", re.I),
        re.compile(r"performance\s+work\s+statement", re.I),
    ),
    (
        "statement_of_work",
        re.compile(r"\bsow\b|statement.?of.?work", re.I),
        re.compile(r"statement\s+of\s+work", re.I),
    ),
    ("scope_of_work", re.compile(r"scope.?of.?work", re.I), re.compile(r"scope\s+of\s+work", re.I)),
    (
        "ufgs_specification",
        re.compile(r"ufgs|division\s*2\d|\b2\d\s?\d\d\s?\d\d\b", re.I),
        re.compile(r"UFGS\s*\d\d\s?\d\d\s?\d\d|SECTION\s+2\d\s?\d\d\s?\d\d", re.I),
    ),
    (
        "specifications",
        re.compile(r"spec(ification)?s?\b", re.I),
        re.compile(r"technical\s+specification|part\s+\d\s+-\s+general", re.I),
    ),
    (
        "drawing_index",
        re.compile(r"drawing|\bdwg\b|sheet\s?index|plan", re.I),
        re.compile(r"drawing\s+index|sheet\s+list", re.I),
    ),
    (
        "design_criteria",
        re.compile(r"design.?criteria|\bdor\b|basis.?of.?design", re.I),
        re.compile(r"design\s+criteria|basis\s+of\s+design", re.I),
    ),
    (
        "section_l",
        re.compile(r"section.?l\b|instructions.?to.?offer", re.I),
        re.compile(r"SECTION\s+L\b|Instructions,?\s+Conditions", re.I),
    ),
    (
        "section_m",
        re.compile(r"section.?m\b|evaluation.?factor", re.I),
        re.compile(r"SECTION\s+M\b|Evaluation\s+Factors\s+for\s+Award", re.I),
    ),
    (
        "wage_determination",
        re.compile(r"wage.?determination|\bwd\b|davis.?bacon", re.I),
        re.compile(r"wage\s+determination|Davis[- ]Bacon", re.I),
    ),
    (
        "qa",
        re.compile(r"\bq\s?&\s?a\b|questions?.?answers?|rfi.?response", re.I),
        re.compile(r"questions?\s+and\s+answers|Q\s?&\s?A", re.I),
    ),
    (
        "sources_sought",
        re.compile(r"sources.?sought|\brfi\b", re.I),
        re.compile(r"sources\s+sought|request\s+for\s+information", re.I),
    ),
    (
        "capability_questionnaire",
        re.compile(r"capabilit|questionnaire", re.I),
        re.compile(r"capability\s+statement|please\s+describe\s+your", re.I),
    ),
    (
        "bidder_list",
        re.compile(r"bidder|plan.?holder|interested.?vendor", re.I),
        re.compile(r"plan\s?holders?\s+list|interested\s+vendors", re.I),
    ),
    (
        "subcontracting_plan",
        re.compile(r"subcontract(ing)?.?plan", re.I),
        re.compile(r"subcontracting\s+plan", re.I),
    ),
    (
        "project_schedule",
        re.compile(r"schedule|milestone|\bpop\b", re.I),
        re.compile(r"project\s+schedule|period\s+of\s+performance", re.I),
    ),
    (
        "cost_or_pricing",
        re.compile(r"price|pricing|cost|\bbid\s?schedule\b", re.I),
        re.compile(r"pricing\s+(sheet|schedule)|schedule\s+of\s+prices", re.I),
    ),
    (
        "past_performance_questionnaire",
        re.compile(r"past.?perform|\bppq\b", re.I),
        re.compile(r"past\s+performance\s+questionnaire", re.I),
    ),
    (
        "security_classification_guide",
        re.compile(r"\bscg\b|classification.?guide|dd.?254", re.I),
        re.compile(r"security\s+classification\s+guide|DD\s?254", re.I),
    ),
    (
        "cdrl",
        re.compile(r"\bcdrl\b|dd.?1423", re.I),
        re.compile(r"CDRL|DD\s?Form\s?1423|data\s+item", re.I),
    ),
    (
        "clauses",
        re.compile(r"clause|far|dfars", re.I),
        re.compile(r"52\.2\d\d-\d+|252\.2\d\d-\d+", re.I),
    ),
    (
        "solicitation",
        re.compile(r"solicitation|\brfp\b|\brfq\b|combined.?synopsis", re.I),
        re.compile(r"request\s+for\s+proposal|solicitation\s+number", re.I),
    ),
]


def classify_document(filename: str, text: str) -> str:
    name = filename or ""
    sample = (text or "")[:6000]
    for doc_class, name_re, _text_re in _RULES:
        if name_re is not None and name_re.search(name):
            return doc_class
    for doc_class, _name_re, text_re in _RULES:
        if text_re is not None and text_re.search(sample):
            return doc_class
    return "other"

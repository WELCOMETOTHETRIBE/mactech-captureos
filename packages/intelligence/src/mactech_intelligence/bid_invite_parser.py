"""Parse BuildingConnected notification emails into structured fields.

Every message BuildingConnected sends (invite, reminder, due-date
change, addendum, plain message) follows one of two text-body
templates:

  Invite:   "{Lead} from {Company} has invited you to bid on
             {Project}: {Bid package}
             ----------"
  Message:  "{Lead} of {Company} sent your company a message about
             {Project}: {Bid package}
             ----------
             {Headline}
             ------"

Both carry a "Project Details" block (Location: / Bid Due:) and a
"Client Details" / "Sender Details" block with the lead's contact
info, plus links to app.buildingconnected.com — including a stable
RFP id in ".../rfps/{24-hex}/bid" links that groups every email
about the same solicitation.

Parsing is deterministic regex over the plain-text body (line wrap
and whitespace vary, so patterns allow flexible whitespace and
results are whitespace-collapsed). Anything unrecognized degrades
gracefully: kind="other" with the subject as the title.
"""

from __future__ import annotations

import html
import re
from dataclasses import asdict, dataclass
from datetime import date, datetime

BID_INVITE_KINDS = (
    "invite",
    "reminder",
    "due_date_change",
    "addendum",
    "message",
    "reply",
    "other",
)

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE_RE = re.compile(r"\+?\d[\d ()./-]{8,}\d")
_RFP_ID_RE = re.compile(r"app\.buildingconnected\.com/rfps/([0-9a-f]{24})", re.I)
_GOTO_URL_RE = re.compile(r"https://app\.buildingconnected\.com/(?:goto|rfps)/[^\s)>\"]+", re.I)

_INVITE_RE = re.compile(
    r"(?P<lead>[^\n]{1,80}?)\s+from\s+(?P<company>.{1,120}?)\s+has\s+invited\s+"
    r"you\s+to\s+bid\s+on\s+(?P<title>.+?)\s*\n\s*-{3,}",
    re.S,
)
_MESSAGE_RE = re.compile(
    r"(?P<lead>[^\n]{1,80}?)\s+of\s+(?P<company>.{1,120}?)\s+sent\s+your\s+"
    r"company\s+a\s+message\s+about\s+(?P<title>.+?)\s*\n\s*-{3,}",
    re.S,
)
# The headline is the chunk right after the title's dash rule,
# terminated by its own (shorter) dash rule.
_HEADLINE_RE = re.compile(r"\s*(?P<headline>.+?)\s*\n\s*-{3,}", re.S)
_LOCATION_RE = re.compile(r"Location:\s*\n?(?P<loc>.+?)\n\s*\n", re.S)
_BID_DUE_RE = re.compile(r"Bid\s+Due:\s*\n?(?P<due>[^\n]+)")
# "extended August 4th, 2026", "extended to August 4, 2026"
_EXTENDED_RE = re.compile(
    r"extended\s+(?:to\s+|until\s+)?"
    r"(?P<date>[A-Z][a-z]+\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4})"
)
_DATE_IN_TEXT_RE = re.compile(r"(?P<date>[A-Z][a-z]+\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4})")


@dataclass
class ParsedBidInvite:
    kind: str = "other"
    project_name: str | None = None
    bid_package: str | None = None
    gc_company: str | None = None
    lead_name: str | None = None
    lead_email: str | None = None
    lead_phone: str | None = None
    location: str | None = None
    bid_due_on: date | None = None
    rfp_id: str | None = None
    rfp_url: str | None = None
    headline: str | None = None

    def as_dict(self) -> dict:
        d = asdict(self)
        d["bid_due_on"] = self.bid_due_on.isoformat() if self.bid_due_on else None
        return d


def _collapse(value: str | None) -> str | None:
    if value is None:
        return None
    out = html.unescape(re.sub(r"\s+", " ", value)).strip()
    return out or None


def _strip_subject_prefixes(subject: str) -> tuple[str, bool, bool]:
    """Return (stripped, was_reply, was_forward)."""
    s = subject.strip()
    was_reply = was_forward = False
    while True:
        low = s.lower()
        if low.startswith("re:"):
            was_reply, s = True, s[3:].lstrip()
        elif low.startswith("fwd:") or low.startswith("fw:"):
            was_forward = True
            s = s.split(":", 1)[1].lstrip()
        else:
            return s, was_reply, was_forward


def _parse_us_date(raw: str) -> date | None:
    cleaned = re.sub(r"(\d{1,2})(st|nd|rd|th)", r"\1", raw).replace(",", "")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    try:
        return datetime.strptime(cleaned, "%B %d %Y").date()
    except ValueError:
        return None


def _split_title(title: str | None) -> tuple[str | None, str | None]:
    """BuildingConnected titles read "{Project}: {Bid package}"."""
    if not title:
        return None, None
    if ":" in title:
        project, package = title.split(":", 1)
        return _collapse(project), _collapse(package)
    return _collapse(title), None


def _classify(
    subject: str, headline: str | None, *, invited: bool, messaged: bool, was_reply: bool
) -> str:
    probe = " ".join(filter(None, [subject.lower(), (headline or "").lower()]))
    if was_reply:
        return "reply"
    if invited:
        return "invite"
    if "due date extended" in probe or "due date change" in probe:
        return "due_date_change"
    if re.search(r"\baddend", probe):
        return "addendum"
    if "reminder" in probe:
        return "reminder"
    if messaged:
        return "message"
    return "other"


def _lead_contact(text: str) -> tuple[str | None, str | None, str | None]:
    """Pull the lead's email/phone from the Client/Sender Details block."""
    section = re.split(r"(?:Client|Sender)\s+Details", text, maxsplit=1)
    tail = section[1] if len(section) > 1 else text
    email = next(
        (e for e in _EMAIL_RE.findall(tail) if "buildingconnected" not in e.lower()),
        None,
    )
    phone_m = _PHONE_RE.search(tail.split("www.buildingconnected", 1)[0])
    phone = _collapse(phone_m.group(0)) if phone_m else None
    name_m = re.search(r"Lead:\s*\n?(?P<name>[^\n]+)", tail)
    name = _collapse(name_m.group("name")) if name_m else None
    return name, email, phone


def parse_bid_invite(subject: str, text_body: str | None) -> ParsedBidInvite:
    subject = _collapse(subject) or ""
    stripped_subject, was_reply, _was_forward = _strip_subject_prefixes(subject)
    text = (text_body or "").replace("\r\n", "\n").replace("\r", "\n")

    invite_m = _INVITE_RE.search(text)
    message_m = _MESSAGE_RE.search(text) if not invite_m else None
    template_m = invite_m or message_m

    title = _collapse(template_m.group("title")) if template_m else None
    if not title:
        # Fall back to the subject with its own prefixes removed.
        fallback = re.sub(r"^bid\s+invite:\s*", "", stripped_subject, flags=re.I)
        title = _collapse(fallback)
    project_name, bid_package = _split_title(title)

    headline = None
    message_body = ""
    if message_m:
        # Everything between the title's dash rule and the Project
        # Details block is the message: headline first, then optional
        # free-text (where a due-date extension states the new date).
        message_body = re.split(r"Project\s+Details", text[message_m.end() :], maxsplit=1)[0]
        headline_m = _HEADLINE_RE.match(message_body)
        if headline_m:
            headline = _collapse(headline_m.group("headline"))
            if headline and len(headline) > 200:
                headline = headline[:200].rsplit(" ", 1)[0] + "…"

    gc_company = _collapse(template_m.group("company")) if template_m else None
    lead_from_template = _collapse(template_m.group("lead")) if template_m else None
    lead_name, lead_email, lead_phone = _lead_contact(text)
    lead_name = lead_name or lead_from_template

    location_m = _LOCATION_RE.search(text)
    location = _collapse(location_m.group("loc")) if location_m else None

    bid_due_on = None
    due_m = _BID_DUE_RE.search(text)
    if due_m:
        bid_due_on = _parse_us_date(due_m.group("due"))
    # A due-date-extension message supersedes the (stale) Bid Due block.
    extension_source = " ".join(filter(None, [message_body, stripped_subject]))
    ext_m = _EXTENDED_RE.search(extension_source)
    if ext_m:
        bid_due_on = _parse_us_date(ext_m.group("date")) or bid_due_on
    elif headline and "due" in headline.lower() and not due_m:
        date_m = _DATE_IN_TEXT_RE.search(headline)
        if date_m:
            bid_due_on = _parse_us_date(date_m.group("date"))

    rfp_id_m = _RFP_ID_RE.search(text)
    rfp_url_m = _GOTO_URL_RE.search(text)
    rfp_id = rfp_id_m.group(1).lower() if rfp_id_m else None
    rfp_url = (
        f"https://app.buildingconnected.com/rfps/{rfp_id}/bid"
        if rfp_id
        else (rfp_url_m.group(0) if rfp_url_m else None)
    )

    kind = _classify(
        stripped_subject,
        headline,
        invited=invite_m is not None,
        messaged=message_m is not None,
        was_reply=was_reply,
    )

    return ParsedBidInvite(
        kind=kind,
        project_name=project_name,
        bid_package=bid_package,
        gc_company=gc_company,
        lead_name=lead_name,
        lead_email=lead_email,
        lead_phone=lead_phone,
        location=location,
        bid_due_on=bid_due_on,
        rfp_id=rfp_id,
        rfp_url=rfp_url,
        headline=headline,
    )

"""One-off: import historical bid-invite emails from a Google Takeout mbox.

Retroactive companion to the Postmark inbound webhook — Gmail forwarding
filters only apply to NEW mail, so the ~47 existing "Bid Invite"-labeled
emails come in via Takeout export instead:

  1. https://takeout.google.com → Deselect all → Mail →
     "All Mail data included" → select only the "Bid Invite" label →
     export, download the .mbox file.
  2. Run:
       python scripts/import_bid_invites_mbox.py path/to/BidInvite.mbox \
         --webhook-url "https://postmark:<secret>@<api-host>/webhooks/postmark/inbound"

POSTs each message to the same webhook the live flow uses, shaped like a
Postmark inbound payload, so parsing/storage/dedupe stay in one place.
MessageID is sha256(RFC-5322 Message-ID) — Gmail message-ids exceed the
64-char column, and hashing keeps re-runs idempotent.
"""

from __future__ import annotations

import argparse
import hashlib
import mailbox
import sys
import time
from email.header import decode_header, make_header
from email.message import Message
from email.utils import parseaddr

import httpx


def _decode(value: str | None) -> str:
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return value


def _bodies(msg: Message) -> tuple[str | None, str | None]:
    """Best-effort (text, html) extraction; skips attachments."""
    text_body: str | None = None
    html_body: str | None = None
    for part in msg.walk():
        if part.is_multipart():
            continue
        disposition = (part.get("Content-Disposition") or "").lower()
        if "attachment" in disposition:
            continue
        try:
            payload = part.get_payload(decode=True)
            if payload is None:
                continue
            charset = part.get_content_charset() or "utf-8"
            decoded = payload.decode(charset, errors="replace")
        except Exception:
            continue
        ctype = part.get_content_type()
        if ctype == "text/plain" and text_body is None:
            text_body = decoded
        elif ctype == "text/html" and html_body is None:
            html_body = decoded
    return text_body, html_body


def _attachments_meta(msg: Message) -> list[dict]:
    out = []
    for part in msg.walk():
        disposition = (part.get("Content-Disposition") or "").lower()
        if "attachment" not in disposition:
            continue
        payload = part.get_payload(decode=True) or b""
        out.append(
            {
                "Name": _decode(part.get_filename()) or "unnamed",
                "ContentType": part.get_content_type(),
                "ContentLength": len(payload),
            }
        )
    return out


def to_postmark_payload(msg: Message) -> dict | None:
    rfc_message_id = (msg.get("Message-ID") or "").strip()
    if not rfc_message_id:
        return None
    from_name, from_email = parseaddr(_decode(msg.get("From")))
    text_body, html_body = _bodies(msg)
    return {
        "MessageID": hashlib.sha256(rfc_message_id.encode()).hexdigest(),
        "Subject": _decode(msg.get("Subject")),
        "FromFull": {"Email": from_email or None, "Name": from_name or None},
        "TextBody": text_body,
        "HtmlBody": html_body,
        "Date": msg.get("Date"),
        "Attachments": _attachments_meta(msg),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mbox_path", help="Path to the Takeout .mbox file")
    parser.add_argument(
        "--webhook-url",
        required=True,
        help="Full webhook URL incl. basic auth: https://postmark:<secret>@host/webhooks/postmark/inbound",
    )
    parser.add_argument("--dry-run", action="store_true", help="Parse and print, don't POST")
    args = parser.parse_args()

    box = mailbox.mbox(args.mbox_path)
    stored = duplicates = skipped = failed = 0
    with httpx.Client(timeout=30) as client:
        for i, msg in enumerate(box):
            payload = to_postmark_payload(msg)
            if payload is None:
                skipped += 1
                print(f"[{i}] SKIP (no Message-ID)")
                continue
            if args.dry_run:
                print(f"[{i}] DRY {payload['Subject'][:80]!r} from {payload['FromFull']['Email']}")
                continue
            try:
                res = client.post(args.webhook_url, json=payload)
                res.raise_for_status()
                body = res.json()
            except Exception as exc:
                failed += 1
                print(f"[{i}] FAIL {payload['Subject'][:60]!r}: {exc}")
                continue
            if body.get("stored"):
                stored += 1
                print(f"[{i}] STORED {payload['Subject'][:80]!r}")
            else:
                duplicates += 1
                print(f"[{i}] {body.get('reason', '?').upper()} {payload['Subject'][:60]!r}")
            time.sleep(0.2)  # be gentle with the API service

    print(
        f"\ndone: {stored} stored, {duplicates} duplicate/ignored, "
        f"{skipped} skipped, {failed} failed"
    )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

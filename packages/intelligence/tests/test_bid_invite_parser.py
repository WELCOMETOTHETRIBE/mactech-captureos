"""BuildingConnected email parser — fixtures modeled on real templates.

The fixtures mirror the two production template shapes (invite /
message) including their line-wrapping quirks, verified against a
real Takeout export locally; all names, companies, addresses, and
contact details below are synthetic.
"""

from __future__ import annotations

from datetime import date

from mactech_intelligence.bid_invite_parser import parse_bid_invite

INVITE_TEXT = """BuildingConnected



Jordan Avery from
Example Builders Inc. has invited
you to
bid on

Riverbend County Jail Expansion: Emergency Responder Communications Enhancement System
----------------------------------------------------------


View this RFP (
https://app.buildingconnected.com/goto/6a5518b44c325500446982be19f5c68813eistb )

Project Details
---------------

Location:
100 Example Road, Ringgold, GA 30736, United States of America

Bid Due:
July 22, 2026

<div>A NEW 13,500SF WORK RELEASE/DORMITORY FACILITY</div>

Client Details
--------------


user

Lead:
Jordan Avery

Project Engineer •
+1 555-014-0100
•
javery@examplebuilders.com

company

Example Builders Inc.

www.buildingconnected.com ( http://www.buildingconnected.com )
"""

EXTENSION_TEXT = """BuildingConnected

Casey Morgan of Example Construction of Georgia
sent your company a message
about

Maple Hills ES Reno: Building Management Systems
-----------------------------------------------

Due Date Extended
------------

The due date for subcontractors has been extended August 4th, 2026.

Reply to
Thomas ( https://app.buildingconnected.com/goto/abc )
Send
Bid ( https://app.buildingconnected.com/rfps/6a565af20f3967bdf4d266f4/bid
)

Project Details
---------------

Location:
200 Example Parkway, Marietta, GA 30064, United States of America

Bid Due:
July 28, 2026

Sender Details
--------------

user

Casey Morgan

cmorgan@exampleconstruction.com
"""

REMINDER_TEXT = """BuildingConnected

Riley Quinn of Northside Construction, Inc.
sent your company a message
about

Roadside Grill - Leland, NC: Testing Services
-----------------------------------------------

Reminder Due date is Bids Due July 28th, 2026 at 5:00 PM EDT
------------

Reply to
Riley ( https://app.buildingconnected.com/goto/xyz )

Project Details
---------------

Location:
300 Example Drive, Leland, NC 28451, United States of America

Bid Due:
July 28, 2026
"""


def test_invite_extracts_everything() -> None:
    p = parse_bid_invite("Bid Invite: Riverbend County Jail Expansion Project", INVITE_TEXT)
    assert p.kind == "invite"
    assert p.project_name == "Riverbend County Jail Expansion"
    assert p.bid_package == "Emergency Responder Communications Enhancement System"
    assert p.gc_company == "Example Builders Inc."
    assert p.lead_name == "Jordan Avery"
    assert p.lead_email == "javery@examplebuilders.com"
    assert p.lead_phone == "+1 555-014-0100"
    assert p.location.startswith("100 Example Road, Ringgold")
    assert p.bid_due_on == date(2026, 7, 22)
    assert p.rfp_url.startswith("https://app.buildingconnected.com/goto/")


def test_due_date_extension_supersedes_stale_bid_due() -> None:
    p = parse_bid_invite("Due Date Extended - Maple Hills ES Reno", EXTENSION_TEXT)
    assert p.kind == "due_date_change"
    assert p.headline == "Due Date Extended"
    # Body's "Bid Due: July 28" is stale; the extension text wins.
    assert p.bid_due_on == date(2026, 8, 4)
    assert p.rfp_id == "6a565af20f3967bdf4d266f4"
    assert p.rfp_url == "https://app.buildingconnected.com/rfps/6a565af20f3967bdf4d266f4/bid"
    assert p.gc_company == "Example Construction of Georgia"
    assert p.lead_email == "cmorgan@exampleconstruction.com"


def test_reminder_kind_and_headline() -> None:
    p = parse_bid_invite(
        "Reminder Due date is Bids Due July 28th, 2026 at 5:00 PM ...",
        REMINDER_TEXT,
    )
    assert p.kind == "reminder"
    assert p.headline.startswith("Reminder Due date")
    assert p.bid_due_on == date(2026, 7, 28)
    assert p.project_name == "Roadside Grill - Leland, NC"
    assert p.bid_package == "Testing Services"


def test_reply_falls_back_to_subject() -> None:
    p = parse_bid_invite("Re: Bid Invite: WX2 Last Mile Facility Project", "")
    assert p.kind == "reply"
    assert p.project_name == "WX2 Last Mile Facility Project"
    assert p.bid_package is None
    assert p.bid_due_on is None


def test_forwarded_invite_still_parses_template() -> None:
    p = parse_bid_invite("Fwd: Bid Invite: Riverbend County Jail Expansion Project", INVITE_TEXT)
    assert p.kind == "invite"
    assert p.gc_company == "Example Builders Inc."


def test_unrecognized_body_degrades_to_other() -> None:
    p = parse_bid_invite("Important links for project access. - NUWC B000", "hello")
    assert p.kind == "other"
    assert p.project_name == "Important links for project access. - NUWC B000"
    assert p.gc_company is None


def test_html_entities_unescaped() -> None:
    text = INVITE_TEXT.replace(
        "Riverbend County Jail Expansion", "O&#39;Malley&#39;s Conversion Dodge City AL"
    )
    p = parse_bid_invite("Bid Invite: x", text)
    assert p.project_name == "O'Malley's Conversion Dodge City AL"

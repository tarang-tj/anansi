"""Baseline theme -- the 'before' DOM the scraper first learns to extract.

Detail pages: a .pantry-card div with an h1 name and <span class="..."> field
pairs for address/phone/hours/services/eligibility/languages/updated.
Index page: a .pantry-table listing, one .pantry-card row per pantry.
"""
from __future__ import annotations

from .helpers import BASE_CSS, page, render_detail_card, render_index_table

# Field -> CSS class map. Reused verbatim by m2 and m5 (which change hours'
# markup, not its classes) and imported by m3 (dl/dt/dd still needs the
# card/name classes for its wrapper).
CLASSES = {
    "card": "pantry-card",
    "name": "pantry-name",
    "address": "address",
    "phone": "phone",
    "hours": "hours",
    "services": "services",
    "eligibility": "eligibility",
    "languages": "languages",
    "updated": "updated",
}

TABLE_CLASS = "pantry-table"

CSS = BASE_CSS + """
    .pantry-card { background: #fff; border: 1px solid #ddd; border-radius: 4px; padding: 1rem; }
    .pantry-card span { display: block; margin: 0.35rem 0; }
"""

TITLE = "Mercer Hollow County Aid Directory"


def render_index(records: list[dict]) -> str:
    body = f"<h1>{TITLE}</h1>\n" + render_index_table(records, CLASSES, TABLE_CLASS)
    return page(TITLE, CSS, body)


def render_detail(record: dict) -> str:
    body = render_detail_card(record, CLASSES) + '\n<p><a href="../index.html">Back to directory</a></p>'
    return page(record["name"], CSS, body)

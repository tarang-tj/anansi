"""m1: class-rename mutation -- identical DOM shape to baseline, only the CSS
class vocabulary changes (.hours -> .schedule-block, .pantry-card ->
.org-tile, etc). Proves healing survives a pure class-name refactor with no
change to element structure or nesting.
"""
from __future__ import annotations

from .helpers import BASE_CSS, page, render_detail_card, render_index_table

CLASSES = {
    "card": "org-tile",
    "name": "org-title",
    "address": "org-address",
    "phone": "org-phone",
    "hours": "schedule-block",
    "services": "org-services",
    "eligibility": "org-eligibility",
    "languages": "org-languages",
    "updated": "org-updated",
}

TABLE_CLASS = "directory-grid"

CSS = BASE_CSS + """
    .org-tile { background: #fff; border: 1px solid #ddd; border-radius: 4px; padding: 1rem; }
    .org-tile span { display: block; margin: 0.35rem 0; }
"""

TITLE = "Mercer Hollow County Aid Directory"


def render_index(records: list[dict]) -> str:
    body = f"<h1>{TITLE}</h1>\n" + render_index_table(records, CLASSES, TABLE_CLASS)
    return page(TITLE, CSS, body)


def render_detail(record: dict) -> str:
    body = render_detail_card(record, CLASSES) + '\n<p><a href="../index.html">Back to directory</a></p>'
    return page(record["name"], CSS, body)

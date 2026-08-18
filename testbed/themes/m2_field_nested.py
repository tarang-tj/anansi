"""m2: field-nesting mutation -- the hours field moves inside a collapsed
<details><summary>Hours</summary>...</details>. Every other field and every
class name stays identical to baseline; only the hours field's container
changes, so a scraper keyed on ".hours" text now finds it one level deeper
and hidden behind a <details> element.
"""
from __future__ import annotations

from .baseline import CLASSES, TABLE_CLASS
from .helpers import BASE_CSS, escape, page, render_detail_card, render_index_table

CSS = BASE_CSS + """
    .pantry-card { background: #fff; border: 1px solid #ddd; border-radius: 4px; padding: 1rem; }
    .pantry-card span { display: block; margin: 0.35rem 0; }
    details { margin: 0.35rem 0; }
    summary { cursor: pointer; font-weight: 700; }
"""

TITLE = "Mercer Hollow County Aid Directory"


def _nested_hours(value: str, css_class: str) -> str:
    return (
        "<details>\n<summary>Hours</summary>\n"
        f'<span class="{css_class}">{escape(value)}</span>\n'
        "</details>"
    )


def render_index(records: list[dict]) -> str:
    body = f"<h1>{TITLE}</h1>\n" + render_index_table(records, CLASSES, TABLE_CLASS)
    return page(TITLE, CSS, body)


def render_detail(record: dict) -> str:
    card = render_detail_card(record, CLASSES, hours_block=_nested_hours)
    body = card + '\n<p><a href="../index.html">Back to directory</a></p>'
    return page(record["name"], CSS, body)

"""m3: tag-swap mutation -- the field list converts from <span class=...>
pairs to a <dl><dt>/<dd> definition list. Same information, same field
order, a completely different tag vocabulary for a scraper that was keyed
on <span> elements.
"""
from __future__ import annotations

from .baseline import CLASSES, TABLE_CLASS
from .helpers import BASE_CSS, FIELD_LABELS, FIELD_ORDER, escape, field_value_text, page, render_index_table

CSS = BASE_CSS + """
    .pantry-card { background: #fff; border: 1px solid #ddd; border-radius: 4px; padding: 1rem; }
    .pantry-fields dt { font-weight: 700; margin-top: 0.5rem; }
    .pantry-fields dd { margin: 0 0 0.35rem 0; }
"""

TITLE = "Mercer Hollow County Aid Directory"


def _render_field_list(record: dict) -> str:
    rows = []
    for field in FIELD_ORDER:
        label = FIELD_LABELS[field]
        value = field_value_text(record, field)
        rows.append(f'<dt>{label}</dt>\n<dd class="{field}">{escape(value)}</dd>')
    return '<dl class="pantry-fields">\n' + "\n".join(rows) + "\n</dl>"


def render_index(records: list[dict]) -> str:
    body = f"<h1>{TITLE}</h1>\n" + render_index_table(records, CLASSES, TABLE_CLASS)
    return page(TITLE, CSS, body)


def render_detail(record: dict) -> str:
    card = (
        f'<div class="{CLASSES["card"]}">\n'
        f'<h1 class="{CLASSES["name"]}">{escape(record["name"])}</h1>\n'
        f"{_render_field_list(record)}\n"
        "</div>"
    )
    body = card + '\n<p><a href="../index.html">Back to directory</a></p>'
    return page(record["name"], CSS, body)

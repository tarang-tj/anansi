"""m5: field-split mutation -- the single hours string splits into seven
per-day elements (<li data-day="mon">9am-4pm</li>), so the old single-field
".hours" extraction has no direct equivalent; a healed scraper must learn to
recombine seven elements into one logical field. Every other field and class
name stays identical to baseline.
"""
from __future__ import annotations

from .baseline import CLASSES, TABLE_CLASS
from .helpers import BASE_CSS, escape, page, parse_hours_to_days, render_detail_card, render_index_table

CSS = BASE_CSS + """
    .pantry-card { background: #fff; border: 1px solid #ddd; border-radius: 4px; padding: 1rem; }
    .pantry-card span { display: block; margin: 0.35rem 0; }
    .hours-list { list-style: none; margin: 0.35rem 0; padding: 0; }
    .hours-list li { display: flex; justify-content: space-between; max-width: 260px; }
"""

TITLE = "Mercer Hollow County Aid Directory"


def _split_hours(value: str, _css_class: str) -> str:
    """Replace the single .hours span with a <ul> of seven <li data-day="...">
    entries, one per weekday, derived from the compact hours string.
    """
    schedule = parse_hours_to_days(value)
    items = "\n".join(f'<li data-day="{day.lower()}">{escape(hours)}</li>' for day, hours in schedule.items())
    return f'<ul class="hours-list">\n{items}\n</ul>'


def render_index(records: list[dict]) -> str:
    body = f"<h1>{TITLE}</h1>\n" + render_index_table(records, CLASSES, TABLE_CLASS)
    return page(TITLE, CSS, body)


def render_detail(record: dict) -> str:
    card = render_detail_card(record, CLASSES, hours_block=_split_hours)
    body = card + '\n<p><a href="../index.html">Back to directory</a></p>'
    return page(record["name"], CSS, body)

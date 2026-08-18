"""m4: full redesign mutation -- the most aggressive change. The table-based
listing becomes a card grid, and the detail page's flat field-span list
becomes a nested article/header/section hierarchy with a fresh class
vocabulary. Nothing shares structure with baseline; the underlying
information is identical, just fully re-hierarchized.
"""
from __future__ import annotations

from .helpers import BASE_CSS, FIELD_LABELS, FIELD_ORDER, escape, field_value_text, page

CSS = BASE_CSS + """
    .directory-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 1rem; }
    .org-card { background: #fff; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.15); padding: 1rem; }
    .org-card__title { font-size: 1.1rem; margin: 0 0 0.5rem 0; }
    .org-card__meta { margin: 0.2rem 0; color: #444; }
    .profile { max-width: 640px; }
    .profile__header { border-bottom: 2px solid #333; padding-bottom: 0.5rem; margin-bottom: 1rem; }
    .profile__row { display: flex; gap: 0.5rem; padding: 0.35rem 0; border-bottom: 1px dashed #ddd; }
    .profile__label { font-weight: 700; min-width: 120px; }
"""

TITLE = "Mercer Hollow County Aid Directory"


def render_index(records: list[dict]) -> str:
    cards = []
    for r in records:
        cards.append(
            '<article class="org-card">\n'
            f'<h2 class="org-card__title"><a href="pantry/{r["slug"]}.html">{escape(r["name"])}</a></h2>\n'
            f'<p class="org-card__meta">{escape(r["address"])}</p>\n'
            f'<p class="org-card__meta">{escape(r["phone"])}</p>\n'
            "</article>"
        )
    body = f"<h1>{TITLE}</h1>\n" '<div class="directory-grid">\n' + "\n".join(cards) + "\n</div>"
    return page(TITLE, CSS, body)


def render_detail(record: dict) -> str:
    rows = []
    for field in FIELD_ORDER:
        value = field_value_text(record, field)
        rows.append(
            '<div class="profile__row">\n'
            f'<span class="profile__label">{FIELD_LABELS[field]}</span>\n'
            f'<span class="profile__value profile__value--{field}">{escape(value)}</span>\n'
            "</div>"
        )
    body = (
        '<article class="profile">\n'
        '<header class="profile__header">\n'
        f'<h1>{escape(record["name"])}</h1>\n'
        "</header>\n"
        '<section class="profile__body">\n' + "\n".join(rows) + "\n</section>\n"
        "</article>\n"
        '<p><a href="../index.html">Back to directory</a></p>'
    )
    return page(record["name"], CSS, body)

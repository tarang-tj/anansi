"""Shared HTML-building helpers for the mutation testbed themes.

Kept separate from themes/__init__.py (which only holds the theme registry)
so no single module grows past a readable size. Theme submodules import
directly from here, e.g. `from .helpers import BASE_CSS, page`.
"""
from __future__ import annotations

import html
import json
import shutil
from pathlib import Path

SYNTHETIC_BANNER_TEXT = (
    "Synthetic test fixture for the Anansi self-healing scraper. "
    "Not real aid information -- do not use to find services."
)

# Shared base styling (banner + typography + table reset). Theme modules
# concatenate their own CSS onto this so the redesign mutation still looks
# visually distinct without repeating the banner/typography rules six times.
BASE_CSS = """
    body { font-family: system-ui, -apple-system, sans-serif; margin: 0; padding: 0; color: #1a1a1a; background: #fafafa; }
    .synthetic-banner { background: #b00020; color: #fff; padding: 0.75rem 1rem; font-weight: 700; text-align: center; }
    main { max-width: 960px; margin: 0 auto; padding: 1.5rem 1rem; }
    a { color: #0b5fa5; }
    table { border-collapse: collapse; width: 100%; }
    th, td { text-align: left; padding: 0.5rem; border-bottom: 1px solid #ddd; }
"""

DAY_ORDER = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# Order and labels for the record's non-identity fields (name is rendered
# separately as the page/card title).
FIELD_ORDER = ["address", "phone", "hours", "services", "eligibility", "languages", "updated"]
FIELD_LABELS = {
    "address": "Address",
    "phone": "Phone",
    "hours": "Hours",
    "services": "Services",
    "eligibility": "Eligibility",
    "languages": "Languages",
    "updated": "Last Updated",
}

REQUIRED_FIELDS = {
    "name", "slug", "address", "phone", "hours",
    "services", "eligibility", "languages", "updated",
}


def escape(value) -> str:
    """HTML-escape any scalar field value."""
    return html.escape(str(value), quote=True)


def field_value_text(record: dict, field: str) -> str:
    """Render a record field as display text, joining list fields with commas."""
    value = record[field]
    if isinstance(value, list):
        return ", ".join(value)
    return str(value)


def render_banner() -> str:
    """The synthetic-data disclaimer banner. Present, unchanged, on every
    generated page regardless of theme -- it is a fixture disclaimer, not a
    scraped field, so it is intentionally not part of any mutation.
    """
    return f'<div class="synthetic-banner" role="alert">{escape(SYNTHETIC_BANNER_TEXT)}</div>'


def page(title: str, css: str, body: str) -> str:
    """Wrap a body fragment in a full, deterministic standalone HTML document."""
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        f"<title>{escape(title)}</title>\n"
        f"<style>{css}</style>\n"
        "</head>\n"
        "<body>\n"
        f"{render_banner()}\n"
        "<main>\n"
        f"{body}\n"
        "</main>\n"
        "</body>\n"
        "</html>\n"
    )


def parse_hours_to_days(hours: str) -> dict[str, str]:
    """Deterministically expand a compact hours string, e.g.
    'Mon-Fri 9am-4pm, Sat 10am-2pm', into a full Mon..Sun schedule. Days not
    mentioned default to 'Closed'. This is a pure derived transform of
    data.json's single hours field -- used by the m5 mutation to split it
    into seven per-day elements without adding new source data.
    """
    schedule = {day: "Closed" for day in DAY_ORDER}
    for segment in hours.split(","):
        segment = segment.strip()
        if not segment:
            continue
        day_part, _, time_part = segment.partition(" ")
        time_part = time_part.strip() or "Closed"
        if day_part in DAY_ORDER:
            schedule[day_part] = time_part
        elif "-" in day_part:
            start, _, end = day_part.partition("-")
            if start in DAY_ORDER and end in DAY_ORDER:
                start_idx, end_idx = DAY_ORDER.index(start), DAY_ORDER.index(end)
                for i in range(start_idx, end_idx + 1):
                    schedule[DAY_ORDER[i]] = time_part
    return schedule


def render_span_fields(record: dict, classes: dict, hours_block=None) -> str:
    """Render the field list as <span class="..."><strong>Label:</strong> value</span>
    pairs -- the baseline field-list DOM shape shared by baseline/m1/m2/m5.

    `hours_block(value, css_class) -> str`, if given, overrides just the
    hours field's markup (used by the nesting and split mutations); every
    other field keeps this exact shape.
    """
    parts = []
    for field in FIELD_ORDER:
        cls = classes[field]
        if field == "hours" and hours_block is not None:
            parts.append(hours_block(record["hours"], cls))
            continue
        value = field_value_text(record, field)
        label = FIELD_LABELS[field]
        parts.append(f'<span class="{cls}"><strong>{label}:</strong> {escape(value)}</span>')
    return "\n".join(parts)


def render_detail_card(record: dict, classes: dict, hours_block=None) -> str:
    """Shared detail-page shape: a wrapper div, an h1 name, then the
    field-span list. Used by baseline, m1 (renamed classes), m2 (nested
    hours), and m5 (split hours) -- all of which keep this DOM shape.
    """
    fields_html = render_span_fields(record, classes, hours_block)
    return (
        f'<div class="{classes["card"]}">\n'
        f'<h1 class="{classes["name"]}">{escape(record["name"])}</h1>\n'
        f"{fields_html}\n"
        "</div>"
    )


def render_index_table(records: list[dict], classes: dict, table_class: str) -> str:
    """Shared index-page shape: one table row per pantry. Used by baseline,
    m1, m2, m3, and m5 -- all of which keep the table-based listing. Only m4
    (the redesign) replaces this with a card grid.
    """
    rows = []
    for r in records:
        rows.append(
            f'<tr class="{classes["card"]}">'
            f'<td class="{classes["name"]}"><a href="pantry/{r["slug"]}.html">{escape(r["name"])}</a></td>'
            f'<td class="{classes["address"]}">{escape(r["address"])}</td>'
            f'<td class="{classes["phone"]}">{escape(r["phone"])}</td>'
            f'<td class="{classes["updated"]}">{escape(r["updated"])}</td>'
            "</tr>"
        )
    rows_html = "\n".join(rows)
    return (
        f'<table class="{table_class}">\n'
        "<thead><tr><th>Name</th><th>Address</th><th>Phone</th><th>Last Updated</th></tr></thead>\n"
        f"<tbody>\n{rows_html}\n</tbody>\n"
        "</table>"
    )


def load_data(data_path: Path) -> list[dict]:
    """Load and validate data.json, sorted by slug for deterministic output."""
    with open(data_path, encoding="utf-8") as f:
        records = json.load(f)
    if not isinstance(records, list) or not records:
        raise ValueError(f"{data_path} must contain a non-empty JSON array")
    seen_slugs: set[str] = set()
    for record in records:
        if not isinstance(record, dict):
            raise ValueError(f"every record must be an object, got: {record!r}")
        missing = REQUIRED_FIELDS - record.keys()
        if missing:
            raise ValueError(f"record {record.get('slug', '?')} missing fields: {sorted(missing)}")
        if record["slug"] in seen_slugs:
            raise ValueError(f"duplicate slug: {record['slug']}")
        seen_slugs.add(record["slug"])
    return sorted(records, key=lambda r: r["slug"])


def write_site(out_dir: Path, index_html: str, detail_pages: dict[str, str]) -> None:
    """Write index.html + pantry/<slug>.html deterministically. Clears any
    previous contents of out_dir first so switching themes never leaves
    stale pages from a prior render behind.
    """
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    (out_dir / "index.html").write_text(index_html, encoding="utf-8", newline="\n")
    pantry_dir = out_dir / "pantry"
    pantry_dir.mkdir()
    for slug in sorted(detail_pages):
        (pantry_dir / f"{slug}.html").write_text(detail_pages[slug], encoding="utf-8", newline="\n")

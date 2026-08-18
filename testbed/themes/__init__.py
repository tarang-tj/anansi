"""Theme registry for the Anansi mutation testbed.

Each theme submodule in this package exposes:
    render_index(records: list[dict]) -> str   -- full index.html document
    render_detail(record: dict) -> str          -- full pantry/<slug>.html document

Shared HTML-building helpers (escape, page(), render_detail_card(), etc.)
live in helpers.py; themes that only change class names or nesting (m1, m2,
m5) reuse those helpers so their DOM shape stays provably shared with
baseline. Themes with a genuinely different tag vocabulary (m3, m4) build
their own markup directly -- that IS the mutation.
"""
from __future__ import annotations

from .helpers import load_data, write_site  # re-exported for render.py

# Theme registry -- populated by importing each theme submodule. Each
# submodule imports its shared helpers from `themes.helpers`, not from this
# module, so there is no circular-import ordering to worry about here.
from . import baseline as _baseline
from . import m1_class_rename as _m1
from . import m2_field_nested as _m2
from . import m3_tag_swap as _m3
from . import m4_redesign as _m4
from . import m5_field_split as _m5

THEMES = {
    "baseline": _baseline,
    "m1_class_rename": _m1,
    "m2_field_nested": _m2,
    "m3_tag_swap": _m3,
    "m4_redesign": _m4,
    "m5_field_split": _m5,
}

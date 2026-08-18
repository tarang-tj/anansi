"""A local, credential-free backend for exercising the loop against real HTML.

NOT THE PRODUCTION PATH. Anansi's real collectors are Bright Data Scraper Studio
collectors driven through `brightdata.BdataCli`; this module exists so the
*detection* half of the system can be verified against genuinely mutated markup
without spending credits or waiting on scraper generation.

Why it earns its place: testing the classifier on hand-built dictionaries proves
the arithmetic but not the premise. This backend behaves like a real scraper in
the one way that matters -- it holds a **fixed set of selectors**. When the
testbed renders a different theme, those selectors miss, extraction silently
returns empty fields, and the classifier has to notice from the data alone. That
is the same failure the live system faces when a site is redesigned.

What it cannot do is heal: repairing extraction logic from a natural-language
description is Scraper Studio's job, and this module deliberately does not fake it.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from anansi.brightdata import HealOutcome
from anansi.models import FetchOutcome, RunResult

BASELINE_SELECTORS: dict[str, str] = {
    "name": "pantry-name",
    "address": "address",
    "phone": "phone",
    "hours": "hours",
    "services": "services",
    "eligibility": "eligibility",
    "languages": "languages",
}
"""The classes a scraper would have learned from the baseline layout."""

_LABEL = re.compile(r"^\s*[A-Za-z ]{3,20}:\s*")


class _ClassTextExtractor(HTMLParser):
    """Collects the text content of every element carrying a watched class."""

    def __init__(self, watched: set[str]) -> None:
        super().__init__(convert_charrefs=True)
        self._watched = watched
        self._stack: list[str | None] = []
        self.found: dict[str, list[str]] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        classes = dict(attrs).get("class") or ""
        match = next((c for c in classes.split() if c in self._watched), None)
        self._stack.append(match)

    def handle_endtag(self, tag: str) -> None:
        if self._stack:
            self._stack.pop()

    def handle_data(self, data: str) -> None:
        active = next((c for c in reversed(self._stack) if c), None)
        if active and data.strip():
            self.found.setdefault(active, []).append(data.strip())


class LocalHtmlBackend:
    """Scrapes the local testbed with fixed selectors, the way a real scraper would."""

    def __init__(
        self,
        site_dir: Path | str,
        selectors: dict[str, str] | None = None,
    ) -> None:
        self.site_dir = Path(site_dir)
        self.selectors = dict(selectors or BASELINE_SELECTORS)

    def run(self, collector_id: str, url: str) -> RunResult:
        """Extract one record per detail page. `url` is accepted for interface parity."""
        index = self.site_dir / "index.html"
        if not index.exists():
            return RunResult(
                collector_id=collector_id,
                url=url,
                records=[],
                fetch=FetchOutcome(ok=False, error=f"no index.html under {self.site_dir}"),
            )

        pages = sorted((self.site_dir / "pantry").glob("*.html"))
        total_bytes = index.stat().st_size + sum(p.stat().st_size for p in pages)
        records = [self._extract(p) for p in pages]
        return RunResult(
            collector_id=collector_id,
            url=url,
            records=records,
            fetch=FetchOutcome(ok=True, status_code=200, html_bytes=total_bytes),
        )

    def heal(self, collector_id: str, prompt: str, auto_approve: bool = True) -> HealOutcome:
        """Deliberately unimplemented. Healing belongs to Scraper Studio."""
        return HealOutcome(
            ok=False,
            awaiting_approval=False,
            detail="LocalHtmlBackend cannot heal; repair requires Bright Data Scraper Studio",
        )

    def _extract(self, page: Path) -> dict[str, Any]:
        watched = set(self.selectors.values())
        parser = _ClassTextExtractor(watched)
        parser.feed(page.read_text(encoding="utf-8"))

        record: dict[str, Any] = {}
        for field, css_class in self.selectors.items():
            chunks = parser.found.get(css_class, [])
            # The baseline markup renders "<strong>Hours:</strong> Mon-Fri 9am-4pm",
            # so the label arrives as its own text node. Drop it and keep the value.
            values = [_LABEL.sub("", c).strip() for c in chunks]
            values = [v for v in values if v and not v.endswith(":")]
            record[field] = " ".join(values) if values else None
        return record

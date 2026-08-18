"""Core vocabulary for Anansi.

The central problem this package exists to solve: a Bright Data collector whose
selectors no longer match returns an empty array with an HTTP 200. Success and
silent failure are the same response. Nothing downstream can tell them apart
from a status code, so every type here is shaped around answering one question
statistically instead: *did the site move, or did the data legitimately change?*
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class HealthState(StrEnum):
    """The verdict on a single collector run.

    Only SELECTOR_BREAK and SCHEMA_DRIFT are healable. The others are either
    fine or not the scraper's fault, and healing them would be thrashing --
    burning credits and risking a "fix" that overwrites correct extraction
    logic in response to a site outage or a genuinely empty page.
    """

    HEALTHY = "healthy"
    INSUFFICIENT_BASELINE = "insufficient_baseline"
    PROVIDER_DOWN = "provider_down"
    SITE_DOWN = "site_down"
    CONTENT_EMPTY = "content_empty"
    SELECTOR_BREAK = "selector_break"
    SCHEMA_DRIFT = "schema_drift"

    @property
    def is_healable(self) -> bool:
        return self in _HEALABLE

    @property
    def feeds_baseline(self) -> bool:
        """Whether a run in this state may teach Anansi what normal looks like.

        Broken and unreachable runs are excluded, or a collector that stays
        broken would slowly drag the expected fill rates down until nothing
        ever fires again.

        Two inclusions are deliberate. INSUFFICIENT_BASELINE runs are perfectly
        good data that simply arrived before there was anything to compare them
        against -- excluding them would mean the baseline could never bootstrap
        at all. CONTENT_EMPTY runs reflect the world genuinely changing, so
        letting them in is how the baseline converges on a new reality instead
        of alerting on it forever.
        """
        return self in _FEEDS_BASELINE


_HEALABLE = frozenset({HealthState.SELECTOR_BREAK, HealthState.SCHEMA_DRIFT})

_FEEDS_BASELINE = frozenset(
    {
        HealthState.HEALTHY,
        HealthState.INSUFFICIENT_BASELINE,
        HealthState.CONTENT_EMPTY,
    }
)


@dataclass(frozen=True)
class Thresholds:
    """Tunable decision boundaries for the classifier.

    Defaults are deliberately conservative: Anansi would rather miss a break
    (and report it next run) than heal a collector that was working. A false
    heal is expensive -- it costs credits and can replace correct logic.
    """

    min_baseline_runs: int = 3
    """Below this many historical runs, refuse to judge."""

    established_fill_rate: float = 0.80
    """A field must have been populated at least this often to count as 'known good'."""

    break_fill_rate: float = 0.05
    """A known-good field at or below this fill rate in the current run reads as broken."""

    partial_loss_floor: float = 0.50
    """Between break_fill_rate and this, treat the loss as real-world content change."""

    record_collapse_ratio: float = 0.50
    """Record count below this fraction of the baseline mean reads as a break."""

    min_html_bytes: int = 500
    """A response smaller than this is treated as the site being down, not a parse failure."""


@dataclass(frozen=True)
class FetchOutcome:
    """What happened at the network layer, independent of extraction.

    This separation is what lets Anansi tell SITE_DOWN from SELECTOR_BREAK: a
    page that fetched fine at 47KB but extracted nothing is a parse problem,
    while a page that 503'd is not the scraper's fault.
    """

    ok: bool
    status_code: int | None = None
    html_bytes: int = 0
    error: str | None = None


@dataclass(frozen=True)
class RunResult:
    """One execution of one collector against one URL."""

    collector_id: str
    url: str
    records: list[dict[str, Any]]
    fetch: FetchOutcome
    ran_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    provider_error: str | None = None
    """Set when the Bright Data CLI/API itself failed, as opposed to the target site."""

    @property
    def record_count(self) -> int:
        return len(self.records)

    def fill_rate(self, key: str) -> float:
        """Fraction of records where `key` holds a non-empty value."""
        if not self.records:
            return 0.0
        populated = sum(1 for r in self.records if _is_populated(r.get(key)))
        return populated / len(self.records)

    def field_names(self) -> set[str]:
        """Every key observed across all records in this run."""
        return {k for r in self.records for k in r}


@dataclass(frozen=True)
class FieldStats:
    """Historical behaviour of a single field across many runs."""

    name: str
    mean_fill_rate: float
    runs_observed: int
    sample_values: tuple[str, ...] = ()
    """Last-known-good example values.

    Carried purely so the generated heal prompt can tell Scraper Studio what the
    field used to look like. "Re-locate the hours field" is a much weaker
    instruction than "re-locate the hours field, which looked like
    'Mon-Fri 9am-4pm'".
    """

    @property
    def is_established(self) -> bool:
        return self.mean_fill_rate >= Thresholds().established_fill_rate


@dataclass(frozen=True)
class Baseline:
    """What 'normal' looks like for a collector, learned from its own history."""

    collector_id: str
    runs_observed: int
    mean_record_count: float
    fields: dict[str, FieldStats]

    def stats_for(self, key: str) -> FieldStats | None:
        return self.fields.get(key)


@dataclass(frozen=True)
class Verdict:
    """The classifier's answer, with its reasoning attached.

    `reasons` is not decoration -- it is the raw material the heal prompt is
    generated from, and the audit trail a human reads when deciding whether to
    trust an automated fix.
    """

    state: HealthState
    reasons: list[str]
    affected_fields: list[str] = field(default_factory=list)
    confidence: float = 0.0

    @property
    def should_heal(self) -> bool:
        return self.state.is_healable


def _is_populated(value: Any) -> bool:
    """Whether an extracted value counts as present.

    Empty strings, empty collections and None are all 'missing' -- Bright Data
    returns several of these shapes for an unmatched selector depending on the
    field type, so they are normalised to one meaning here.
    """
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list | dict | tuple | set):
        return len(value) > 0
    return True

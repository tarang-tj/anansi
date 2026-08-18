"""Learn what 'normal' looks like for a collector, from its own history.

The caller is responsible for passing only baseline-eligible runs (see
`HealthState.feeds_baseline`). Letting a broken run into the baseline is how a
self-healing system quietly stops working: each bad run drags the expected fill
rate down, until a totally broken collector looks perfectly normal and nothing
ever fires again.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from anansi.models import Baseline, FieldStats, RunResult


def build_baseline(
    collector_id: str,
    eligible_runs: Sequence[RunResult],
    window: int = 40,
) -> Baseline:
    """Summarise the most recent `window` eligible runs into a Baseline.

    Only the trailing window is used, so a collector that legitimately changes
    shape converges on its new normal after enough clean runs rather than
    being compared against its distant past forever.
    """
    recent = list(eligible_runs)[-window:]
    if not recent:
        return Baseline(
            collector_id=collector_id,
            runs_observed=0,
            mean_record_count=0.0,
            fields={},
        )

    mean_records = sum(r.record_count for r in recent) / len(recent)
    return Baseline(
        collector_id=collector_id,
        runs_observed=len(recent),
        mean_record_count=mean_records,
        fields=_field_stats(recent),
    )


def _field_stats(runs: Sequence[RunResult]) -> dict[str, FieldStats]:
    """Mean fill rate per field across the window.

    A field is scored against every run in the window, including runs where the
    key was absent entirely (counted as a 0% fill). A field that only appeared
    recently therefore has to earn its 'established' status over several runs
    before its disappearance can trigger a heal.
    """
    names = _observed_field_names(runs)
    stats: dict[str, FieldStats] = {}
    for name in sorted(names):
        rates = [run.fill_rate(name) for run in runs]
        stats[name] = FieldStats(
            name=name,
            mean_fill_rate=sum(rates) / len(rates),
            runs_observed=len(rates),
            sample_values=_sample_values(runs, name),
        )
    return stats


def _sample_values(runs: Sequence[RunResult], name: str, limit: int = 3) -> tuple[str, ...]:
    """A few distinct recent values for a field, newest runs first.

    Truncated hard: these end up inside a heal prompt with a 1000-character
    budget, so they are illustrative examples, not a data dump.
    """
    seen: list[str] = []
    for run in reversed(runs):
        for record in run.records:
            rendered = _render(record.get(name))
            if rendered and rendered not in seen:
                seen.append(rendered)
                if len(seen) == limit:
                    return tuple(seen)
    return tuple(seen)


def _render(value: object) -> str:
    """Flatten an extracted value to a short display string."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()[:60]
    if isinstance(value, list | tuple):
        return ", ".join(str(v) for v in value)[:60]
    return str(value)[:60]


def _observed_field_names(runs: Iterable[RunResult]) -> set[str]:
    return {name for run in runs for name in run.field_names()}

"""Decide whether a collector broke, or whether the world simply changed.

A Bright Data collector that extracts nothing returns `[]` with an HTTP 200.
So does a directory page that genuinely has no entries today. Telling those
apart is the entire job, and it cannot be done from a single run -- only by
comparing a run against what that collector's own history says is normal.

The rules run in a fixed order, cheapest and most certain first. Each rule can
end the decision; falling through all of them means healthy. Order matters:
ruling out "the provider broke" and "the site is down" *before* looking at
extraction is what stops Anansi from healing a collector in response to an
outage it had nothing to do with.
"""

from __future__ import annotations

from anansi.models import (
    Baseline,
    HealthState,
    RunResult,
    Thresholds,
    Verdict,
)


def classify(
    run: RunResult,
    baseline: Baseline,
    thresholds: Thresholds | None = None,
) -> Verdict:
    """Classify one run against its collector's learned baseline."""
    t = thresholds or Thresholds()

    for rule in (
        _provider_failed,
        _site_unreachable,
        _baseline_too_thin,
        _total_extraction_loss,
        _record_count_collapsed,
        _schema_changed,
        _fields_stopped_populating,
    ):
        verdict = rule(run, baseline, t)
        if verdict is not None:
            return verdict

    return Verdict(
        state=HealthState.HEALTHY,
        reasons=[f"{run.record_count} records extracted, all established fields populated"],
        confidence=_baseline_weight(baseline),
    )


def _provider_failed(run: RunResult, _b: Baseline, _t: Thresholds) -> Verdict | None:
    """Bright Data itself failed. Not the target site's fault, and not healable.

    Anansi runs outside the provider precisely so this case is observable: a
    monitor that shared a failure domain with the thing it monitors would
    report the outage as a scraper defect.
    """
    if run.provider_error:
        return Verdict(
            state=HealthState.PROVIDER_DOWN,
            reasons=[f"Bright Data returned an error: {run.provider_error}"],
            confidence=1.0,
        )
    return None


def _site_unreachable(run: RunResult, _b: Baseline, t: Thresholds) -> Verdict | None:
    """The page never arrived, so there was nothing to parse."""
    if not run.fetch.ok:
        detail = run.fetch.error or f"HTTP {run.fetch.status_code}"
        return Verdict(
            state=HealthState.SITE_DOWN,
            reasons=[f"target did not serve a usable page ({detail})"],
            confidence=1.0,
        )
    if run.fetch.html_bytes < t.min_html_bytes:
        return Verdict(
            state=HealthState.SITE_DOWN,
            reasons=[
                f"response was only {run.fetch.html_bytes} bytes, "
                f"below the {t.min_html_bytes}-byte floor for a real page"
            ],
            confidence=0.9,
        )
    return None


def _baseline_too_thin(_r: RunResult, baseline: Baseline, t: Thresholds) -> Verdict | None:
    """Refuse to judge a collector that has not yet established what normal is."""
    if baseline.runs_observed < t.min_baseline_runs:
        return Verdict(
            state=HealthState.INSUFFICIENT_BASELINE,
            reasons=[
                f"only {baseline.runs_observed} historical run(s); "
                f"need {t.min_baseline_runs} before drift can be judged"
            ],
            confidence=0.0,
        )
    return None


def _total_extraction_loss(run: RunResult, baseline: Baseline, _t: Thresholds) -> Verdict | None:
    """Nothing came back from a page that used to yield records."""
    if run.record_count > 0:
        return None
    if baseline.mean_record_count < 1:
        return Verdict(
            state=HealthState.HEALTHY,
            reasons=["no records extracted, consistent with this collector's history"],
            confidence=_baseline_weight(baseline),
        )
    return Verdict(
        state=HealthState.SELECTOR_BREAK,
        reasons=[
            f"zero records extracted from a {run.fetch.html_bytes}-byte page that "
            f"normally yields ~{baseline.mean_record_count:.0f}"
        ],
        confidence=_baseline_weight(baseline),
    )


def _record_count_collapsed(run: RunResult, baseline: Baseline, t: Thresholds) -> Verdict | None:
    """Records still come back, but far fewer than usual."""
    if baseline.mean_record_count < 1:
        return None
    ratio = run.record_count / baseline.mean_record_count
    if ratio >= t.record_collapse_ratio:
        return None
    return Verdict(
        state=HealthState.SELECTOR_BREAK,
        reasons=[
            f"record count fell to {run.record_count} from a baseline mean of "
            f"{baseline.mean_record_count:.1f} ({ratio:.0%} of normal)"
        ],
        confidence=_baseline_weight(baseline) * (1.0 - ratio),
    )


def _schema_changed(run: RunResult, baseline: Baseline, _t: Thresholds) -> Verdict | None:
    """An established field disappeared from the payload shape entirely.

    Distinct from a field that is present but null: a vanished key means the
    extraction contract itself changed, which is a different repair than a
    selector that stopped matching.
    """
    observed = run.field_names()
    vanished = sorted(
        name
        for name, stats in baseline.fields.items()
        if stats.is_established and name not in observed
    )
    if not vanished:
        return None
    return Verdict(
        state=HealthState.SCHEMA_DRIFT,
        reasons=[
            f"established field(s) absent from the output schema entirely: {', '.join(vanished)}"
        ],
        affected_fields=vanished,
        confidence=_baseline_weight(baseline),
    )


def _fields_stopped_populating(run: RunResult, baseline: Baseline, t: Thresholds) -> Verdict | None:
    """The crux: every record losing one field is a break; one record losing it is news.

    A selector that no longer matches fails uniformly -- it misses on every
    record at once. A pantry that genuinely stopped publishing its hours
    affects that pantry alone. The fill rate is what separates them.
    """
    broken: list[str] = []
    degraded: list[str] = []
    reasons: list[str] = []

    for name, stats in sorted(baseline.fields.items()):
        if not stats.is_established:
            continue
        current = run.fill_rate(name)
        if current <= t.break_fill_rate:
            broken.append(name)
            reasons.append(
                f"'{name}' populated in {current:.0%} of records, "
                f"down from {stats.mean_fill_rate:.0%} across {stats.runs_observed} runs"
            )
        elif current < t.partial_loss_floor:
            degraded.append(name)
            reasons.append(
                f"'{name}' populated in {current:.0%} of records "
                f"(was {stats.mean_fill_rate:.0%}), a partial loss"
            )

    if broken:
        return Verdict(
            state=HealthState.SELECTOR_BREAK,
            reasons=reasons,
            affected_fields=sorted(broken),
            confidence=_baseline_weight(baseline),
        )
    if degraded:
        return Verdict(
            state=HealthState.CONTENT_EMPTY,
            reasons=[*reasons, "loss is partial, so the records themselves likely changed"],
            affected_fields=sorted(degraded),
            confidence=_baseline_weight(baseline) * 0.6,
        )
    return None


def _baseline_weight(baseline: Baseline) -> float:
    """How much the history earns trust. Ten clean runs is full confidence."""
    return min(1.0, baseline.runs_observed / 10)

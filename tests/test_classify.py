"""The classifier is the project's load-bearing claim, so it is tested hardest.

The case that matters most is `test_one_record_losing_a_field_is_content_not_breakage`
paired with `test_every_record_losing_a_field_is_a_selector_break`. Those two
runs are nearly identical -- same collector, same page, same field missing. Only
the *proportion* differs, and that alone decides whether Anansi spends credits
healing or leaves a working scraper alone.
"""

from __future__ import annotations

from anansi.classify import classify
from anansi.models import Baseline, HealthState, Thresholds

from .conftest import COLLECTOR, make_baseline, make_record, make_run


def test_normal_run_is_healthy(healthy_baseline: Baseline) -> None:
    verdict = classify(make_run(), healthy_baseline)
    assert verdict.state is HealthState.HEALTHY
    assert not verdict.should_heal


def test_provider_error_outranks_everything(healthy_baseline: Baseline) -> None:
    """A Bright Data outage must never be mistaken for a broken scraper."""
    run = make_run(records=[], provider_error="502 from api.brightdata.com")
    verdict = classify(run, healthy_baseline)
    assert verdict.state is HealthState.PROVIDER_DOWN
    assert not verdict.should_heal


def test_unreachable_site_is_not_healed(healthy_baseline: Baseline) -> None:
    run = make_run(records=[], fetch_ok=False, status_code=503, html_bytes=0)
    verdict = classify(run, healthy_baseline)
    assert verdict.state is HealthState.SITE_DOWN
    assert not verdict.should_heal


def test_truncated_response_reads_as_site_down(healthy_baseline: Baseline) -> None:
    """An error page is short. Parsing failure requires a page worth parsing."""
    run = make_run(records=[], html_bytes=120)
    assert classify(run, healthy_baseline).state is HealthState.SITE_DOWN


def test_thin_baseline_refuses_to_judge() -> None:
    thin = make_baseline(runs=2)
    verdict = classify(make_run(records=[]), thin)
    assert verdict.state is HealthState.INSUFFICIENT_BASELINE
    assert not verdict.should_heal


def test_total_extraction_loss_is_a_break(healthy_baseline: Baseline) -> None:
    """Zero records from a full-size page, where 12 was normal."""
    verdict = classify(make_run(records=[]), healthy_baseline)
    assert verdict.state is HealthState.SELECTOR_BREAK
    assert verdict.should_heal


def test_empty_stays_healthy_when_empty_is_normal() -> None:
    """A collector whose page is usually empty has not broken by being empty."""
    empty_history = make_baseline(runs=0)
    always_empty = Baseline(
        collector_id=COLLECTOR, runs_observed=10, mean_record_count=0.0, fields={}
    )
    assert classify(make_run(records=[]), always_empty).state is HealthState.HEALTHY
    assert empty_history.runs_observed == 0


def test_record_count_collapse_is_a_break(healthy_baseline: Baseline) -> None:
    run = make_run(count=3)  # baseline mean is 12
    verdict = classify(run, healthy_baseline)
    assert verdict.state is HealthState.SELECTOR_BREAK
    assert "25% of normal" in " ".join(verdict.reasons)


def test_vanished_key_is_schema_drift(healthy_baseline: Baseline) -> None:
    """The key is gone from the payload, not merely null."""
    records = [make_record(i) for i in range(12)]
    for r in records:
        del r["hours"]
    verdict = classify(make_run(records=records), healthy_baseline)
    assert verdict.state is HealthState.SCHEMA_DRIFT
    assert verdict.affected_fields == ["hours"]
    assert verdict.should_heal


def test_every_record_losing_a_field_is_a_selector_break(healthy_baseline: Baseline) -> None:
    """Uniform failure across every record is the signature of a dead selector."""
    records = [make_record(i, hours=None) for i in range(12)]
    verdict = classify(make_run(records=records), healthy_baseline)
    assert verdict.state is HealthState.SELECTOR_BREAK
    assert verdict.affected_fields == ["hours"]
    assert verdict.should_heal


def test_one_record_losing_a_field_is_content_not_breakage(healthy_baseline: Baseline) -> None:
    """One pantry dropping its hours is news about that pantry, not a bug.

    This is the false-positive Anansi exists to avoid. Healing here would burn
    credits rewriting a selector that works.
    """
    records = [make_record(i) for i in range(12)]
    records[0]["hours"] = None
    verdict = classify(make_run(records=records), healthy_baseline)
    assert verdict.state is HealthState.HEALTHY
    assert not verdict.should_heal


def test_majority_loss_is_reported_but_not_healed(healthy_baseline: Baseline) -> None:
    """Between the thresholds: suspicious enough to surface, not to auto-fix."""
    records = [make_record(i) for i in range(12)]
    for r in records[:8]:
        r["hours"] = None
    verdict = classify(make_run(records=records), healthy_baseline)
    assert verdict.state is HealthState.CONTENT_EMPTY
    assert not verdict.should_heal
    assert verdict.affected_fields == ["hours"]


def test_empty_string_counts_as_missing(healthy_baseline: Baseline) -> None:
    """Bright Data returns '' as often as null for an unmatched selector."""
    records = [make_record(i, hours="   ") for i in range(12)]
    assert classify(make_run(records=records), healthy_baseline).state is HealthState.SELECTOR_BREAK


def test_empty_list_counts_as_missing(healthy_baseline: Baseline) -> None:
    records = [make_record(i, services=[]) for i in range(12)]
    verdict = classify(make_run(records=records), healthy_baseline)
    assert verdict.state is HealthState.SELECTOR_BREAK
    assert verdict.affected_fields == ["services"]


def test_never_established_field_does_not_trigger() -> None:
    """A field that was always sparse cannot 'break' by being sparse."""
    from anansi.baseline import build_baseline

    history = [make_run(records=[make_record(i, note=None) for i in range(12)]) for _ in range(40)]
    baseline = build_baseline(COLLECTOR, history)
    assert baseline.fields["note"].is_established is False
    assert classify(make_run(), baseline).state is HealthState.HEALTHY


def test_thresholds_are_tunable(healthy_baseline: Baseline) -> None:
    """A stricter collapse ratio changes the verdict on the same run."""
    run = make_run(count=8)  # 67% of baseline
    assert classify(run, healthy_baseline).state is HealthState.HEALTHY
    strict = Thresholds(record_collapse_ratio=0.9)
    assert classify(run, healthy_baseline, strict).state is HealthState.SELECTOR_BREAK


def test_confidence_scales_with_history() -> None:
    """Five runs of evidence should not be as convincing as forty."""
    weak = classify(make_run(records=[]), make_baseline(runs=5))
    strong = classify(make_run(records=[]), make_baseline(runs=40))
    assert weak.confidence < strong.confidence == 1.0

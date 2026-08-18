"""The heal loop, including the failure mode that looks like success.

`test_heal_that_reports_success_but_does_not_fix_is_not_recovery` is the reason
the verify step exists. Scraper Studio returning "healed" means it produced new
extraction logic, not that the logic is right. A system that trusted that claim
would report green while shipping empty data.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from anansi.brightdata import HealOutcome
from anansi.models import HealthState, RunResult
from anansi.sentinel import Sentinel
from anansi.store import RunStore

from .conftest import COLLECTOR, URL, make_record, make_run


class FakeBackend:
    """Returns a scripted sequence of runs and records every heal request."""

    def __init__(self, runs: list[RunResult], heal: HealOutcome | None = None) -> None:
        self._runs = list(runs)
        self._heal_outcome = heal or HealOutcome(True, False, "healed")
        self.heal_calls: list[tuple[str, str, bool]] = []

    def run(self, collector_id: str, url: str) -> RunResult:
        return self._runs.pop(0) if self._runs else make_run()

    def heal(self, collector_id: str, prompt: str, auto_approve: bool = True) -> HealOutcome:
        self.heal_calls.append((collector_id, prompt, auto_approve))
        return self._heal_outcome


@pytest.fixture
def store(tmp_path: Path) -> RunStore:
    with RunStore(tmp_path / "test.db") as s:
        yield s


def seed_healthy(store: RunStore, sentinel: Sentinel, n: int = 5) -> None:
    """Give a collector enough clean history to have a baseline."""
    for _ in range(n):
        sentinel.check(COLLECTOR, URL, heal=False)


def test_healthy_collector_is_not_healed(store: RunStore) -> None:
    backend = FakeBackend([make_run() for _ in range(6)])
    sentinel = Sentinel(backend, store)
    seed_healthy(store, sentinel)

    report = sentinel.check(COLLECTOR, URL)
    assert report.verdict.state is HealthState.HEALTHY
    assert not report.heal_attempted
    assert backend.heal_calls == []


def test_broken_collector_is_healed_and_verified(store: RunStore) -> None:
    broken = make_run(records=[make_record(i, hours=None) for i in range(12)])
    backend = FakeBackend([*[make_run() for _ in range(5)], broken, make_run()])
    sentinel = Sentinel(backend, store)
    seed_healthy(store, sentinel)

    report = sentinel.check(COLLECTOR, URL)
    assert report.verdict.state is HealthState.SELECTOR_BREAK
    assert report.heal_attempted
    assert report.recovered
    assert not report.needs_human
    assert report.post_verdict is not None
    assert report.post_verdict.state is HealthState.HEALTHY


def test_heal_prompt_carries_the_evidence(store: RunStore) -> None:
    """The prompt is generated, not typed. It must name the field and its history."""
    broken = make_run(records=[make_record(i, hours=None) for i in range(12)])
    backend = FakeBackend([*[make_run() for _ in range(5)], broken, make_run()])
    sentinel = Sentinel(backend, store)
    seed_healthy(store, sentinel)

    sentinel.check(COLLECTOR, URL)
    _, prompt, auto_approve = backend.heal_calls[0]
    assert "'hours'" in prompt
    assert "Mon-Fri 9am-4pm" in prompt
    assert "still loads normally" in prompt
    assert auto_approve is True
    assert len(prompt) <= 1000


def test_heal_that_reports_success_but_does_not_fix_is_not_recovery(store: RunStore) -> None:
    """The provider says healed; the re-run says otherwise. The re-run wins."""
    broken = make_run(records=[make_record(i, hours=None) for i in range(12)])
    still_broken = make_run(records=[make_record(i, hours=None) for i in range(12)])
    backend = FakeBackend([*[make_run() for _ in range(5)], broken, still_broken])
    sentinel = Sentinel(backend, store)
    seed_healthy(store, sentinel)

    report = sentinel.check(COLLECTOR, URL)
    assert report.heal_attempted
    assert not report.recovered
    assert report.needs_human


def test_heal_awaiting_approval_is_surfaced_not_swallowed(store: RunStore) -> None:
    """Without --auto-approve the fix is staged, which is not the same as fixed."""
    broken = make_run(records=[make_record(i, hours=None) for i in range(12)])
    staged = HealOutcome(False, True, "fix staged, awaiting human approval")
    backend = FakeBackend([*[make_run() for _ in range(5)], broken], heal=staged)
    sentinel = Sentinel(backend, store, auto_approve=False)
    seed_healthy(store, sentinel)

    report = sentinel.check(COLLECTOR, URL)
    assert report.heal_attempted
    assert not report.recovered
    assert report.needs_human
    assert "approval" in (report.heal_detail or "")


def test_site_outage_never_triggers_a_heal(store: RunStore) -> None:
    """Healing a collector because the target 503'd would burn credits for nothing."""
    down = make_run(records=[], fetch_ok=False, status_code=503, html_bytes=0)
    backend = FakeBackend([*[make_run() for _ in range(5)], down])
    sentinel = Sentinel(backend, store)
    seed_healthy(store, sentinel)

    report = sentinel.check(COLLECTOR, URL)
    assert report.verdict.state is HealthState.SITE_DOWN
    assert not report.heal_attempted
    assert backend.heal_calls == []


def test_broken_runs_never_poison_the_baseline(store: RunStore) -> None:
    """A collector that stays broken must not teach Anansi that broken is normal."""
    broken = [make_run(records=[]) for _ in range(10)]
    backend = FakeBackend([*[make_run() for _ in range(5)], *broken])
    sentinel = Sentinel(backend, store)
    seed_healthy(store, sentinel)

    for _ in range(10):
        report = sentinel.check(COLLECTOR, URL, heal=False)

    assert report.verdict.state is HealthState.SELECTOR_BREAK
    healthy_history = store.baseline_runs(COLLECTOR)
    assert len(healthy_history) == 5
    assert all(r.record_count == 12 for r in healthy_history)


def test_fleet_sweep_covers_every_collector(store: RunStore) -> None:
    backend = FakeBackend([make_run() for _ in range(4)])
    sentinel = Sentinel(backend, store)
    reports = sentinel.check_fleet({"c_a": URL, "c_b": URL}, heal=False)
    assert [r.collector_id for r in reports] == ["c_a", "c_b"]


def test_every_run_is_persisted_with_its_verdict(store: RunStore) -> None:
    backend = FakeBackend([make_run() for _ in range(3)])
    sentinel = Sentinel(backend, store)
    for _ in range(3):
        sentinel.check(COLLECTOR, URL, heal=False)

    latest = store.latest_run(COLLECTOR)
    assert latest is not None
    run, state = latest
    assert run.collector_id == COLLECTOR
    assert state in {s.value for s in HealthState}


def test_heal_events_form_an_audit_trail(store: RunStore) -> None:
    broken = make_run(records=[make_record(i, hours=None) for i in range(12)])
    backend = FakeBackend([*[make_run() for _ in range(5)], broken, make_run()])
    sentinel = Sentinel(backend, store)
    seed_healthy(store, sentinel)
    sentinel.check(COLLECTOR, URL)

    events: list[dict[str, Any]] = store.heal_events(COLLECTOR)
    assert len(events) == 1
    assert events[0]["before_state"] == HealthState.SELECTOR_BREAK.value
    assert events[0]["after_state"] == HealthState.HEALTHY.value
    assert events[0]["recovered"] == 1
    assert "'hours'" in events[0]["prompt"]

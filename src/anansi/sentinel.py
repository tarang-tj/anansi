"""The loop: run, judge, repair, and confirm the repair actually worked.

The last step is the one most self-healing demos skip. `bdata scraper heal`
reporting success means Scraper Studio produced new extraction logic -- not that
the new logic is correct. A heal that "succeeds" while returning garbage is
worse than no heal at all, because it looks green. Anansi re-runs and re-scores
against the same baseline before it will call a collector recovered.
"""

from __future__ import annotations

from dataclasses import dataclass

from anansi.baseline import build_baseline
from anansi.brightdata import ScraperBackend
from anansi.classify import classify
from anansi.healprompt import build_heal_prompt
from anansi.models import HealthState, RunResult, Thresholds, Verdict
from anansi.store import RunStore


@dataclass
class SentinelReport:
    """Everything that happened during one check of one collector."""

    collector_id: str
    url: str
    verdict: Verdict
    run: RunResult
    heal_attempted: bool = False
    heal_prompt: str | None = None
    heal_detail: str | None = None
    recovered: bool = False
    post_verdict: Verdict | None = None

    @property
    def needs_human(self) -> bool:
        """True when Anansi could not resolve this on its own."""
        return self.verdict.should_heal and not self.recovered

    def summary(self) -> str:
        line = f"{self.collector_id} {self.verdict.state.value}"
        if self.heal_attempted:
            line += " -> healed" if self.recovered else " -> heal did not recover"
        return line


class Sentinel:
    """Checks collectors, and repairs the ones that are genuinely broken."""

    def __init__(
        self,
        backend: ScraperBackend,
        store: RunStore,
        thresholds: Thresholds | None = None,
        *,
        auto_approve: bool = True,
        baseline_window: int = 40,
    ) -> None:
        self.backend = backend
        self.store = store
        self.thresholds = thresholds or Thresholds()
        self.auto_approve = auto_approve
        self.baseline_window = baseline_window

    def check(self, collector_id: str, url: str, *, heal: bool = True) -> SentinelReport:
        """Run one collector, judge it, and heal it if it is genuinely broken."""
        run = self.backend.run(collector_id, url)
        baseline = build_baseline(
            collector_id,
            self.store.baseline_runs(collector_id, limit=self.baseline_window),
            window=self.baseline_window,
        )
        verdict = classify(run, baseline, self.thresholds)
        self.store.record_run(run, verdict)

        report = SentinelReport(collector_id=collector_id, url=url, verdict=verdict, run=run)
        if not (heal and verdict.should_heal):
            return report

        prompt = build_heal_prompt(run, baseline, verdict)
        report.heal_attempted = True
        report.heal_prompt = prompt
        heal_id = self.store.open_heal(collector_id, prompt, verdict.state.value)

        outcome = self.backend.heal(collector_id, prompt, self.auto_approve)
        if not outcome.ok:
            report.heal_detail = outcome.detail
            self.store.close_heal(heal_id, verdict.state.value, False, outcome.detail)
            return report

        # A successful heal call is a claim. Re-run and re-score to test it.
        post_run = self.backend.run(collector_id, url)
        post_verdict = classify(post_run, baseline, self.thresholds)
        self.store.record_run(post_run, post_verdict)

        report.post_verdict = post_verdict
        report.recovered = post_verdict.state is HealthState.HEALTHY
        report.heal_detail = outcome.detail
        self.store.close_heal(
            heal_id,
            post_verdict.state.value,
            report.recovered,
            outcome.detail,
        )
        return report

    def check_fleet(self, targets: dict[str, str], *, heal: bool = True) -> list[SentinelReport]:
        """Check every collector in the fleet. One failure never stops the sweep."""
        return [self.check(cid, url, heal=heal) for cid, url in targets.items()]

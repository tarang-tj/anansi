"""End-to-end detection against real mutated HTML, with no credentials.

Every other test in this suite feeds the classifier hand-built dictionaries.
Those prove the arithmetic. These prove the premise: render the testbed through
a different theme, point a fixed-selector scraper at it, and check that the
classifier works out what happened from the extracted data alone.

The most valuable assertions here are the ones that expect NOTHING to happen.
m2 and m3 genuinely change the layout but preserve the class attributes a
selector keys on, so extraction survives and Anansi must stay quiet. A detector
that fired on those would cry wolf on every cosmetic redesign, and the credits
it burned healing a working collector would be the least of the problem.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from anansi.baseline import build_baseline
from anansi.classify import classify
from anansi.harness import LocalHtmlBackend
from anansi.models import Baseline, HealthState

REPO_ROOT = Path(__file__).resolve().parents[1]
COLLECTOR = "c_local_testbed"

BREAKING = ["m1_class_rename", "m4_redesign", "m5_field_split"]
NON_BREAKING = ["m2_field_nested", "m3_tag_swap"]


def render(theme: str, out: Path) -> Path:
    """Render one testbed theme into `out`."""
    subprocess.run(
        [sys.executable, "testbed/render.py", "--theme", theme, "--out", str(out)],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
    )
    return out


@pytest.fixture(scope="module")
def baseline_site(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return render("baseline", tmp_path_factory.mktemp("baseline"))


@pytest.fixture(scope="module")
def learned_baseline(baseline_site: Path) -> Baseline:
    """Six clean runs against the unmutated site."""
    backend = LocalHtmlBackend(baseline_site)
    runs = [backend.run(COLLECTOR, "local") for _ in range(6)]
    return build_baseline(COLLECTOR, runs)


def test_baseline_extraction_is_complete(baseline_site: Path) -> None:
    run = LocalHtmlBackend(baseline_site).run(COLLECTOR, "local")
    assert run.record_count == 12
    for field in ("name", "address", "phone", "hours", "services"):
        assert run.fill_rate(field) == 1.0, f"{field} did not extract from the baseline"


def test_unmutated_site_stays_healthy(baseline_site: Path, learned_baseline: Baseline) -> None:
    run = LocalHtmlBackend(baseline_site).run(COLLECTOR, "local")
    assert classify(run, learned_baseline).state is HealthState.HEALTHY


@pytest.mark.parametrize("theme", BREAKING)
def test_structural_mutation_is_detected(
    theme: str, learned_baseline: Baseline, tmp_path: Path
) -> None:
    """A layout change that moves data out from under the selectors must be caught."""
    site = render(theme, tmp_path / theme)
    run = LocalHtmlBackend(site).run(COLLECTOR, "local")

    # The page is intact and still returns 12 records -- only extraction failed.
    # That is exactly the silent failure this project exists to catch.
    assert run.record_count == 12
    assert run.fetch.ok

    verdict = classify(run, learned_baseline)
    assert verdict.state is HealthState.SELECTOR_BREAK
    assert verdict.should_heal


@pytest.mark.parametrize("theme", NON_BREAKING)
def test_cosmetic_mutation_does_not_cry_wolf(
    theme: str, learned_baseline: Baseline, tmp_path: Path
) -> None:
    """These themes change the DOM but keep the class hooks, so nothing broke."""
    site = render(theme, tmp_path / theme)
    run = LocalHtmlBackend(site).run(COLLECTOR, "local")

    verdict = classify(run, learned_baseline)
    assert verdict.state is HealthState.HEALTHY
    assert not verdict.should_heal


def test_field_split_loses_only_the_field_it_split(
    learned_baseline: Baseline, tmp_path: Path
) -> None:
    """m5 is the surgical case: hours fragments into seven per-day elements.

    Everything else keeps extracting, which is what makes the generated heal
    prompt useful -- it can name the one broken field and list the six intact
    ones, scoping the repair instead of inviting a full rewrite.
    """
    site = render("m5_field_split", tmp_path / "m5")
    run = LocalHtmlBackend(site).run(COLLECTOR, "local")

    verdict = classify(run, learned_baseline)
    assert verdict.affected_fields == ["hours"]
    for intact in ("name", "address", "phone", "services"):
        assert run.fill_rate(intact) == 1.0, f"{intact} should have survived the hours split"


def test_local_harness_refuses_to_fake_healing(baseline_site: Path) -> None:
    """Repair is Scraper Studio's job; the harness must not pretend otherwise."""
    outcome = LocalHtmlBackend(baseline_site).heal(COLLECTOR, "fix hours")
    assert not outcome.ok
    assert "Scraper Studio" in outcome.detail

"""Run the detection half of Anansi end to end, offline, in about two seconds.

    uv run python scripts/demo_detection.py

Renders the testbed, learns a baseline from clean runs, then mutates the site
and shows the classifier working out what happened from the extracted data
alone. Writes a dashboard and structured-output artifacts on the way through.

This deliberately stops short of healing. Repair is Bright Data Scraper Studio's
job and is not simulated here -- see `anansi prove` for the live loop.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from anansi.baseline import build_baseline
from anansi.dashboard import render_dashboard
from anansi.harness import LocalHtmlBackend
from anansi.healprompt import build_heal_prompt
from anansi.sentinel import Sentinel
from anansi.store import RunStore

REPO = Path(__file__).resolve().parents[1]
COLLECTOR = "c_demo_testbed"
WORK = REPO / "site-out"


def render(theme: str, out: Path) -> Path:
    subprocess.run(
        [sys.executable, "testbed/render.py", "--theme", theme, "--out", str(out)],
        cwd=REPO,
        check=True,
        capture_output=True,
    )
    return out


def main() -> int:
    WORK.mkdir(exist_ok=True)
    db = WORK / "demo.db"
    db.unlink(missing_ok=True)
    site = WORK / "site"

    print("1. Rendering the baseline testbed and learning what normal looks like")
    render("baseline", site)
    with RunStore(db) as store:
        sentinel = Sentinel(LocalHtmlBackend(site), store)
        for i in range(6):
            report = sentinel.check(COLLECTOR, "local://testbed", heal=False)
            print(
                f"   run {i + 1}: {report.verdict.state.value} ({report.run.record_count} records)"
            )

        print("\n2. The site is redesigned overnight (theme m5_field_split)")
        print("   hours splits from one string into seven per-day elements")
        render("m5_field_split", site)

        report = sentinel.check(COLLECTOR, "local://testbed", heal=False)
        print(f"\n3. Verdict: {report.verdict.state.value.upper()}")
        for reason in report.verdict.reasons:
            print(f"   - {reason}")
        print(f"   affected fields: {report.verdict.affected_fields}")
        print(f"   confidence: {report.verdict.confidence:.0%}")

        # Note what did NOT happen: the page still returned 12 complete-looking
        # records with a 200. Nothing downstream would have noticed.
        print(f"\n   the run still returned {report.run.record_count} records at HTTP 200")
        print("   nothing downstream would have seen a gap")

        baseline = build_baseline(COLLECTOR, store.baseline_runs(COLLECTOR))
        prompt = build_heal_prompt(report.run, baseline, report.verdict)
        print(f"\n4. Heal prompt Anansi generated (unedited, {len(prompt)} chars):\n")
        print(f"   {prompt}\n")
        print("   -> this is what `bdata scraper heal <collector_id>` would receive")

        dash = WORK / "index.html"
        dash.write_text(render_dashboard(store))
        print(f"\n5. Wrote dashboard: {dash}")

    render("baseline", site)
    print("   testbed restored to baseline")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

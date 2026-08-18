"""Produce the structured-output artifacts committed under `examples/`.

    uv run python scripts/generate_examples.py

The hackathon asks submissions to include example structured output. A single
successful run would satisfy that literally, but it would not show the thing
this project is about. So the artifacts come in a set: the healthy extraction,
the broken extraction that still returned HTTP 200 with a full record count,
the classifier's verdict with its evidence, and the heal prompt generated from
that evidence.

Everything here is produced by actually running the pipeline over real HTML.
Nothing is hand-written.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from anansi.baseline import build_baseline
from anansi.classify import classify
from anansi.harness import LocalHtmlBackend
from anansi.healprompt import build_heal_prompt
from anansi.models import RunResult, Verdict

REPO = Path(__file__).resolve().parents[1]
EXAMPLES = REPO / "examples"
COLLECTOR = "c_demo_testbed"
MUTATION = "m5_field_split"


def render(theme: str, out: Path) -> Path:
    subprocess.run(
        [sys.executable, "testbed/render.py", "--theme", theme, "--out", str(out)],
        cwd=REPO,
        check=True,
        capture_output=True,
    )
    return out


def as_payload(run: RunResult, verdict: Verdict, note: str) -> dict[str, Any]:
    return {
        "collector_id": run.collector_id,
        "note": note,
        "http_status": run.fetch.status_code,
        "html_bytes": run.fetch.html_bytes,
        "record_count": run.record_count,
        "verdict": verdict.state.value,
        "records": run.records,
    }


def main() -> int:
    EXAMPLES.mkdir(exist_ok=True)
    work = REPO / "site-out" / "examples-site"

    backend_site = render("baseline", work)
    backend = LocalHtmlBackend(backend_site)
    history = [backend.run(COLLECTOR, "local://testbed") for _ in range(6)]
    baseline = build_baseline(COLLECTOR, history)

    healthy = history[-1]
    healthy_verdict = classify(healthy, baseline)
    _write(
        "healthy-run.json",
        as_payload(
            healthy,
            healthy_verdict,
            "Baseline layout. Every established field populated.",
        ),
    )

    render(MUTATION, work)
    broken = LocalHtmlBackend(work).run(COLLECTOR, "local://testbed")
    broken_verdict = classify(broken, baseline)
    _write(
        "broken-run.json",
        as_payload(
            broken,
            broken_verdict,
            f"After the {MUTATION} layout change. Note the HTTP 200 and the full "
            f"record count: every record is present and looks well-formed, but "
            f"'hours' is null throughout. Nothing downstream would see a gap.",
        ),
    )

    _write(
        "verdict.json",
        {
            "collector_id": COLLECTOR,
            "state": broken_verdict.state.value,
            "should_heal": broken_verdict.should_heal,
            "affected_fields": broken_verdict.affected_fields,
            "confidence": round(broken_verdict.confidence, 3),
            "reasons": broken_verdict.reasons,
            "baseline": {
                "runs_observed": baseline.runs_observed,
                "mean_record_count": baseline.mean_record_count,
                "fields": {
                    name: {
                        "mean_fill_rate": round(stats.mean_fill_rate, 3),
                        "established": stats.is_established,
                        "sample_values": list(stats.sample_values),
                    }
                    for name, stats in sorted(baseline.fields.items())
                },
            },
        },
    )

    prompt = build_heal_prompt(broken, baseline, broken_verdict)
    (EXAMPLES / "heal-prompt.txt").write_text(prompt + "\n")
    print(f"wrote examples/heal-prompt.txt ({len(prompt)} chars)")

    render("baseline", work)
    return 0


def _write(name: str, payload: dict[str, Any]) -> None:
    path = EXAMPLES / name
    path.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"wrote examples/{name}")


if __name__ == "__main__":
    raise SystemExit(main())

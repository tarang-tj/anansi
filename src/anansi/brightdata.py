"""The only place Anansi talks to Bright Data.

Everything else in the package operates on `RunResult` objects and has no idea
whether they came from a live collector, a recorded capture, or a test fixture.
That boundary is what lets the classifier -- the part being judged -- be tested
exhaustively offline with no credentials and no credit burn.

VERIFICATION STATUS: the exact JSON envelope returned by `bdata scraper run` is
not documented publicly and has NOT yet been confirmed against a live account.
`extract_records` therefore accepts every plausible shape rather than assuming
one, and `docs/status.md` tracks this as an open verification item. Guessing a
single shape and being wrong would fail silently, which is the exact class of
bug this project exists to catch.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from anansi.models import FetchOutcome, RunResult

DEFAULT_TIMEOUT_SECONDS = 1800
"""Generation and healing are documented at 5-15 minutes, up to 25 on complex sites."""


@dataclass(frozen=True)
class HealOutcome:
    """Result of asking Scraper Studio to repair a collector."""

    ok: bool
    awaiting_approval: bool
    detail: str
    raw: dict[str, Any] = field(default_factory=dict)


class ScraperBackend(Protocol):
    """What Anansi needs from a scraping provider. Deliberately tiny."""

    def run(self, collector_id: str, url: str) -> RunResult: ...

    def heal(self, collector_id: str, prompt: str, auto_approve: bool = True) -> HealOutcome: ...


class BdataCli:
    """Drives the real `bdata` CLI as a subprocess.

    The CLI is invoked rather than the REST API because `scraper heal` has no
    documented REST equivalent -- it is CLI-only. Running the collector through
    the same tool keeps one auth path and one failure mode.
    """

    def __init__(
        self,
        binary: tuple[str, ...] = ("npx", "-p", "@brightdata/cli", "bdata"),
        timeout: int = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self.binary = binary
        self.timeout = timeout

    def run(self, collector_id: str, url: str) -> RunResult:
        proc = self._invoke(["scraper", "run", collector_id, url, "--json"])
        if proc.returncode != 0:
            return RunResult(
                collector_id=collector_id,
                url=url,
                records=[],
                fetch=FetchOutcome(ok=False, error=_tail(proc.stderr)),
                provider_error=f"bdata exited {proc.returncode}: {_tail(proc.stderr)}",
            )
        try:
            payload = json.loads(proc.stdout or "{}")
        except json.JSONDecodeError as exc:
            return RunResult(
                collector_id=collector_id,
                url=url,
                records=[],
                fetch=FetchOutcome(ok=False, error="unparseable CLI output"),
                provider_error=f"could not parse bdata output as JSON: {exc}",
            )
        return build_run_result(collector_id, url, payload)

    def heal(self, collector_id: str, prompt: str, auto_approve: bool = True) -> HealOutcome:
        """Ask Scraper Studio to repair the collector, preserving its ID.

        `--auto-approve` skips the human review gate. When it is off (or if the
        flag turns out not to exist on this CLI version), the command returns
        with the fix staged and awaiting approval, which Anansi surfaces rather
        than silently treating as success.
        """
        args = ["scraper", "heal", collector_id, prompt]
        if auto_approve:
            args.append("--auto-approve")
        proc = self._invoke(args)
        raw = _try_json(proc.stdout)
        status = str(raw.get("status", "")).lower()

        if proc.returncode != 0:
            return HealOutcome(False, False, f"heal failed: {_tail(proc.stderr)}", raw)
        if status == "awaiting_approval":
            return HealOutcome(False, True, "fix staged, awaiting human approval", raw)
        return HealOutcome(True, False, status or "heal completed", raw)

    def approve(self, collector_id: str) -> HealOutcome:
        """Commit a staged fix after review."""
        proc = self._invoke(["scraper", "approve", collector_id])
        raw = _try_json(proc.stdout)
        ok = proc.returncode == 0
        return HealOutcome(ok, False, "approved" if ok else _tail(proc.stderr), raw)

    def _invoke(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [*self.binary, *args],
            capture_output=True,
            text=True,
            timeout=self.timeout,
            check=False,
        )


class RecordedBackend:
    """Replays a captured live run from disk. No network, no credentials.

    A frozen capture of a real run beats both a hand-written mock and hoping the
    API is up during judging: the demo cannot fail in front of an audience, and
    the data is genuinely what the live collector returned rather than something
    invented to look plausible.
    """

    def __init__(self, capture_dir: Path | str) -> None:
        self.capture_dir = Path(capture_dir)

    def run(self, collector_id: str, url: str) -> RunResult:
        path = self.capture_dir / f"{collector_id}.json"
        if not path.exists():
            return RunResult(
                collector_id=collector_id,
                url=url,
                records=[],
                fetch=FetchOutcome(ok=False, error=f"no capture at {path}"),
                provider_error=f"no recorded capture for {collector_id}",
            )
        return build_run_result(collector_id, url, json.loads(path.read_text()))

    def heal(self, collector_id: str, prompt: str, auto_approve: bool = True) -> HealOutcome:
        return HealOutcome(False, False, "RecordedBackend cannot heal; replay only", {})


def build_run_result(collector_id: str, url: str, payload: dict[str, Any]) -> RunResult:
    """Normalise a CLI/API envelope into a RunResult."""
    records = extract_records(payload)
    meta = payload if isinstance(payload, dict) else {}
    status = meta.get("status_code") or meta.get("statusCode")
    html_bytes = int(meta.get("html_bytes") or meta.get("page_size") or 0)
    if not html_bytes and records:
        # No size reported, but records came back, so the page plainly arrived.
        # Estimating from payload size keeps the SITE_DOWN floor from firing on
        # a healthy run purely because the provider omitted a size field.
        html_bytes = len(json.dumps(records))
    return RunResult(
        collector_id=collector_id,
        url=url,
        records=records,
        fetch=FetchOutcome(
            ok=True, status_code=int(status) if status else 200, html_bytes=html_bytes
        ),
    )


def extract_records(payload: Any) -> list[dict[str, Any]]:
    """Pull the record list out of whatever envelope the provider used.

    Accepts a bare array or any of the common wrapper keys. An unrecognised
    shape yields an empty list, which the classifier will read as a possible
    break rather than crashing -- loud in the report, not fatal at runtime.
    """
    if isinstance(payload, list):
        return [r for r in payload if isinstance(r, dict)]
    if isinstance(payload, dict):
        for key in ("data", "records", "results", "items", "output"):
            value = payload.get(key)
            if isinstance(value, list):
                return [r for r in value if isinstance(r, dict)]
    return []


def _try_json(text: str) -> dict[str, Any]:
    try:
        parsed = json.loads(text or "{}")
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _tail(text: str, limit: int = 300) -> str:
    return (text or "").strip()[-limit:]

"""Shared fixtures: builders for runs that look like real collector output."""

from __future__ import annotations

from typing import Any

import pytest

from anansi.baseline import build_baseline
from anansi.models import Baseline, FetchOutcome, RunResult

COLLECTOR = "c_test123"
URL = "https://example.test/pantries"


def make_record(index: int, **overrides: Any) -> dict[str, Any]:
    """One well-formed pantry record."""
    record: dict[str, Any] = {
        "name": f"Pantry {index}",
        "address": f"{index} Elm St",
        "hours": "Mon-Fri 9am-4pm",
        "phone": f"555-01{index:02d}",
        "services": ["groceries"],
    }
    record.update(overrides)
    return record


def make_run(
    records: list[dict[str, Any]] | None = None,
    *,
    count: int = 12,
    html_bytes: int = 47_000,
    fetch_ok: bool = True,
    status_code: int | None = 200,
    provider_error: str | None = None,
) -> RunResult:
    """A collector run, healthy by default."""
    if records is None:
        records = [make_record(i) for i in range(count)]
    return RunResult(
        collector_id=COLLECTOR,
        url=URL,
        records=records,
        fetch=FetchOutcome(ok=fetch_ok, status_code=status_code, html_bytes=html_bytes),
        provider_error=provider_error,
    )


def make_baseline(runs: int = 40) -> Baseline:
    """A well-established baseline from many healthy runs."""
    return build_baseline(COLLECTOR, [make_run() for _ in range(runs)])


@pytest.fixture
def healthy_baseline() -> Baseline:
    return make_baseline()

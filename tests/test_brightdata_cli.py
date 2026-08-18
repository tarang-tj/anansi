"""The exact flags sent to the `bdata` CLI.

These assertions look pedantic until you know what they are guarding. The
`--auto-save` case is a bug that already happened: `--auto-approve` alone
clears the review gate but does not persist the healed template, so the CLI
reports a successful heal while the collector carries on running the old,
broken one. The loop would have gone green forever and shipped empty data.

Flags verified against `bdata scraper heal --help` and
`bdata scraper approve --help` on CLI v0.3.x.
"""

from __future__ import annotations

import subprocess
from typing import Any

import pytest

from anansi.brightdata import BdataCli, extract_records


class _Recorder:
    """Captures the argv a command would have run, and returns a canned result."""

    def __init__(self, stdout: str = "{}", returncode: int = 0) -> None:
        self.stdout = stdout
        self.returncode = returncode
        self.calls: list[list[str]] = []

    def __call__(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        self.calls.append(args)
        return subprocess.CompletedProcess(args, self.returncode, self.stdout, "")


@pytest.fixture
def cli() -> BdataCli:
    return BdataCli()


def test_heal_passes_both_approve_and_save(cli: BdataCli, monkeypatch: pytest.MonkeyPatch) -> None:
    """Approving without saving silently discards the fix. Both flags or neither."""
    rec = _Recorder('{"status": "done"}')
    monkeypatch.setattr(cli, "_invoke", rec)

    cli.heal("c_abc", "hours stopped extracting", auto_approve=True)

    args = rec.calls[0]
    assert "--auto-approve" in args
    assert "--auto-save" in args, "approving without saving leaves the old template live"
    assert args[:4] == ["scraper", "heal", "c_abc", "hours stopped extracting"]


def test_heal_without_auto_approve_sends_neither_flag(
    cli: BdataCli, monkeypatch: pytest.MonkeyPatch
) -> None:
    rec = _Recorder('{"status": "awaiting_approval"}')
    monkeypatch.setattr(cli, "_invoke", rec)

    outcome = cli.heal("c_abc", "hours broke", auto_approve=False)

    assert "--auto-approve" not in rec.calls[0]
    assert "--auto-save" not in rec.calls[0]
    assert outcome.awaiting_approval
    assert not outcome.ok


def test_awaiting_approval_is_not_success(cli: BdataCli, monkeypatch: pytest.MonkeyPatch) -> None:
    """Exit code 0 plus a staged fix is not a repair."""
    monkeypatch.setattr(cli, "_invoke", _Recorder('{"status": "awaiting_approval"}', returncode=0))
    outcome = cli.heal("c_abc", "broke")
    assert not outcome.ok
    assert outcome.awaiting_approval


def test_approve_saves_by_default(cli: BdataCli, monkeypatch: pytest.MonkeyPatch) -> None:
    rec = _Recorder()
    monkeypatch.setattr(cli, "_invoke", rec)
    cli.approve("c_abc")
    assert "--auto-save" in rec.calls[0]
    assert "--reject" not in rec.calls[0]


def test_reject_never_saves(cli: BdataCli, monkeypatch: pytest.MonkeyPatch) -> None:
    rec = _Recorder()
    monkeypatch.setattr(cli, "_invoke", rec)
    cli.approve("c_abc", reject=True)
    assert "--reject" in rec.calls[0]
    assert "--auto-save" not in rec.calls[0], "saving a rejected fix would apply it"


def test_nonzero_exit_is_a_provider_error(cli: BdataCli, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "_invoke", _Recorder("", returncode=1))
    run = cli.run("c_abc", "https://example.test")
    assert run.provider_error is not None
    assert not run.fetch.ok


def test_unparseable_output_fails_loudly(cli: BdataCli, monkeypatch: pytest.MonkeyPatch) -> None:
    """Garbage on stdout must not be read as an empty result set."""
    monkeypatch.setattr(cli, "_invoke", _Recorder("not json at all"))
    run = cli.run("c_abc", "https://example.test")
    assert run.provider_error is not None
    assert "parse" in run.provider_error


@pytest.mark.parametrize(
    "payload",
    [
        [{"name": "a"}],
        {"data": [{"name": "a"}]},
        {"records": [{"name": "a"}]},
        {"results": [{"name": "a"}]},
        {"items": [{"name": "a"}]},
        {"output": [{"name": "a"}]},
    ],
)
def test_records_are_found_in_any_common_envelope(payload: Any) -> None:
    """The live envelope shape is undocumented, so accept the plausible ones."""
    assert extract_records(payload) == [{"name": "a"}]


def test_unknown_envelope_yields_no_records_rather_than_crashing() -> None:
    assert extract_records({"unexpected": {"nested": 1}}) == []

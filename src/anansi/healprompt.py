"""Turn a verdict into the plain-language repair instruction Scraper Studio needs.

`bdata scraper heal` takes a natural-language description of what broke. Writing
that by hand is the manual step most self-healing demos never actually remove --
they detect automatically and then a human types the fix request. Anansi
generates it from the evidence the classifier already gathered, which is what
closes the loop.

A good heal prompt answers three questions: which field is wrong, what it used
to look like, and what is still working. The third matters most -- telling the
healer that the page still loads and that four other fields extract fine scopes
the repair to one selector instead of inviting a rewrite of the whole scraper.
"""

from __future__ import annotations

from anansi.models import Baseline, HealthState, RunResult, Verdict

PROMPT_CHAR_LIMIT = 1000
"""Bright Data caps the heal description at 1000 characters."""


class NotHealableError(ValueError):
    """Raised when asked to build a prompt for a verdict that must not be healed."""


def build_heal_prompt(
    run: RunResult,
    baseline: Baseline,
    verdict: Verdict,
    limit: int = PROMPT_CHAR_LIMIT,
) -> str:
    """Compose the repair instruction for a healable verdict.

    Raises NotHealableError for any other state. This is a guard rail, not a
    formality: the states it rejects include site outages and genuinely empty
    pages, where healing would rewrite working extraction logic in response to
    a problem the scraper did not cause.
    """
    if not verdict.should_heal:
        raise NotHealableError(
            f"{verdict.state.value} is not a healable state; "
            "healing here would risk overwriting correct extraction logic"
        )

    sections = [
        _opening(verdict),
        _evidence(run, baseline, verdict),
        _still_working(run, baseline, verdict),
        _instruction(verdict),
    ]
    return _fit(" ".join(s for s in sections if s), limit)


def _opening(verdict: Verdict) -> str:
    fields = _quoted(verdict.affected_fields)
    if verdict.state is HealthState.SCHEMA_DRIFT:
        if fields:
            return f"The {fields} field(s) disappeared from the output entirely."
        return "The output schema changed and expected fields are missing."
    if fields:
        return f"The {fields} field(s) stopped extracting and now return empty."
    return "Extraction stopped returning records."


def _evidence(run: RunResult, baseline: Baseline, verdict: Verdict) -> str:
    """What the numbers say, plus what the field used to look like."""
    parts: list[str] = []
    for name in verdict.affected_fields:
        stats = baseline.stats_for(name)
        if stats is None:
            continue
        detail = (
            f"'{name}' was populated in {stats.mean_fill_rate:.0%} of records "
            f"across {stats.runs_observed} prior runs"
        )
        if stats.sample_values:
            examples = "; ".join(f'"{v}"' for v in stats.sample_values)
            detail += f", with values like {examples}"
        parts.append(detail + ".")

    if not verdict.affected_fields and baseline.mean_record_count >= 1:
        parts.append(
            f"This page normally yields about {baseline.mean_record_count:.0f} records "
            f"but returned {run.record_count}."
        )
    return " ".join(parts)


def _still_working(run: RunResult, baseline: Baseline, verdict: Verdict) -> str:
    """Name what is healthy, to scope the repair.

    Without this the healer has no way to know the failure is localised, and a
    broad regeneration can lose extraction logic that was working fine.
    """
    broken = set(verdict.affected_fields)
    intact = sorted(
        name
        for name, stats in baseline.fields.items()
        if stats.is_established and name not in broken and run.fill_rate(name) > 0.5
    )
    clauses = [
        f"The page still loads normally (HTTP {run.fetch.status_code or 200}, "
        f"{run.fetch.html_bytes} bytes of HTML)."
    ]
    if intact:
        clauses.append(f"These fields still extract correctly: {', '.join(intact)}.")
    return " ".join(clauses)


def _instruction(verdict: Verdict) -> str:
    fields = _quoted(verdict.affected_fields)
    target = f"the {fields} field(s)" if fields else "the records"
    return (
        f"The information is still on the page but has moved. "
        f"Re-locate {target} and restore extraction to the original output shape."
    )


def _quoted(names: list[str]) -> str:
    return ", ".join(f"'{n}'" for n in names)


def _fit(text: str, limit: int) -> str:
    """Trim to the character budget on a sentence boundary where possible."""
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    clipped = text[:limit]
    cut = clipped.rfind(". ")
    return clipped[: cut + 1] if cut > limit // 2 else clipped[: limit - 1] + "."

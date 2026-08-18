# AI assistance disclosure

Hackathon rule 10 requires disclosing the use of AI coding assistants, and rule
11 requires the participant to understand and be able to explain the code. This
file states plainly what was used and where.

## Tool

Claude Code (Anthropic) was used throughout, in an agentic terminal workflow.
This is also the intended workflow for the hackathon itself: Bright Data's
Scraper Studio is driven from a coding agent via the `bdata` CLI, so the whole
create/run/heal cycle happens inside the same terminal session.

## What the AI did

- Drafted the Python implementation of the classifier, baseline, heal-prompt
  generator, store, sentinel loop, and CLI from a specified design.
- Researched the live Bright Data documentation and produced the reference notes
  the design rests on.
- Generated the testbed renderer and the six mutation themes.
- Wrote the test suite and the CI workflows.

## What the author directed and verified

- **The architecture.** The four-component shape (fleet, sentinel, heal loop,
  proving ground) and the decision to make the *detection* problem the centre of
  the project rather than the scraping.
- **The classifier's decision rules and their order.** Specifically the rule
  that provider and site failures are ruled out before extraction is examined,
  and the fill-rate rule that separates a dead selector from a genuine content
  change.
- **The thresholds** (80% established / 5% break / 50% partial loss) and the
  conservative bias behind them: missing a break costs one cycle, while a false
  heal can overwrite working extraction logic.
- **The decision not to trust a heal that reports success**, which is why the
  loop re-runs and re-scores before reporting recovery.
- **Target selection** and the judgement that the civic long tail is outside
  Bright Data's pre-built library.
- **Verification.** Every claim in [`status.md`](status.md) was checked by
  running the command and reading the real output. The gate was deliberately
  broken to confirm it could fail before it was trusted. The testbed was
  independently re-verified after the agent reported it complete, including a
  check the agent had not run — that each mutation *relocates* data rather than
  deleting it, without which the healing proof would be meaningless.

## Corrections made to AI output during the build

Recorded because they are the substance of rule 11 — the places where the
generated code was wrong and had to be understood to be fixed.

1. **Baseline cold-start bug.** Only `HEALTHY` runs fed the baseline, but the
   first three runs of any collector are judged `INSUFFICIENT_BASELINE`, so the
   baseline could never bootstrap and every collector stayed unjudgeable
   forever. Fixed by introducing `HealthState.feeds_baseline`, which admits
   `INSUFFICIENT_BASELINE` and `CONTENT_EMPTY` runs while still excluding broken
   and unreachable ones. Caught by the sentinel test suite, not by inspection.
2. **`RunResult.keys()` was a misleading name** that read as a dict method and
   triggered a lint rule. Renamed to `field_names()`.
3. **`--db` only worked before the subcommand**, which would have made a judge's
   first command fail. Moved to a shared parent parser.
4. **Docstrings that became false** after the baseline-eligibility change were
   rewritten rather than left describing behaviour the code no longer had.

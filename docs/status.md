# Verification status

What is actually proven, and what is still an assumption. Updated as things get
confirmed against live infrastructure.

A claim is only listed as VERIFIED if the check was run and its real output
observed. "It should work" does not appear in this file.

Last updated: 2026-08-18

## Verified

| Claim | How it was checked |
|---|---|
| The classifier separates a dead selector from a genuine content change | 27 tests, including the paired cases where 12/12 records lose a field (heals) vs 1/12 (does not) |
| The gate can actually fail | Injected a bug flipping the partial-loss threshold; `test_majority_loss_is_reported_but_not_healed` went red; reverted; green again |
| A heal that reports success but does not fix is not counted as recovery | `test_heal_that_reports_success_but_does_not_fix_is_not_recovery` |
| Broken runs never poison the baseline | `test_broken_runs_never_poison_the_baseline` — 10 consecutive broken runs leave the 5 good runs as the only baseline input |
| Site outages and provider outages never trigger a heal | `test_site_outage_never_triggers_a_heal`, `test_provider_error_outranks_everything` |
| All six testbed themes render, deterministically | Rendered each twice; `diff -r` byte-identical |
| Every mutation is a real structural change | `diff -rq` against baseline differs for all five |
| Every mutation relocates data rather than deleting it | Probed a known record across all six themes: name, phone and hours survive every mutation; m5 splits hours into 7 `data-day` elements |
| Every generated testbed page carries the synthetic-data banner | 13/13 pages |
| Gate: `ruff check` + `ruff format --check` + `mypy --strict` + `pytest` | Run locally, all green, 36 passed |
| **Detection works against real mutated HTML, not just fixtures** | `tests/test_harness_integration.py` renders each theme and runs a fixed-selector scraper over it. m1, m4 and m5 are detected as `SELECTOR_BREAK`; m2 and m3 correctly produce no alert |
| The detector does not cry wolf on cosmetic changes | m2 (hours nested in `<details>`) and m3 (`<span>` to `<dl>`) change the DOM but keep the class hooks, so extraction survives and the verdict stays `HEALTHY` |
| m5 is surgical: only the split field is lost | `test_field_split_loses_only_the_field_it_split` — `affected_fields == ["hours"]`, six other fields still at 100% |
| The detection tests can fail | Set `break_fill_rate` to -1.0 to disable the detector; all three `test_structural_mutation_is_detected` cases went red; restored, green |
| **`bdata scraper heal --auto-approve` exists and is non-interactive** | `bdata scraper heal --help` on live CLI v0.3.x (runs without auth). Approval gate is real; default is "stop and let you review" |
| **`--auto-save` is a SEPARATE required flag** | Same source: "With `--auto-approve`, also save the healed template automatically." Approving without saving leaves the collector running the old broken template. Caught and fixed; `test_heal_passes_both_approve_and_save` guards it |
| `scraper approve` supports `--reject` and `--auto-save` | `bdata scraper approve --help` |
| Heal does NOT re-fetch via `--url` | `--help`: "Not sent to the heal call; heal only mutates the scraper." The `--url` flag only decorates the next-step hint |
| Heal polling timeout defaults to 600s, with 429 retry backoff | `--timeout`, `--max-retries` documented in `--help` |
| `scraper run` routes batches via `/dca/trigger`; `--sync` caps at 25-50s | `bdata scraper run --help` |
| **The mutation testbed is live and mutable on the public internet** | Deployed to https://tarang-tj.github.io/anansi/ via the gh-pages branch. Verified by fetching it: baseline serves a 1729-byte detail page with one `class="hours"` span; after `scripts/deploy-testbed.sh m5_field_split` the same URL serves 2071 bytes with seven `data-day` elements. Propagation under a minute |
| `scripts/deploy-testbed.sh` renders and publishes any theme | Run for real against both `m5_field_split` and `baseline` |
| The generated heal prompt is usable and within budget | `scripts/demo_detection.py` produced a 504-character prompt naming the field, its 100%-across-6-runs history, three real sample values, the six intact fields, and a scoped instruction |

## UNVERIFIED — blocked on a live Bright Data account

These cannot be checked without credentials. Nothing in this repo claims them as
working, and the code is written to survive either answer.

| Assumption | Why it matters | What happens if it is wrong |
|---|---|---|
| The JSON envelope shape returned by `bdata scraper run` | Records must be found in the payload | `extract_records` accepts a bare array plus five common wrapper keys; an unknown shape yields `[]`, which reads as a possible break rather than crashing |
| `BRIGHTDATA_API_KEY` authenticates CI runs | Both scheduled workflows depend on it | The workflows fail loudly with an explicit error rather than silently skipping |
| Scraper Studio will *accept* a GitHub Pages domain as a target | The healing proof depends on it | The testbed itself is now live and confirmed publicly reachable, so only Bright Data's willingness to target it remains open. Fallback is recorded-capture replay via `RecordedBackend`, labelled as weaker evidence |
| `scraper create` / `scraper heal` do not consume page-load credits | Budget planning | Fleet capped at 4-5 collectors and mutations at 5 to stay inside the free tier plus the $50 promo |
| No export exists for generated scraper source | Affects what the README may claim | If export does exist, it is upside: the scraper source gets versioned in-repo |

## Known limitations

- **The baseline needs history.** A brand-new collector reports
  `INSUFFICIENT_BASELINE` until it has 3 runs. This is intentional — judging
  drift against no history produces confident nonsense — but it means the
  system is not useful on its first run, only from its fourth.
- **Thresholds are defaults, not tuned.** 80% established / 5% break / 50%
  partial are reasoned, not empirically fitted. They are constructor arguments
  precisely so they can be tuned once real fleet data exists.
- **One heal attempt per detection.** No retry-with-a-different-prompt loop.
  If the first heal does not recover the collector, it escalates to a human.

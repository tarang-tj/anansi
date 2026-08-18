# Anansi

**A self-healing data layer for the civic long tail.**

Built for [Into the Scrape-Verse](https://www.wemakedevs.org/hackathons/scrape-verse)
(WeMakeDevs × Bright Data, August 2026) on Bright Data Scraper Studio.

---

## The problem

A scraper over a food-pantry directory does not fail loudly. It returns `[]`
with an HTTP 200, exactly like a directory that genuinely has no entries today.
Nothing downstream can tell the difference from a status code. The dashboard
shows a pantry with no hours, and somebody drives to a closed door.

The civic long tail — pantries, free clinics, shelters, community fridges — is
simultaneously the highest-stakes and worst-maintained corner of the web.
Hand-built county and nonprofit sites. No APIs. Layouts that change with no
warning and no changelog. It is precisely the data that Bright Data's 800+
pre-built scrapers do not cover, and precisely the data where silent staleness
does real harm.

## What Anansi does

1. **Scrapes** civic aid directories with custom Scraper Studio collectors.
2. **Judges every run statistically** against that collector's own history,
   because `[]`-at-200 is unfalsifiable in isolation.
3. **Distinguishes a broken scraper from a changed world** — five named states,
   only two of which are healable.
4. **Heals in place** via `bdata scraper heal`, with the repair instruction
   *generated from the evidence*, not hand-typed.
5. **Verifies the fix** by re-running and re-scoring before declaring recovery.
6. **Proves the whole loop is real** with a mutation harness in CI.

## The part that is actually hard

Detection. Consider two runs of the same collector against the same page, both
returning HTTP 200:

| | Run A | Run B |
|---|---|---|
| Records returned | 12 | 12 |
| Records missing `hours` | 12 | 1 |
| Correct response | **heal it** | **leave it alone** |

Run A is a dead selector: selectors fail *uniformly*, missing on every record at
once. Run B is one pantry that stopped publishing its hours — real news about
the world, and healing it would burn credits rewriting logic that works.

Anansi separates them with a rolling per-field baseline. A field must have been
populated in ≥80% of records across ≥3 prior runs to count as established;
established fields dropping to ≤5% read as breakage, while partial losses read
as content change. The full decision order lives in [`src/anansi/classify.py`](src/anansi/classify.py).

### The five states

| State | Meaning | Heals? |
|---|---|---|
| `HEALTHY` | Extraction matches the baseline | no |
| `INSUFFICIENT_BASELINE` | Too little history to judge | no |
| `PROVIDER_DOWN` | Bright Data itself errored | no |
| `SITE_DOWN` | Target served no usable page | no |
| `CONTENT_EMPTY` | Some records lost a field — the data changed | no |
| `SELECTOR_BREAK` | Every record lost an established field | **yes** |
| `SCHEMA_DRIFT` | A field vanished from the payload shape | **yes** |

Ruling out provider and site failures *before* looking at extraction is what
keeps Anansi from "healing" a collector in response to an outage it did not
cause. The monitor deliberately runs outside Bright Data, in GitHub Actions, so
it does not share a failure domain with the thing it is monitoring.

## Proving that healing works

Real websites do not redesign themselves on demand during a seven-day hackathon.
So Anansi ships its own [mutation testbed](testbed/): a static replica of a
pantry directory, rendered from one dataset through six interchangeable themes.

| Mutation | What changes |
|---|---|
| `m1_class_rename` | `.hours` → `.schedule-block` |
| `m2_field_nested` | hours moves inside a collapsed `<details>` |
| `m3_tag_swap` | `<span>` pairs become a `<dl>/<dt>/<dd>` list |
| `m4_redesign` | table listing becomes a card grid |
| `m5_field_split` | one `hours` string becomes seven per-day elements |

Every theme renders the **same data**. Only the markup moves — which is what
makes the test honest: the information is still there and still extractable,
just no longer where the collector learned to look.

The testbed is live at **https://tarang-tj.github.io/anansi/** and any theme can
be published to it with one command:

```bash
scripts/deploy-testbed.sh m5_field_split   # break it
scripts/deploy-testbed.sh baseline         # put it back
```

So the loop runs end to end against a real public URL: **green → mutate →
detect red → heal → green**, same Collector ID throughout, nothing downstream
touched.

## Status

This project is under active development for the hackathon window
(2026-08-17 → 2026-08-23). See [`docs/status.md`](docs/status.md) for what is
verified against live Bright Data infrastructure and what is not yet.

## Quick start

```bash
git clone https://github.com/tarang-tj/anansi
cd anansi
uv sync
uv run pytest            # the classifier suite runs offline, no credentials needed
```

To drive live collectors you need a Bright Data account:

```bash
export BRIGHTDATA_API_KEY=...        # never commit this
uv run anansi status                 # fleet health from stored history
```

## Honest notes on Bright Data

Two things worth stating plainly, because they shaped the design:

- **"You own the code" is not literally true today.** There is no
  `bdata scraper export`, and no REST endpoint returns the generated scraper
  source — it stays server-side. What you genuinely own is the Collector ID, the
  output data, and the ability to run, schedule and heal it. Anansi treats the
  Collector ID as the stable contract and versions everything *around* it.
- **Batch results are deleted after 16 days.** Any system that wants a baseline
  longer than that has to persist its own history, which is why Anansi keeps a
  local SQLite run log rather than querying Bright Data for its past.

## AI disclosure

Per hackathon rule 10: this project was built with AI assistance (Claude Code).
The architecture, the classifier's decision rules and thresholds, the target
selection, and all design trade-offs were directed and reviewed by the author.
See [`docs/ai-disclosure.md`](docs/ai-disclosure.md) for specifics.

## Licence

MIT. The data in `testbed/` is synthetic and must not be used to find real
services.

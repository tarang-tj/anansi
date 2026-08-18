# Anansi mutation testbed

## What this is

A small, self-hosted static website used to prove that Anansi's self-healing
scraper actually heals. Real civic-aid directories do not redesign their
markup on cue during a 7-day hackathon window, so instead of scraping a real
site we host one we fully control: `testbed/site/`. We render it from a
single source of truth (`data.json`) through six interchangeable "themes,"
each producing a different DOM shape for the exact same underlying data.
Swapping the theme and re-deploying is the mutation; Anansi's job is to
notice the collector broke, diagnose why, and heal itself back to green
without a human rewriting the scraper.

## The data is synthetic -- read this before using anything here

**Every record in `data.json`, and every generated page, describes a
fictional organization.** Organization names, phone numbers
(`(555) 555-01XX`), street addresses, and the county/state
("Mercer Hollow County, State of Serenoa") are all invented for this
project. Every generated HTML page carries a visible red banner:

> Synthetic test fixture for the Anansi self-healing scraper. Not real aid
> information -- do not use to find services.

This is deliberate and non-negotiable: realistic-looking fake aid data could
genuinely mislead someone searching for real help if it escaped this
context. Do not repurpose this data, these page templates, or this banner
text to represent any real service. If you are reading this file because you
found a generated page and are looking for real food assistance or a free
clinic, this is not that -- try 211.org or your local county health
department instead.

## Layout

```
testbed/
├── data.json              # the 12 synthetic source records
├── render.py               # CLI: renders data.json -> site/ using a named theme
├── themes/
│   ├── __init__.py         # THEMES registry (name -> theme module)
│   ├── helpers.py          # shared HTML-building helpers used by the themes
│   ├── baseline.py         # the "before" DOM the scraper first learns
│   ├── m1_class_rename.py  # semantic class rename, same DOM shape
│   ├── m2_field_nested.py  # hours field moves inside <details>/<summary>
│   ├── m3_tag_swap.py      # <span> field pairs become a <dl>/<dt>/<dd>
│   ├── m4_redesign.py      # full layout change: table -> card grid
│   └── m5_field_split.py   # hours splits into 7 per-day <li> elements
└── site/                   # GENERATED output (git-tracked so diffs are visible)
```

`site/` is generated but committed on purpose: a `git diff` of `site/`
between two theme renders is the literal, reviewable proof of what a
mutation changed in the DOM -- that diff is part of the hackathon
submission's evidence trail.

## The two page shapes

- `site/index.html` -- a directory listing linking to all 12 detail pages.
  This is the **Discovery** scraper target.
- `site/pantry/<slug>.html` -- one detail page per organization with every
  field. This is the **PDP** (product/profile detail page) scraper target.

Every page, on every theme, is valid standalone HTML with relative links, no
external assets (fonts/scripts/images), and no JavaScript required to read
any field -- a scraper must be able to extract every value from the static
HTML alone. CSS is minimal and inline so the redesign mutation is also
visually obvious to a human watching the demo.

## The six themes

All six render the *same* `data.json`; only the markup differs. That is what
makes the healing test honest -- the information never disappears, it just
moves somewhere the old scraper doesn't know to look.

| Theme | What changes | DOM shape vs baseline |
|---|---|---|
| `baseline` | n/a -- the starting point | -- |
| `m1_class_rename` | `.hours` -> `.schedule-block`, `.pantry-card` -> `.org-tile`, etc. | Identical nesting, only class names differ |
| `m2_field_nested` | Hours moves inside a collapsed `<details><summary>Hours</summary>...</details>` | One extra nesting level around hours only |
| `m3_tag_swap` | Field list converts from `<span class="...">` pairs to a `<dl><dt>/<dd>` | Different tags, same field order |
| `m4_redesign` | Table-based listing becomes a card grid; detail page becomes an `<article>/<header>/<section>` hierarchy with a new class vocabulary | Most aggressive -- nothing structurally shared with baseline |
| `m5_field_split` | The single `hours` string splits into seven `<li data-day="mon">9am-4pm</li>` elements | The old single-field extraction has no direct equivalent |

`m5`'s per-day split is computed deterministically from the same compact
`hours` string in `data.json` (e.g. `"Mon-Fri 9am-4pm, Sat 10am-2pm"`) via
`parse_hours_to_days()` in `themes/__init__.py` -- there is no separate,
hidden source of per-day data; it is a pure derived transform.

## Rendering

Standard library only (no Jinja2, no dependencies). Python 3.12.

```bash
# from the repo root
python testbed/render.py --theme baseline --out testbed/site
python testbed/render.py --theme m1_class_rename --out testbed/site
python testbed/render.py --theme m4_redesign --out testbed/site
```

Each invocation clears and fully re-writes `--out` (13 files: `index.html` +
12 files under `pantry/`). Rendering is deterministic: the same `--theme`
against the same `data.json` produces byte-identical output every time, so
`git diff testbed/site/` after a theme swap shows exactly, and only, what
that mutation changed.

To apply a mutation for a demo or CI job: re-render with a different
`--theme` value and re-deploy `site/` (see below). To revert: re-render with
`--theme baseline`.

## Deploying to GitHub Pages

`site/` is plain static HTML, so any of the standard GitHub Pages paths
work. Simplest for this repo:

1. In the repo's GitHub settings -> Pages, set the source to "Deploy from a
   branch," branch `main` (or whichever branch holds the render), folder
   `/testbed/site`.
2. Every time you want to mutate the live demo target, run
   `python testbed/render.py --theme <name> --out testbed/site`, commit the
   regenerated `site/`, and push. GitHub Pages redeploys automatically.
3. Alternatively, wire a GitHub Actions workflow that runs `render.py` and
   publishes `testbed/site` via `actions/deploy-pages` on demand -- useful
   if the mutation needs to happen mid-demo without a manual commit. That
   workflow lives outside `testbed/` (owned by CI, not this directory).

## Verifying it works

```bash
# every theme renders without error
for t in baseline m1_class_rename m2_field_nested m3_tag_swap m4_redesign m5_field_split; do
  python testbed/render.py --theme "$t" --out testbed/site
done

# data.json is valid and has 12 records
python -c "import json; d = json.load(open('testbed/data.json')); assert len(d) == 12; print('ok')"

# determinism: two renders of the same theme are byte-identical
python testbed/render.py --theme baseline --out /tmp/run1
python testbed/render.py --theme baseline --out /tmp/run2
diff -r /tmp/run1 /tmp/run2 && echo "byte-identical"
```

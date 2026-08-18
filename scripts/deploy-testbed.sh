#!/usr/bin/env bash
# Render one testbed theme and publish it to GitHub Pages.
#
#   scripts/deploy-testbed.sh baseline
#   scripts/deploy-testbed.sh m5_field_split
#
# This is how the site "changes under" a live collector on demand. Pushing the
# gh-pages branch directly avoids needing the `workflow` OAuth scope, so the
# healing demo can be driven without a GitHub Actions run.
#
# Pages serves from the gh-pages branch; allow ~30-60s for the CDN to catch up
# before running a collector against it, or the scraper will read the old markup
# and the proof will be meaningless.

set -euo pipefail

THEME="${1:-baseline}"
REPO_URL="https://github.com/tarang-tj/anansi.git"
PAGES_URL="https://tarang-tj.github.io/anansi/"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

VALID="baseline m1_class_rename m2_field_nested m3_tag_swap m4_redesign m5_field_split"
if ! grep -qw "$THEME" <<<"$VALID"; then
  echo "unknown theme: $THEME" >&2
  echo "expected one of: $VALID" >&2
  exit 1
fi

echo "rendering theme: $THEME"
# Run through uv, not a bare `python3`. On macOS `python3` resolves to the
# system 3.9, and the renderer needs 3.10+ for Path.write_text(newline=...).
# Rendering with the wrong interpreter fails loudly here, but the same mistake
# inside a deploy pipeline would publish a stale site and quietly invalidate
# whatever the collector then measured.
(cd "$ROOT" && uv run python testbed/render.py --theme "$THEME" --out testbed/site)

STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
cp -R "$ROOT/testbed/site/." "$STAGE/"
touch "$STAGE/.nojekyll" # keep Jekyll from eating the directory structure

cd "$STAGE"
git init -q
git checkout -qb gh-pages
git add -A
git -c user.name="anansi-bot" -c user.email="anansi-bot@users.noreply.github.com" \
  commit -q -m "deploy: testbed theme $THEME"
git remote add origin "$REPO_URL"
git push -qf origin gh-pages

echo "deployed $THEME to $PAGES_URL"
echo "wait ~30-60s for the CDN, then run the collector against it"

#!/usr/bin/env python3
"""Render testbed/data.json into a static site using a named theme.

Usage:
    python testbed/render.py --theme baseline --out testbed/site
    python testbed/render.py --theme m4_redesign --out testbed/site

Standard library only. Deterministic: re-running the same theme against the
same data.json produces byte-identical output, so a git diff of site/ shows
exactly what a mutation changed.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure the themes package (a sibling of this script) is importable
# regardless of the caller's working directory or invocation style.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from themes import THEMES, load_data, write_site  # noqa: E402  (path must be set first)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--theme", required=True, choices=sorted(THEMES), help="which theme to render")
    parser.add_argument("--out", required=True, type=Path, help="output directory for the generated site")
    parser.add_argument(
        "--data",
        type=Path,
        default=Path(__file__).resolve().parent / "data.json",
        help="path to data.json (default: testbed/data.json)",
    )
    args = parser.parse_args(argv)

    try:
        records = load_data(args.data)
    except (OSError, ValueError) as exc:
        print(f"error: failed to load {args.data}: {exc}", file=sys.stderr)
        return 1

    theme = THEMES[args.theme]
    index_html = theme.render_index(records)
    detail_pages = {record["slug"]: theme.render_detail(record) for record in records}

    write_site(args.out, index_html, detail_pages)
    print(f"rendered theme '{args.theme}': {1 + len(detail_pages)} pages -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

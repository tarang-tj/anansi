"""Render the fleet's health and heal history as one static HTML page.

No framework, no build step, no external assets -- the page is generated from
the SQLite log and can be opened from disk or served by GitHub Pages. Data is
only useful once somebody can read it, and a self-healing system's most
interesting artifact is its scar tissue: the log of what broke and what fixed it.
"""

from __future__ import annotations

import html
from datetime import UTC, datetime
from typing import Any

from anansi.models import HealthState
from anansi.store import RunStore

_STATE_LABEL = {
    HealthState.HEALTHY.value: ("ok", "healthy"),
    HealthState.INSUFFICIENT_BASELINE.value: ("warn", "learning"),
    HealthState.CONTENT_EMPTY.value: ("warn", "content changed"),
    HealthState.SITE_DOWN.value: ("bad", "site down"),
    HealthState.PROVIDER_DOWN.value: ("bad", "provider down"),
    HealthState.SELECTOR_BREAK.value: ("bad", "selector break"),
    HealthState.SCHEMA_DRIFT.value: ("bad", "schema drift"),
}

_CSS = """
:root { --bg:#fbfaf8; --fg:#1c1a17; --muted:#6b6560; --line:#e3ded7;
        --ok:#1f7a4d; --warn:#8a6100; --bad:#a32020; --card:#fff; }
@media (prefers-color-scheme: dark) {
  :root { --bg:#16150f; --fg:#efe9e0; --muted:#a19a90; --line:#312d26;
          --ok:#5fd39b; --warn:#e0b357; --bad:#f0837b; --card:#1e1c16; }
}
* { box-sizing:border-box; }
body { margin:0; padding:2.5rem 1.25rem; background:var(--bg); color:var(--fg);
       font:16px/1.55 ui-sans-serif,-apple-system,Segoe UI,Roboto,sans-serif; }
main { max-width:60rem; margin:0 auto; }
h1 { font-size:1.6rem; margin:0 0 .25rem; letter-spacing:-.01em; }
.sub { color:var(--muted); margin:0 0 2rem; }
h2 { font-size:1.05rem; margin:2.5rem 0 .75rem; }
table { width:100%; border-collapse:collapse; font-size:.9rem; }
th { text-align:left; font-weight:600; color:var(--muted); font-size:.75rem;
     text-transform:uppercase; letter-spacing:.05em; padding:.5rem .6rem; }
td { padding:.6rem; border-top:1px solid var(--line); vertical-align:top; }
.wrap { overflow-x:auto; border:1px solid var(--line); border-radius:.6rem;
        background:var(--card); }
.pill { display:inline-block; padding:.12rem .5rem; border-radius:1rem;
        font-size:.75rem; font-weight:600; border:1px solid currentColor; }
.ok{color:var(--ok)} .warn{color:var(--warn)} .bad{color:var(--bad)}
.mono { font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-size:.82rem; }
.prompt { color:var(--muted); font-size:.82rem; max-width:38rem; }
.empty { color:var(--muted); padding:1.5rem; text-align:center; }
footer { margin-top:3rem; color:var(--muted); font-size:.8rem;
         border-top:1px solid var(--line); padding-top:1rem; }
"""


def render_dashboard(store: RunStore) -> str:
    """Build the whole page from stored history."""
    rows = _fleet_rows(store)
    heals = store.heal_events()
    generated = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Anansi fleet health</title><style>{_CSS}</style></head>
<body><main>
<h1>Anansi fleet health</h1>
<p class="sub">Self-healing collectors over the civic long tail.
Generated {generated}.</p>
{_fleet_table(rows)}
{_heal_table(heals)}
<footer>A collector is only judged against its own history. States other than
<em>selector break</em> and <em>schema drift</em> are never healed, so a site
outage or a genuine content change can't trigger a repair.</footer>
</main></body></html>
"""


def _fleet_rows(store: RunStore) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for cid in store.collectors():
        latest = store.latest_run(cid)
        if latest is None:
            continue
        run, state = latest
        rows.append(
            {
                "collector_id": cid,
                "url": run.url,
                "state": state,
                "records": run.record_count,
                "ran_at": run.ran_at.strftime("%Y-%m-%d %H:%M"),
            }
        )
    return rows


def _fleet_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return '<div class="wrap"><p class="empty">No runs recorded yet.</p></div>'
    body = "\n".join(
        f"<tr><td class='mono'>{_e(r['collector_id'])}</td>"
        f"<td>{_pill(r['state'])}</td>"
        f"<td>{r['records']}</td>"
        f"<td class='mono'>{_e(r['ran_at'])}</td>"
        f"<td class='prompt'>{_e(r['url'])}</td></tr>"
        for r in rows
    )
    return f"""<div class="wrap"><table>
<thead><tr><th>Collector</th><th>State</th><th>Records</th><th>Last run</th>
<th>Target</th></tr></thead><tbody>{body}</tbody></table></div>"""


def _heal_table(heals: list[dict[str, Any]]) -> str:
    heading = "<h2>Heal history</h2>"
    if not heals:
        return heading + '<div class="wrap"><p class="empty">Nothing has broken yet.</p></div>'
    body = "\n".join(
        f"<tr><td class='mono'>{_e(str(h['collector_id']))}</td>"
        f"<td>{_pill(str(h['before_state']))}</td>"
        f"<td>{_pill(str(h['after_state'] or 'unknown'))}</td>"
        f"<td>{'recovered' if h['recovered'] else 'needs a human'}</td>"
        f"<td class='prompt'>{_e(str(h['prompt']))}</td></tr>"
        for h in heals
    )
    return f"""{heading}<div class="wrap"><table>
<thead><tr><th>Collector</th><th>Broke as</th><th>Then</th><th>Outcome</th>
<th>Generated heal prompt</th></tr></thead><tbody>{body}</tbody></table></div>"""


def _pill(state: str) -> str:
    cls, label = _STATE_LABEL.get(state, ("warn", state))
    return f'<span class="pill {cls}">{_e(label)}</span>'


def _e(text: str) -> str:
    return html.escape(str(text))

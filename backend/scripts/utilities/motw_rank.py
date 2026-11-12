#!/usr/bin/env python3
"""Rank a week's Match of the Week candidates with this checkout's code, on real data.

Preview a scoring change before it deploys. Read-only by construction: it drops the
service key and connects with the anon key, so row-level security refuses any write.

    ../scripts/motw.sh rank [--week YYYY-MM-DD] [--top N] [--rematches] [--env local]
"""

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from structlog.testing import capture_logs

BACKEND = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND))
COLUMNS = {"quality": "QUAL", "closeness": "CLOSE", "stakes": "STAKES", "form": "FORM"}


def connect(env: str):
    env_file = Path(os.environ.get("MT_ENV_FILE", BACKEND / f".env.{env}"))
    if not env_file.exists():
        raise SystemExit(f"{env_file} not found")
    load_dotenv(env_file, override=True)
    os.environ["APP_ENV"] = env
    # Empty, not unset: the DAO module runs load_dotenv() on import, which fills in a
    # missing variable from backend/.env but leaves one that exists alone.
    os.environ["SUPABASE_SERVICE_KEY"] = ""
    if not os.environ.get("SUPABASE_ANON_KEY"):
        raise SystemExit(f"SUPABASE_ANON_KEY missing from {env_file}")
    from mt_ai.tools.deps import dao_tool_deps

    return dao_tool_deps()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--week", help="any YYYY-MM-DD in the week (default: this week)")
    parser.add_argument("--top", type=int, help="show only the first N")
    parser.add_argument("--rematches", action="store_true", help="only fixtures flagged rematch")
    parser.add_argument("--env", choices=("prod", "local"), default="prod")
    parser.add_argument("--pool", choices=("main", "pathway"), default="main", help="MOTW pool (SB-1638)")
    parser.add_argument("--age-group", help="one slot, e.g. U16 (default: every age in the pool)")
    args = parser.parse_args()

    deps = connect(args.env)
    from mt_tools.motw_candidates import MAX_LIMIT, suggest_from_deps

    # The result stops at MAX_LIMIT; the log line has every eligible fixture.
    with capture_logs() as logs:
        result = suggest_from_deps(deps, args.week, limit=MAX_LIMIT, pool=args.pool, age_group=args.age_group)
    if result.error:
        raise SystemExit(f"{result.error.kind}: {result.error.message}")
    lines = [e for e in logs if e["event"] == "motw_candidates_scored"]
    if not lines:
        raise SystemExit(result.reason or "no candidates")
    line = lines[0]

    console = Console(width=150)
    table = Table(
        title=f"Week of {line['week_start']} ({args.pool} {args.age_group or 'all ages'}): {line['eligible']} eligible of {line['fixtures_in_week']}"
    )
    table.add_column("#", justify="right")
    table.add_column("TOTAL", justify="right", style="bold")
    for header in COLUMNS.values():
        table.add_column(header, justify="right")
    table.add_column("AGE")
    table.add_column("DIVISION")
    table.add_column("MATCH", no_wrap=True)
    table.add_column("FLAGS")

    rows = list(enumerate(line["candidates"], 1))
    if args.rematches:
        rows = [(n, c) for n, c in rows if "rematch" in c["flags"]]
    for n, c in rows[: args.top]:
        style = "green" if n <= 3 else None
        table.add_row(
            str(n),
            f"{c['total']:.3f}",
            *(f"{c[name]:.2f}" for name in COLUMNS),
            c["age_group"],
            c["division"],
            c["fixture"],
            ", ".join(c["flags"]),
            style=style,
        )
    console.print(table)
    console.print("Green rows go to Slack. Rematch facts in the top 10:")
    for c in result.candidates:
        for fact in c.facts:
            if fact.id.endswith(":h2h") and "meeting this season" in fact.text:
                console.print(f"  {c.home.name} vs {c.away.name} ({c.age_group.name}): {fact.text}")


if __name__ == "__main__":
    main()

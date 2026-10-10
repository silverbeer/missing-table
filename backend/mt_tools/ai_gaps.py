"""What MT AI could not answer (SB-1308): not_found and ambiguous tool calls.

Read from `ai_tool_calls` (SB-1197), which keeps each MT AI tool call with the
arguments the model sent. A call's outcome is read the way mt-mcp's
ToolCallObserver labels it: the tool's error kind when it reported one, else its
own `status`. So a search_teams `not_found` that was really an outage
(`error.kind = unavailable`) is an outage here too, not a gap.

Calls are grouped by tool and query — the same name typed with different case or
spacing is one gap — with counts and when it was last asked. The output feeds
team aliases (a not_found name that is a real team), eval cases (ai-quality.md)
and what tool to build next (mt2/mcp.md § Observability).

Arguments can name minors: this is admin only, and argument values are never
logged.
"""

import json
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

import structlog
from pydantic import BaseModel

from mt_ai.tools.schemas import ToolError

logger = structlog.get_logger()

GAP_OUTCOMES = ("not_found", "ambiguous")

DEFAULT_DAYS = 30
MAX_DAYS = 365
# A guard on how many gap calls one report reads; a report that hits it says so.
MAX_ROWS = 5000


class ToolCallSource(Protocol):
    def gap_tool_calls(
        self, since: str, outcomes: tuple[str, ...], tool: str | None = None, max_rows: int = MAX_ROWS
    ) -> list[dict[str, Any]]: ...

    def count_tool_calls(self, since: str, tool: str | None = None) -> int: ...


class AIGap(BaseModel):
    tool: str
    query: str  # as most recently typed
    age_groups: list[str] = []
    count: int
    not_found: int = 0
    ambiguous: int = 0
    first_seen: str | None = None
    last_seen: str | None = None


class AIGapsResult(BaseModel):
    """`gaps` is [] when nothing went unanswered, and null only when the read failed.

    `total_calls` is the denominator: every tool call in the window, any outcome.
    """

    gaps: list[AIGap] | None = None
    count: int = 0
    gap_calls: int = 0
    total_calls: int | None = None
    days: int = DEFAULT_DAYS
    since: str | None = None
    tool: str | None = None
    truncated: bool = False
    error: ToolError | None = None


def call_outcome(row: dict[str, Any]) -> str | None:
    """The error kind the tool reported, else its status (as ToolCallObserver labels it)."""
    if row.get("error_kind"):
        return str(row["error_kind"])
    status = row.get("status")
    if status is None and isinstance(row.get("result"), dict):
        status = row["result"].get("status")
    return str(status) if status else None


def query_of(args: Any) -> str:
    """The text that was looked up: `query` when the tool takes one, else every argument but the age group."""
    if not isinstance(args, dict):
        return ""
    query = args.get("query")
    if isinstance(query, str):
        return " ".join(query.split())
    rest = {k: v for k, v in args.items() if k != "age_group"}
    return ", ".join(f"{k}={json.dumps(v, default=str)}" for k, v in sorted(rest.items()))


def _key(query: str) -> str:
    return query.casefold()


def group_gaps(rows: list[dict[str, Any]]) -> list[AIGap]:
    """not_found / ambiguous calls → one row per (tool, query), most asked first.

    Other outcomes are skipped, so a caller may pass every call it has.
    """
    groups: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        outcome = call_outcome(row)
        if outcome not in GAP_OUTCOMES:
            continue
        tool = str(row.get("tool_name") or "unknown")
        args = row.get("args") if isinstance(row.get("args"), dict) else {}
        query = query_of(args)
        seen = str(row["created_at"]) if row.get("created_at") is not None else None
        group = groups.setdefault(
            (tool, _key(query)),
            {
                "tool": tool,
                "query": query,
                "age_groups": [],
                "count": 0,
                "not_found": 0,
                "ambiguous": 0,
                "first_seen": seen,
                "last_seen": seen,
            },
        )
        group["count"] += 1
        group[outcome] += 1
        age_group = args.get("age_group")
        if isinstance(age_group, str) and age_group.strip() and age_group.strip() not in group["age_groups"]:
            group["age_groups"].append(age_group.strip())
        if seen is not None:
            if group["first_seen"] is None or seen < group["first_seen"]:
                group["first_seen"] = seen
            if group["last_seen"] is None or seen >= group["last_seen"]:
                group["last_seen"] = seen
                group["query"] = query  # show the latest spelling
    gaps = [AIGap(**g) for g in groups.values()]
    gaps.sort(key=lambda g: g.last_seen or "", reverse=True)
    gaps.sort(key=lambda g: g.count, reverse=True)  # stable: ties stay newest first
    return gaps


def list_ai_gaps(
    source: ToolCallSource, days: int = DEFAULT_DAYS, tool: str | None = None, now: datetime | None = None
) -> AIGapsResult:
    days = max(1, min(days, MAX_DAYS))
    since = ((now or datetime.now(UTC)) - timedelta(days=days)).isoformat()
    try:
        rows = source.gap_tool_calls(since, GAP_OUTCOMES, tool=tool, max_rows=MAX_ROWS)
        total = source.count_tool_calls(since, tool=tool)
    except Exception:
        logger.exception("list_ai_gaps failed", days=days)
        return AIGapsResult(
            days=days,
            since=since,
            tool=tool,
            error=ToolError(kind="unavailable", message="The AI gap report is unavailable right now."),
        )
    gaps = group_gaps(rows)
    return AIGapsResult(
        gaps=gaps,
        count=len(gaps),
        gap_calls=sum(g.count for g in gaps),
        total_calls=total,
        days=days,
        since=since,
        tool=tool,
        truncated=len(rows) >= MAX_ROWS,
    )

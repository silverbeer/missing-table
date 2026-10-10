"""What mt-mcp is asked, by whom, and how it went (SB-1302).

`ToolCallObserver` is the outermost server middleware. For every tools/call it
emits one structlog event and two Prometheus series (served on the backend's
existing /metrics, scraped by Grafana Alloy):

    mt_mcp_tool_calls_total{tool, client, role, outcome}
    mt_mcp_tool_call_seconds{tool, outcome}

HTTP metrics see only "POST /mcp"; these say which tool. `outcome` is the
tool's own verdict where it has one — `resolved` / `ambiguous` / `not_found`
for search_teams, an error kind (`unavailable`, ...) — so "what do people ask
for that MT cannot find" is a query, not a log trawl. Calls refused by the tier
gate are `refused`; protocol-level failures are `failed`.

Every label is bounded: names outside the known sets collapse to "other".
Arguments are not labels; the log carries their names only. Recording argument
values for replay is a separate decision (tool arguments can name minors).
"""

import time
from collections.abc import Iterable
from typing import Any

import structlog
from mcp.server.context import CallNext, HandlerResult, ServerRequestContext
from prometheus_client import Counter, Histogram

from mt_mcp.auth import current_principal
from mt_mcp.scopes import CLIENT_CAPS, CLIENT_HEADER, ROLE_TIERS

logger = structlog.get_logger()

TOOL_CALLS = Counter(
    "mt_mcp_tool_calls_total",
    "mt-mcp tool calls by tool, client, caller role and outcome",
    ["tool", "client", "role", "outcome"],
)
TOOL_SECONDS = Histogram(
    "mt_mcp_tool_call_seconds",
    "mt-mcp tool call duration",
    ["tool", "outcome"],
    buckets=(0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)

# The tool's own verdicts and MT's error kinds; anything else is "other".
KNOWN_OUTCOMES = frozenset(
    {"ok", "resolved", "ambiguous", "not_found", "unavailable", "invalid", "refused", "failed", "error"}
)


def bounded(value: str | None, known: Iterable[str], *, missing: str = "none") -> str:
    if not value:
        return missing
    value = value.strip().lower()
    return value if value in known else "other"


def outcome_of(result: Any) -> str:
    """A tools/call result → one bounded outcome label."""
    if result is None:
        return "failed"
    data = result.model_dump(by_alias=True) if hasattr(result, "model_dump") else result
    if not isinstance(data, dict):
        return "ok"
    structured = data.get("structuredContent")
    if data.get("isError"):
        text = "".join(c.get("text", "") for c in data.get("content") or [] if isinstance(c, dict))
        return "refused" if text.startswith("Unknown tool:") else "error"
    if isinstance(structured, dict):
        error = structured.get("error")
        if isinstance(error, dict) and error.get("kind"):
            return bounded(str(error["kind"]), KNOWN_OUTCOMES)
        status = structured.get("status")
        if isinstance(status, str):
            return bounded(status, KNOWN_OUTCOMES)
    return "ok"


class ToolCallObserver:
    """ServerMiddleware: one log line and two metric samples per tools/call."""

    def __init__(self, tool_names: Iterable[str], clock: Any = time.perf_counter) -> None:
        self.tool_names = frozenset(tool_names)
        self.clock = clock

    async def __call__(self, ctx: ServerRequestContext[Any, Any], call_next: CallNext) -> HandlerResult:
        if ctx.method != "tools/call":
            return await call_next(ctx)

        params = ctx.params or {}
        tool = bounded(str(params.get("name", "")), self.tool_names, missing="other")
        headers = getattr(ctx.request, "headers", None)
        client = bounded(headers.get(CLIENT_HEADER) if headers is not None else None, CLIENT_CAPS)
        principal = current_principal()
        role = bounded(principal.role if principal else None, ROLE_TIERS)

        started = self.clock()
        result: HandlerResult = None
        try:
            result = await call_next(ctx)
            return result
        finally:
            seconds = self.clock() - started
            outcome = outcome_of(result)
            TOOL_CALLS.labels(tool=tool, client=client, role=role, outcome=outcome).inc()
            TOOL_SECONDS.labels(tool=tool, outcome=outcome).observe(seconds)
            logger.info(
                "mt_mcp.tool_call",
                tool=tool,
                client=client,
                role=role,
                outcome=outcome,
                duration_ms=round(seconds * 1000),
                user_id=principal.user_id if principal else None,
                arg_names=sorted((params.get("arguments") or {}).keys()),
            )

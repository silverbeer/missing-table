"""What one turn did and how long it took (SB-1197).

`TurnRecorder` is fed by the agent's ADK callbacks: model calls are timed
(before/after model), tool calls are timed and their arguments and results
kept (before/after tool). It imports nothing from ADK: the callbacks pass it
plain values, so it is unit-tested with a fake clock.

The service writes the records to `ai_tool_calls` and the timings to the
assistant row of `ai_messages`, best-effort, after the turn itself is saved.
"""

import hashlib
import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

# A tool result bigger than this (as JSON) is stored as a digest. MT's tools
# cap their output (8 candidates, 20 matches), so this is a guard, not a norm.
MAX_RESULT_BYTES = 32_000


@dataclass(frozen=True)
class ToolCallRecord:
    seq: int
    tool_name: str
    args: dict[str, Any]
    result: dict[str, Any] | None
    error_kind: str | None
    duration_ms: int | None


@dataclass
class TurnRecorder:
    """Collects one turn's tool calls and model time. Not thread-safe: one per turn."""

    clock: Callable[[], float] = time.perf_counter
    calls: list[ToolCallRecord] = field(default_factory=list)
    llm_seconds: float = 0.0
    _model_started: float | None = None
    _tool_started: dict[str, float] = field(default_factory=dict)

    @property
    def llm_ms(self) -> int:
        return round(self.llm_seconds * 1000)

    def before_model(self, callback_context: Any = None, llm_request: Any = None) -> None:
        self._model_started = self.clock()

    def after_model(self, callback_context: Any = None, llm_response: Any = None) -> None:
        if self._model_started is not None:
            self.llm_seconds += self.clock() - self._model_started
            self._model_started = None

    def before_tool(self, tool: Any, args: dict[str, Any], tool_context: Any) -> None:
        self._tool_started[_call_key(tool, tool_context)] = self.clock()

    def after_tool(self, tool: Any, args: dict[str, Any], tool_context: Any, tool_response: Any) -> None:
        started = self._tool_started.pop(_call_key(tool, tool_context), None)
        duration = None if started is None else round((self.clock() - started) * 1000)
        result = tool_response if isinstance(tool_response, dict) else {"value": tool_response}
        self.calls.append(
            ToolCallRecord(
                seq=len(self.calls) + 1,
                tool_name=getattr(tool, "name", str(tool)),
                args=dict(args or {}),
                result=bounded(result),
                error_kind=error_kind(result),
                duration_ms=duration,
            )
        )


def _call_key(tool: Any, tool_context: Any) -> str:
    """ADK gives each function call an id; fall back to the tool name."""
    return str(getattr(tool_context, "function_call_id", None) or getattr(tool, "name", tool))


def error_kind(result: dict[str, Any]) -> str | None:
    """The `error.kind` a tool reported in its result, if any."""
    error = result.get("error")
    if isinstance(error, dict):
        kind = error.get("kind")
        return str(kind) if kind else "unknown"
    return None


def bounded(result: dict[str, Any]) -> dict[str, Any]:
    """The result itself, or a digest when it is too big to keep."""
    text = json.dumps(result, default=str, sort_keys=True)
    size = len(text.encode())
    if size <= MAX_RESULT_BYTES:
        return json.loads(text)  # plain JSON types only, as jsonb will hold them
    return {"truncated": True, "bytes": size, "sha256": hashlib.sha256(text.encode()).hexdigest()}

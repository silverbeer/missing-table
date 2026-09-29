"""Per-request work budget for one MT AI turn (SB-1143).

Two limits, both deterministic:

- `max_llm_calls` — enforced by ADK itself (`RunConfig.max_llm_calls`), which
  raises `LlmCallsLimitExceededError` before the call that would exceed it.
- `max_tool_calls` — enforced by `ToolCallGuard`, an ADK `before_tool_callback`
  that raises before the tool that would exceed it runs.

Either way the run stops; nothing continues in the background. Token and cost
budgets, and per-user quotas, belong to later slices (mt2/ai-cost.md).
"""

from dataclasses import dataclass
from typing import Any, Literal

BudgetLimit = Literal["llm_calls", "tool_calls"]


@dataclass(frozen=True)
class Budget:
    max_llm_calls: int = 4
    max_tool_calls: int = 3

    def __post_init__(self) -> None:
        if self.max_llm_calls < 1 or self.max_tool_calls < 0:
            raise ValueError("budget limits must be positive")


class BudgetExhaustedError(Exception):
    def __init__(self, limit: BudgetLimit) -> None:
        super().__init__(f"MT AI budget exhausted: {limit}")
        self.limit = limit


class ToolCallGuard:
    """Counts tool calls in one run and stops the run at the limit."""

    def __init__(self, max_tool_calls: int) -> None:
        self.max_tool_calls = max_tool_calls
        self.calls = 0

    def before_tool(self, tool: Any, args: dict[str, Any], tool_context: Any) -> None:
        if self.calls >= self.max_tool_calls:
            raise BudgetExhaustedError("tool_calls")
        self.calls += 1

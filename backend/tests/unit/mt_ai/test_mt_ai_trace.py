"""mt_ai.trace (SB-1197): what a turn did and how long it took, on a fake clock."""

from types import SimpleNamespace

import pytest

from mt_ai.trace import MAX_RESULT_BYTES, TurnRecorder, bounded, error_kind

pytestmark = [pytest.mark.unit, pytest.mark.backend]


class Clock:
    """Seconds that only move when told to."""

    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


def tool(name):
    return SimpleNamespace(name=name)


def ctx(call_id):
    return SimpleNamespace(function_call_id=call_id)


def test_model_time_adds_up_across_calls():
    clock = Clock()
    recorder = TurnRecorder(clock=clock)

    recorder.before_model()
    clock.now += 1.5
    recorder.after_model()
    clock.now += 10  # tool time is not model time
    recorder.before_model()
    clock.now += 0.25
    recorder.after_model()

    assert recorder.llm_ms == 1750


def test_an_unmatched_after_model_adds_nothing():
    recorder = TurnRecorder(clock=Clock())
    recorder.after_model()
    assert recorder.llm_ms == 0


def test_each_tool_call_is_kept_in_order_with_its_args_result_and_time():
    clock = Clock()
    recorder = TurnRecorder(clock=clock)

    recorder.before_tool(tool("search_teams"), {"query": "IFA"}, ctx("c1"))
    clock.now += 0.2
    recorder.after_tool(tool("search_teams"), {"query": "IFA"}, ctx("c1"), {"status": "resolved", "team": {"id": 1}})
    recorder.before_tool(tool("get_upcoming_matches"), {"team_id": 1}, ctx("c2"))
    clock.now += 0.05
    recorder.after_tool(
        tool("get_upcoming_matches"),
        {"team_id": 1},
        ctx("c2"),
        {"matches": None, "error": {"kind": "unavailable", "message": "down"}},
    )

    first, second = recorder.calls
    assert (first.seq, first.tool_name, first.args, first.duration_ms) == (1, "search_teams", {"query": "IFA"}, 200)
    assert first.result == {"status": "resolved", "team": {"id": 1}}
    assert first.error_kind is None
    assert (second.seq, second.tool_name, second.duration_ms) == (2, "get_upcoming_matches", 50)
    assert second.error_kind == "unavailable"


def test_parallel_calls_are_timed_by_call_id():
    clock = Clock()
    recorder = TurnRecorder(clock=clock)
    recorder.before_tool(tool("search_teams"), {"query": "A"}, ctx("a"))
    clock.now += 1
    recorder.before_tool(tool("search_teams"), {"query": "B"}, ctx("b"))
    clock.now += 1
    recorder.after_tool(tool("search_teams"), {"query": "B"}, ctx("b"), {})
    recorder.after_tool(tool("search_teams"), {"query": "A"}, ctx("a"), {})

    assert [(c.args["query"], c.duration_ms) for c in recorder.calls] == [("B", 1000), ("A", 2000)]


def test_a_call_without_a_start_has_no_duration_and_odd_results_are_wrapped():
    recorder = TurnRecorder(clock=Clock())
    recorder.after_tool(tool("search_teams"), None, SimpleNamespace(), "plain text")

    [call] = recorder.calls
    assert call.duration_ms is None
    assert call.args == {}
    assert call.result == {"value": "plain text"}


def test_error_kinds():
    assert error_kind({"error": {"kind": "not_found"}}) == "not_found"
    assert error_kind({"error": {"message": "x"}}) == "unknown"
    assert error_kind({"error": None}) is None
    assert error_kind({}) is None


def test_big_results_are_stored_as_a_digest():
    small = {"ok": True, "when": "2026-10-03"}
    assert bounded(small) == small

    big = {"rows": ["x" * 100] * (MAX_RESULT_BYTES // 100 + 10)}
    digest = bounded(big)
    assert digest["truncated"] is True
    assert digest["bytes"] > MAX_RESULT_BYTES
    assert len(digest["sha256"]) == 64

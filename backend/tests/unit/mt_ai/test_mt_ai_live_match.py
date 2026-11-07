"""get_live_match (SB-1584): score, clock, goals and cards — players never past "#7 Tom D."."""

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from mt_ai.tools import get_live_match
from mt_ai.tools.live import NOT_TRACKED, player_label

pytestmark = [pytest.mark.unit, pytest.mark.backend]

IFA, VALEO = 102, 100
KICKOFF = datetime(2026, 11, 7, 18, 15, tzinfo=UTC)


def state(**overrides) -> dict:
    """A scraped fixture nobody has kicked off: the default world."""
    row = {
        "match_id": 7,
        "match_status": "scheduled",
        "home_score": 0,
        "away_score": 0,
        "home_penalty_score": None,
        "away_penalty_score": None,
        "kickoff_time": None,
        "halftime_start": None,
        "second_half_start": None,
        "match_end_time": None,
        "half_duration": 40,
        "home_team_id": IFA,
        "home_team_name": "IFA",
        "away_team_id": VALEO,
        "away_team_name": "Valeo FC",
        "age_group_name": "U15",
        "match_type_name": "Flex",
    }
    return row | overrides


class FakeLive:
    def __init__(self, row: dict | None, test_only: bool = False) -> None:
        self.row, self.test_only = row, test_only

    def get_live_match_state(self, match_id: int, include_test: bool = False) -> dict | None:
        if self.row is None or (self.test_only and not include_test):
            return None
        return self.row


class FakeEvents:
    def __init__(self, rows: list[dict] | None) -> None:
        self.rows = rows

    def get_key_events(self, match_id: int) -> list[dict] | None:
        return self.rows


class FakeRoster:
    def __init__(self, players: dict[int, dict]) -> None:
        self.players = players

    def get_player_by_id(self, player_id: int) -> dict | None:
        return self.players.get(player_id)


# Full surnames in the data: the tool must never pass them on.
ROSTER = {
    9: {"jersey_number": 9, "first_name": "Samuel", "last_name": "Kowalczyk"},
    14: {"jersey_number": 14, "first_name": None, "last_name": "Morales"},
    21: {
        "jersey_number": 21,
        "first_name": None,
        "last_name": None,
        "user_profile": {"first_name": "Leo", "last_name": "Fitzgerald", "display_name": "Leo Fitzgerald"},
    },
}


def goal(minute: int, team: int, player_id: int | None = None, name: str | None = None, **kw) -> dict:
    return {
        "event_type": "goal",
        "match_minute": minute,
        "team_id": team,
        "player_id": player_id,
        "player_name": name,
        "message": f"GOAL by {name or 'someone'} Fullsurname",
    } | kw


@pytest.fixture
def deps(make_deps):
    def build(row: dict | None, events: list[dict] | None = None, test_only: bool = False):
        return replace(
            make_deps(),
            live=FakeLive(row, test_only),
            events=FakeEvents([] if events is None else events),
            roster=FakeRoster(ROSTER),
        )

    return build


class TestScoreAndClock:
    def test_second_half_minute_and_score(self, deps, real_viewer):
        row = state(
            match_status="live",
            home_score=2,
            away_score=1,
            kickoff_time="2026-11-07T18:15:00Z",
            halftime_start="2026-11-07T18:56:00Z",
            second_half_start="2026-11-07T19:06:00Z",
        )
        now = datetime(2026, 11, 7, 19, 28, 30, tzinfo=UTC)  # 22.5 min into the second half
        result = get_live_match(deps(row), 7, real_viewer, now=now)

        assert result.error is None
        assert (result.period, result.minute, result.extra_time) == ("second_half", 63, None)
        assert (result.home_score, result.away_score) == (2, 1)
        assert result.home_team.name == "IFA" and result.competition == "Flex"

    def test_stoppage_time_is_extra_time(self, deps, real_viewer):
        row = state(match_status="live", kickoff_time="2026-11-07T18:15:00Z")
        result = get_live_match(deps(row), 7, real_viewer, now=datetime(2026, 11, 7, 18, 57, tzinfo=UTC))

        assert (result.period, result.minute, result.extra_time) == ("first_half", 40, 3)

    def test_halftime_and_full_time(self, deps, real_viewer):
        half = state(match_status="live", kickoff_time="x", halftime_start="2026-11-07T18:56:00Z")
        done = state(match_status="completed", home_score=3, away_score=0)

        assert (
            get_live_match(deps(half), 7, real_viewer).period,
            get_live_match(deps(half), 7, real_viewer).minute,
        ) == (
            "halftime",
            40,
        )
        finished = get_live_match(deps(done), 7, real_viewer)
        assert (finished.period, finished.minute, finished.home_score) == ("full_time", None, 3)

    def test_a_match_not_kicked_off_has_no_score_not_nil_nil(self, deps, real_viewer):
        result = get_live_match(deps(state()), 7, real_viewer)

        assert result.period == "not_started"
        assert (result.home_score, result.away_score) == (None, None)


class TestEvents:
    def test_goals_and_cards_oldest_first_with_teams(self, deps, real_viewer):
        events = [
            goal(12, IFA, 9),
            {"event_type": "yellow_card", "match_minute": 30, "team_id": VALEO, "player_name": "Jo Smith"},
            goal(45, VALEO, name="Max Power", extra_time=2),
        ]
        result = get_live_match(deps(state(match_status="live", kickoff_time="x"), events), 7, real_viewer)

        assert [(e.type, e.minute, e.extra_time, e.team) for e in result.events] == [
            ("goal", 12, None, "IFA"),
            ("yellow_card", 30, None, "Valeo FC"),
            ("goal", 45, 2, "Valeo FC"),
        ]

    def test_full_surnames_in_the_data_never_leave_the_tool(self, deps, real_viewer):
        events = [
            goal(5, IFA, 9, name="Samuel Kowalczyk", assist_player_id=21),
            goal(20, IFA, 14),
            goal(33, VALEO, name="Maximilian Oberhauser"),
        ]
        result = get_live_match(deps(state(match_status="live", kickoff_time="x"), events), 7, real_viewer)

        assert [(e.player, e.assist) for e in result.events] == [
            ("#9 Samuel K.", "#21 Leo F."),
            ("#14", None),
            ("Maximilian O.", None),
        ]
        dumped = result.model_dump_json()
        for surname in ("Kowalczyk", "Morales", "Fitzgerald", "Oberhauser", "Fullsurname"):
            assert surname not in dumped

    def test_chat_is_never_read(self, deps, real_viewer):
        events = [{"event_type": "message", "message": "Go Tom Drake!"}, goal(3, IFA, 9)]
        result = get_live_match(deps(state(match_status="live", kickoff_time="x"), events), 7, real_viewer)

        assert [e.type for e in result.events] == ["goal"]
        assert "Drake" not in result.model_dump_json()

    def test_an_untracked_match_is_score_only_and_says_so(self, deps, real_viewer):
        result = get_live_match(deps(state(match_status="completed", home_score=2, away_score=2)), 7, real_viewer)

        assert result.events == []
        assert result.meta.coverage == NOT_TRACKED
        assert (result.home_score, result.away_score) == (2, 2)

    def test_unreadable_events_are_null_not_empty(self, deps, real_viewer, make_deps):
        d = replace(deps(state(match_status="live", kickoff_time="x")), events=FakeEvents(None))
        result = get_live_match(d, 7, real_viewer)

        assert result.events is None
        assert result.error.kind == "unavailable"


class TestVisibilityAndFailures:
    def test_a_test_match_is_invisible_to_real_viewers(self, deps, real_viewer, test_viewer):
        d = deps(state(), test_only=True)

        assert get_live_match(d, 7, real_viewer).error.kind == "not_found"
        assert get_live_match(d, 7, test_viewer).error is None

    def test_missing_live_sources_are_unavailable(self, make_deps, real_viewer):
        assert get_live_match(make_deps(), 7, real_viewer).error.kind == "unavailable"


class TestPlayerLabel:
    @pytest.mark.parametrize(
        ("player", "recorded", "expected"),
        [
            ({"jersey_number": 7, "first_name": "Tom", "last_name": "Drake"}, None, "#7 Tom D."),
            ({"jersey_number": 7, "first_name": "Tom", "last_name": "D."}, None, "#7 Tom D."),
            ({"jersey_number": 7, "first_name": "Tom", "last_name": None}, None, "#7 Tom"),
            ({"jersey_number": 7, "first_name": "", "last_name": "Drake"}, None, "#7"),
            (None, "#23", "#23"),
            (None, "#23 Tom van der Berg", "#23 Tom B."),
            (None, "Tom", "Tom"),
            (None, None, None),
        ],
    )
    def test_format(self, player, recorded, expected):
        assert player_label(player, recorded) == expected

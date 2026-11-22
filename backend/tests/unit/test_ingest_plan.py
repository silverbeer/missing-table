"""Planning a tournament's teams and aliases, without a database (SB-1763).

The planner is handed each name's verdict — what the resolver ingest uses
said about it — and what MT holds, as plain rows. These pin what it proposes
for a name that failed, and above all what it refuses to decide by itself: a
club with several Academy teams, a name MT has never seen, a placeholder.

The world here is the production shape: a club's Homegrown team carries the
bare club name, and none of these teams has any user data.
"""

from __future__ import annotations

import json

import pytest

from dao.ingest_plan import (
    ALIAS,
    APPROVED,
    CREATE_TEAM,
    NEEDS_REVIEW,
    PROPOSED,
    UNKNOWN_AGE_GROUP,
    Entry,
    PlanInputError,
    Verdict,
    World,
    action_error,
    applicable,
    build_plan,
    is_placeholder,
    parse_brackets_input,
    parse_teams_input,
    plan_id_for,
    read_plan,
)
from dao.team_sides import AMBIGUOUS, MISSING, RESOLVED, UNKNOWN_LEAGUE, WRONG_SIDE

pytestmark = pytest.mark.unit

HOMEGROWN, ACADEMY, FLEX = 1, 2, 290
U15, U16 = 3, 4
NORTHEAST, NEW_ENGLAND, EMPIRE = 10, 20, 30

WRONG = "wrong side: exists as Homegrown"


def _world(teams: list[dict]) -> World:
    return World(
        teams=teams,
        clubs={1: "River FC", 2: "Lake United", 3: "Hill Soccer Academy"},
        leagues={
            HOMEGROWN: {"id": HOMEGROWN, "name": "Homegrown", "parent_league_id": None},
            ACADEMY: {"id": ACADEMY, "name": "Academy", "parent_league_id": None},
            FLEX: {"id": FLEX, "name": "Flex", "parent_league_id": HOMEGROWN},
        },
        divisions=[
            {"id": NORTHEAST, "name": "Northeast", "league_id": HOMEGROWN},
            {"id": NEW_ENGLAND, "name": "New England", "league_id": ACADEMY},
            {"id": EMPIRE, "name": "Empire", "league_id": FLEX},
        ],
        age_groups={U15: "U15", U16: "U16"},
    )


def _team(team_id: int, name: str, club_id: int | None, league_id: int | None, mappings=()) -> dict:
    return {"id": team_id, "name": name, "club_id": club_id, "league_id": league_id, "mappings": list(mappings)}


RIVER = _team(11, "River FC", 1, FLEX, [(U15, HOMEGROWN), (U16, HOMEGROWN)])
RIVER_ACADEMY = _team(12, "River FC Academy", 1, ACADEMY, [(U15, ACADEMY)])
RIVER_WEST = _team(13, "River FC West", 1, ACADEMY, [(U15, ACADEMY)])
LAKE = _team(21, "Lake United", 2, FLEX, [(U15, HOMEGROWN)])
HILL = _team(31, "Hill Soccer Academy", 3, FLEX, [(U15, HOMEGROWN)])


def _plan(entries, verdicts, teams, **kwargs) -> dict:
    by_key = {entry.key: verdict for entry, verdict in zip(entries, verdicts, strict=True)}
    return build_plan(entries, kwargs.pop("matches", []), by_key, _world(teams), **kwargs)


class TestAnAlias:
    def test_the_clubs_one_team_on_the_hinted_side_is_proposed(self):
        entries = [Entry("River FC", "U15", "Academy"), Entry("River FC", "U16", "Academy")]
        wrong = Verdict(WRONG_SIDE, reason=WRONG, candidate_ids=(11,))
        plan = _plan(entries, [wrong, wrong], [RIVER, RIVER_ACADEMY, LAKE])

        (action,) = plan["actions"]
        assert action["type"] == ALIAS
        assert action["status"] == PROPOSED
        assert (action["external_name"], action["league"], action["team_id"]) == ("River FC", "Academy", 12)
        assert action["team_name"] == "River FC Academy"
        assert action["fixes"] == [
            {"name": "River FC", "age_group": "U15", "league": "Academy", "status": WRONG_SIDE},
            {"name": "River FC", "age_group": "U16", "league": "Academy", "status": WRONG_SIDE},
        ]
        assert "River FC Academy" in action["reason"]

    def test_a_club_with_several_academy_teams_is_left_to_a_person(self):
        entries = [Entry("River FC", "U15", "Academy")]
        plan = _plan(
            entries, [Verdict(WRONG_SIDE, reason=WRONG, candidate_ids=(11,))], [RIVER, RIVER_ACADEMY, RIVER_WEST]
        )

        (action,) = plan["actions"]
        assert action["type"] == ALIAS
        assert action["status"] == NEEDS_REVIEW
        assert action["team_id"] is None
        assert [c["team_id"] for c in action["candidates"]] == [12, 13]
        assert action["candidates"][0]["registered_age_groups"] == ["U15"]
        assert "pick one of the candidates" in action["reason"]
        # Unpicked, it cannot be applied even if someone approves it as it stands.
        assert action_error({**action, "status": APPROVED}) == "team_id is not set"

    def test_a_team_in_another_club_is_never_a_sibling(self):
        elsewhere = _team(22, "River FC Academy", 2, ACADEMY, [(U15, ACADEMY)])
        entries = [Entry("River FC", "U15", "Academy")]
        plan = _plan(entries, [Verdict(WRONG_SIDE, reason=WRONG, candidate_ids=(11,))], [RIVER, elsewhere])

        (action,) = plan["actions"]
        assert action["type"] == CREATE_TEAM
        assert action["status"] == NEEDS_REVIEW
        assert "already taken by team 22" in action["reason"]

    def test_an_alias_that_would_move_an_age_group_that_works_needs_review(self):
        entries = [Entry("River FC", "U15", "Academy"), Entry("River FC", "U16", "Academy")]
        verdicts = [Verdict(WRONG_SIDE, reason=WRONG, candidate_ids=(11,)), Verdict(RESOLVED, team_id=11)]
        plan = _plan(entries, verdicts, [RIVER, RIVER_ACADEMY])

        (action,) = plan["actions"]
        assert action["status"] == NEEDS_REVIEW
        assert "already resolves on this side at U16 (team 11)" in action["reason"]


class TestCreatingATeam:
    def test_a_club_only_on_the_other_side_gets_club_academy(self):
        entries = [Entry("Lake United", "U15", "Academy")]
        plan = _plan(entries, [Verdict(WRONG_SIDE, reason=WRONG, candidate_ids=(21,))], [RIVER, LAKE])

        (action,) = plan["actions"]
        assert action["type"] == CREATE_TEAM
        assert action["status"] == PROPOSED
        assert action["team_name"] == "Lake United Academy"
        assert (action["club_id"], action["new_club_name"]) == (2, None)
        assert (action["league"], action["external_name"]) == ("Academy", "Lake United")
        assert action["age_groups"] == ["U15"]
        assert action["placements"] == []

    def test_a_taken_name_needs_review(self):
        taken = _team(99, "lake united academy", None, None)
        entries = [Entry("Lake United", "U15", "Academy")]
        plan = _plan(entries, [Verdict(WRONG_SIDE, reason=WRONG, candidate_ids=(21,))], [LAKE, taken])

        (action,) = plan["actions"]
        assert action["status"] == NEEDS_REVIEW
        assert "already taken by team 99" in action["reason"]

    def test_a_club_already_called_academy_needs_review(self):
        entries = [Entry("Hill Soccer Academy", "U15", "Academy")]
        plan = _plan(entries, [Verdict(WRONG_SIDE, reason=WRONG, candidate_ids=(31,))], [HILL])

        (action,) = plan["actions"]
        assert action["team_name"] == "Hill Soccer Academy Academy"
        assert action["status"] == NEEDS_REVIEW

    def test_a_homegrown_side_team_has_no_convention_and_needs_review(self):
        academy_only = _team(41, "Lake United", 2, ACADEMY, [(U15, ACADEMY)])
        entries = [Entry("Lake United", "U15", "Homegrown")]
        verdict = Verdict(WRONG_SIDE, reason="wrong side: exists as Academy", candidate_ids=(41,))
        plan = _plan(entries, [verdict], [academy_only])

        (action,) = plan["actions"]
        assert action["team_name"] == "Lake United Homegrown"
        assert action["status"] == NEEDS_REVIEW

    def test_an_unknown_name_is_a_new_club_always_for_review_with_near_matches(self):
        asked = []

        def near(name):
            asked.append(name)
            return [{"team_id": 21, "team_name": "Lake United", "club_id": 2}]

        entries = [Entry("Lake Utd", "U15", "Academy")]
        plan = _plan(entries, [Verdict(MISSING)], [LAKE], near_matches=near)

        (action,) = plan["actions"]
        assert action["type"] == CREATE_TEAM
        assert action["status"] == NEEDS_REVIEW
        assert (action["club_id"], action["new_club_name"], action["team_name"]) == (None, "Lake Utd", "Lake Utd")
        assert action["near_matches"] == [{"team_id": 21, "team_name": "Lake United", "club_id": 2}]
        assert asked == ["Lake Utd"]

    def test_a_near_match_is_shown_and_never_becomes_the_action(self):
        entries = [Entry("Lake Utd", "U15", "Academy")]
        near = [{"team_id": 21, "team_name": "Lake United"}]
        plan = _plan(entries, [Verdict(MISSING)], [LAKE], near_matches=lambda name: near)

        assert [action["type"] for action in plan["actions"]] == [CREATE_TEAM]
        assert "team_id" not in plan["actions"][0]

    def test_near_matches_are_only_asked_for_unknown_names(self):
        asked = []
        entries = [Entry("Lake United", "U15", "Academy"), Entry("River FC", "U15", "Homegrown")]
        verdicts = [Verdict(WRONG_SIDE, reason=WRONG, candidate_ids=(21,)), Verdict(RESOLVED, team_id=11)]
        _plan(entries, verdicts, [RIVER, LAKE], near_matches=lambda name: asked.append(name) or [])

        assert asked == []

    def test_an_unknown_name_with_an_existing_club_uses_the_club(self):
        entries = [Entry("river fc", "U15", "Academy")]
        plan = _plan(entries, [Verdict(MISSING)], [])

        (action,) = plan["actions"]
        assert (action["club_id"], action["new_club_name"]) == (1, None)
        assert action["status"] == NEEDS_REVIEW

    def test_an_unhinted_missing_name_rides_on_the_one_team_created_for_it(self):
        entries = [Entry("New Town", "U15", "Academy"), Entry("New Town", "U16", None)]
        plan = _plan(entries, [Verdict(MISSING), Verdict(MISSING)], [])

        (action,) = plan["actions"]
        assert [fix["league"] for fix in action["fixes"]] == ["Academy", None]
        assert plan["report"]["sides"]["no hint"]["missing"]["needs_create"] == 1

    def test_an_unhinted_missing_name_alone_gets_a_team_with_no_league(self):
        plan = _plan([Entry("New Town", "U15", None)], [Verdict(MISSING)], [])

        (action,) = plan["actions"]
        assert action["league"] is None
        assert action["status"] == NEEDS_REVIEW
        assert action["placements"] == []

    def test_a_named_team_registered_nowhere_is_reported_not_duplicated(self):
        nowhere = _team(51, "Lake United", 2, None)
        entries = [Entry("Lake United", "U15", "Academy")]
        reason = "wrong side: team has no league or division registration"
        plan = _plan(entries, [Verdict(WRONG_SIDE, reason=reason, candidate_ids=(51,))], [nowhere])

        assert plan["actions"] == []
        assert plan["report"]["sides"]["Academy"]["missing"]["unknown"] == 1
        assert "register it rather than create another" in plan["report"]["unknown"][0]["reason"]


class TestNoAction:
    @pytest.mark.parametrize("name", ["TBD", "tbd", "East AD One", "West HD Two", " east  ad  one "])
    def test_placeholders(self, name):
        assert is_placeholder(name)
        plan = _plan([Entry(name, "U15", "Academy")], [Verdict(MISSING)], [])

        assert plan["actions"] == []
        assert plan["report"]["sides"]["Academy"]["missing"] == {
            "total": 1,
            "alias_fixable": 0,
            "needs_create": 0,
            "unknown": 1,
        }
        assert plan["report"]["unknown"][0]["reason"] == "placeholder name, not a team"

    @pytest.mark.parametrize("name", ["One FC", "East Side AD", "TBD United", "Eastern AD One FC"])
    def test_real_names_are_not_placeholders(self, name):
        assert not is_placeholder(name)

    def test_an_ambiguous_name_is_listed_with_the_resolvers_reason(self):
        reason = "ambiguous: team 17 is registered as both Academy and Homegrown at this age group"
        plan = _plan([Entry("River FC", "U15", "Homegrown")], [Verdict(AMBIGUOUS, reason=reason)], [RIVER])

        assert plan["actions"] == []
        assert plan["report"]["ambiguous"] == [
            {"name": "River FC", "age_group": "U15", "league": "Homegrown", "reason": reason}
        ]
        assert plan["report"]["sides"]["Homegrown"]["ambiguous"] == 1

    def test_an_unknown_league_or_age_group_is_counted_and_left_alone(self):
        entries = [Entry("River FC", "U15", "Premier"), Entry("River FC", "U99", "Homegrown")]
        plan = _plan(entries, [Verdict(UNKNOWN_LEAGUE), Verdict(UNKNOWN_AGE_GROUP)], [RIVER])

        assert plan["actions"] == []
        assert plan["report"]["sides"]["Premier"]["unknown_league"] == 1
        assert plan["report"]["sides"]["Homegrown"]["unknown_age_group"] == 1


class TestConferences:
    BRACKETS = [
        {"league": "Academy", "conference": "New England", "age_group": "U15", "teams": ["Lake United", "Other"]},
        {"league": "Homegrown", "conference": "Northeast", "age_group": "U16", "teams": ["Lake United"]},
    ]

    def _create(self, brackets, entries=None):
        entries = entries or [Entry("Lake United", "U15", "Academy"), Entry("Lake United", "U16", "Academy")]
        wrong = Verdict(WRONG_SIDE, reason=WRONG, candidate_ids=(21,))
        return _plan(entries, [wrong] * len(entries), [LAKE], brackets=parse_brackets_input(brackets))

    def test_a_team_found_in_a_bracket_is_placed_there_at_that_age_only(self):
        plan = self._create(self.BRACKETS)

        (action,) = plan["actions"]
        # U16 is in a Homegrown bracket: the other side's, so not this team's.
        assert action["placements"] == [{"age_group": "U15", "league": "Academy", "conference": "New England"}]
        assert action["age_groups"] == ["U15", "U16"]
        assert plan["report"]["conferences"] == {
            "placed": [{"league": "Academy", "conference": "New England", "teams": 1, "registrations": 1}],
            "unplaced": 0,
            "unknown": [],
        }

    def test_a_team_in_no_bracket_is_unplaced(self):
        plan = self._create([{**self.BRACKETS[0], "teams": ["Other"]}])

        assert plan["actions"][0]["placements"] == []
        assert plan["report"]["conferences"]["unplaced"] == 1
        assert plan["report"]["conferences"]["placed"] == []

    def test_no_brackets_at_all_leaves_every_created_team_unplaced(self):
        plan = self._create(None)

        assert plan["report"]["conferences"]["unplaced"] == 1

    def test_the_bracket_name_is_matched_exactly_apart_from_case_and_spacing(self):
        placed = self._create([{**self.BRACKETS[0], "teams": ["  lake   UNITED "]}])
        near = self._create([{**self.BRACKETS[0], "teams": ["Lake United FC"]}])

        assert placed["actions"][0]["placements"]
        assert near["actions"][0]["placements"] == []

    def test_a_conference_mt_does_not_have_is_reported_and_not_used(self):
        plan = self._create([{**self.BRACKETS[0], "conference": "Atlantis"}])

        assert plan["actions"][0]["placements"] == []
        assert plan["report"]["conferences"]["unknown"] == [
            {
                "league": "Academy",
                "conference": "Atlantis",
                "reason": "MT has no conference by that name in that league",
            }
        ]

    def test_a_conference_is_looked_up_in_its_own_league(self):
        # "Northeast" is a Homegrown conference; MT has no Academy one by that name.
        plan = self._create([{**self.BRACKETS[0], "conference": "Northeast"}])

        assert plan["actions"][0]["placements"] == []
        assert len(plan["report"]["conferences"]["unknown"]) == 1

    def test_a_league_mt_does_not_have_is_reported(self):
        plan = self._create([{**self.BRACKETS[0], "league": "Premier"}])

        assert plan["report"]["conferences"]["unknown"][0]["reason"] == "MT has no league by that name"

    def test_a_flex_bracket_places_a_homegrown_side_team(self):
        academy_only = _team(41, "Lake United", 2, ACADEMY, [(U15, ACADEMY)])
        entries = [Entry("Lake United", "U15", "Homegrown")]
        verdict = Verdict(WRONG_SIDE, reason="wrong side: exists as Academy", candidate_ids=(41,))
        brackets = parse_brackets_input(
            [{"league": "Flex", "conference": "Empire", "age_group": "U15", "teams": ["Lake United"]}]
        )
        plan = _plan(entries, [verdict], [academy_only], brackets=brackets)

        assert plan["actions"][0]["placements"] == [{"age_group": "U15", "league": "Flex", "conference": "Empire"}]


class TestTheReport:
    def _mixed(self):
        entries = [
            Entry("River FC", "U15", "Homegrown"),
            Entry("River FC", "U15", "Academy"),
            Entry("Lake United", "U15", "Academy"),
            Entry("Lake Utd", "U15", "Academy"),
            Entry("TBD", "U15", "Academy"),
            Entry("River FC", "U16", None),
            Entry("Ghost", "U16", None),
            Entry("Both", "U15", "Homegrown"),
        ]
        verdicts = [
            Verdict(RESOLVED, team_id=11),
            Verdict(WRONG_SIDE, reason=WRONG, candidate_ids=(11,)),
            Verdict(WRONG_SIDE, reason=WRONG, candidate_ids=(21,)),
            Verdict(MISSING),
            Verdict(MISSING),
            Verdict(RESOLVED, team_id=11),
            Verdict(MISSING),
            Verdict(AMBIGUOUS, reason="ambiguous: team ids 7, 9"),
        ]
        e = entries
        matches = [
            {"home": e[0], "away": e[7], "competition": "HD Group Play"},  # ambiguous away: never lands
            {"home": e[1], "away": e[2], "competition": "AD Group Play"},  # lands once both are fixed
            {"home": e[1], "away": e[4], "competition": "AD Showcase"},  # a placeholder: never lands
            {"home": e[5], "away": e[5], "competition": "GA Cup Qualifier"},  # lands now
        ]
        return _plan(entries, verdicts, [RIVER, RIVER_ACADEMY, LAKE], matches=matches)

    def test_each_side_adds_up(self):
        report = self._mixed()["report"]

        assert report["entries"] == 8
        assert set(report["sides"]) == {"Homegrown", "Academy", "no hint"}
        for side in report["sides"].values():
            missing = side["missing"]
            assert missing["total"] == missing["alias_fixable"] + missing["needs_create"] + missing["unknown"]
            assert missing["total"] == side["resolver"]["wrong_side"] + side["resolver"]["missing"]
            assert side["entries"] == (
                side["resolved"]
                + side["ambiguous"]
                + missing["total"]
                + side["unknown_league"]
                + side["unknown_age_group"]
            )
        assert sum(side["entries"] for side in report["sides"].values()) == report["entries"]

    def test_the_split_of_missing(self):
        sides = self._mixed()["report"]["sides"]

        assert sides["Academy"]["missing"] == {"total": 4, "alias_fixable": 1, "needs_create": 2, "unknown": 1}
        assert sides["Academy"]["resolver"] == {"wrong_side": 2, "missing": 2}
        assert sides["Homegrown"]["resolved"] == 1
        assert sides["Homegrown"]["ambiguous"] == 1
        assert sides["no hint"]["missing"] == {"total": 1, "alias_fixable": 0, "needs_create": 1, "unknown": 0}

    def test_matches_that_would_land_now_and_after_the_plan(self):
        assert self._mixed()["report"]["matches"] == {"total": 4, "would_land": 1, "would_land_after_plan": 2}

    def test_input_without_matches_reports_none_rather_than_zero(self):
        plan = _plan([Entry("River FC", "U15", "Homegrown")], [Verdict(RESOLVED, team_id=11)], [RIVER])

        assert plan["report"]["matches"] is None

    def test_actions_are_counted_by_type_and_status_and_numbered(self):
        plan = self._mixed()

        assert plan["report"]["actions"] == {
            ALIAS: {PROPOSED: 1, NEEDS_REVIEW: 0},
            CREATE_TEAM: {PROPOSED: 1, NEEDS_REVIEW: 2},
        }
        assert [action["id"] for action in plan["actions"]] == ["a001", "a002", "a003", "a004"]

    def test_a_fresh_plan_holds_nothing_approved(self):
        assert {action["status"] for action in self._mixed()["actions"]} <= {PROPOSED, NEEDS_REVIEW}


class TestReadingTheTeamsInput:
    def test_scraper_messages_give_distinct_entries_and_matches(self):
        messages = [
            {
                "home_team": "River FC",
                "away_team": "Lake United",
                "age_group": "U15",
                "league": "Academy",
                "competition": "AD Group Play",
                "match_date": "2026-12-02",
                "external_match_id": "m11-75-1",
            },
            {"home_team": "river  fc", "away_team": "Hill SA", "age_group": "U15", "league": "Academy"},
            {"home_team": "River FC", "away_team": "Hill SA", "age_group": "U15", "competition": "Best Of"},
        ]
        entries, matches = parse_teams_input(messages)

        assert [entry.as_dict() for entry in entries] == [
            {"name": "River FC", "age_group": "U15", "league": "Academy"},
            {"name": "Lake United", "age_group": "U15", "league": "Academy"},
            {"name": "Hill SA", "age_group": "U15", "league": "Academy"},
            {"name": "River FC", "age_group": "U15", "league": None},
            {"name": "Hill SA", "age_group": "U15", "league": None},
        ]
        assert len(matches) == 3
        assert matches[1]["home"] is entries[0]
        assert matches[0]["competition"] == "AD Group Play"

    def test_a_plain_list_of_names_has_no_matches(self):
        entries, matches = parse_teams_input(
            [{"name": "River FC", "age_group": "U15", "league": "Academy"}, {"name": "Lake United", "age_group": "U16"}]
        )

        assert [(e.name, e.age_group, e.league) for e in entries] == [
            ("River FC", "U15", "Academy"),
            ("Lake United", "U16", None),
        ]
        assert matches == []

    @pytest.mark.parametrize(
        ("items", "message"),
        [
            ({"teams": []}, "must be a JSON list"),
            (["River FC"], r"teams\[0\]: expected an object"),
            ([{"age_group": "U15"}], r"teams\[0\]: expected 'home_team' and 'away_team', or 'name'"),
            ([{"name": "River FC"}], r"teams\[0\]: 'age_group' is missing"),
            ([{"home_team": "River FC", "age_group": "U15"}], r"teams\[0\]: a team name is missing"),
            ([{"name": 7, "age_group": "U15"}], r"teams\[0\]: 'name' must be text"),
        ],
    )
    def test_input_it_cannot_read_is_refused_with_where(self, items, message):
        with pytest.raises(PlanInputError, match=message):
            parse_teams_input(items)


class TestReadingTheBracketsInput:
    def test_absent_is_no_brackets(self):
        assert parse_brackets_input(None) == []

    def test_names_are_normalised(self):
        rows = parse_brackets_input(
            [{"league": " Academy ", "conference": "New  England", "age_group": "U15", "teams": [" River  FC ", ""]}]
        )

        assert rows == [{"league": "Academy", "conference": "New England", "age_group": "U15", "teams": ["River FC"]}]

    @pytest.mark.parametrize(
        ("items", "message"),
        [
            ({}, "must be a JSON list"),
            ([[]], r"brackets\[0\]: expected an object"),
            ([{"league": "Academy", "age_group": "U15", "teams": []}], r"brackets\[0\]: 'conference' is missing"),
            (
                [{"league": "Academy", "conference": "X", "age_group": "U15", "teams": "River FC"}],
                r"brackets\[0\]: 'teams' must be a list of names",
            ),
        ],
    )
    def test_a_bad_shape_is_refused_with_where(self, items, message):
        with pytest.raises(PlanInputError, match=message):
            parse_brackets_input(items)


class TestThePlanFile:
    def _plan_file(self) -> dict:
        entries = [Entry("River FC", "U15", "Academy"), Entry("Lake United", "U15", "Academy")]
        verdicts = [
            Verdict(WRONG_SIDE, reason=WRONG, candidate_ids=(11,)),
            Verdict(WRONG_SIDE, reason=WRONG, candidate_ids=(21,)),
        ]
        plan = _plan(entries, verdicts, [RIVER, RIVER_ACADEMY, LAKE])
        return {"plan_id": plan_id_for(plan["actions"], "2026-11-22T16:03:01.123456+00:00"), **plan}

    def test_it_survives_a_round_trip_through_json(self):
        plan = self._plan_file()

        assert read_plan(json.loads(json.dumps(plan))) == plan

    def test_the_plan_id_names_when_and_what(self):
        plan = self._plan_file()

        assert plan["plan_id"].startswith("plan-20261122T160301-")
        assert plan_id_for(plan["actions"], "2026-11-22T16:03:01+00:00") == plan["plan_id"]
        assert plan_id_for(plan["actions"][:1], "2026-11-22T16:03:01+00:00") != plan["plan_id"]

    @pytest.mark.parametrize("plan", [[], {"actions": []}, {"plan_id": "p", "actions": {}}, {"plan_id": " "}])
    def test_something_that_is_not_a_plan_is_refused(self, plan):
        with pytest.raises(PlanInputError):
            read_plan(plan)

    def test_only_approved_actions_are_applicable(self):
        actions = self._plan_file()["actions"]
        assert applicable(actions) == []

        actions[1]["status"] = APPROVED
        assert applicable(actions) == [actions[1]]

    @pytest.mark.parametrize("status", [PROPOSED, NEEDS_REVIEW, "Approved", "yes", None, True])
    def test_nothing_but_the_exact_word_is_approval(self, status):
        assert applicable([{"type": ALIAS, "status": status}]) == []

    def test_generated_actions_are_readable(self):
        for action in self._plan_file()["actions"]:
            assert action_error(action) is None

    @pytest.mark.parametrize(
        ("change", "error"),
        [
            ({"type": "merge"}, "unknown action type 'merge'"),
            ({"external_name": " "}, "external_name is missing"),
            ({"team_name": None}, "team_name is missing"),
            ({"club_id": None}, "one of club_id and new_club_name must be set"),
            ({"new_club_name": "Lake"}, "club_id and new_club_name are both set: keep one"),
            ({"club_id": "2"}, "club_id must be a club id or null"),
            ({"placements": [{"age_group": "U15"}]}, "placements must be a list of {age_group, league, conference}"),
            ({"fixes": [{"name": "x"}]}, "fixes must be a list of {name, age_group, league, status}"),
            ({"league": 2}, "league must be a league name or null"),
        ],
    )
    def test_a_hand_edit_that_breaks_an_action_is_named(self, change, error):
        create = self._plan_file()["actions"][1]
        assert create["type"] == CREATE_TEAM

        assert action_error({**create, **change}) == error

    def test_an_alias_needs_a_league_and_a_team(self):
        alias = self._plan_file()["actions"][0]

        assert action_error({**alias, "league": None}) == "an alias needs a league"
        assert action_error({**alias, "team_id": True}) == "team_id is not set"
        assert action_error("alias") == "not an object"


class TestActionsThatClash:
    def test_two_actions_proposing_one_team_name_flag_the_later_one(self):
        south = _team(14, "River FC South", 1, FLEX, [(U15, HOMEGROWN)])
        entries = [Entry("River FC", "U15", "Academy"), Entry("River FC South", "U15", "Academy")]
        verdicts = [
            Verdict(WRONG_SIDE, reason=WRONG, candidate_ids=(11,)),
            Verdict(WRONG_SIDE, reason=WRONG, candidate_ids=(14,)),
        ]
        first, second = _plan(entries, verdicts, [RIVER, south])["actions"]

        assert first["team_name"] == second["team_name"] == "River FC Academy"
        assert first["status"] == PROPOSED
        assert second["status"] == NEEDS_REVIEW
        assert "action a001 proposes the same new team, 'River FC Academy'" in second["reason"]

    def test_two_actions_proposing_one_new_club_flag_the_later_one(self):
        entries = [Entry("New Town", "U15", "Academy"), Entry("New Town", "U15", "Homegrown")]
        first, second = _plan(entries, [Verdict(MISSING), Verdict(MISSING)], [])["actions"]

        assert first["new_club_name"] == second["new_club_name"] == "New Town"
        assert "action a001" not in first["reason"]
        assert "action a001 proposes the same new team, 'New Town'" in second["reason"]
        assert "action a001 proposes the same new club, 'New Town'" in second["reason"]

    def test_the_clash_is_counted_as_needs_review(self):
        south = _team(14, "River FC South", 1, FLEX, [(U15, HOMEGROWN)])
        entries = [Entry("River FC", "U15", "Academy"), Entry("River FC South", "U15", "Academy")]
        wrong = [Verdict(WRONG_SIDE, reason=WRONG, candidate_ids=(team_id,)) for team_id in (11, 14)]

        assert _plan(entries, wrong, [RIVER, south])["report"]["actions"][CREATE_TEAM] == {PROPOSED: 1, NEEDS_REVIEW: 1}


class TestATeamsLeagueIsItsSide:
    def test_a_flex_hint_makes_a_homegrown_team_and_says_so(self):
        academy_only = _team(41, "Lake United", 2, ACADEMY, [(U15, ACADEMY)])
        verdict = Verdict(WRONG_SIDE, reason="wrong side: exists as Academy", candidate_ids=(41,))
        (action,) = _plan([Entry("Lake United", "U15", "Flex")], [verdict], [academy_only])["actions"]

        assert action["league"] == "Homegrown"
        assert action["status"] == NEEDS_REVIEW
        assert "the feed says Flex; the team and its alias are made in Homegrown" in action["reason"]


class TestNamesBesideIds:
    def _actions(self):
        entries = [Entry("River FC", "U15", "Academy"), Entry("Lake United", "U15", "Academy")]
        verdicts = [
            Verdict(WRONG_SIDE, reason=WRONG, candidate_ids=(11,)),
            Verdict(WRONG_SIDE, reason=WRONG, candidate_ids=(21,)),
        ]
        return _plan(entries, verdicts, [RIVER, RIVER_ACADEMY, LAKE])["actions"]

    def test_an_alias_must_name_the_team_its_id_refers_to(self):
        alias, _ = self._actions()

        assert action_error({**alias, "team_name": None}) == (
            "team_name is not set: it must name the team team_id refers to"
        )

    def test_a_create_must_name_the_club_its_id_refers_to(self):
        _, create = self._actions()

        assert action_error({**create, "club_name": " "}) == (
            "club_name is not set: it must name the club club_id refers to"
        )

    def test_fixes_for_another_name_are_refused(self):
        alias, _ = self._actions()
        other = [{"name": "Lake United", "age_group": "U15", "league": "Academy", "status": WRONG_SIDE}]

        assert action_error({**alias, "fixes": other}) == "every entry in fixes must be for external_name"

"""flatten_team_mappings: one team in several divisions at one age group (SB-1468)."""

from dao.team_dao import flatten_team_mappings

U15 = {"id": 3, "name": "U15"}
U16 = {"id": 4, "name": "U16"}


def _div(div_id: int, name: str, league_id: int, league_name: str) -> dict:
    return {
        "id": div_id,
        "name": name,
        "league_id": league_id,
        "leagues": {"id": league_id, "name": league_name, "sport_type": "soccer"},
    }


def _ironbound() -> dict:
    # PostgREST returns embedded rows in no guaranteed order — Flex first here on purpose.
    return {
        "id": 33,
        "league_id": 1,
        "team_mappings": [
            {"age_groups": U16, "divisions": _div(20, "Turnpike", 2, "Flex")},
            {"age_groups": U16, "divisions": _div(21, "Empire", 2, "Flex")},
            {"age_groups": U16, "divisions": _div(5, "Northeast", 1, "Homegrown")},
            {"age_groups": U15, "divisions": _div(5, "Northeast", 1, "Homegrown")},
        ],
    }


def test_age_groups_listed_once_each():
    team = _ironbound()
    flatten_team_mappings(team)
    assert [ag["name"] for ag in team["age_groups"]] == ["U16", "U15"]


def test_every_division_kept_home_league_first():
    team = _ironbound()
    flatten_team_mappings(team)
    names = [d["name"] for d in team["divisions_by_age_group_all"][4]]
    assert names == ["Northeast", "Turnpike", "Empire"]


def test_single_division_view_prefers_home_league():
    team = _ironbound()
    flatten_team_mappings(team)
    assert team["divisions_by_age_group"][4]["name"] == "Northeast"
    assert team["divisions_by_age_group"][4]["league_name"] == "Homegrown"


def test_no_home_league_falls_back_to_lowest_division_id():
    team = _ironbound()
    team["league_id"] = None
    flatten_team_mappings(team)
    assert [d["id"] for d in team["divisions_by_age_group_all"][4]] == [5, 20, 21]


def test_unclaimed_team_with_no_mappings_is_empty_not_missing():
    team = {"id": 1, "team_mappings": []}
    flatten_team_mappings(team)
    assert team["age_groups"] == []
    assert team["divisions_by_age_group"] == {}
    assert team["divisions_by_age_group_all"] == {}


def test_mapping_without_division_still_lists_age_group():
    team = {"id": 1, "team_mappings": [{"age_groups": U15, "divisions": None}]}
    flatten_team_mappings(team)
    assert team["age_groups"] == [U15]
    assert 3 not in team["divisions_by_age_group"]

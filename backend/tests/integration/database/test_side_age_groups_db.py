"""A playing-up side finds its match under its own age group (SB-1444).

Against the local database: IFA U15 vs a club fielding its U16 side. The match
is U15; the away side is U16. Each team's match list at its own age group must
include it, and the away team's list at the match's age group must not — that
squad did not play.
"""

import uuid

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.database]


@pytest.fixture
def playing_up_match(enhanced_dao):
    client = enhanced_dao.client
    teams = client.table("teams").select("id").order("id").limit(2).execute().data
    ages = {a["name"]: a["id"] for a in client.table("age_groups").select("id,name").execute().data}
    season = client.table("seasons").select("id").order("id", desc=True).limit(1).execute().data
    friendly = client.table("match_types").select("id").eq("name", "Friendly").execute().data
    if len(teams) < 2 or not {"U15", "U16"} <= ages.keys() or not season or not friendly:
        pytest.skip("local DB lacks teams, U15/U16, a season or the Friendly type")

    home, away = teams[0]["id"], teams[1]["id"]
    external_id = f"sb1444-{uuid.uuid4().hex[:12]}"
    assert enhanced_dao.add_match(
        home_team_id=home,
        away_team_id=away,
        match_date="2099-01-15",
        home_score=0,
        away_score=0,
        season_id=season[0]["id"],
        age_group_id=ages["U15"],
        match_type_id=friendly[0]["id"],
        external_match_id=external_id,
        away_age_group_id=ages["U16"],
        home_age_group_id=ages["U15"],  # same as the match: must store NULL
    )
    row = client.table("matches").select("*").eq("match_id", external_id).execute().data[0]
    yield {"row": row, "home": home, "away": away, "u15": ages["U15"], "u16": ages["U16"]}
    client.table("matches").delete().eq("id", row["id"]).execute()


# The two lowest-id teams may belong to a test club (SB-591); these tests are
# about age groups, not the test partition, so every read includes test rows.
def _ids(matches):
    return {m["id"] for m in matches}


def test_only_the_playing_up_side_is_stored(playing_up_match):
    row = playing_up_match["row"]
    assert row["home_age_group_id"] is None
    assert row["away_age_group_id"] == playing_up_match["u16"]


def test_each_team_finds_it_under_its_own_age_group(enhanced_dao, playing_up_match):
    m = playing_up_match
    match_id = m["row"]["id"]
    assert match_id in _ids(enhanced_dao.get_matches_by_team(m["home"], age_group_id=m["u15"], include_test=True))
    assert match_id in _ids(enhanced_dao.get_matches_by_team(m["away"], age_group_id=m["u16"], include_test=True))
    assert match_id in _ids(enhanced_dao.get_all_matches(team_id=m["away"], age_group_id=m["u16"], include_test=True))


def test_the_away_teams_own_age_group_squad_did_not_play(enhanced_dao, playing_up_match):
    m = playing_up_match
    match_id = m["row"]["id"]
    assert match_id not in _ids(enhanced_dao.get_matches_by_team(m["away"], age_group_id=m["u15"], include_test=True))


def test_the_match_still_lists_under_its_own_age_group(enhanced_dao, playing_up_match):
    m = playing_up_match
    assert m["row"]["id"] in _ids(
        enhanced_dao.get_all_matches(age_group_id=m["u15"], start_date="2099-01-01", include_test=True)
    )


def test_update_without_side_fields_keeps_the_playing_up_side(enhanced_dao, playing_up_match):
    row = playing_up_match["row"]
    enhanced_dao.update_match(
        match_id=row["id"],
        home_team_id=row["home_team_id"],
        away_team_id=row["away_team_id"],
        match_date=row["match_date"],
        home_score=1,
        away_score=0,
        season_id=row["season_id"],
        age_group_id=row["age_group_id"],
        match_type_id=row["match_type_id"],
    )
    after = enhanced_dao.client.table("matches").select("away_age_group_id").eq("id", row["id"]).execute().data[0]
    assert after["away_age_group_id"] == playing_up_match["u16"]

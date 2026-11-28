"""merge_team / merge_club against local Supabase (SB-1822).

Every row is built here under a unique tag and removed afterwards; nothing that
already exists in the (prod-mirror) local database is touched. The default
fixture is the common case: teams with scraped matches and no user data.

Requires local Supabase with migration 20261128120000. Skips cleanly otherwise.
"""

from __future__ import annotations

import os
import uuid
from datetime import date

import psycopg2
import pytest

pytestmark = [pytest.mark.integration, pytest.mark.backend, pytest.mark.database]

DAY = date(2020, 3, 1).isoformat()
OTHER_DAY = date(2020, 3, 8).isoformat()


def _admin():
    from supabase import create_client

    url = os.getenv("SUPABASE_URL", "http://127.0.0.1:55321")
    if not ("127.0.0.1" in url or "localhost" in url):
        pytest.skip(f"Refusing to run destructive test against non-local Supabase: {url}")
    key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not key:
        pytest.skip("SUPABASE_SERVICE_KEY not set")
    return create_client(url, key)


def _local_database_url() -> str:
    """Local Postgres for the checks PostgREST cannot express (DDL, locks)."""
    if url := os.getenv("DATABASE_URL"):
        return url
    user = os.getenv("LOCAL_PG_USER", "postgres")
    password = os.getenv("LOCAL_PG_PASSWORD", "postgres")
    host = os.getenv("LOCAL_PG_HOST", "127.0.0.1")
    port = os.getenv("LOCAL_PG_PORT", "55322")
    return f"postgresql://{user}:{password}@{host}:{port}/postgres"


def _pg():
    try:
        return psycopg2.connect(_local_database_url(), connect_timeout=5)
    except psycopg2.OperationalError as exc:  # pragma: no cover - env dependent
        pytest.skip(f"local Postgres not reachable: {exc}")


def _first_id(admin, table):
    rows = admin.table(table).select("id").order("id").limit(1).execute().data
    if not rows:
        pytest.skip(f"No reference rows in {table}; seed the local DB first")
    return rows[0]["id"]


class World:
    """Two duplicate teams (source, target) in two clubs, plus a third opponent."""

    def __init__(self, admin):
        self.admin = admin
        self.tag = uuid.uuid4().hex[:8]
        self.club_ids: list[int] = []
        self.team_ids: list[int] = []
        self.match_ids: list[int] = []
        self.player_ids: list[int] = []
        self.alias_names: list[str] = []
        self.user_ids: list[str] = []
        self.season_id = _first_id(admin, "seasons")
        self.age_group_id = _first_id(admin, "age_groups")
        self.match_type_id = _first_id(admin, "match_types")

    # -- builders ---------------------------------------------------------
    def club(self, label, **extra):
        row = {"name": f"ZZ Merge Club {label} {self.tag}", "is_test": False, **extra}
        cid = self.admin.table("clubs").insert(row).execute().data[0]["id"]
        self.club_ids.append(cid)
        return cid

    def team(self, label, club_id):
        name = f"ZZ Merge {label} {self.tag}"
        tid = self.admin.table("teams").insert({"name": name, "club_id": club_id}).execute().data[0]["id"]
        self.team_ids.append(tid)
        return tid, name

    def match(self, home, away, day=DAY, **extra):
        row = {
            "match_date": day,
            "home_team_id": home,
            "away_team_id": away,
            "season_id": self.season_id,
            "age_group_id": self.age_group_id,
            "match_type_id": self.match_type_id,
            "match_status": "scheduled",
            **extra,
        }
        mid = self.admin.table("matches").insert(row).execute().data[0]["id"]
        self.match_ids.append(mid)
        return mid

    def player(self, team_id, jersey):
        row = {
            "team_id": team_id,
            "season_id": self.season_id,
            "age_group_id": self.age_group_id,
            "jersey_number": jersey,
            "first_name": "ZZ",
            "last_name": self.tag,
            "is_active": True,
        }
        pid = self.admin.table("players").insert(row).execute().data[0]["id"]
        self.player_ids.append(pid)
        return pid

    def user(self, **profile):
        email = f"zz-merge-{uuid.uuid4().hex[:8]}@missingtable.local"
        uid = self.admin.auth.admin.create_user(
            {"email": email, "password": uuid.uuid4().hex, "email_confirm": True}
        ).user.id
        self.user_ids.append(uid)
        self.admin.table("user_profiles").upsert({"id": uid, "email": email, "role": "team-fan", **profile}).execute()
        return uid

    def team_channel(self, team_id, destination):
        row = {
            "scope_type": "team",
            "team_id": team_id,
            "age_group_id": self.age_group_id,
            "platform": "telegram",
            "destination": destination,
        }
        return self.admin.table("notification_channels").insert(row).execute().data[0]["id"]

    # -- observation ------------------------------------------------------
    def rpc(self, fn, src, tgt, dry_run):
        return self.admin.rpc(fn, {"p_from": src, "p_into": tgt, "p_dry_run": dry_run}).execute().data

    def exists(self, table, row_id):
        return bool(self.admin.table(table).select("id").eq("id", row_id).execute().data)

    def snapshot(self):
        """Everything a merge could change among this world's rows."""
        a = self.admin
        ids = self.team_ids
        matches = a.table("matches").select("id, home_team_id, away_team_id").in_("id", self.match_ids).execute().data
        return {
            "teams": sorted(r["id"] for r in a.table("teams").select("id").in_("id", ids).execute().data),
            "clubs": sorted(r["id"] for r in a.table("clubs").select("id").in_("id", self.club_ids).execute().data),
            "matches": sorted((m["id"], m["home_team_id"], m["away_team_id"]) for m in matches),
            "aliases": a.table("team_aliases").select("id").in_("team_id", ids).execute().data
            and sorted(r["id"] for r in a.table("team_aliases").select("id").in_("team_id", ids).execute().data),
            "players": sorted(
                (r["id"], r["team_id"])
                for r in a.table("players").select("id, team_id").in_("id", self.player_ids).execute().data
            )
            if self.player_ids
            else [],
        }

    def cleanup(self):
        a = self.admin
        failures = []

        def step(fn):
            try:
                fn()
            except Exception as exc:  # keep going, report after
                failures.append(repr(exc))

        if self.match_ids:
            step(lambda: a.table("matches").delete().in_("id", self.match_ids).execute())
        # Matches the merge itself moved still point at ids we know; sweep by team too.
        for tid in self.team_ids:
            step(lambda tid=tid: a.table("matches").delete().eq("home_team_id", tid).execute())
            step(lambda tid=tid: a.table("matches").delete().eq("away_team_id", tid).execute())
        if self.player_ids:
            step(lambda: a.table("players").delete().in_("id", self.player_ids).execute())
        for tid in self.team_ids:
            step(lambda tid=tid: a.table("team_aliases").delete().eq("team_id", tid).execute())
        for name in self.alias_names:
            step(lambda name=name: a.table("team_aliases").delete().ilike("external_name", name).execute())
        for uid in self.user_ids:
            step(lambda uid=uid: a.table("user_profiles").delete().eq("id", uid).execute())
            step(lambda uid=uid: a.auth.admin.delete_user(uid))
        for tid in self.team_ids:
            step(lambda tid=tid: a.table("teams").delete().eq("id", tid).execute())
        for cid in self.club_ids:
            step(lambda cid=cid: a.table("clubs").delete().eq("id", cid).execute())
        if failures:
            raise RuntimeError("merge test cleanup left rows behind: " + "; ".join(failures))


@pytest.fixture
def world():
    admin = _admin()
    try:
        admin.rpc("merge_team", {"p_from": 0, "p_into": 0, "p_dry_run": True}).execute()
    except Exception as exc:
        msg = str(exc)
        if "two different" not in msg:
            pytest.skip(f"merge_team not available on local Supabase: {msg[:120]}")
    w = World(admin)
    try:
        yield w
    finally:
        w.cleanup()


@pytest.fixture
def duplicate_teams(world):
    """src (club A) and tgt (club B), each with one scraped match against `opp`, no user data."""
    club_a, club_b = world.club("A"), world.club("B")
    src, src_name = world.team("Dup", club_a)
    tgt, tgt_name = world.team("Canon", club_b)
    opp, _ = world.team("Opp", club_b)
    world.alias_names.append(src_name)
    world.src, world.tgt, world.opp = src, tgt, opp
    world.src_name, world.tgt_name = src_name, tgt_name
    world.src_match = world.match(src, opp, day=DAY)
    world.tgt_match = world.match(tgt, opp, day=OTHER_DAY)
    return world


def _error_text(excinfo):
    return str(excinfo.value).lower()


def _error_code(excinfo):
    return getattr(excinfo.value, "code", None)


def _kinds(result):
    return [b["kind"] for b in result["blockers"]]


# ---------------------------------------------------------------------------
# merge_team
# ---------------------------------------------------------------------------
class TestMergeTeam:
    def test_dry_run_changes_nothing_and_counts_match_the_real_run(self, duplicate_teams):
        w = duplicate_teams
        before = w.snapshot()

        dry = w.rpc("merge_team", w.src, w.tgt, True)

        assert dry["dry_run"] is True
        assert dry["blockers"] == []
        assert dry["complete"] is True
        assert w.snapshot() == before

        real = w.rpc("merge_team", w.src, w.tgt, False)
        assert real["dry_run"] is False
        assert real["tables"] == dry["tables"]
        assert real["alias"] == dry["alias"]

    def test_clean_merge_moves_matches_writes_alias_deletes_source(self, duplicate_teams):
        w = duplicate_teams

        result = w.rpc("merge_team", w.src, w.tgt, False)

        assert result["tables"]["matches"] == {"moved": 1, "dropped": 0}
        assert result["alias"] == "added"
        assert not w.exists("teams", w.src)
        moved = w.admin.table("matches").select("home_team_id").eq("id", w.src_match).execute().data[0]
        assert moved["home_team_id"] == w.tgt
        alias = w.admin.table("team_aliases").select("team_id, kind").ilike("external_name", w.src_name).execute().data
        assert alias == [{"team_id": w.tgt, "kind": "former_name"}]

    def test_alias_of_the_old_name_on_another_team_is_a_blocker(self, duplicate_teams):
        w = duplicate_teams
        w.admin.table("team_aliases").insert(
            {"team_id": w.opp, "league_id": None, "external_name": w.src_name, "kind": "feed_variant"}
        ).execute()

        dry = w.rpc("merge_team", w.src, w.tgt, True)

        assert _kinds(dry) == ["alias_conflict"]
        with pytest.raises(Exception) as exc:
            w.rpc("merge_team", w.src, w.tgt, False)
        assert _error_code(exc) == "MTBLK"
        rows = w.admin.table("team_aliases").select("team_id, kind").ilike("external_name", w.src_name).execute().data
        assert rows == [{"team_id": w.opp, "kind": "feed_variant"}]
        assert w.exists("teams", w.src)

    def test_alias_of_the_old_name_on_the_source_follows_it_and_counts_as_existing(self, duplicate_teams):
        w = duplicate_teams
        w.admin.table("team_aliases").insert(
            {"team_id": w.src, "league_id": None, "external_name": w.src_name, "kind": "feed_variant"}
        ).execute()

        result = w.rpc("merge_team", w.src, w.tgt, False)

        assert result["alias"] == "exists"
        rows = w.admin.table("team_aliases").select("team_id, kind").ilike("external_name", w.src_name).execute().data
        assert rows == [{"team_id": w.tgt, "kind": "feed_variant"}]

    def test_league_scoped_alias_elsewhere_does_not_stop_the_former_name(self, duplicate_teams):
        w = duplicate_teams
        league_id = _first_id(w.admin, "leagues")
        w.admin.table("team_aliases").insert(
            {"team_id": w.opp, "league_id": league_id, "external_name": w.src_name, "kind": "feed_variant"}
        ).execute()

        result = w.rpc("merge_team", w.src, w.tgt, False)

        assert result["alias"] == "added"
        rows = (
            w.admin.table("team_aliases")
            .select("team_id, league_id")
            .ilike("external_name", w.src_name)
            .order("team_id")
            .execute()
            .data
        )
        assert sorted((r["team_id"], r["league_id"]) for r in rows) == sorted([(w.opp, league_id), (w.tgt, None)])

    def test_duplicate_fixture_without_user_data_is_dropped(self, duplicate_teams):
        w = duplicate_teams
        # The target already has the same fixture; the source copy is a scraped
        # row with no score, events or lineups.
        w.match(w.tgt, w.opp, day=DAY)

        dry = w.rpc("merge_team", w.src, w.tgt, True)
        assert dry["blockers"] == []
        assert dry["tables"]["matches"] == {"moved": 0, "dropped": 1}

        w.rpc("merge_team", w.src, w.tgt, False)
        assert not w.exists("matches", w.src_match)

    def test_duplicate_fixture_with_matching_score_and_no_data_is_dropped(self, duplicate_teams):
        w = duplicate_teams
        w.admin.table("matches").update({"home_score": 2, "away_score": 1}).eq("id", w.src_match).execute()
        w.match(w.tgt, w.opp, day=DAY, home_score=2, away_score=1)

        assert w.rpc("merge_team", w.src, w.tgt, True)["blockers"] == []

    def test_duplicate_fixture_with_differing_score_is_a_blocker(self, duplicate_teams):
        w = duplicate_teams
        w.admin.table("matches").update({"home_score": 3, "away_score": 0}).eq("id", w.src_match).execute()
        w.match(w.tgt, w.opp, day=DAY, home_score=1, away_score=0)

        dry = w.rpc("merge_team", w.src, w.tgt, True)

        assert [b["kind"] for b in dry["blockers"]] == ["duplicate_fixture_has_data"]
        assert dry["blockers"][0]["match_id"] == w.src_match

    def test_duplicate_fixture_with_a_match_event_is_a_blocker(self, duplicate_teams):
        w = duplicate_teams
        w.match(w.tgt, w.opp, day=DAY)
        w.admin.table("match_events").insert(
            {"match_id": w.src_match, "event_type": "goal", "team_id": w.src, "message": "ZZ goal"}
        ).execute()

        dry = w.rpc("merge_team", w.src, w.tgt, True)
        assert [b["kind"] for b in dry["blockers"]] == ["duplicate_fixture_has_data"]

        before = w.snapshot()
        with pytest.raises(Exception) as exc:
            w.rpc("merge_team", w.src, w.tgt, False)
        assert "blocker" in _error_text(exc)
        assert _error_code(exc) == "MTBLK"
        assert w.snapshot() == before
        assert w.exists("teams", w.src)

    def test_match_between_the_two_teams_is_a_blocker(self, duplicate_teams):
        w = duplicate_teams
        between = w.match(w.src, w.tgt, day="2020-04-01")

        dry = w.rpc("merge_team", w.src, w.tgt, True)

        assert any(b["kind"] == "self_match" and b["match_id"] == between for b in dry["blockers"])
        with pytest.raises(Exception) as exc:
            w.rpc("merge_team", w.src, w.tgt, False)
        assert "blocker" in _error_text(exc)

    def test_active_jersey_collision_is_a_blocker_but_distinct_jerseys_merge(self, duplicate_teams):
        w = duplicate_teams
        w.player(w.src, 7)
        w.player(w.tgt, 7)

        dry = w.rpc("merge_team", w.src, w.tgt, True)
        assert [b["kind"] for b in dry["blockers"]] == ["jersey_conflict"]

    def test_roster_without_collision_moves(self, duplicate_teams):
        w = duplicate_teams
        pid = w.player(w.src, 7)
        w.player(w.tgt, 8)

        result = w.rpc("merge_team", w.src, w.tgt, False)

        assert result["tables"]["players"]["moved"] == 1
        row = w.admin.table("players").select("team_id").eq("id", pid).execute().data[0]
        assert row["team_id"] == w.tgt

    def test_team_with_no_user_data_has_zero_counts_not_blockers(self, duplicate_teams):
        w = duplicate_teams
        dry = w.rpc("merge_team", w.src, w.tgt, True)
        assert dry["blockers"] == []
        assert dry["tables"]["players"] == {"moved": 0, "dropped": 0}
        assert dry["tables"]["match_events"] == {"moved": 0, "dropped": 0}

    def test_same_id_is_refused(self, duplicate_teams):
        w = duplicate_teams
        with pytest.raises(Exception) as exc:
            w.rpc("merge_team", w.src, w.src, True)
        assert "two different" in _error_text(exc)
        assert _error_code(exc) == "MTSAM"

    def test_missing_source_or_target_is_refused(self, duplicate_teams):
        w = duplicate_teams
        for src, tgt in ((2_000_000_000, w.tgt), (w.src, 2_000_000_000)):
            with pytest.raises(Exception) as exc:
                w.rpc("merge_team", src, tgt, True)
            assert "does not exist" in _error_text(exc)
            assert _error_code(exc) == "MTNF1"

    def test_null_dry_run_is_a_dry_run(self, duplicate_teams):
        w = duplicate_teams
        result = w.rpc("merge_team", w.src, w.tgt, None)
        assert result["dry_run"] is True
        assert w.exists("teams", w.src)

    def test_dry_run_that_trips_a_constraint_reports_a_code_not_a_message(self, duplicate_teams):
        w = duplicate_teams
        w.match(w.src, w.tgt, day="2020-04-01")

        dry = w.rpc("merge_team", w.src, w.tgt, True)

        assert dry["complete"] is False
        assert dry["error"] == {"sqlstate": "23514", "table": "matches", "constraint": "matches_check"}

    # -- duplicate fixtures: same key, different fixture --------------------
    @pytest.mark.parametrize(
        ("src_extra", "tgt_extra"),
        [
            ({"match_id": "ZZ-A"}, {"match_id": "ZZ-B"}),
            ({"tournament_round": "Group"}, {"tournament_round": "Final"}),
            ({"tournament_round": "Group"}, {}),
        ],
        ids=["external_match_id", "round", "round_source_only"],
    )
    def test_same_day_distinct_fixture_is_a_collision_blocker(self, duplicate_teams, src_extra, tgt_extra):
        w = duplicate_teams
        src_extra = {k: (f"{v}-{w.tag}" if k == "match_id" else v) for k, v in src_extra.items()}
        tgt_extra = {k: (f"{v}-{w.tag}" if k == "match_id" else v) for k, v in tgt_extra.items()}
        w.admin.table("matches").update(src_extra).eq("id", w.src_match).execute()
        tgt_dup = w.match(w.tgt, w.opp, day=DAY, **tgt_extra)

        dry = w.rpc("merge_team", w.src, w.tgt, True)

        assert _kinds(dry) == ["fixture_collision"]
        assert dry["blockers"][0]["match_id"] == w.src_match
        assert dry["blockers"][0]["duplicate_of"] == tgt_dup

    def test_one_side_external_id_is_still_the_same_fixture(self, duplicate_teams):
        w = duplicate_teams
        w.admin.table("matches").update({"match_id": f"ZZ-ONLY-{w.tag}"}).eq("id", w.src_match).execute()
        w.match(w.tgt, w.opp, day=DAY)

        dry = w.rpc("merge_team", w.src, w.tgt, True)

        assert dry["blockers"] == []
        assert dry["tables"]["matches"] == {"moved": 0, "dropped": 1}

    def test_dropped_copy_hands_its_external_id_to_the_target(self, duplicate_teams):
        w = duplicate_teams
        ext = f"ZZ-EXT-{w.tag}"
        w.admin.table("matches").update({"match_id": ext}).eq("id", w.src_match).execute()
        tgt_dup = w.match(w.tgt, w.opp, day=DAY)

        result = w.rpc("merge_team", w.src, w.tgt, False)

        assert result["tables"]["matches.match_id"] == {"moved": 1, "dropped": 0}
        assert not w.exists("matches", w.src_match)
        assert w.admin.table("matches").select("match_id").eq("id", tgt_dup).execute().data[0]["match_id"] == ext

    def test_external_id_with_two_possible_targets_is_a_blocker(self, duplicate_teams):
        w = duplicate_teams
        # division_id NULL: unique_manual_match lets the target hold the key twice.
        w.admin.table("matches").update({"match_id": f"ZZ-EXT-{w.tag}"}).eq("id", w.src_match).execute()
        w.match(w.tgt, w.opp, day=DAY)
        w.match(w.tgt, w.opp, day=DAY)

        dry = w.rpc("merge_team", w.src, w.tgt, True)

        assert set(_kinds(dry)) == {"external_id_conflict"}
        with pytest.raises(Exception) as exc:
            w.rpc("merge_team", w.src, w.tgt, False)
        assert _error_code(exc) == "MTBLK"
        assert w.exists("matches", w.src_match)

    def test_duplicate_fixture_with_a_notification_thread_is_a_blocker(self, duplicate_teams):
        w = duplicate_teams
        w.match(w.tgt, w.opp, day=DAY)
        channel = w.team_channel(w.opp, f"zz-thread-{w.tag}")
        w.admin.table("notification_threads").insert(
            {"channel_id": channel, "match_id": w.src_match, "thread_name": "ZZ thread"}
        ).execute()

        assert _kinds(w.rpc("merge_team", w.src, w.tgt, True)) == ["duplicate_fixture_has_data"]

    # -- duplicate fixtures: source copy carries something -------------------
    @pytest.mark.parametrize(
        ("src_extra", "tgt_extra"),
        [
            ({"score_locked": True}, {}),
            ({"photo_url": "https://example.test/p.jpg"}, {}),
            ({"photo_key": "zz/p.jpg"}, {}),
            ({"match_status": "completed"}, {"match_status": "scheduled"}),
            (
                {"home_score": 1, "away_score": 1, "home_penalty_score": 4, "away_penalty_score": 3},
                {"home_score": 1, "away_score": 1},
            ),
            (
                {"home_score": 1, "away_score": 1, "home_penalty_score": 4, "away_penalty_score": 3},
                {"home_score": 1, "away_score": 1, "home_penalty_score": 3, "away_penalty_score": 4},
            ),
        ],
        ids=["score_locked", "photo_url", "photo_key", "status", "penalties_source_only", "penalties_differ"],
    )
    def test_duplicate_fixture_carrying_more_than_the_target_is_a_blocker(self, duplicate_teams, src_extra, tgt_extra):
        w = duplicate_teams
        w.admin.table("matches").update(src_extra).eq("id", w.src_match).execute()
        w.match(w.tgt, w.opp, day=DAY, **tgt_extra)

        dry = w.rpc("merge_team", w.src, w.tgt, True)

        assert _kinds(dry) == ["duplicate_fixture_has_data"]

    # -- the target fills its gaps from the source ---------------------------
    def test_target_without_club_or_city_takes_the_sources(self, world):
        club = world.club("Only")
        src, _ = world.team("Dup", club)
        tgt, _ = world.team("Canon", None)
        world.admin.table("teams").update({"city": "ZZ Town"}).eq("id", src).execute()

        result = world.rpc("merge_team", src, tgt, False)

        assert sorted(result["copied"]) == ["city", "club_id"]
        row = world.admin.table("teams").select("club_id, city").eq("id", tgt).execute().data[0]
        assert row == {"club_id": club, "city": "ZZ Town"}

    def test_target_club_and_city_are_never_overwritten(self, duplicate_teams):
        w = duplicate_teams
        w.admin.table("teams").update({"city": "Src City"}).eq("id", w.src).execute()
        w.admin.table("teams").update({"city": "Tgt City"}).eq("id", w.tgt).execute()
        tgt_club = w.admin.table("teams").select("club_id").eq("id", w.tgt).execute().data[0]["club_id"]

        result = w.rpc("merge_team", w.src, w.tgt, False)

        assert result["copied"] == []
        row = w.admin.table("teams").select("club_id, city").eq("id", w.tgt).execute().data[0]
        assert row == {"club_id": tgt_club, "city": "Tgt City"}

    def test_moved_members_follow_the_target_club(self, duplicate_teams):
        w = duplicate_teams
        src_club, tgt_club = w.club_ids[0], w.club_ids[1]
        uid = w.user(team_id=w.src, club_id=src_club)

        result = w.rpc("merge_team", w.src, w.tgt, False)

        assert result["tables"]["user_profiles.club_id"]["moved"] == 1
        row = w.admin.table("user_profiles").select("team_id, club_id").eq("id", uid).execute().data[0]
        assert row == {"team_id": w.tgt, "club_id": tgt_club}

    # -- collisions that are blockers, or merged -----------------------------
    def test_notification_channel_on_both_teams_is_a_blocker(self, duplicate_teams):
        w = duplicate_teams
        dest = f"zz-{w.tag}"
        w.team_channel(w.src, dest)
        w.team_channel(w.tgt, dest)

        dry = w.rpc("merge_team", w.src, w.tgt, True)

        assert _kinds(dry) == ["channel_conflict"]

    def test_distinct_notification_channel_moves(self, duplicate_teams):
        w = duplicate_teams
        cid = w.team_channel(w.src, f"zz-src-{w.tag}")
        w.team_channel(w.tgt, f"zz-tgt-{w.tag}")

        result = w.rpc("merge_team", w.src, w.tgt, False)

        assert result["tables"]["notification_channels"] == {"moved": 1, "dropped": 0}
        assert (
            w.admin.table("notification_channels").select("team_id").eq("id", cid).execute().data[0]["team_id"] == w.tgt
        )

    def test_history_collision_keeps_target_row_and_current_flag(self, duplicate_teams):
        w = duplicate_teams
        uid = w.user()
        base = {"player_id": uid, "season_id": w.season_id}
        w.admin.table("player_team_history").insert({**base, "team_id": w.src, "is_current": True}).execute()
        tgt_row = (
            w.admin.table("player_team_history").insert({**base, "team_id": w.tgt, "is_current": False}).execute()
        ).data[0]["id"]

        result = w.rpc("merge_team", w.src, w.tgt, False)

        assert result["tables"]["player_team_history"] == {"moved": 0, "dropped": 1}
        rows = (
            w.admin.table("player_team_history").select("id, team_id, is_current").eq("player_id", uid).execute().data
        )
        assert rows == [{"id": tgt_row, "team_id": w.tgt, "is_current": True}]


# ---------------------------------------------------------------------------
# merge_club
# ---------------------------------------------------------------------------
@pytest.fixture
def duplicate_clubs(world):
    world.club_src = world.club("Dup", logo_url="https://example.test/dup.png", city="ZZ City")
    world.club_tgt = world.club("Canon", logo_url="https://example.test/canon.png")
    world.team_src, _ = world.team("ClubDupTeam", world.club_src)
    world.team_tgt, _ = world.team("ClubCanonTeam", world.club_tgt)
    return world


class TestMergeClub:
    def test_dry_run_changes_nothing(self, duplicate_clubs):
        w = duplicate_clubs
        before = w.admin.table("teams").select("id, club_id").eq("id", w.team_src).execute().data

        dry = w.rpc("merge_club", w.club_src, w.club_tgt, True)

        assert dry["dry_run"] is True
        assert dry["blockers"] == []
        assert w.exists("clubs", w.club_src)
        assert w.admin.table("teams").select("id, club_id").eq("id", w.team_src).execute().data == before

        real = w.rpc("merge_club", w.club_src, w.club_tgt, False)
        assert real["tables"] == dry["tables"]
        assert real["copied"] == dry["copied"]

    def test_moves_teams_keeps_target_logo_deletes_source(self, duplicate_clubs):
        w = duplicate_clubs

        result = w.rpc("merge_club", w.club_src, w.club_tgt, False)

        assert result["tables"]["teams"] == {"moved": 1, "dropped": 0}
        assert "logo_url" not in result["copied"]
        assert not w.exists("clubs", w.club_src)
        assert w.admin.table("teams").select("club_id").eq("id", w.team_src).execute().data[0]["club_id"] == w.club_tgt
        club = w.admin.table("clubs").select("logo_url, city").eq("id", w.club_tgt).execute().data[0]
        assert club["logo_url"] == "https://example.test/canon.png"
        assert club["city"] == "ZZ City"  # target had none, source's fills it
        assert "city" in result["copied"]

    def test_copies_logo_when_target_has_none(self, world):
        src = world.club("Dup", logo_url="https://example.test/dup.png")
        tgt = world.club("Canon")  # logo_url null: never provided
        world.team("T", src)

        result = world.rpc("merge_club", src, tgt, False)

        assert "logo_url" in result["copied"]
        row = world.admin.table("clubs").select("logo_url").eq("id", tgt).execute().data[0]
        assert row["logo_url"] == "https://example.test/dup.png"

    def test_blank_target_logo_counts_as_none(self, world):
        src = world.club("Dup", logo_url="https://example.test/dup.png")
        tgt = world.club("Canon", logo_url="  ")

        result = world.rpc("merge_club", src, tgt, True)

        assert "logo_url" in result["copied"]

    def test_neither_has_a_logo_copies_nothing(self, world):
        src, tgt = world.club("Dup"), world.club("Canon")
        assert world.rpc("merge_club", src, tgt, True)["copied"] == []

    def test_same_team_name_in_both_clubs_is_a_blocker(self, world):
        src, tgt = world.club("Dup"), world.club("Canon")
        name = f"ZZ Same Name {world.tag}"
        for cid in (src, tgt):
            tid = world.admin.table("teams").insert({"name": name, "club_id": cid}).execute().data[0]["id"]
            world.team_ids.append(tid)

        dry = world.rpc("merge_club", src, tgt, True)
        assert [b["kind"] for b in dry["blockers"]] == ["team_name_conflict"]
        with pytest.raises(Exception) as exc:
            world.rpc("merge_club", src, tgt, False)
        assert "blocker" in _error_text(exc)
        assert world.exists("clubs", src)

    def test_same_id_and_missing_id_are_refused(self, world):
        club = world.club("Only")
        with pytest.raises(Exception) as exc:
            world.rpc("merge_club", club, club, True)
        assert "two different" in _error_text(exc)
        with pytest.raises(Exception) as exc:
            world.rpc("merge_club", club, 2_000_000_000, True)
        assert "does not exist" in _error_text(exc)
        assert _error_code(exc) == "MTNF1"

    def test_null_dry_run_is_a_dry_run(self, duplicate_clubs):
        w = duplicate_clubs
        assert w.rpc("merge_club", w.club_src, w.club_tgt, None)["dry_run"] is True
        assert w.exists("clubs", w.club_src)

    def test_club_notification_channel_on_both_clubs_is_a_blocker(self, duplicate_clubs):
        w = duplicate_clubs
        for cid in (w.club_src, w.club_tgt):
            w.admin.table("club_notification_channels").insert(
                {"club_id": cid, "platform": "telegram", "destination": f"zz-{cid}"}
            ).execute()

        dry = w.rpc("merge_club", w.club_src, w.club_tgt, True)

        assert _kinds(dry) == ["club_channel_conflict"]
        with pytest.raises(Exception) as exc:
            w.rpc("merge_club", w.club_src, w.club_tgt, False)
        assert _error_code(exc) == "MTBLK"

    def test_club_scoped_notification_channel_on_both_clubs_is_a_blocker(self, duplicate_clubs):
        w = duplicate_clubs
        for cid in (w.club_src, w.club_tgt):
            w.admin.table("notification_channels").insert(
                {"scope_type": "club", "club_id": cid, "platform": "telegram", "destination": f"zz-{w.tag}"}
            ).execute()

        assert _kinds(w.rpc("merge_club", w.club_src, w.club_tgt, True)) == ["channel_conflict"]


# ---------------------------------------------------------------------------
# What PostgREST cannot express: privileges, unlisted tables, locks
# ---------------------------------------------------------------------------
class TestMergeInternals:
    def test_merge_rows_is_not_callable_through_the_api(self, world):
        from postgrest.exceptions import APIError

        with pytest.raises(APIError):
            world.admin.rpc(
                "_merge_rows",
                {"p_table": "public.teams", "p_col": "club_id", "p_from": 1, "p_into": 2, "p_key": []},
            ).execute()

    def test_merge_rows_refuses_unlisted_tables_and_same_ids(self, world):
        conn = _pg()
        try:
            with conn.cursor() as cur:
                with pytest.raises(psycopg2.Error) as exc:
                    cur.execute("SELECT public._merge_rows('public.seasons', 'id', 1, 2)")
                assert "not a merge column" in str(exc.value)
                conn.rollback()
                with pytest.raises(psycopg2.Error) as exc:
                    cur.execute("SELECT public._merge_rows('public.teams', 'club_id', 1, 1)")
                assert exc.value.pgcode == "MTSAM"
        finally:
            conn.rollback()
            conn.close()

    def test_unlisted_table_referencing_the_team_blocks(self, duplicate_teams):
        w = duplicate_teams
        conn = _pg()
        try:
            with conn.cursor() as cur:
                # Rolled back below: the table never exists outside this test.
                cur.execute("CREATE TABLE public.zz_merge_unlisted (team_id integer REFERENCES public.teams(id))")
                cur.execute("INSERT INTO public.zz_merge_unlisted VALUES (%s)", (w.src,))
                cur.execute("SELECT public.merge_team(%s, %s, true)", (w.src, w.tgt))
                dry = cur.fetchone()[0]
                assert [b["kind"] for b in dry["blockers"]] == ["unlisted_reference"]
                assert dry["blockers"][0]["table"] == "zz_merge_unlisted"
                with pytest.raises(psycopg2.Error) as exc:
                    cur.execute("SELECT public.merge_team(%s, %s, false)", (w.src, w.tgt))
                assert exc.value.pgcode == "MTBLK"
                assert "zz_merge_unlisted" in str(exc.value)
        finally:
            conn.rollback()
            conn.close()
        assert w.exists("teams", w.src)

    def test_source_row_is_locked_for_the_merge(self, duplicate_teams):
        w = duplicate_teams
        merging, other = _pg(), _pg()
        try:
            with merging.cursor() as cur:
                cur.execute("SELECT public.merge_team(%s, %s, true)", (w.src, w.tgt))
            with other.cursor() as cur:
                cur.execute("SET lock_timeout = '200ms'")
                with pytest.raises(psycopg2.Error) as exc:
                    cur.execute("UPDATE public.teams SET city = 'x' WHERE id = %s", (w.src,))
                assert exc.value.pgcode == "55P03"  # lock_not_available
                other.rollback()
                # The target is only key-share locked: a plain edit still goes through.
                cur.execute("SET lock_timeout = '200ms'")
                cur.execute("UPDATE public.teams SET city = city WHERE id = %s", (w.tgt,))
        finally:
            for c in (merging, other):
                c.rollback()
                c.close()

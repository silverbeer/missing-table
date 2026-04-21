"""
Integration-style tests for ClubNotificationsDAO.

Hits the real local Supabase database (not mocks), per the DAO testing
convention documented in CLAUDE.md. The service role key bypasses RLS, so
these tests exercise DAO behavior only; RLS is verified separately at the
API contract layer (Phase 3).
"""

import uuid

import pytest

from dao.club_dao import ClubDAO
from dao.club_notifications_dao import ClubNotificationsDAO
from dao.match_dao import SupabaseConnection

pytestmark = [
    pytest.mark.integration,
    pytest.mark.backend,
    pytest.mark.dao,
    pytest.mark.database,
]


def _unique_club_name() -> str:
    return f"NotifyTestClub-{uuid.uuid4().hex[:8]}"


class TestClubNotificationsDAO:
    """CRUD behavior for the notification channels DAO."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.conn = SupabaseConnection()
        self.dao = ClubNotificationsDAO(self.conn)
        self.club_dao = ClubDAO(self.conn)

        self.club = self.club_dao.create_club(
            name=_unique_club_name(),
            city="Boston, MA",
        )
        self.club_id = self.club["id"]

        yield

        # ON DELETE CASCADE on club_id removes any notification rows.
        try:
            self.club_dao.delete_club(self.club_id)
        except Exception:
            pass

    # ------------------------------------------------------------------ upsert

    def test_upsert_creates_new_row(self):
        row = self.dao.upsert(self.club_id, "telegram", "-1001234567890")

        assert row is not None
        assert row["club_id"] == self.club_id
        assert row["platform"] == "telegram"
        assert row["destination"] == "-1001234567890"
        assert row["enabled"] is True
        assert row["id"] is not None

    def test_upsert_overwrites_existing_same_platform(self):
        self.dao.upsert(self.club_id, "discord", "https://discord.com/api/webhooks/1/aaa")
        updated = self.dao.upsert(
            self.club_id,
            "discord",
            "https://discord.com/api/webhooks/2/bbb",
            enabled=False,
        )

        assert updated is not None
        assert updated["destination"].endswith("/2/bbb")
        assert updated["enabled"] is False

        rows = self.dao.list_by_club(self.club_id)
        discord_rows = [r for r in rows if r["platform"] == "discord"]
        assert len(discord_rows) == 1

    def test_upsert_allows_one_row_per_platform_per_club(self):
        self.dao.upsert(self.club_id, "telegram", "-100111")
        self.dao.upsert(self.club_id, "discord", "https://discord.com/api/webhooks/1/a")

        rows = self.dao.list_by_club(self.club_id)
        platforms = sorted(r["platform"] for r in rows)
        assert platforms == ["discord", "telegram"]

    # ---------------------------------------------------------------------- get

    def test_get_returns_existing_row(self):
        self.dao.upsert(self.club_id, "telegram", "-100999")
        row = self.dao.get(self.club_id, "telegram")

        assert row is not None
        assert row["destination"] == "-100999"
        assert row["platform"] == "telegram"

    def test_get_returns_none_when_missing(self):
        assert self.dao.get(self.club_id, "telegram") is None

    def test_get_scopes_by_platform(self):
        self.dao.upsert(self.club_id, "telegram", "-100aaa")
        self.dao.upsert(self.club_id, "discord", "https://discord.com/api/webhooks/1/z")

        tg = self.dao.get(self.club_id, "telegram")
        dc = self.dao.get(self.club_id, "discord")

        assert tg["destination"] == "-100aaa"
        assert dc["destination"].endswith("/1/z")

    # --------------------------------------------------------------- list_by_club

    def test_list_by_club_returns_empty_when_no_rows(self):
        assert self.dao.list_by_club(self.club_id) == []

    def test_list_by_club_does_not_leak_other_clubs(self):
        other_club = self.club_dao.create_club(name=_unique_club_name(), city="NYC")
        try:
            self.dao.upsert(self.club_id, "telegram", "-100ours")
            self.dao.upsert(other_club["id"], "telegram", "-100theirs")

            rows = self.dao.list_by_club(self.club_id)
            assert len(rows) == 1
            assert rows[0]["destination"] == "-100ours"
        finally:
            self.club_dao.delete_club(other_club["id"])

    # ------------------------------------------------------------------- delete

    def test_delete_removes_row(self):
        self.dao.upsert(self.club_id, "telegram", "-100xxx")

        assert self.dao.delete(self.club_id, "telegram") is True
        assert self.dao.get(self.club_id, "telegram") is None

    def test_delete_nonexistent_returns_false(self):
        assert self.dao.delete(self.club_id, "telegram") is False

    def test_delete_only_affects_target_platform(self):
        self.dao.upsert(self.club_id, "telegram", "-100tg")
        self.dao.upsert(self.club_id, "discord", "https://discord.com/api/webhooks/1/d")

        self.dao.delete(self.club_id, "telegram")

        assert self.dao.get(self.club_id, "telegram") is None
        assert self.dao.get(self.club_id, "discord") is not None


class TestClubTimezoneColumn:
    """The migration also adds a timezone column to clubs; quick smoke check."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.conn = SupabaseConnection()
        self.club_dao = ClubDAO(self.conn)
        self.club = self.club_dao.create_club(name=_unique_club_name(), city="Boston")
        yield
        try:
            self.club_dao.delete_club(self.club["id"])
        except Exception:
            pass

    def test_new_club_has_default_timezone(self):
        # Re-fetch via raw client to see the new column regardless of DAO shape.
        client = self.conn.get_client()
        resp = client.table("clubs").select("timezone").eq("id", self.club["id"]).execute()
        assert resp.data
        assert resp.data[0]["timezone"] == "America/New_York"

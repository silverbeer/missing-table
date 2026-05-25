"""Unit tests for the admin-attention badge API.

Covers the aggregator endpoint + DAO summation. DAOs are mocked so we
exercise the wiring + the `total` math without touching the DB.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def admin_client():
    """Minimal FastAPI app with the admin_attention router and
    require_admin overridden to a stub admin user."""
    from api import admin_attention
    from auth import require_admin

    app = FastAPI()
    app.include_router(admin_attention.router)
    app.dependency_overrides[require_admin] = lambda: {
        "id": "admin-user-1", "role": "admin", "username": "admin"
    }
    return TestClient(app), admin_attention


class TestAttentionCountsEndpoint:
    def test_returns_per_queue_counts_and_total(self, admin_client):
        client, module = admin_client
        with patch.object(
            module._dao, "get_counts",
            return_value={
                "invite_requests": 3,
                "channel_requests": 1,
                "support_inbox": 2,
                "total": 6,
            },
        ):
            resp = client.get("/api/admin/attention/counts")

        assert resp.status_code == 200
        assert resp.json() == {
            "invite_requests": 3,
            "channel_requests": 1,
            "support_inbox": 2,
            "total": 6,
        }

    def test_zero_when_no_pending_work(self, admin_client):
        client, module = admin_client
        with patch.object(
            module._dao, "get_counts",
            return_value={
                "invite_requests": 0,
                "channel_requests": 0,
                "support_inbox": 0,
                "total": 0,
            },
        ):
            resp = client.get("/api/admin/attention/counts")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_requires_admin(self):
        """Without an admin dep override, non-admins should be rejected."""
        from api import admin_attention
        from auth import require_admin

        app = FastAPI()
        app.include_router(admin_attention.router)

        def _non_admin():
            from fastapi import HTTPException
            raise HTTPException(status_code=403, detail="Admin access required")
        app.dependency_overrides[require_admin] = _non_admin

        client = TestClient(app)
        resp = client.get("/api/admin/attention/counts")
        assert resp.status_code == 403


class TestAdminAttentionDAO:
    """Direct tests on the DAO's aggregation math.

    Mocks the source DAO/client calls so we don't hit Supabase, then asserts
    the `total` is the sum and each queue's count is reported separately.
    """

    def _make_dao(self):
        from unittest.mock import MagicMock
        from dao.admin_attention_dao import AdminAttentionDAO

        # AdminAttentionDAO inherits BaseDAO and uses a SupabaseConnection.
        # Bypass the runtime isinstance check by patching __init__ to set
        # the connection_holder + client directly.
        dao = AdminAttentionDAO.__new__(AdminAttentionDAO)
        dao.connection_holder = MagicMock()
        dao.client = MagicMock()
        return dao

    def test_total_is_sum_of_queues(self):
        dao = self._make_dao()
        with (
            patch.object(dao, "_count_pending_invite_requests", return_value=3),
            patch.object(dao, "_count_pending_channel_requests", return_value=1),
            patch(
                "dao.admin_attention_dao.EmailThreadsDAO"
            ) as mock_email_threads_cls,
        ):
            mock_email_threads_cls.return_value.unread_count_for_attention.return_value = 2
            result = dao.get_counts()

        assert result == {
            "invite_requests": 3,
            "channel_requests": 1,
            "support_inbox": 2,
            "total": 6,
        }

    def test_all_zero_yields_zero_total(self):
        dao = self._make_dao()
        with (
            patch.object(dao, "_count_pending_invite_requests", return_value=0),
            patch.object(dao, "_count_pending_channel_requests", return_value=0),
            patch(
                "dao.admin_attention_dao.EmailThreadsDAO"
            ) as mock_email_threads_cls,
        ):
            mock_email_threads_cls.return_value.unread_count_for_attention.return_value = 0
            result = dao.get_counts()
        assert result == {
            "invite_requests": 0,
            "channel_requests": 0,
            "support_inbox": 0,
            "total": 0,
        }

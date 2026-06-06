"""Unit tests for stateless backend auth clients (SB-115).

The shared `auth_ops_client` previously used library defaults
(persist_session=True, auto_refresh_token=True). Any user's login/refresh
stored their session on the shared client, and gotrue's background thread
silently refreshed it — rotating that user's refresh token server-side.
The device still held the pre-rotation token, so its next refresh was
rejected ("already used") and the user was forced to log in again on
every device.

These tests pin the stateless configuration so the defaults can't creep
back in via a refactor.
"""

from __future__ import annotations

import app as app_module


class TestStatelessAuthClients:
    def test_auth_ops_client_does_not_auto_refresh(self):
        assert app_module.auth_ops_client.options.auto_refresh_token is False

    def test_auth_ops_client_does_not_persist_session(self):
        assert app_module.auth_ops_client.options.persist_session is False

    def test_auth_service_client_does_not_auto_refresh(self):
        assert app_module.auth_service_client.options.auto_refresh_token is False

    def test_auth_service_client_does_not_persist_session(self):
        assert app_module.auth_service_client.options.persist_session is False

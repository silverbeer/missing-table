"""Unit tests for the R2 client wrapper (SB-31).

These tests cover the env-var-driven configuration surface and don't require
network access to Cloudflare R2. End-to-end upload/download tests live in
`tests/integration/test_r2_upload.py` and require real R2 credentials.
"""

from __future__ import annotations

import pytest

import r2_client


@pytest.fixture(autouse=True)
def _reset_r2_client_cache_and_env(monkeypatch):
    """Drop the boto3 client cache + ensure R2 env vars are clean per test."""
    for var in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET", "R2_ENDPOINT_URL"):
        monkeypatch.delenv(var, raising=False)
    r2_client._reset_client_for_tests()
    yield
    r2_client._reset_client_for_tests()


class TestIsConfigured:
    def test_returns_false_when_no_env_vars_set(self):
        assert r2_client.is_configured() is False

    def test_returns_false_when_partial_env_vars_set(self, monkeypatch):
        monkeypatch.setenv("R2_ACCOUNT_ID", "abc123")
        monkeypatch.setenv("R2_ACCESS_KEY_ID", "key")
        # R2_SECRET_ACCESS_KEY and R2_BUCKET still missing
        assert r2_client.is_configured() is False

    def test_returns_false_when_env_var_is_empty_string(self, monkeypatch):
        monkeypatch.setenv("R2_ACCOUNT_ID", "abc123")
        monkeypatch.setenv("R2_ACCESS_KEY_ID", "key")
        monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "secret")
        monkeypatch.setenv("R2_BUCKET", "")  # empty
        assert r2_client.is_configured() is False

    def test_returns_true_when_all_required_vars_set(self, monkeypatch):
        monkeypatch.setenv("R2_ACCOUNT_ID", "abc123")
        monkeypatch.setenv("R2_ACCESS_KEY_ID", "key")
        monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "secret")
        monkeypatch.setenv("R2_BUCKET", "mt-match-photos")
        assert r2_client.is_configured() is True


class TestGetClient:
    def test_raises_runtime_error_when_not_configured(self):
        with pytest.raises(RuntimeError) as exc_info:
            r2_client._get_client()
        assert "R2_ACCOUNT_ID" in str(exc_info.value)

    def test_builds_client_with_default_endpoint(self, monkeypatch):
        monkeypatch.setenv("R2_ACCOUNT_ID", "abc123")
        monkeypatch.setenv("R2_ACCESS_KEY_ID", "key")
        monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "secret")
        monkeypatch.setenv("R2_BUCKET", "mt-match-photos")

        client = r2_client._get_client()
        assert client is not None
        # boto3 stores endpoint on the client's meta
        assert "abc123.r2.cloudflarestorage.com" in client.meta.endpoint_url

    def test_honors_explicit_endpoint_override(self, monkeypatch):
        monkeypatch.setenv("R2_ACCOUNT_ID", "abc123")
        monkeypatch.setenv("R2_ACCESS_KEY_ID", "key")
        monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "secret")
        monkeypatch.setenv("R2_BUCKET", "mt-match-photos")
        monkeypatch.setenv("R2_ENDPOINT_URL", "https://custom.example.com")

        client = r2_client._get_client()
        assert client.meta.endpoint_url == "https://custom.example.com"

    def test_caches_client_across_calls(self, monkeypatch):
        monkeypatch.setenv("R2_ACCOUNT_ID", "abc123")
        monkeypatch.setenv("R2_ACCESS_KEY_ID", "key")
        monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "secret")
        monkeypatch.setenv("R2_BUCKET", "mt-match-photos")

        client_a = r2_client._get_client()
        client_b = r2_client._get_client()
        assert client_a is client_b


class TestConstants:
    def test_default_ttl_is_one_hour(self):
        assert r2_client.DEFAULT_SIGNED_URL_TTL_SECONDS == 3600

    def test_not_configured_msg_mentions_all_required_vars(self):
        msg = r2_client.R2_NOT_CONFIGURED_MSG
        for var in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET"):
            assert var in msg

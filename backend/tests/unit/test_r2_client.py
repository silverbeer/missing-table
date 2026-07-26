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
    for var in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET", "R2_ENDPOINT_URL", "R2_ANDROID_BUCKET"):
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


class TestAndroidApk:
    def _configure(self, monkeypatch):
        monkeypatch.setenv("R2_ACCOUNT_ID", "abc123")
        monkeypatch.setenv("R2_ACCESS_KEY_ID", "key")
        monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "secret")
        monkeypatch.setenv("R2_BUCKET", "mt-match-photos")

    def test_key_and_default_bucket(self):
        assert r2_client.ANDROID_APK_KEY == "latest/missingtable.apk"
        assert r2_client._android_bucket() == "mt-android-releases"
        assert r2_client.ANDROID_APK_URL_TTL_SECONDS == 300

    def test_android_bucket_can_be_overridden(self, monkeypatch):
        monkeypatch.setenv("R2_ANDROID_BUCKET", "custom-releases")
        assert r2_client._android_bucket() == "custom-releases"

    def test_presigned_url_targets_android_bucket_and_key(self, monkeypatch):
        self._configure(monkeypatch)
        url = r2_client.get_apk_download_url()
        assert "mt-android-releases" in url
        assert "latest/missingtable.apk" in url
        assert "X-Amz-Signature" in url  # genuinely presigned, not a bare URL

    def test_versions_read_from_metadata(self, monkeypatch):
        class _Fake:
            def head_object(self, Bucket, Key):
                assert Bucket == "mt-android-releases"
                assert Key == "latest/missingtable.apk"
                return {"Metadata": {"versioncode": "42", "minversioncode": "41"}}

        monkeypatch.setattr(r2_client, "_client", _Fake())
        assert r2_client.get_apk_versions() == (42, 41)

    def test_versions_partial_metadata(self, monkeypatch):
        class _Fake:
            def head_object(self, Bucket, Key):
                return {"Metadata": {"versioncode": "42"}}

        monkeypatch.setattr(r2_client, "_client", _Fake())
        assert r2_client.get_apk_versions() == (42, None)

    def test_versions_none_when_metadata_absent(self, monkeypatch):
        class _Fake:
            def head_object(self, Bucket, Key):
                return {"Metadata": {}}

        monkeypatch.setattr(r2_client, "_client", _Fake())
        assert r2_client.get_apk_versions() == (None, None)

    def test_versions_none_on_r2_error(self, monkeypatch):
        class _Fake:
            def head_object(self, Bucket, Key):
                raise RuntimeError("boom")

        monkeypatch.setattr(r2_client, "_client", _Fake())
        assert r2_client.get_apk_versions() == (None, None)


class TestConstants:
    def test_default_ttl_is_one_hour(self):
        assert r2_client.DEFAULT_SIGNED_URL_TTL_SECONDS == 3600

    def test_not_configured_msg_mentions_all_required_vars(self):
        msg = r2_client.R2_NOT_CONFIGURED_MSG
        for var in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET"):
            assert var in msg

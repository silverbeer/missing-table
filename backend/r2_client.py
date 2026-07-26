"""Cloudflare R2 client for match-photo storage (SB-31).

R2 is S3-compatible, so we use boto3. Credentials are loaded from env vars; if
any are missing the module reports `is_configured() == False` and callers should
return HTTP 503 with a helpful message rather than crashing.

Why R2 (not Supabase Storage): zero egress fees + 10GB free preserves our
Supabase free-tier headroom. See Linear SB-19 for the cost analysis.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client

logger = structlog.get_logger(__name__)

_R2_ENV_VARS = (
    "R2_ACCOUNT_ID",
    "R2_ACCESS_KEY_ID",
    "R2_SECRET_ACCESS_KEY",
    "R2_BUCKET",
)

R2_NOT_CONFIGURED_MSG = (
    "Cloudflare R2 is not configured. Set R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, "
    "R2_SECRET_ACCESS_KEY, R2_BUCKET env vars to enable match-photo upload."
)

DEFAULT_SIGNED_URL_TTL_SECONDS = 3600

_client: S3Client | None = None


def is_configured() -> bool:
    """True iff all required R2 env vars are present and non-empty."""
    return all(os.environ.get(var) for var in _R2_ENV_VARS)


def _bucket() -> str:
    return os.environ["R2_BUCKET"]


def _get_client() -> S3Client:
    """Lazily build and cache the boto3 S3 client pointed at R2.

    R2 endpoint format: https://<account_id>.r2.cloudflarestorage.com.
    R2 ignores the region but boto3 requires one — use 'auto'.
    """
    global _client
    if _client is not None:
        return _client

    if not is_configured():
        raise RuntimeError(R2_NOT_CONFIGURED_MSG)

    import boto3

    account_id = os.environ["R2_ACCOUNT_ID"]
    endpoint_url = os.environ.get(
        "R2_ENDPOINT_URL",
        f"https://{account_id}.r2.cloudflarestorage.com",
    )

    _client = boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        region_name="auto",
    )
    return _client


def _reset_client_for_tests() -> None:
    """Drop the cached client. Tests use this between configurations."""
    global _client
    _client = None


def upload_photo(key: str, content: bytes, content_type: str = "image/jpeg") -> str:
    """Upload bytes to R2 at the given key, return a signed URL (1h TTL).

    Overwrites any existing object at the same key (upsert semantics, matching
    the club-logo upload pattern in `backend/app.py`).
    """
    client = _get_client()
    client.put_object(
        Bucket=_bucket(),
        Key=key,
        Body=content,
        ContentType=content_type,
    )
    logger.info("r2_upload_succeeded", key=key, bytes=len(content))
    return get_signed_url(key)


def get_signed_url(key: str, expires_in: int = DEFAULT_SIGNED_URL_TTL_SECONDS) -> str:
    """Mint a presigned GET URL for an object. Local-only HMAC, no network call."""
    client = _get_client()
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": _bucket(), "Key": key},
        ExpiresIn=expires_in,
    )


def delete_photo(key: str) -> None:
    """Delete an object from R2. Idempotent — succeeds on a missing key."""
    client = _get_client()
    client.delete_object(Bucket=_bucket(), Key=key)
    logger.info("r2_delete_succeeded", key=key)


# ── Android APK distribution (SB-313) ────────────────────────────────────────
# The release CI uploads the signed APK to a SEPARATE, PRIVATE bucket
# (mt-android-releases). It's private on purpose: MT is invite-only, so the APK
# must not be anonymously downloadable. The backend hands authenticated users a
# short-lived presigned URL instead.

ANDROID_APK_KEY = "latest/missingtable.apk"
ANDROID_APK_URL_TTL_SECONDS = 300  # 5 min: minted per authenticated request


def _android_bucket() -> str:
    return os.environ.get("R2_ANDROID_BUCKET", "mt-android-releases")


def get_apk_download_url(expires_in: int = ANDROID_APK_URL_TTL_SECONDS) -> str:
    """Mint a short-lived presigned GET URL for the latest Android APK.

    Reuses the account-level R2 client; the backend's R2 credentials must have
    read access to R2_ANDROID_BUCKET (default 'mt-android-releases'). Local HMAC
    signing, no network call.
    """
    client = _get_client()
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": _android_bucket(), "Key": ANDROID_APK_KEY},
        ExpiresIn=expires_in,
    )


def get_apk_versions() -> tuple[int | None, int | None]:
    """(version_code, min_version_code) from the latest APK's R2 metadata.

    The Android release CI stamps `versioncode` (this build) and
    `minversioncode` (oldest still-supported build — SB-328 force-upgrade) on
    upload. One head_object serves both. Missing metadata or any R2 error
    degrades to None, which the app treats as "no update information".
    """
    try:
        client = _get_client()
        head = client.head_object(Bucket=_android_bucket(), Key=ANDROID_APK_KEY)
        meta = head.get("Metadata") or {}

        def _int(key: str) -> int | None:
            raw = meta.get(key)
            return int(raw) if raw else None

        return _int("versioncode"), _int("minversioncode")
    except Exception:
        logger.warning("r2_apk_version_lookup_failed", exc_info=True)
        return None, None

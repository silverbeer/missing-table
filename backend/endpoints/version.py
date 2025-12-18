"""
Version endpoint for application versioning and build information.
"""
import os
from fastapi import APIRouter
from pydantic import BaseModel
from datetime import datetime

router = APIRouter(prefix="/api", tags=["version"])


class VersionInfo(BaseModel):
    """Version information response model."""
    version: str
    build_id: str | None = None
    environment: str
    commit_sha: str | None = None
    build_date: str | None = None
    status: str = "healthy"


@router.get("/version", response_model=VersionInfo)
async def get_version():
    """
    Get application version and build information.

    Returns:
        VersionInfo: Application version, environment, and build details

    Environment Variables:
        - APP_VERSION: Semantic version (e.g., "1.0.0")
        - BUILD_ID: CI/CD build/workflow run ID
        - ENVIRONMENT: Environment name (local, dev, production)
        - COMMIT_SHA: Git commit SHA
        - BUILD_DATE: ISO format build timestamp
    """
    version = os.getenv("APP_VERSION", "1.0.0")
    build_id = os.getenv("BUILD_ID")
    environment = os.getenv("ENVIRONMENT", "development")
    commit_sha = os.getenv("COMMIT_SHA")
    build_date = os.getenv("BUILD_DATE")

    # Construct full version string with build ID if available
    full_version = version
    if build_id:
        full_version = f"{version}.{build_id}"

    return VersionInfo(
        version=full_version,
        build_id=build_id,
        environment=environment,
        commit_sha=commit_sha,
        build_date=build_date,
        status="healthy"
    )

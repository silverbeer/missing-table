
"""Test suite for /api/version endpoint"""
import pytest
from fastapi.testclient import TestClient
from backend.app import app

client = TestClient(app)


def test_get_version_success():
    """Test successful GET request"""
    response = client.get("/api/version")
    assert response.status_code == 200
    assert "version" in response.json()


def test_invalid_method():
    """Test POST to GET-only endpoint"""
    response = client.post("/api/version")
    assert response.status_code == 405


def test_get_version_with_extra_param():
    """Test GET request with additional query parameters"""
    response = client.get("/api/version?extra=param")
    assert response.status_code == 200
    assert "version" in response.json()


def test_get_version_with_unsupported_media_type():
    """Test GET request with unsupported media type"""
    headers = {"Accept": "application/xml"}
    response = client.get("/api/version", headers=headers)
    assert response.status_code == 406


def test_sql_injection_attempt():
    """Test GET request with SQL injection attempt"""
    response = client.get("/api/version?query=' OR '1'='1")
    assert response.status_code == 200
    assert "version" in response.json()


def test_xss_attempt():
    """Test GET request with XSS attempt"""
    response = client.get("/api/version?query=<script>alert('xss')</script>")
    assert response.status_code == 200
    assert "version" in response.json()


def test_unauthorized_access_attempt():
    """Test GET request without authentication"""
    response = client.get("/api/version")
    assert response.status_code == 200
    assert "version" in response.json()


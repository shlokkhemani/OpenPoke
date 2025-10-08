"""
Health check tests for Docker containers.

These tests verify that the Docker containers are running and healthy.
"""

import pytest
import requests


def test_backend_health_endpoint(backend_url: str, wait_for_services):
    """Test that backend health endpoint returns correct response."""
    response = requests.get(f"{backend_url}/api/v1/health", timeout=10)
    
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    
    data = response.json()
    assert data["ok"] is True, "Health check should return ok=True"
    assert data["service"] == "openpoke", f"Expected service 'openpoke', got {data.get('service')}"
    assert "version" in data, "Health check should include version"


def test_backend_meta_endpoint(backend_url: str, wait_for_services):
    """Test that backend meta endpoint returns correct response."""
    response = requests.get(f"{backend_url}/api/v1/meta", timeout=10)
    
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    
    data = response.json()
    assert data["status"] == "ok", f"Expected status 'ok', got {data.get('status')}"
    assert data["service"] == "openpoke", f"Expected service 'openpoke', got {data.get('service')}"
    assert isinstance(data["endpoints"], list), "Endpoints should be a list"
    assert len(data["endpoints"]) > 0, "Should have at least one endpoint"


def test_frontend_accessible(frontend_url: str, wait_for_services):
    """Test that frontend is accessible and returns HTML."""
    response = requests.get(frontend_url, timeout=10)
    
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    assert "text/html" in response.headers.get("Content-Type", ""), \
        "Frontend should return HTML content"


def test_backend_cors_headers(backend_url: str, wait_for_services):
    """Test that backend has proper CORS configuration."""
    response = requests.options(
        f"{backend_url}/api/v1/health",
        headers={"Origin": "http://localhost:3000"},
        timeout=10
    )
    
    # CORS headers should be present
    assert "access-control-allow-origin" in response.headers or \
           "Access-Control-Allow-Origin" in response.headers, \
           "CORS headers should be present"


def test_backend_docs_accessible(backend_url: str, wait_for_services):
    """Test that backend API documentation is accessible."""
    response = requests.get(f"{backend_url}/docs", timeout=10)
    
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    assert "text/html" in response.headers.get("Content-Type", ""), \
        "API docs should return HTML"


def test_backend_timezone_endpoint(backend_url: str, wait_for_services):
    """Test that backend timezone endpoint is accessible."""
    response = requests.get(f"{backend_url}/api/v1/meta/timezone", timeout=10)
    
    # Should return 200 with timezone data
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    
    data = response.json()
    assert "timezone" in data, "Response should include timezone"


@pytest.mark.parametrize("endpoint", [
    "/api/v1/health",
    "/api/v1/meta",
    "/api/v1/meta/timezone",
])
def test_backend_endpoints_respond(backend_url: str, wait_for_services, endpoint: str):
    """Test that all critical backend endpoints respond."""
    response = requests.get(f"{backend_url}{endpoint}", timeout=10)
    
    assert response.status_code in [200, 401, 422], \
        f"Endpoint {endpoint} should respond (got {response.status_code})"


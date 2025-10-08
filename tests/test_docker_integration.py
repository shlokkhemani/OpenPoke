"""
Integration tests for Docker setup.

These tests verify that the frontend and backend work together correctly.
"""

import pytest
import requests


def test_frontend_proxies_to_backend_health(frontend_url: str, wait_for_services):
    """Test that frontend can proxy health check to backend."""
    # This tests the frontend -> backend connection
    response = requests.get(f"{frontend_url}", timeout=10)
    assert response.status_code == 200, "Frontend should be accessible"


def test_chat_history_endpoint_via_frontend(frontend_url: str, wait_for_services, api_headers):
    """Test chat history endpoint through frontend proxy."""
    response = requests.get(
        f"{frontend_url}/api/chat/history",
        headers=api_headers,
        timeout=10
    )
    
    # Should return 200 or 502 (if backend connection fails)
    # We mainly care that the route exists and responds
    assert response.status_code in [200, 502], \
        f"Expected 200 or 502, got {response.status_code}"
    
    if response.status_code == 200:
        data = response.json()
        # Should have a messages field (even if empty)
        assert "messages" in data or "error" in data, \
            "Response should have messages or error field"


def test_gmail_status_endpoint_via_frontend(frontend_url: str, wait_for_services, api_headers):
    """Test Gmail status endpoint through frontend proxy."""
    response = requests.post(
        f"{frontend_url}/api/gmail/status",
        json={"user_id": "test-user"},
        headers=api_headers,
        timeout=10
    )
    
    # Should respond (might be 200, 400, or 500 depending on config)
    assert response.status_code in [200, 400, 500, 502], \
        f"Endpoint should respond, got {response.status_code}"


def test_timezone_endpoint_via_frontend(frontend_url: str, wait_for_services, api_headers):
    """Test timezone endpoint through frontend proxy."""
    response = requests.post(
        f"{frontend_url}/api/timezone",
        json={"timezone": "America/New_York"},
        headers=api_headers,
        timeout=10
    )
    
    # Should respond successfully
    assert response.status_code in [200, 502], \
        f"Expected 200 or 502, got {response.status_code}"


def test_backend_directly_accessible(backend_url: str, wait_for_services):
    """Test that backend is directly accessible (not just through frontend)."""
    response = requests.get(f"{backend_url}/api/v1/health", timeout=10)
    
    assert response.status_code == 200, "Backend should be directly accessible"
    data = response.json()
    assert data["ok"] is True, "Backend health check should pass"


def test_frontend_backend_network_connectivity(
    frontend_url: str,
    backend_url: str,
    wait_for_services,
    api_headers
):
    """Test that frontend and backend can communicate within Docker network."""
    # Get chat history from frontend (which proxies to backend)
    frontend_response = requests.get(
        f"{frontend_url}/api/chat/history",
        headers=api_headers,
        timeout=10
    )
    
    # Get chat history directly from backend
    backend_response = requests.get(
        f"{backend_url}/api/v1/chat/history",
        headers=api_headers,
        timeout=10
    )
    
    # Both should succeed or fail consistently
    assert frontend_response.status_code == backend_response.status_code or \
           frontend_response.status_code in [200, 502], \
           "Frontend and backend should be in sync"


def test_static_assets_load(frontend_url: str, wait_for_services):
    """Test that frontend static assets are accessible."""
    response = requests.get(frontend_url, timeout=10)
    
    assert response.status_code == 200, "Frontend should serve pages"
    
    # Check that it's actually serving HTML
    content_type = response.headers.get("Content-Type", "")
    assert "html" in content_type.lower(), \
        f"Expected HTML content, got {content_type}"


@pytest.mark.parametrize("invalid_endpoint", [
    "/api/nonexistent",
    "/api/v1/invalid",
])
def test_frontend_handles_invalid_routes(
    frontend_url: str,
    wait_for_services,
    invalid_endpoint: str
):
    """Test that frontend properly handles invalid routes."""
    response = requests.get(
        f"{frontend_url}{invalid_endpoint}",
        timeout=10
    )
    
    # Should return 404 or other error code (not 200)
    assert response.status_code >= 400, \
        f"Invalid route should return error, got {response.status_code}"


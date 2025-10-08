"""Pytest configuration and shared fixtures for Docker tests."""

import os
import time
import pytest
import requests
from typing import Generator


@pytest.fixture(scope="session")
def backend_url() -> str:
    """Get the backend API base URL."""
    return os.getenv("BACKEND_URL", "http://localhost:8001")


@pytest.fixture(scope="session")
def frontend_url() -> str:
    """Get the frontend base URL."""
    return os.getenv("FRONTEND_URL", "http://localhost:3000")


@pytest.fixture(scope="session")
def wait_for_services(backend_url: str, frontend_url: str) -> Generator[None, None, None]:
    """Wait for both backend and frontend services to be ready."""
    max_retries = 30
    retry_delay = 2
    
    # Wait for backend
    for i in range(max_retries):
        try:
            response = requests.get(f"{backend_url}/api/v1/health", timeout=5)
            if response.status_code == 200:
                print(f"✓ Backend ready at {backend_url}")
                break
        except requests.exceptions.RequestException:
            if i == max_retries - 1:
                pytest.fail(f"Backend not ready after {max_retries * retry_delay} seconds")
            time.sleep(retry_delay)
    
    # Wait for frontend
    for i in range(max_retries):
        try:
            response = requests.get(frontend_url, timeout=5)
            if response.status_code == 200:
                print(f"✓ Frontend ready at {frontend_url}")
                break
        except requests.exceptions.RequestException:
            if i == max_retries - 1:
                pytest.fail(f"Frontend not ready after {max_retries * retry_delay} seconds")
            time.sleep(retry_delay)
    
    yield
    
    # Cleanup happens in docker-compose down


@pytest.fixture
def api_headers() -> dict:
    """Common headers for API requests."""
    return {
        "Content-Type": "application/json",
        "Accept": "application/json"
    }


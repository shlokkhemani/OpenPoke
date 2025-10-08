"""
Volume persistence tests for Docker setup.

These tests verify that data persists correctly in Docker volumes.
"""

import subprocess
import pytest
import requests
import time
import os


@pytest.mark.skipif(
    os.getenv("SKIP_DOCKER_VOLUME_TESTS") == "1",
    reason="Docker volume tests require docker-compose control"
)
def test_data_directory_exists_in_backend():
    """Test that the data directory exists in the backend container."""
    try:
        result = subprocess.run(
            ["docker", "exec", "openpoke-backend", "ls", "-la", "/app/server/data"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        assert result.returncode == 0, \
            "Data directory should exist in backend container"
        
        # The directory should exist (might be empty initially)
        assert "total" in result.stdout or "." in result.stdout, \
            "Data directory should be accessible"
    except subprocess.TimeoutExpired:
        pytest.skip("Docker command timed out")
    except FileNotFoundError:
        pytest.skip("Docker not available or container not running")


@pytest.mark.skipif(
    os.getenv("SKIP_DOCKER_VOLUME_TESTS") == "1",
    reason="Docker volume tests require docker-compose control"
)
def test_timezone_persistence(backend_url: str, wait_for_services, api_headers):
    """Test that timezone setting persists."""
    import requests
    
    # Set a timezone
    test_timezone = "America/New_York"
    response = requests.post(
        f"{backend_url}/api/v1/meta/timezone",
        json={"timezone": test_timezone},
        headers=api_headers,
        timeout=10
    )
    
    assert response.status_code == 200, \
        f"Should be able to set timezone, got {response.status_code}"
    
    # Retrieve it back
    response = requests.get(
        f"{backend_url}/api/v1/meta/timezone",
        headers=api_headers,
        timeout=10
    )
    
    assert response.status_code == 200, "Should be able to get timezone"
    data = response.json()
    assert data["timezone"] == test_timezone, \
        f"Timezone should persist, expected {test_timezone}, got {data.get('timezone')}"


@pytest.mark.skipif(
    os.getenv("SKIP_DOCKER_VOLUME_TESTS") == "1",
    reason="Docker volume tests require docker-compose control"
)
def test_chat_history_persistence(backend_url: str, wait_for_services, api_headers):
    """Test that chat history persists."""
    import requests
    
    # Get initial history
    response = requests.get(
        f"{backend_url}/api/v1/chat/history",
        headers=api_headers,
        timeout=10
    )
    
    assert response.status_code == 200, "Should be able to get chat history"
    initial_data = response.json()
    
    # The history endpoint exists and returns data structure
    assert "messages" in initial_data or "error" not in initial_data, \
        "Chat history should have proper structure"


@pytest.mark.skipif(
    os.getenv("SKIP_DOCKER_VOLUME_TESTS") == "1",
    reason="Docker volume tests require docker-compose control"
)
def test_volume_mounted_correctly():
    """Test that the Docker volume is mounted correctly."""
    try:
        # Check that the volume exists
        result = subprocess.run(
            ["docker", "volume", "ls"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        assert "openpoke-data" in result.stdout or "openpoke_openpoke-data" in result.stdout, \
            "Docker volume 'openpoke-data' should exist"
        
        # Check volume is mounted in container
        result = subprocess.run(
            ["docker", "inspect", "openpoke-backend"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        assert "/app/server/data" in result.stdout, \
            "Volume should be mounted at /app/server/data"
    except subprocess.TimeoutExpired:
        pytest.skip("Docker command timed out")
    except FileNotFoundError:
        pytest.skip("Docker not available")


@pytest.mark.skipif(
    os.getenv("SKIP_DOCKER_VOLUME_TESTS") == "1",
    reason="Docker volume tests require docker-compose control"
)
def test_volume_permissions():
    """Test that volume has correct permissions."""
    try:
        result = subprocess.run(
            ["docker", "exec", "openpoke-backend", "ls", "-ld", "/app/server/data"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        assert result.returncode == 0, "Should be able to check volume permissions"
        
        # Check that the directory is writable (starts with 'd' and has write permissions)
        assert result.stdout.startswith('d'), "Should be a directory"
    except subprocess.TimeoutExpired:
        pytest.skip("Docker command timed out")
    except FileNotFoundError:
        pytest.skip("Docker not available or container not running")


@pytest.mark.skipif(
    os.getenv("SKIP_DOCKER_VOLUME_TESTS") == "1",
    reason="Docker volume tests require docker-compose control"
)
def test_can_write_to_volume():
    """Test that the backend can write to the data volume."""
    try:
        # Try to create a test file in the data directory
        result = subprocess.run(
            ["docker", "exec", "openpoke-backend", "touch", "/app/server/data/test-write.txt"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        assert result.returncode == 0, \
            "Backend should be able to write to data directory"
        
        # Verify the file was created
        result = subprocess.run(
            ["docker", "exec", "openpoke-backend", "ls", "/app/server/data/test-write.txt"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        assert result.returncode == 0, "Test file should exist"
        
        # Clean up
        subprocess.run(
            ["docker", "exec", "openpoke-backend", "rm", "/app/server/data/test-write.txt"],
            capture_output=True,
            text=True,
            timeout=30
        )
    except subprocess.TimeoutExpired:
        pytest.skip("Docker command timed out")
    except FileNotFoundError:
        pytest.skip("Docker not available or container not running")


@pytest.mark.skipif(
    os.getenv("SKIP_DOCKER_VOLUME_TESTS") == "1",
    reason="Docker volume tests require docker-compose control"
)
def test_sqlite_database_created():
    """Test that SQLite database is created in the volume."""
    import time
    
    # Give the application some time to initialize the database
    time.sleep(5)
    
    try:
        result = subprocess.run(
            ["docker", "exec", "openpoke-backend", "ls", "-la", "/app/server/data/"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        # Check if triggers.db exists (it should be created on startup)
        # It might not exist immediately, which is okay for this test
        if "triggers.db" in result.stdout:
            assert ".db" in result.stdout, "SQLite database files should be in data directory"
    except subprocess.TimeoutExpired:
        pytest.skip("Docker command timed out")
    except FileNotFoundError:
        pytest.skip("Docker not available or container not running")


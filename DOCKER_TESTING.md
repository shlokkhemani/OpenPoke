# Testing Guide for OpenPoke Docker Setup

This guide covers testing the Docker implementation for OpenPoke.

## Prerequisites

1. Docker and Docker Compose installed
2. `.env` file configured with API keys
3. Ports 3000 and 8001 available

## Quick Test

Run the automated test script:

```bash
./docker-test.sh
```

This script will:
1. Build both Docker images
2. Start services with docker-compose
3. Wait for services to be healthy
4. Run basic smoke tests
5. Show service status

## Manual Testing

### 1. Build Images

```bash
# Build backend
docker build -f server/Dockerfile -t openpoke-backend:test .

# Build frontend  
docker build -f web/Dockerfile -t openpoke-frontend:test .

# Check images
docker images | grep openpoke
```

### 2. Start Services

```bash
# Start with docker-compose
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f
```

### 3. Health Checks

```bash
# Backend health
curl http://localhost:8001/api/v1/health
# Expected: {"ok":true,"service":"openpoke","version":"0.3.0"}

# Backend meta
curl http://localhost:8001/api/v1/meta

# Frontend
curl http://localhost:3000
# Expected: HTML response
```

### 4. API Documentation

Open in browser: http://localhost:8001/docs

### 5. Frontend Access

Open in browser: http://localhost:3000

## Automated Test Suite

### Install Test Dependencies

```bash
pip install -r tests/requirements.txt
```

### Run Tests

```bash
# Run all tests
pytest tests/

# Run specific test file
pytest tests/test_docker_health.py -v

# Run with coverage
pytest tests/ --cov=server --cov-report=html

# Run only integration tests
pytest tests/test_docker_integration.py -v

# Skip Docker image tests (if images not built)
SKIP_DOCKER_IMAGE_TESTS=1 pytest tests/

# Skip volume tests (if you don't have docker-compose control)
SKIP_DOCKER_VOLUME_TESTS=1 pytest tests/
```

### Test Categories

#### Health Tests (`test_docker_health.py`)
- Backend health endpoint
- Backend meta endpoint
- Frontend accessibility
- CORS configuration
- API documentation
- Timezone endpoint
- All critical endpoints

#### Integration Tests (`test_docker_integration.py`)
- Frontend-to-backend proxy
- Chat history endpoint
- Gmail status endpoint
- Timezone endpoint
- Network connectivity
- Static assets
- Invalid route handling

#### Security Tests (`test_docker_security.py`)
- No .env files in images
- No secrets in responses
- Non-root user execution
- CORS configuration
- Directory listing disabled

#### Volume Tests (`test_docker_volumes.py`)
- Data directory exists
- Timezone persistence
- Chat history persistence
- Volume mounted correctly
- Volume permissions
- Write permissions
- SQLite database creation

## Development Mode Testing

### Start Development Environment

```bash
docker-compose -f docker-compose.dev.yml up
```

Features to test:
- Hot-reload for Python files
- Hot-reload for TypeScript/React files
- Data persistence across restarts
- Log streaming

## Performance Testing

### Image Sizes

```bash
docker images | grep openpoke
```

Expected sizes:
- Backend: ~200-300 MB
- Frontend: ~150-200 MB (with standalone output)

### Memory Usage

```bash
docker stats
```

Expected memory:
- Backend: ~100-200 MB
- Frontend: ~50-100 MB

### Build Time

Time the build process:

```bash
time docker build -f server/Dockerfile -t openpoke-backend:test .
time docker build -f web/Dockerfile -t openpoke-frontend:test .
```

## Security Testing

### Check for Secrets in Images

```bash
# Backend
docker run --rm openpoke-backend:latest find /app -name ".env*"
# Should return nothing

# Frontend
docker run --rm openpoke-frontend:latest find /app -name ".env*"
# Should return nothing
```

### Check User

```bash
# Backend (should be 'openpoke')
docker run --rm openpoke-backend:latest whoami

# Frontend (should be 'nextjs')
docker run --rm openpoke-frontend:latest whoami
```

### Check Exposed Ports

```bash
docker ps
# Should only show 3000 and 8001
```

## Data Persistence Testing

### 1. Create Test Data

```bash
# Set timezone
curl -X POST http://localhost:8001/api/v1/meta/timezone \
  -H "Content-Type: application/json" \
  -d '{"timezone":"America/New_York"}'

# Verify it was saved
curl http://localhost:8001/api/v1/meta/timezone
```

### 2. Restart Containers

```bash
docker-compose restart
```

### 3. Verify Data Persists

```bash
# Check timezone again
curl http://localhost:8001/api/v1/meta/timezone
# Should still show America/New_York
```

### 4. Check Volume

```bash
# List volume contents
docker run --rm -v openpoke-data:/data alpine ls -la /data

# Check database
docker exec openpoke-backend ls -la /app/server/data/
```

## Backup and Restore Testing

### Create Backup

```bash
docker run --rm \
  -v openpoke-data:/data \
  -v $(pwd):/backup \
  alpine tar czf /backup/test-backup.tar.gz /data
```

### Simulate Data Loss

```bash
docker-compose down -v
```

### Restore Backup

```bash
docker volume create openpoke-data

docker run --rm \
  -v openpoke-data:/data \
  -v $(pwd):/backup \
  alpine sh -c "cd / && tar xzf /backup/test-backup.tar.gz"

docker-compose up -d
```

### Verify Restoration

```bash
curl http://localhost:8001/api/v1/meta/timezone
```

## Troubleshooting Tests

### Logs

```bash
# All logs
docker-compose logs

# Specific service
docker-compose logs backend
docker-compose logs frontend

# Follow logs
docker-compose logs -f

# Tail last 100 lines
docker-compose logs --tail=100
```

### Container Shell Access

```bash
# Backend
docker-compose exec backend sh

# Frontend (if using dev mode)
docker-compose exec frontend sh
```

### Network Inspection

```bash
# Inspect network
docker network inspect openpoke_openpoke-network

# Test connectivity from frontend to backend
docker-compose exec frontend wget -O- http://backend:8001/api/v1/health
```

### Volume Inspection

```bash
# List volumes
docker volume ls | grep openpoke

# Inspect volume
docker volume inspect openpoke_openpoke-data

# Access volume data
docker run --rm -it -v openpoke-data:/data alpine sh
```

## CI/CD Testing

### GitHub Actions (Example)

```yaml
name: Docker Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Build images
        run: |
          docker build -f server/Dockerfile -t openpoke-backend:test .
          docker build -f web/Dockerfile -t openpoke-frontend:test .
      
      - name: Start services
        run: |
          echo "OPENROUTER_API_KEY=test" > .env
          echo "COMPOSIO_API_KEY=test" >> .env
          echo "COMPOSIO_GMAIL_AUTH_CONFIG_ID=test" >> .env
          docker-compose up -d
      
      - name: Wait for services
        run: |
          sleep 30
      
      - name: Run tests
        run: |
          pip install -r tests/requirements.txt
          SKIP_DOCKER_IMAGE_TESTS=1 pytest tests/ -v
      
      - name: Show logs
        if: failure()
        run: docker-compose logs
```

## Test Results Documentation

### Expected Outcomes

All tests should:
- ✅ Pass on first run
- ✅ Be repeatable
- ✅ Clean up after themselves
- ✅ Provide clear error messages
- ✅ Run in under 5 minutes

### Known Limitations

- Volume tests require docker-compose control
- Some tests require actual API keys
- Integration tests depend on service startup time

## Reporting Issues

When reporting Docker-related issues, include:

1. Docker version: `docker --version`
2. Docker Compose version: `docker-compose --version`
3. OS and version
4. Output of `docker-compose logs`
5. Output of `docker-compose ps`
6. Steps to reproduce

## Cleanup

After testing:

```bash
# Stop services
docker-compose down

# Remove images
docker rmi openpoke-backend openpoke-frontend

# Remove volume (WARNING: deletes data)
docker volume rm openpoke_openpoke-data

# Clean up all
docker system prune -a
```


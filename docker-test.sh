#!/bin/bash
# Docker Build and Test Script for OpenPoke

set -e

echo "================================"
echo "OpenPoke Docker Build & Test"
echo "================================"
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if .env exists
if [ ! -f .env ]; then
    echo -e "${YELLOW}Warning: .env file not found${NC}"
    echo "Creating .env from template..."
    if [ -f .env.example ]; then
        cp .env.example .env
        echo -e "${GREEN}✓${NC} Created .env file"
        echo -e "${YELLOW}Please edit .env with your API keys before proceeding${NC}"
    else
        echo -e "${RED}✗${NC} .env.example not found"
        echo "Please create a .env file with your API keys"
        exit 1
    fi
fi

echo "Step 1: Building Docker images..."
echo "=================================="
echo ""

# Build backend
echo "Building backend image..."
docker build -f server/Dockerfile -t openpoke-backend:latest . || {
    echo -e "${RED}✗${NC} Backend build failed"
    exit 1
}
echo -e "${GREEN}✓${NC} Backend image built successfully"
echo ""

# Build frontend
echo "Building frontend image..."
docker build -f web/Dockerfile -t openpoke-frontend:latest . || {
    echo -e "${RED}✗${NC} Frontend build failed"
    exit 1
}
echo -e "${GREEN}✓${NC} Frontend image built successfully"
echo ""

echo "Step 2: Checking image sizes..."
echo "=================================="
docker images | grep openpoke
echo ""

echo "Step 3: Starting services with docker-compose..."
echo "================================================="
docker-compose up -d || {
    echo -e "${RED}✗${NC} Failed to start services"
    docker-compose logs
    exit 1
}
echo -e "${GREEN}✓${NC} Services started"
echo ""

echo "Step 4: Waiting for services to be ready..."
echo "==========================================="
sleep 10

# Check backend health
echo "Checking backend health..."
for i in {1..30}; do
    if curl -s http://localhost:8001/api/v1/health > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} Backend is healthy"
        break
    fi
    if [ $i -eq 30 ]; then
        echo -e "${RED}✗${NC} Backend health check failed"
        docker-compose logs backend
        exit 1
    fi
    sleep 2
done

# Check frontend
echo "Checking frontend..."
for i in {1..30}; do
    if curl -s http://localhost:3000 > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} Frontend is accessible"
        break
    fi
    if [ $i -eq 30 ]; then
        echo -e "${RED}✗${NC} Frontend check failed"
        docker-compose logs frontend
        exit 1
    fi
    sleep 2
done
echo ""

echo "Step 5: Running basic smoke tests..."
echo "===================================="

# Test backend health endpoint
echo -n "Testing backend health endpoint... "
HEALTH_RESPONSE=$(curl -s http://localhost:8001/api/v1/health)
if echo "$HEALTH_RESPONSE" | grep -q '"ok":true'; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗${NC}"
    echo "Response: $HEALTH_RESPONSE"
fi

# Test backend meta endpoint
echo -n "Testing backend meta endpoint... "
META_RESPONSE=$(curl -s http://localhost:8001/api/v1/meta)
if echo "$META_RESPONSE" | grep -q '"status":"ok"'; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗${NC}"
    echo "Response: $META_RESPONSE"
fi

# Test frontend
echo -n "Testing frontend accessibility... "
if curl -s http://localhost:3000 | grep -q "<!DOCTYPE html" || curl -s http://localhost:3000 | grep -q "<html"; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗${NC}"
fi

echo ""
echo "Step 6: Container status"
echo "========================"
docker-compose ps
echo ""

echo "Step 7: Data volume check"
echo "========================="
docker volume ls | grep openpoke
echo ""

echo "================================"
echo -e "${GREEN}Docker build and deployment successful!${NC}"
echo "================================"
echo ""
echo "Services:"
echo "  - Frontend: http://localhost:3000"
echo "  - Backend API: http://localhost:8001"
echo "  - API Docs: http://localhost:8001/docs"
echo ""
echo "Useful commands:"
echo "  View logs: docker-compose logs -f"
echo "  Stop services: docker-compose down"
echo "  Restart: docker-compose restart"
echo ""


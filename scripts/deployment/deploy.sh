#!/bin/bash
# Deployment script for js-craw on pi-forge
# Rebuilds Docker image and restarts containers after code changes

set -e

REPO_PATH="${1:-/home/admin/js-craw}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

cd "$REPO_PATH"

echo "=========================================="
echo "Starting deployment for js-craw"
echo "Repository: $REPO_PATH"
echo "Time: $(date)"
echo "=========================================="

# Check if docker-compose.yml exists
if [ ! -f "docker-compose.yml" ]; then
    echo "Error: docker-compose.yml not found in $REPO_PATH"
    exit 1
fi

# Get current commit info
CURRENT_COMMIT=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
echo "Current commit: $CURRENT_COMMIT"

# Build Docker image
echo ""
echo "Building Docker image..."
if docker compose build job-crawler; then
    echo "✓ Docker image built successfully"
else
    echo "✗ Docker build failed"
    exit 1
fi

# Restart containers with force recreate to ensure new images are used
echo ""
echo "Restarting containers with new images..."
if docker compose down && docker compose up -d --force-recreate; then
    echo "✓ Containers restarted successfully with new images"
else
    echo "✗ Container restart failed"
    exit 1
fi

# Wait for services to be healthy
echo ""
echo "Waiting for services to be healthy..."
sleep 5

# Check container status
echo ""
echo "Container status:"
docker-compose ps

# Check if API is responding
echo ""
echo "Checking API health..."
if curl -s -f http://localhost:8001/api/stats > /dev/null 2>&1; then
    echo "✓ API is responding"
else
    echo "⚠ API not responding yet (may need more time)"
fi

echo ""
echo "=========================================="
echo "Deployment complete!"
echo "=========================================="


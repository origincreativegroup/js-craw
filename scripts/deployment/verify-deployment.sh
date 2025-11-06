#!/bin/bash

# Deployment Verification Script for pi-forge
# Run this script on pi-forge to verify the last deployment

set -e

echo "🔍 Verifying Deployment on pi-forge"
echo "===================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if we're in the right directory
if [ -d "/home/admin/js-craw" ]; then
    DEPLOY_DIR="/home/admin/js-craw"
elif [ -d "/home/admin/docker/js-craw" ]; then
    DEPLOY_DIR="/home/admin/docker/js-craw"
else
    echo -e "${RED}✗ Cannot find deployment directory${NC}"
    exit 1
fi

cd "$DEPLOY_DIR"

echo "📂 Deployment Directory: $DEPLOY_DIR"
echo ""

# 1. Check last git commit
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📝 Last Git Commit"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ -d ".git" ]; then
    git log -1 --pretty=format:"%h - %an, %ar : %s"
    echo ""
    echo ""
    echo "Commit Date: $(git log -1 --format='%ai')"
    echo "Commit Hash: $(git log -1 --format='%H')"
else
    echo -e "${YELLOW}⚠ No .git directory found (this is normal if code was synced)${NC}"
    
    # Check deployment marker if it exists
    if [ -f "/home/admin/deployments/js-craw/current/DEPLOYMENT_INFO.txt" ]; then
        echo ""
        echo "Deployment Info:"
        cat /home/admin/deployments/js-craw/current/DEPLOYMENT_INFO.txt
    fi
fi
echo ""
echo ""

# 2. Check Docker containers
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🐳 Docker Container Status"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
docker compose ps
echo ""
echo ""

# 3. Check container health
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "💚 Container Health Checks"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
CONTAINERS=("job-crawler-app" "job-crawler-postgres" "job-crawler-redis" "job-crawler-selenium")

for container in "${CONTAINERS[@]}"; do
    if docker ps --format '{{.Names}}' | grep -q "^${container}$"; then
        STATUS=$(docker inspect --format='{{.State.Status}}' "$container" 2>/dev/null || echo "unknown")
        HEALTH=$(docker inspect --format='{{.State.Health.Status}}' "$container" 2>/dev/null || echo "no-healthcheck")
        
        if [ "$STATUS" == "running" ]; then
            if [ "$HEALTH" == "healthy" ] || [ "$HEALTH" == "no-healthcheck" ]; then
                echo -e "${GREEN}✓${NC} $container: $STATUS ($HEALTH)"
            else
                echo -e "${YELLOW}⚠${NC} $container: $STATUS ($HEALTH)"
            fi
        else
            echo -e "${RED}✗${NC} $container: $STATUS"
        fi
    else
        echo -e "${RED}✗${NC} $container: Not found"
    fi
done
echo ""
echo ""

# 4. Check application health endpoint
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🏥 Application Health Check"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if curl -f -s http://localhost:8001/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} Health endpoint responding"
    curl -s http://localhost:8001/health | python3 -m json.tool 2>/dev/null || curl -s http://localhost:8001/health
else
    echo -e "${RED}✗${NC} Health endpoint not responding"
fi
echo ""
echo ""

# 5. Check frontend files
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🎨 Frontend Files"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ -d "static" ]; then
    echo "Static directory found:"
    ls -lh static/ | head -10
    echo ""
    
    if [ -f "static/index.html" ]; then
        echo -e "${GREEN}✓${NC} static/index.html exists"
        FILE_SIZE=$(stat -f%z static/index.html 2>/dev/null || stat -c%s static/index.html 2>/dev/null || echo "unknown")
        echo "   Size: $FILE_SIZE bytes"
    else
        echo -e "${YELLOW}⚠${NC} static/index.html not found"
    fi
else
    echo -e "${YELLOW}⚠${NC} static/ directory not found"
fi
echo ""
echo ""

# 6. Test frontend accessibility
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🌐 Frontend Accessibility"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
FRONTEND_URL="http://localhost:8001/static/index.html"
if curl -f -s -o /dev/null -w "HTTP Status: %{http_code}\n" "$FRONTEND_URL" 2>/dev/null; then
    echo -e "${GREEN}✓${NC} Frontend accessible at $FRONTEND_URL"
else
    echo -e "${RED}✗${NC} Frontend not accessible at $FRONTEND_URL"
fi
echo ""
echo ""

# 7. Check container restart times
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔄 Container Restart Times"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
for container in "${CONTAINERS[@]}"; do
    if docker ps --format '{{.Names}}' | grep -q "^${container}$"; then
        STARTED=$(docker inspect --format='{{.State.StartedAt}}' "$container" 2>/dev/null || echo "unknown")
        echo "$container: $STARTED"
    fi
done
echo ""
echo ""

# 8. Check recent logs (last 5 lines)
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 Recent Application Logs (last 5 lines)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
docker compose logs --tail=5 job-crawler 2>/dev/null || echo "No logs available"
echo ""
echo ""

# 9. Summary
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 Summary"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

ALL_HEALTHY=true

# Check if all containers are running
for container in "${CONTAINERS[@]}"; do
    if ! docker ps --format '{{.Names}}' | grep -q "^${container}$"; then
        ALL_HEALTHY=false
        break
    fi
    STATUS=$(docker inspect --format='{{.State.Status}}' "$container" 2>/dev/null || echo "stopped")
    if [ "$STATUS" != "running" ]; then
        ALL_HEALTHY=false
        break
    fi
done

# Check health endpoint
if ! curl -f -s http://localhost:8001/health > /dev/null 2>&1; then
    ALL_HEALTHY=false
fi

if [ "$ALL_HEALTHY" = true ]; then
    echo -e "${GREEN}✅ Deployment appears successful!${NC}"
    echo ""
    echo "Access points:"
    echo "  - Dashboard: http://192.168.50.157:8001/static/index.html"
    echo "  - API Docs: http://192.168.50.157:8001/docs"
    echo "  - Health: http://192.168.50.157:8001/health"
else
    echo -e "${RED}❌ Some issues detected. Check the details above.${NC}"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"


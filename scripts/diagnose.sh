#!/bin/bash

echo "🔍 Job Crawler Diagnostics"
echo "=========================="
echo ""

# Check if Docker is running
echo "1. Checking Docker..."
if docker info > /dev/null 2>&1; then
    echo "   ✅ Docker is running"
else
    echo "   ❌ Docker is not running. Please start Docker."
    exit 1
fi

# Check if containers are running
echo ""
echo "2. Checking containers..."
containers=("job-crawler" "job-crawler-db" "job-crawler-ollama" "selenium-chrome" "selenium-hub")
all_running=true

for container in "${containers[@]}"; do
    if docker ps --format '{{.Names}}' | grep -q "^${container}$"; then
        echo "   ✅ $container is running"
    else
        echo "   ❌ $container is not running"
        all_running=false
    fi
done

if [ "$all_running" = false ]; then
    echo ""
    echo "   💡 Try: docker-compose up -d"
    exit 1
fi

# Check Ollama model
echo ""
echo "3. Checking Ollama model..."
if docker exec job-crawler-ollama ollama list 2>/dev/null | grep -q "llama2"; then
    echo "   ✅ Ollama model (llama2) is installed"
else
    echo "   ⚠️  Ollama model not found"
    echo "   💡 Run: docker exec job-crawler-ollama ollama pull llama2"
fi

# Check if .env exists
echo ""
echo "4. Checking configuration..."
if [ -f .env ]; then
    echo "   ✅ .env file exists"
    
    # Check for required variables
    if grep -q "NOTIFICATION_METHOD=" .env && grep -q "SECRET_KEY=" .env; then
        echo "   ✅ Required variables are set"
    else
        echo "   ⚠️  Some required variables may be missing"
    fi
else
    echo "   ❌ .env file not found"
    echo "   💡 Run: cp .env.example .env"
    exit 1
fi

# Check database connectivity
echo ""
echo "5. Checking database..."
if docker exec job-crawler-db psql -U jobcrawler -d jobcrawler -c "SELECT 1" > /dev/null 2>&1; then
    echo "   ✅ Database is accessible"
else
    echo "   ⚠️  Database connection issue"
fi

# Check API
echo ""
echo "6. Checking API..."
if curl -s http://localhost:8001/health > /dev/null 2>&1; then
    echo "   ✅ API is responding"
else
    echo "   ⚠️  API is not responding"
    echo "   💡 Check logs: docker-compose logs job-crawler"
fi

# Check recent logs for errors
echo ""
echo "7. Checking recent logs for errors..."
error_count=$(docker-compose logs --tail=100 job-crawler 2>/dev/null | grep -i "error\|exception\|failed" | wc -l)
if [ "$error_count" -eq 0 ]; then
    echo "   ✅ No recent errors found"
else
    echo "   ⚠️  Found $error_count error messages in recent logs"
    echo "   💡 View: docker-compose logs job-crawler | grep -i error"
fi

# Summary
echo ""
echo "=========================="
echo "📊 System Status Summary"
echo "=========================="

# Count running containers
running=$(docker ps --format '{{.Names}}' | wc -l)
echo "Running containers: $running/5"

# Get API status
api_status=$(curl -s http://localhost:8001/health 2>/dev/null | grep -o '"status":"[^"]*"' | cut -d'"' -f4)
if [ ! -z "$api_status" ]; then
    echo "API Status: $api_status"
fi

echo ""
echo "🔗 Quick Links:"
echo "   Dashboard: http://localhost:8001/static/index.html"
echo "   OpenWebUI: http://localhost:3000"
echo "   API Docs:  http://localhost:8001/docs"

echo ""
echo "💡 Common Commands:"
echo "   View logs:     docker-compose logs -f job-crawler"
echo "   Restart:       docker-compose restart"
echo "   Stop all:      docker-compose down"
echo "   Start all:     docker-compose up -d"
echo "   Check status:  docker-compose ps"

echo ""

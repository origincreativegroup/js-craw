#!/bin/bash
# Script to check crawl logs via API

API_URL="${API_URL:-http://localhost:8001}"

echo "Checking crawl status from $API_URL..."
echo ""

# Get crawl status
echo "=== CRAWL STATUS ==="
curl -s "$API_URL/api/crawl/status" | python3 -m json.tool 2>/dev/null || curl -s "$API_URL/api/crawl/status"

echo ""
echo ""
echo "=== RECENT JOBS (Last 20) ==="
curl -s "$API_URL/api/jobs?limit=20" | python3 -m json.tool 2>/dev/null || curl -s "$API_URL/api/jobs?limit=20"

echo ""
echo ""
echo "=== STATISTICS ==="
curl -s "$API_URL/api/stats" | python3 -m json.tool 2>/dev/null || curl -s "$API_URL/api/stats"


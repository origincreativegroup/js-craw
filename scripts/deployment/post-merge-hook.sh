#!/bin/bash
# Git post-merge hook for automatic deployment after git pull
# This hook runs automatically after a successful git merge/pull

set -e

REPO_PATH="/home/admin/js-craw"
DEPLOY_SCRIPT="$REPO_PATH/scripts/deployment/deploy.sh"
LOG_FILE="/home/admin/js-craw/deployment.log"

# Only run if we're in the main branch
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")

if [ "$CURRENT_BRANCH" != "main" ]; then
    echo "Not on main branch ($CURRENT_BRANCH), skipping auto-deployment"
    exit 0
fi

# Check if deploy script exists
if [ ! -f "$DEPLOY_SCRIPT" ]; then
    echo "Deploy script not found at $DEPLOY_SCRIPT, skipping auto-deployment"
    exit 0
fi

# Get commit info
COMMIT=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Post-merge hook triggered after pull (commit: $COMMIT)" >> "$LOG_FILE"

# Run deployment script
echo "🔄 Auto-deploying after git pull (commit: $COMMIT)..."
bash "$DEPLOY_SCRIPT" "$REPO_PATH" >> "$LOG_FILE" 2>&1

if [ $? -eq 0 ]; then
    echo "✅ Auto-deployment completed successfully"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Auto-deployment completed successfully" >> "$LOG_FILE"
else
    echo "❌ Auto-deployment failed, check $LOG_FILE for details"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Auto-deployment failed" >> "$LOG_FILE"
    exit 1
fi


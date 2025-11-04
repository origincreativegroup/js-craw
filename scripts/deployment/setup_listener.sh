#!/bin/bash
# Setup script for GitHub listener service

set -e

REPO_PATH="${1:-/home/admin/js-craw}"
BRANCH="${2:-main}"
INTERVAL="${3:-60}"

echo "Setting up GitHub listener service..."
echo "Repository: $REPO_PATH"
echo "Branch: $BRANCH"
echo "Check interval: ${INTERVAL}s"

# Create systemd service file
SERVICE_FILE="/etc/systemd/system/github-listener.service"
SCRIPT_PATH="$REPO_PATH/scripts/deployment/github_listener.py"

# Check if script exists
if [ ! -f "$SCRIPT_PATH" ]; then
    echo "Error: Listener script not found at $SCRIPT_PATH"
    exit 1
fi

# Create service file
sudo tee "$SERVICE_FILE" > /dev/null <<EOF
[Unit]
Description=GitHub Repository Listener
After=network.target

[Service]
Type=simple
User=admin
WorkingDirectory=$REPO_PATH
ExecStart=/usr/bin/python3 $SCRIPT_PATH \\
    --repo-path $REPO_PATH \\
    --branch $BRANCH \\
    --interval $INTERVAL
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

echo "Service file created: $SERVICE_FILE"

# Reload systemd
sudo systemctl daemon-reload

echo ""
echo "Service setup complete!"
echo ""
echo "To start the service:"
echo "  sudo systemctl start github-listener"
echo ""
echo "To enable on boot:"
echo "  sudo systemctl enable github-listener"
echo ""
echo "To check status:"
echo "  sudo systemctl status github-listener"
echo ""
echo "To view logs:"
echo "  sudo journalctl -u github-listener -f"


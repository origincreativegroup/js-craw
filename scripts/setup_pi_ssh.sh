#!/bin/bash

# Setup SSH for Raspberry Pi servers (pi-net and pi-forge)
# This script helps copy your SSH key to the Pi servers

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}Pi Server SSH Setup${NC}"
echo "==================="
echo ""

# Get SSH public key
if [ -f ~/.ssh/id_ed25519.pub ]; then
    PUB_KEY=~/.ssh/id_ed25519.pub
elif [ -f ~/.ssh/id_rsa.pub ]; then
    PUB_KEY=~/.ssh/id_rsa.pub
else
    echo -e "${RED}No SSH public key found!${NC}"
    exit 1
fi

echo -e "${YELLOW}Your SSH public key:${NC}"
cat "$PUB_KEY"
echo ""

# Function to copy key to a server
copy_key_to_server() {
    local host=$1
    local hostname=$2
    
    echo -e "${YELLOW}Setting up SSH for ${host} (${hostname})...${NC}"
    
    # Test if we can connect
    if ssh -o ConnectTimeout=5 -o PreferredAuthentications=publickey "$host" "echo 'SSH key already works!'" 2>/dev/null; then
        echo -e "${GREEN}✓ SSH key already configured for ${host}${NC}"
        return 0
    fi
    
    echo -e "${YELLOW}You'll need to enter your password for ${host}${NC}"
    echo ""
    
    # Method 1: Try ssh-copy-id
    if ssh-copy-id "$host" 2>&1 | grep -q "Number of key(s) added"; then
        echo -e "${GREEN}✓ SSH key copied to ${host}${NC}"
        return 0
    fi
    
    # Method 2: Manual copy
    echo -e "${YELLOW}Manual method: Copying key to ${host}...${NC}"
    
    # Create the command to run on remote server
    cat "$PUB_KEY" | ssh "$host" "mkdir -p ~/.ssh && chmod 700 ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys" 2>&1
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ SSH key copied to ${host}${NC}"
    else
        echo -e "${RED}✗ Failed to copy key to ${host}${NC}"
        echo ""
        echo -e "${YELLOW}Manual steps for ${host}:${NC}"
        echo "1. SSH to the server: ssh ${host}"
        echo "2. Run these commands:"
        echo "   mkdir -p ~/.ssh"
        echo "   chmod 700 ~/.ssh"
        echo "   echo '$(cat "$PUB_KEY")' >> ~/.ssh/authorized_keys"
        echo "   chmod 600 ~/.ssh/authorized_keys"
        return 1
    fi
}

# Setup pi-net
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}Setting up pi-net${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
copy_key_to_server "pi-net" "192.168.50.70"
echo ""

# Setup pi-forge
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}Setting up pi-forge${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
copy_key_to_server "pi-forge" "192.168.50.158"
echo ""

# Test connections
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}Testing connections...${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

for host in pi-net pi-forge; do
    echo -e "${YELLOW}Testing ${host}...${NC}"
    if ssh -o ConnectTimeout=5 "$host" "echo '✓ Connected to ${host} as $(whoami)@$(hostname)'" 2>/dev/null; then
        echo -e "${GREEN}✓ ${host} is working!${NC}"
    else
        echo -e "${RED}✗ ${host} connection failed${NC}"
    fi
    echo ""
done

echo -e "${GREEN}Setup complete!${NC}"
echo ""
echo "You can now connect with:"
echo "  ssh pi-net"
echo "  ssh pi-forge"


#!/bin/bash

# SSH Setup Script for js-craw
# This script helps set up SSH keys for GitHub/GitLab and configures SSH

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}SSH Setup Script${NC}"
echo "=================="
echo ""

# Check if SSH directory exists
if [ ! -d ~/.ssh ]; then
    echo -e "${YELLOW}Creating ~/.ssh directory...${NC}"
    mkdir -p ~/.ssh
    chmod 700 ~/.ssh
fi

# Check for existing SSH keys
echo -e "${YELLOW}Checking for existing SSH keys...${NC}"
if [ -f ~/.ssh/id_ed25519 ] || [ -f ~/.ssh/id_rsa ]; then
    echo -e "${GREEN}SSH key found!${NC}"
    ls -la ~/.ssh/*.pub 2>/dev/null || echo "No public keys found"
    echo ""
    read -p "Do you want to generate a new key? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${GREEN}Using existing keys.${NC}"
        EXISTING_KEY=true
    fi
fi

# Generate SSH key if needed
if [ "$EXISTING_KEY" != "true" ]; then
    echo -e "${YELLOW}Generating new SSH key...${NC}"
    read -p "Enter your email address: " email
    
    # Try ed25519 first, fallback to RSA
    if ssh-keygen -t ed25519 -C "$email" -f ~/.ssh/id_ed25519 -N "" 2>/dev/null; then
        KEY_FILE=~/.ssh/id_ed25519
        echo -e "${GREEN}✓ Generated ed25519 key${NC}"
    elif ssh-keygen -t rsa -b 4096 -C "$email" -f ~/.ssh/id_rsa -N "" 2>/dev/null; then
        KEY_FILE=~/.ssh/id_rsa
        echo -e "${GREEN}✓ Generated RSA key${NC}"
    else
        echo -e "${RED}Failed to generate SSH key${NC}"
        exit 1
    fi
    
    # Set proper permissions
    chmod 600 "$KEY_FILE"
    chmod 644 "${KEY_FILE}.pub"
fi

# Determine which key to use
if [ -f ~/.ssh/id_ed25519 ]; then
    KEY_FILE=~/.ssh/id_ed25519
elif [ -f ~/.ssh/id_rsa ]; then
    KEY_FILE=~/.ssh/id_rsa
else
    echo -e "${RED}No SSH key found!${NC}"
    exit 1
fi

# Start SSH agent
echo -e "${YELLOW}Starting SSH agent...${NC}"
eval "$(ssh-agent -s)" > /dev/null

# Add key to agent
echo -e "${YELLOW}Adding key to SSH agent...${NC}"
if ssh-add "$KEY_FILE" 2>/dev/null; then
    echo -e "${GREEN}✓ Key added to SSH agent${NC}"
else
    echo -e "${YELLOW}Note: Key may require a passphrase${NC}"
fi

# Display public key
echo ""
echo -e "${GREEN}Your public SSH key:${NC}"
echo "----------------------------------------"
cat "${KEY_FILE}.pub"
echo "----------------------------------------"
echo ""

# Copy to clipboard if on macOS
if command -v pbcopy &> /dev/null; then
    cat "${KEY_FILE}.pub" | pbcopy
    echo -e "${GREEN}✓ Public key copied to clipboard${NC}"
    echo ""
fi

# Create SSH config if it doesn't exist
if [ ! -f ~/.ssh/config ]; then
    echo -e "${YELLOW}Creating SSH config file...${NC}"
    touch ~/.ssh/config
    chmod 600 ~/.ssh/config
    
    # Add basic GitHub configuration
    cat >> ~/.ssh/config <<EOF

# GitHub
Host github.com
    HostName github.com
    User git
    IdentityFile $KEY_FILE
    AddKeysToAgent yes
    UseKeychain yes

EOF
    echo -e "${GREEN}✓ SSH config created${NC}"
fi

# Instructions
echo ""
echo -e "${GREEN}Next steps:${NC}"
echo "1. Add your public key to GitHub:"
echo "   https://github.com/settings/keys"
echo ""
echo "2. Add your public key to GitLab (if needed):"
echo "   https://gitlab.com/-/profile/keys"
echo ""
echo "3. Test your connection:"
echo "   ssh -T git@github.com"
echo ""

# Optionally test GitHub connection
read -p "Do you want to test GitHub connection now? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}Testing GitHub connection...${NC}"
    if ssh -T git@github.com 2>&1 | grep -q "successfully authenticated"; then
        echo -e "${GREEN}✓ GitHub connection successful!${NC}"
    else
        echo -e "${YELLOW}Note: You may need to add your key to GitHub first${NC}"
    fi
fi

echo ""
echo -e "${GREEN}SSH setup complete!${NC}"


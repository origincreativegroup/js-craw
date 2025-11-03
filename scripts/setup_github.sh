#!/bin/bash

# GitHub Setup Script
# Helps set up GitHub repository and push code

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}GitHub Repository Setup${NC}"
echo "========================"
echo ""

# Check if SSH key is added to GitHub
echo -e "${YELLOW}Testing GitHub SSH connection...${NC}"
if ssh -T git@github.com 2>&1 | grep -q "successfully authenticated"; then
    echo -e "${GREEN}✓ SSH key is configured on GitHub${NC}"
    SSH_WORKING=true
else
    echo -e "${YELLOW}⚠ SSH key not yet added to GitHub${NC}"
    echo ""
    echo "Your SSH public key:"
    cat ~/.ssh/id_ed25519.pub 2>/dev/null || cat ~/.ssh/id_rsa.pub
    echo ""
    echo -e "${YELLOW}Please add this key to GitHub:${NC}"
    echo "1. Go to: https://github.com/settings/keys"
    echo "2. Click 'New SSH key'"
    echo "3. Paste the key above and save"
    echo ""
    read -p "Press Enter after adding the key to GitHub..."
    SSH_WORKING=false
fi

# Get repository URL
echo ""
read -p "Enter your GitHub repository URL (e.g., git@github.com:username/js-craw.git): " repo_url

if [ -z "$repo_url" ]; then
    echo -e "${YELLOW}No URL provided. Creating repository setup instructions...${NC}"
    echo ""
    echo "To create a new repository:"
    echo "1. Go to: https://github.com/new"
    echo "2. Repository name: js-craw"
    echo "3. Choose Public or Private"
    echo "4. DO NOT initialize with README (we already have one)"
    echo "5. Click 'Create repository'"
    echo "6. Copy the SSH URL (git@github.com:username/js-craw.git)"
    echo ""
    read -p "Enter the repository URL now: " repo_url
fi

if [ -z "$repo_url" ]; then
    echo -e "${YELLOW}No repository URL provided. Exiting.${NC}"
    exit 1
fi

# Add remote
echo ""
echo -e "${YELLOW}Adding GitHub remote...${NC}"
if git remote get-url origin &>/dev/null; then
    echo -e "${YELLOW}Remote 'origin' already exists. Updating...${NC}"
    git remote set-url origin "$repo_url"
else
    git remote add origin "$repo_url"
fi
echo -e "${GREEN}✓ Remote added${NC}"

# Test SSH connection again if needed
if [ "$SSH_WORKING" != "true" ]; then
    echo ""
    echo -e "${YELLOW}Testing GitHub connection again...${NC}"
    if ssh -T git@github.com 2>&1 | grep -q "successfully authenticated"; then
        echo -e "${GREEN}✓ SSH connection working!${NC}"
    else
        echo -e "${YELLOW}⚠ SSH still not working. Please verify your key is added to GitHub.${NC}"
        exit 1
    fi
fi

# Push to GitHub
echo ""
read -p "Ready to push to GitHub? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}Pushing to GitHub...${NC}"
    git push -u origin main
    echo ""
    echo -e "${GREEN}✓ Code pushed to GitHub!${NC}"
    echo ""
    echo "Repository URL: ${repo_url/git@github.com:/https:\/\/github.com\/}"
    echo "Remove .git from the end to get the web URL"
else
    echo -e "${YELLOW}Skipping push. You can push manually with:${NC}"
    echo "  git push -u origin main"
fi


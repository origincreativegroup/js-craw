# SSH Complete Guide

A comprehensive guide to SSH (Secure Shell) setup, configuration, and troubleshooting for development and remote server access.

## Table of Contents

1. [Quick Start](#quick-start)
2. [SSH Key Generation](#ssh-key-generation)
3. [SSH Agent Setup](#ssh-agent-setup)
4. [GitHub/GitLab Integration](#githubgitlab-integration)
5. [Remote Server Access](#remote-server-access)
6. [Raspberry Pi Setup](#raspberry-pi-setup)
7. [SSH Configuration](#ssh-configuration)
8. [Troubleshooting](#troubleshooting)
9. [Security Best Practices](#security-best-practices)
10. [Advanced Usage](#advanced-usage)

---

## Quick Start

### Automated Setup

For GitHub/GitLab:
```bash
chmod +x scripts/setup_ssh.sh
./scripts/setup_ssh.sh
```

For Raspberry Pi servers:
```bash
./scripts/setup_pi_ssh.sh
```

### Manual Quick Setup

```bash
# 1. Generate SSH key
ssh-keygen -t ed25519 -C "your_email@example.com"

# 2. Start SSH agent
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/id_ed25519

# 3. Copy public key to server
ssh-copy-id user@server.example.com

# 4. Test connection
ssh user@server.example.com
```

---

## SSH Key Generation

### Generate Ed25519 Key (Recommended)

Ed25519 is more secure and faster than RSA:

```bash
ssh-keygen -t ed25519 -C "your_email@example.com" -f ~/.ssh/id_ed25519
```

**When prompted:**
- Press Enter to accept default location (`~/.ssh/id_ed25519`)
- Optionally enter a passphrase for extra security
- Press Enter again to confirm

### Generate RSA Key (Alternative)

If Ed25519 is not supported, use RSA:

```bash
ssh-keygen -t rsa -b 4096 -C "your_email@example.com" -f ~/.ssh/id_rsa
```

### Generate Multiple Keys

For different purposes (personal, work, servers):

```bash
# Personal key
ssh-keygen -t ed25519 -C "personal@example.com" -f ~/.ssh/id_ed25519_personal

# Work key
ssh-keygen -t ed25519 -C "work@example.com" -f ~/.ssh/id_ed25519_work

# Server key
ssh-keygen -t ed25519 -C "server@example.com" -f ~/.ssh/id_ed25519_server
```

### View Your Public Key

```bash
# Ed25519
cat ~/.ssh/id_ed25519.pub

# RSA
cat ~/.ssh/id_rsa.pub
```

### Key File Permissions

Ensure correct permissions:

```bash
chmod 700 ~/.ssh
chmod 600 ~/.ssh/id_ed25519      # Private key
chmod 644 ~/.ssh/id_ed25519.pub  # Public key
```

---

## SSH Agent Setup

The SSH agent manages your keys and provides single sign-on functionality.

### Start SSH Agent

```bash
# Start the agent
eval "$(ssh-agent -s)"

# Add your key
ssh-add ~/.ssh/id_ed25519

# Or for RSA
ssh-add ~/.ssh/id_rsa
```

### List Loaded Keys

```bash
ssh-add -l
```

### Remove a Key

```bash
ssh-add -d ~/.ssh/id_ed25519
```

### Remove All Keys

```bash
ssh-add -D
```

### Auto-Start SSH Agent (macOS/Linux)

Add to your shell profile (`~/.zshrc` or `~/.bashrc`):

```bash
# Auto-start SSH agent
if [ -z "$SSH_AUTH_SOCK" ]; then
   eval "$(ssh-agent -s)"
   ssh-add ~/.ssh/id_ed25519 2>/dev/null
fi
```

### Persistent SSH Agent (macOS)

For macOS, use Keychain integration:

```bash
# Add to Keychain (will persist across reboots)
ssh-add --apple-use-keychain ~/.ssh/id_ed25519
```

Add to `~/.ssh/config`:
```
Host *
  AddKeysToAgent yes
  UseKeychain yes
  IdentityFile ~/.ssh/id_ed25519
```

---

## GitHub/GitLab Integration

### Add SSH Key to GitHub

1. **Copy your public key:**
   ```bash
   cat ~/.ssh/id_ed25519.pub | pbcopy  # macOS
   cat ~/.ssh/id_ed25519.pub | xclip  # Linux
   cat ~/.ssh/id_ed25519.pub           # Display to copy manually
   ```

2. **Add to GitHub:**
   - Go to GitHub → Settings → SSH and GPG keys
   - Click "New SSH key"
   - Paste your public key
   - Give it a descriptive title
   - Click "Add SSH key"

3. **Test connection:**
   ```bash
   ssh -T git@github.com
   ```
   You should see: `Hi username! You've successfully authenticated...`

### Add SSH Key to GitLab

1. **Copy your public key** (same as above)

2. **Add to GitLab:**
   - Go to GitLab → Preferences → SSH Keys
   - Paste your public key
   - Give it a title
   - Click "Add key"

3. **Test connection:**
   ```bash
   ssh -T git@gitlab.com
   ```

### Clone Repository with SSH

```bash
# GitHub
git clone git@github.com:username/repo.git

# GitLab
git clone git@gitlab.com:username/repo.git
```

### Multiple GitHub Accounts

If you need separate keys for personal and work accounts:

1. **Generate separate keys:**
   ```bash
   ssh-keygen -t ed25519 -C "personal@example.com" -f ~/.ssh/id_ed25519_personal
   ssh-keygen -t ed25519 -C "work@example.com" -f ~/.ssh/id_ed25519_work
   ```

2. **Configure SSH config** (`~/.ssh/config`):
   ```
   # Personal GitHub
   Host github.com-personal
       HostName github.com
       User git
       IdentityFile ~/.ssh/id_ed25519_personal

   # Work GitHub
   Host github.com-work
       HostName github.com
       User git
       IdentityFile ~/.ssh/id_ed25519_work
   ```

3. **Use different hosts:**
   ```bash
   # Personal repo
   git clone git@github.com-personal:username/personal-repo.git

   # Work repo
   git clone git@github.com-work:company/work-repo.git
   ```

4. **Update existing remotes:**
   ```bash
   git remote set-url origin git@github.com-personal:username/repo.git
   ```

---

## Remote Server Access

### Copy SSH Key to Server

**Method 1: Using ssh-copy-id (Recommended)**

```bash
ssh-copy-id user@server.example.com
```

**Method 2: Manual Copy**

```bash
# 1. Display your public key
cat ~/.ssh/id_ed25519.pub

# 2. SSH to server
ssh user@server.example.com

# 3. On server, create .ssh directory
mkdir -p ~/.ssh
chmod 700 ~/.ssh

# 4. Add your public key
nano ~/.ssh/authorized_keys
# Paste your public key, save and exit

# 5. Set permissions
chmod 600 ~/.ssh/authorized_keys
```

**Method 3: Using SCP**

```bash
cat ~/.ssh/id_ed25519.pub | ssh user@server.example.com "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys"
```

### Test Passwordless Login

```bash
ssh user@server.example.com
# Should connect without asking for password
```

### Run Remote Commands

```bash
# Single command
ssh user@server.example.com "uptime"

# Multiple commands
ssh user@server.example.com "df -h && free -m"

# With output
ssh user@server.example.com "ls -la /var/log" > log_list.txt
```

### Copy Files with SCP

```bash
# Copy file to server
scp file.txt user@server.example.com:~/

# Copy file from server
scp user@server.example.com:~/file.txt ./

# Copy directory
scp -r directory user@server.example.com:~/

# Copy with progress
scp -P 2222 -r directory user@server.example.com:~/  # Custom port
```

### Copy Files with RSYNC

```bash
# Sync directory
rsync -avz local_directory/ user@server.example.com:~/remote_directory/

# Exclude files
rsync -avz --exclude '*.log' local_directory/ user@server.example.com:~/remote_directory/

# Dry run (see what would be copied)
rsync -avz --dry-run local_directory/ user@server.example.com:~/remote_directory/
```

---

## Raspberry Pi Setup

### Quick Setup for Pi Servers

Your Raspberry Pi servers are configured in `~/.ssh/config`:

- **pi-net**: 192.168.50.70 (user: origin)
- **pi-forge**: 192.168.50.158 (user: origin)

### Automated Setup

```bash
./scripts/setup_pi_ssh.sh
```

### Manual Setup

```bash
# Copy key to pi-net
ssh-copy-id pi-net

# Copy key to pi-forge
ssh-copy-id pi-forge

# Test connections
ssh pi-net "echo 'Connected!'"
ssh pi-forge "echo 'Connected!'"
```

### Connect to Pi Servers

```bash
# Connect to pi-net
ssh pi-net

# Connect to pi-forge
ssh pi-forge

# Run commands remotely
ssh pi-net "uptime"
ssh pi-forge "df -h"
```

---

## SSH Configuration

The `~/.ssh/config` file allows you to create shortcuts and set default options for SSH connections.

### Create SSH Config File

```bash
touch ~/.ssh/config
chmod 600 ~/.ssh/config
```

### Basic Server Configuration

```bash
Host myserver
    HostName example.com
    User your_username
    Port 22
    IdentityFile ~/.ssh/id_ed25519
    ServerAliveInterval 60
    ServerAliveCountMax 3
```

Then connect with:
```bash
ssh myserver  # Instead of ssh user@example.com
```

### Multiple Server Configuration

```
# Production Server
Host production
    HostName prod.example.com
    User deploy
    Port 2222
    IdentityFile ~/.ssh/id_ed25519
    ForwardAgent yes
    ServerAliveInterval 60
    ServerAliveCountMax 3

# Staging Server
Host staging
    HostName staging.example.com
    User deploy
    IdentityFile ~/.ssh/id_ed25519
    ServerAliveInterval 60

# Development Server
Host dev
    HostName dev.example.com
    User developer
    IdentityFile ~/.ssh/id_ed25519_dev
    LocalForward 8080 localhost:8080
```

### Raspberry Pi Configuration

```
Host pi-net
    HostName 192.168.50.70
    User origin
    IdentityFile ~/.ssh/id_ed25519
    ServerAliveInterval 60
    ServerAliveCountMax 3
    ForwardAgent yes

Host pi-forge
    HostName 192.168.50.158
    User origin
    IdentityFile ~/.ssh/id_ed25519
    ServerAliveInterval 60
    ServerAliveCountMax 3
    ForwardAgent yes
```

### Useful SSH Config Options

```
Host *
    # Keep connections alive
    ServerAliveInterval 60
    ServerAliveCountMax 3
    
    # SSH agent forwarding
    ForwardAgent yes
    
    # Compression for slow connections
    Compression yes
    
    # Control master for faster connections
    ControlMaster auto
    ControlPath ~/.ssh/control-%h-%p-%r
    ControlPersist 10m

Host specific-server
    # Jump host (bastion/proxy)
    ProxyJump bastion.example.com
    
    # Port forwarding
    LocalForward 8888 localhost:8888
    RemoteForward 3306 localhost:3306
    
    # Custom port
    Port 2222
    
    # Strict host key checking
    StrictHostKeyChecking yes
    UserKnownHostsFile ~/.ssh/known_hosts
    
    # Connect timeout
    ConnectTimeout 10
```

---

## Troubleshooting

### SSH Key Not Working

**1. Check if key is added to agent:**
```bash
ssh-add -l
```

**2. Re-add key if needed:**
```bash
ssh-add ~/.ssh/id_ed25519
```

**3. Check permissions:**
```bash
chmod 700 ~/.ssh
chmod 600 ~/.ssh/id_ed25519
chmod 644 ~/.ssh/id_ed25519.pub
```

**4. Verify key format:**
```bash
# Check if key is valid
ssh-keygen -l -f ~/.ssh/id_ed25519.pub
```

### Connection Refused

**1. Check if server is reachable:**
```bash
ping server.example.com
```

**2. Check if SSH service is running:**
```bash
ssh -v user@server.example.com
```

**3. Verify port number:**
```bash
ssh -p 2222 user@server.example.com  # If using non-standard port
```

**4. Check firewall settings:**
```bash
# On server
sudo ufw status
sudo iptables -L
```

### Permission Denied

**1. Verify public key is on server:**
```bash
ssh user@server.example.com "cat ~/.ssh/authorized_keys"
```

**2. Check file permissions on server:**
```bash
ssh user@server.example.com "ls -la ~/.ssh/"
```

Should show:
- `~/.ssh/` directory: permissions 700 (drwx------)
- `~/.ssh/authorized_keys`: permissions 600 (-rw-------)

**3. Fix permissions on server:**
```bash
ssh user@server.example.com "chmod 700 ~/.ssh && chmod 600 ~/.ssh/authorized_keys"
```

**4. Check SSH server configuration:**
```bash
# On server
sudo nano /etc/ssh/sshd_config
# Ensure these are set:
# PubkeyAuthentication yes
# AuthorizedKeysFile .ssh/authorized_keys
sudo systemctl restart sshd
```

### Host Key Verification Failed

**1. Remove old host key:**
```bash
ssh-keygen -R server.example.com
```

**2. Add new host key:**
```bash
ssh-keyscan -H server.example.com >> ~/.ssh/known_hosts
```

**3. Disable strict checking (not recommended for production):**
Add to `~/.ssh/config`:
```
Host server.example.com
    StrictHostKeyChecking no
    UserKnownHostsFile /dev/null
```

### SSH Agent Not Remembering Keys

**1. Check if agent is running:**
```bash
echo $SSH_AUTH_SOCK
```

**2. Restart agent:**
```bash
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/id_ed25519
```

**3. Add to shell profile:**
```bash
# Add to ~/.zshrc or ~/.bashrc
if [ -z "$SSH_AUTH_SOCK" ]; then
   eval "$(ssh-agent -s)"
   ssh-add ~/.ssh/id_ed25519 2>/dev/null
fi
```

### Wrong Username

**1. Update SSH config:**
```bash
nano ~/.ssh/config
```

**2. Specify user in connection:**
```bash
ssh correct_user@server.example.com
```

### Slow Connection

**1. Enable compression:**
Add to `~/.ssh/config`:
```
Host slow-server
    Compression yes
```

**2. Use ControlMaster (faster subsequent connections):**
```
Host *
    ControlMaster auto
    ControlPath ~/.ssh/control-%h-%p-%r
    ControlPersist 10m
```

**3. Check network:**
```bash
ping server.example.com
traceroute server.example.com
```

### Verbose Debugging

```bash
# Level 1: Basic debugging
ssh -v user@server.example.com

# Level 2: More detailed
ssh -vv user@server.example.com

# Level 3: Maximum verbosity
ssh -vvv user@server.example.com
```

---

## Security Best Practices

### 1. Use Strong Key Types

- **Preferred**: Ed25519 (faster, more secure)
- **Alternative**: RSA with 4096-bit keys
- **Avoid**: RSA with < 2048 bits

### 2. Use Passphrases

Always use strong passphrases for your private keys:
```bash
ssh-keygen -t ed25519 -C "your_email@example.com"
# Enter a strong passphrase when prompted
```

### 3. Never Share Private Keys

- **Private keys** (`id_ed25519`, `id_rsa`) - NEVER share
- **Public keys** (`id_ed25519.pub`, `id_rsa.pub`) - Safe to share

### 4. Rotate Keys Regularly

Rotate SSH keys every 6-12 months:
```bash
# Generate new key
ssh-keygen -t ed25519 -C "your_email@example.com" -f ~/.ssh/id_ed25519_new

# Add new public key to servers/services
# Remove old key after confirming new one works
```

### 5. Use Different Keys for Different Purposes

- Personal GitHub account → Separate key
- Work GitHub account → Separate key
- Production servers → Separate key
- Development servers → Separate key

### 6. Keep Private Keys Encrypted

- Use passphrases
- Store keys in secure locations
- Consider using hardware security modules (HSMs) for production

### 7. Limit SSH Access

**On server, configure `/etc/ssh/sshd_config`:**
```
# Disable password authentication (use keys only)
PasswordAuthentication no
PubkeyAuthentication yes

# Disable root login
PermitRootLogin no

# Limit users who can SSH
AllowUsers username1 username2

# Change default port (optional)
Port 2222
```

### 8. Use SSH Agent Forwarding Carefully

Only enable agent forwarding when necessary:
```
Host specific-server
    ForwardAgent yes  # Only for trusted servers
```

### 9. Monitor SSH Access

```bash
# View SSH login attempts
sudo tail -f /var/log/auth.log  # Linux
sudo tail -f /var/log/system.log  # macOS

# Check who's logged in
who
w
```

### 10. Use Firewall Rules

```bash
# Allow SSH only from specific IPs
sudo ufw allow from 192.168.1.0/24 to any port 22
sudo ufw enable
```

---

## Advanced Usage

### Port Forwarding

**Local Port Forwarding (Forward remote port to local):**
```bash
# Forward remote port 3306 to local port 3306
ssh -L 3306:localhost:3306 user@server.example.com

# Access remote database via localhost:3306
mysql -h localhost -P 3306
```

**Remote Port Forwarding (Forward local port to remote):**
```bash
# Forward local port 8080 to remote port 8080
ssh -R 8080:localhost:8080 user@server.example.com
```

**Dynamic Port Forwarding (SOCKS proxy):**
```bash
# Create SOCKS proxy on local port 1080
ssh -D 1080 user@server.example.com

# Configure browser to use SOCKS5 proxy on localhost:1080
```

### SSH Tunneling

**Create persistent tunnel:**
```bash
# Background tunnel
ssh -f -N -L 3306:localhost:3306 user@server.example.com

# With keepalive
ssh -f -N -o ServerAliveInterval=60 -L 3306:localhost:3306 user@server.example.com
```

### Jump Host (Bastion)

**Connect through jump host:**
```bash
# Using command line
ssh -J bastion.example.com user@internal-server.example.com

# Using config
```

In `~/.ssh/config`:
```
Host bastion
    HostName bastion.example.com
    User bastion_user
    IdentityFile ~/.ssh/id_ed25519

Host internal-server
    HostName internal-server.example.com
    User internal_user
    IdentityFile ~/.ssh/id_ed25519
    ProxyJump bastion
```

Then connect:
```bash
ssh internal-server
```

### SSH Agent Forwarding

**Forward your SSH agent to remote server:**
```bash
ssh -A user@server.example.com
```

Or in config:
```
Host server
    ForwardAgent yes
```

**Use forwarded agent:**
```bash
# On remote server
ssh git@github.com  # Uses your local SSH key
```

### Execute Commands on Remote Server

```bash
# Single command
ssh user@server.example.com "ls -la"

# Multiple commands
ssh user@server.example.com "cd /var/log && tail -f syslog"

# With sudo
ssh user@server.example.com "sudo systemctl restart nginx"

# Run local script on remote
cat script.sh | ssh user@server.example.com "bash"
```

### SCP and RSYNC

**SCP Examples:**
```bash
# Copy file
scp file.txt user@server.example.com:~/

# Copy with custom port
scp -P 2222 file.txt user@server.example.com:~/

# Copy directory
scp -r directory user@server.example.com:~/

# Preserve permissions
scp -p file.txt user@server.example.com:~/
```

**RSYNC Examples:**
```bash
# Sync directory
rsync -avz local_dir/ user@server.example.com:~/remote_dir/

# Sync with progress
rsync -avz --progress local_dir/ user@server.example.com:~/remote_dir/

# Exclude files
rsync -avz --exclude '*.log' --exclude '*.tmp' local_dir/ user@server.example.com:~/remote_dir/

# Delete files on destination that don't exist in source
rsync -avz --delete local_dir/ user@server.example.com:~/remote_dir/

# Dry run
rsync -avz --dry-run local_dir/ user@server.example.com:~/remote_dir/
```

### ControlMaster (Faster Connections)

**Enable ControlMaster in config:**
```
Host *
    ControlMaster auto
    ControlPath ~/.ssh/control-%h-%p-%r
    ControlPersist 10m
```

This creates a master connection that persists for 10 minutes, making subsequent connections much faster.

### SSH Config Inheritance

**Use wildcards and inheritance:**
```
# Default settings for all hosts
Host *
    ServerAliveInterval 60
    ServerAliveCountMax 3
    Compression yes

# Override for specific hosts
Host github.com
    Compression no  # GitHub is fast, no need for compression

Host *.example.com
    User admin
    IdentityFile ~/.ssh/id_ed25519_work
```

### Key Management Scripts

**List all keys:**
```bash
for key in ~/.ssh/id_*; do
    if [[ ! "$key" =~ \.pub$ ]]; then
        echo "Key: $key"
        ssh-keygen -l -f "$key.pub" 2>/dev/null || echo "  No public key found"
    fi
done
```

**Test all keys:**
```bash
# Test GitHub
ssh -T git@github.com

# Test GitLab
ssh -T git@gitlab.com

# Test server
ssh -T user@server.example.com
```

---

## Quick Reference

### Common Commands

```bash
# Generate key
ssh-keygen -t ed25519 -C "email@example.com"

# Start agent
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/id_ed25519

# Copy key to server
ssh-copy-id user@server.example.com

# Connect
ssh user@server.example.com

# Run command
ssh user@server.example.com "command"

# Copy file
scp file.txt user@server.example.com:~/

# Copy directory
scp -r directory user@server.example.com:~/

# Sync directory
rsync -avz local_dir/ user@server.example.com:~/remote_dir/

# Port forward
ssh -L 3306:localhost:3306 user@server.example.com

# Jump host
ssh -J bastion.example.com user@internal.example.com

# Test connection
ssh -T git@github.com
```

### File Locations

```
~/.ssh/id_ed25519          # Private key (keep secret!)
~/.ssh/id_ed25519.pub      # Public key (safe to share)
~/.ssh/config              # SSH configuration
~/.ssh/known_hosts         # Known host keys
~/.ssh/authorized_keys     # Authorized keys (on server)
```

### Common Ports

- **22**: Default SSH port
- **2222**: Alternative SSH port (common alternative)
- **443**: SSH over HTTPS (for bypassing firewalls)

---

## Additional Resources

- [GitHub SSH Setup Guide](https://docs.github.com/en/authentication/connecting-to-github-with-ssh)
- [GitLab SSH Setup Guide](https://docs.gitlab.com/ee/user/ssh.html)
- [OpenSSH Documentation](https://www.openssh.com/manual.html)
- [SSH Best Practices](https://www.ssh.com/academy/ssh)

---

**Last Updated**: 2024


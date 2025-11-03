# SSH Setup Guide

This guide will help you set up SSH for your development environment, including:
- Generating SSH keys for GitHub/GitLab
- Configuring SSH for remote server access
- Setting up SSH agent for key management

## Quick Setup

Run the automated setup script:
```bash
chmod +x scripts/setup_ssh.sh
./scripts/setup_ssh.sh
```

Or follow the manual steps below.

## Manual Setup

### 1. Generate SSH Key Pair

Generate a new SSH key for GitHub/GitLab:

```bash
# Generate a new SSH key (replace with your email)
ssh-keygen -t ed25519 -C "your_email@example.com" -f ~/.ssh/id_ed25519

# Or if ed25519 is not supported, use RSA:
ssh-keygen -t rsa -b 4096 -C "your_email@example.com" -f ~/.ssh/id_rsa
```

**When prompted:**
- Press Enter to accept default location (~/.ssh/id_ed25519)
- Optionally enter a passphrase for extra security
- Press Enter again to confirm

### 2. Start SSH Agent

```bash
# Start the ssh-agent
eval "$(ssh-agent -s)"

# Add your SSH key to the agent
ssh-add ~/.ssh/id_ed25519
# Or if using RSA:
ssh-add ~/.ssh/id_rsa
```

### 3. Add SSH Key to GitHub/GitLab

#### For GitHub:
1. Copy your public key:
   ```bash
   cat ~/.ssh/id_ed25519.pub
   # Or for RSA:
   cat ~/.ssh/id_rsa.pub
   ```

2. Go to GitHub → Settings → SSH and GPG keys
3. Click "New SSH key"
4. Paste your public key and save

#### For GitLab:
1. Copy your public key (same as above)
2. Go to GitLab → Preferences → SSH Keys
3. Paste your public key and save

### 4. Test SSH Connection

```bash
# Test GitHub connection
ssh -T git@github.com

# Test GitLab connection
ssh -T git@gitlab.com
```

You should see a success message.

### 5. Configure SSH for Remote Servers (Optional)

If you need to connect to remote servers, create/edit `~/.ssh/config`:

```bash
# Create SSH config file
touch ~/.ssh/config
chmod 600 ~/.ssh/config
```

Then add server configurations. See `scripts/ssh_config_example` for a template.

## SSH Config Examples

### Basic Server Configuration

Add to `~/.ssh/config`:

```
Host myserver
    HostName example.com
    User your_username
    Port 22
    IdentityFile ~/.ssh/id_ed25519
    ServerAliveInterval 60
    ServerAliveCountMax 3
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

# Staging Server
Host staging
    HostName staging.example.com
    User deploy
    IdentityFile ~/.ssh/id_ed25519
```

### GitHub with Multiple Accounts

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

Then use:
```bash
git clone git@github.com-personal:username/repo.git
```

## Troubleshooting

### SSH Key Not Working

1. **Check if key is added to agent:**
   ```bash
   ssh-add -l
   ```

2. **Re-add key if needed:**
   ```bash
   ssh-add ~/.ssh/id_ed25519
   ```

3. **Check permissions:**
   ```bash
   chmod 700 ~/.ssh
   chmod 600 ~/.ssh/id_ed25519
   chmod 644 ~/.ssh/id_ed25519.pub
   ```

### Connection Refused

- Verify the server is running SSH: `ssh -v user@hostname`
- Check firewall settings
- Verify port number (default is 22)

### Permission Denied

- Ensure public key is added to server's `~/.ssh/authorized_keys`
- Check file permissions on server:
  ```bash
  chmod 700 ~/.ssh
  chmod 600 ~/.ssh/authorized_keys
  ```

### SSH Agent Not Remembering Keys

Add to your shell profile (`~/.zshrc` or `~/.bashrc`):

```bash
# Start SSH agent and add keys
if [ -z "$SSH_AUTH_SOCK" ]; then
   eval "$(ssh-agent -s)"
   ssh-add ~/.ssh/id_ed25519 2>/dev/null
fi
```

## Security Best Practices

1. **Use strong passphrases** for your SSH keys
2. **Never share your private key** (files without .pub extension)
3. **Use ed25519 keys** when possible (more secure than RSA)
4. **Rotate keys regularly** (every 6-12 months)
5. **Use different keys** for different purposes (personal vs work)
6. **Keep private keys encrypted** at rest
7. **Use SSH agent forwarding carefully** (only when necessary)

## Additional Resources

- [GitHub SSH Setup Guide](https://docs.github.com/en/authentication/connecting-to-github-with-ssh)
- [GitLab SSH Setup Guide](https://docs.gitlab.com/ee/user/ssh.html)
- [OpenSSH Documentation](https://www.openssh.com/manual.html)


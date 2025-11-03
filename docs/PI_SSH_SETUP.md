# Raspberry Pi SSH Setup Guide

This guide helps you set up passwordless SSH access to your Raspberry Pi servers: `pi-net` and `pi-forge`.

## Current Configuration

Your SSH config (`~/.ssh/config`) has been set up with:

- **pi-net**: 192.168.50.70 (user: origin)
- **pi-forge**: 192.168.50.158 (user: origin)

## Quick Setup

### Option 1: Automated Script (Recommended)

Run the setup script and enter your password when prompted:

```bash
./scripts/setup_pi_ssh.sh
```

### Option 2: Manual Setup

For each server (pi-net and pi-forge), follow these steps:

#### Step 1: Copy your SSH key to the server

```bash
# For pi-net
ssh-copy-id pi-net

# For pi-forge  
ssh-copy-id pi-forge
```

You'll be prompted for your password. After entering it, your SSH key will be copied.

#### Step 2: Verify the connection

```bash
# Test pi-net (should not ask for password)
ssh pi-net "echo 'Connected!'"

# Test pi-forge (should not ask for password)
ssh pi-forge "echo 'Connected!'"
```

### Option 3: Manual Key Copy (if ssh-copy-id doesn't work)

If `ssh-copy-id` doesn't work, you can manually copy your key:

1. **Display your public key:**
   ```bash
   cat ~/.ssh/id_ed25519.pub
   ```

2. **SSH to the server:**
   ```bash
   ssh pi-net
   # or
   ssh pi-forge
   ```

3. **On the server, run:**
   ```bash
   mkdir -p ~/.ssh
   chmod 700 ~/.ssh
   nano ~/.ssh/authorized_keys
   ```

4. **Paste your public key** (from step 1) into the file, save and exit.

5. **Set proper permissions:**
   ```bash
   chmod 600 ~/.ssh/authorized_keys
   ```

6. **Exit the server:**
   ```bash
   exit
   ```

7. **Test passwordless login:**
   ```bash
   ssh pi-net
   # Should connect without asking for password
   ```

## Troubleshooting

### Wrong Username

If the username is not "origin", update the SSH config:

```bash
nano ~/.ssh/config
```

Change the `User` line for each host:
```
Host pi-net
    HostName 192.168.50.70
    User pi  # Change this if different
    ...
```

### Permission Denied

If you get "Permission denied":

1. **Verify the server is reachable:**
   ```bash
   ping pi-net
   ping pi-forge
   ```

2. **Check SSH service is running:**
   ```bash
   ssh -v pi-net
   ```

3. **Verify your key is on the server:**
   ```bash
   ssh pi-net "cat ~/.ssh/authorized_keys"
   ```

4. **Check file permissions on the server:**
   ```bash
   ssh pi-net "ls -la ~/.ssh/"
   ```
   
   Should show:
   - `~/.ssh/` directory: permissions 700 (drwx------)
   - `~/.ssh/authorized_keys`: permissions 600 (-rw-------)

### Host Key Verification Failed

If you see "Host key verification failed":

```bash
ssh-keyscan -H 192.168.50.70 >> ~/.ssh/known_hosts
ssh-keyscan -H 192.168.50.158 >> ~/.ssh/known_hosts
```

## Using SSH

Once set up, you can connect to your Pi servers easily:

```bash
# Connect to pi-net
ssh pi-net

# Connect to pi-forge
ssh pi-forge

# Run commands remotely
ssh pi-net "uptime"
ssh pi-forge "df -h"

# Copy files
scp file.txt pi-net:~/
scp -r directory pi-forge:~/
```

## Advanced: SSH Config Options

Your current SSH config includes:

- `ServerAliveInterval 60` - Keeps connection alive
- `ServerAliveCountMax 3` - Max failed keepalive attempts
- `ForwardAgent yes` - Allows SSH agent forwarding

You can add more options like:

```
Host pi-net
    HostName 192.168.50.70
    User origin
    IdentityFile ~/.ssh/id_ed25519
    ServerAliveInterval 60
    ServerAliveCountMax 3
    ForwardAgent yes
    LocalForward 8888 localhost:8888  # Port forwarding example
    Compression yes  # Enable compression for slow connections
```

## Security Notes

- Always use SSH keys instead of passwords when possible
- Keep your private keys secure (never share them)
- Regularly update your Raspberry Pi systems
- Consider changing the default SSH port (22) for additional security
- Use firewall rules to restrict SSH access if needed


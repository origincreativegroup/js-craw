# Deployment Guide

This document describes the CI/CD pipeline and deployment process for the Job Search Crawler application.

## CI/CD Pipeline

The project uses GitHub Actions to automatically build and push Docker images to pi-forge when code is pushed to the `main` branch.

### Workflow Overview

1. **Trigger**: Push to `main` branch
2. **Build**: SSH into pi-forge and build Docker image
3. **Tag**: Tag image with `latest` and commit SHA
4. **Push**: Push images to Docker registry at `jscraw.lan`

### GitHub Secrets Configuration

The following secrets must be configured in your GitHub repository settings:

1. Go to: `Settings` → `Secrets and variables` → `Actions` → `New repository secret`

#### Required Secrets

- **`PI_FORGE_SSH_KEY`**: Private SSH key for accessing pi-forge
  - Generate with: `ssh-keygen -t ed25519 -f ~/.ssh/pi_forge_deploy`
  - Copy private key content: `cat ~/.ssh/pi_forge_deploy`
  - Add public key to pi-forge: `ssh-copy-id -i ~/.ssh/pi_forge_deploy.pub admin@192.168.50.158`
  
- **`PI_FORGE_SSH_USER`**: SSH username for pi-forge (default: `admin`)
  - Only set if different from `admin`
  
- **`PI_FORGE_HOST`**: IP address or hostname of pi-forge (default: `192.168.50.158`)
  - Only set if different from the default

#### Optional Secrets

- **`DOCKER_REGISTRY_USER`**: Docker registry username (if registry requires authentication)
- **`DOCKER_REGISTRY_PASSWORD`**: Docker registry password (if registry requires authentication)

### Image Tags

Images are tagged with:
- `jscraw.lan/js-craw:latest` - Always points to the latest build
- `jscraw.lan/js-craw:{commit-sha}` - Specific commit SHA (e.g., `jscraw.lan/js-craw:abc1234`)

### Viewing Workflow Runs

1. Go to your GitHub repository
2. Click on the `Actions` tab
3. Select `Build and Push Docker Image` workflow
4. View logs for each run

## Docker Registry Setup on pi-forge

The Docker registry must be configured on pi-forge to accept pushes from `jscraw.lan` domain.

### Option 1: Docker Registry (Default)

If using Docker's registry service:

```bash
# On pi-forge, ensure Docker registry is running
docker ps | grep registry

# If not running, start it:
docker run -d -p 5000:5000 --name registry registry:2
```

### Option 2: Custom Registry with Domain

If you have a custom registry setup with `jscraw.lan` domain, ensure:
- DNS resolves `jscraw.lan` to pi-forge IP (192.168.50.158)
- Registry is accessible from pi-forge
- Registry accepts images with `jscraw.lan` prefix

### Testing Registry Access

On pi-forge, test the registry:

```bash
# Pull a test image
docker pull hello-world

# Tag for your registry
docker tag hello-world jscraw.lan/test:latest

# Push to registry
docker push jscraw.lan/test:latest

# If successful, registry is working
```

## Caddy Reverse Proxy Configuration

The `jscraw.lan` domain must be configured in Caddy on pi-net to reverse proxy to pi-forge.

### Adding jscraw.lan to Caddyfile

On pi-net server, edit the Caddyfile:

```bash
ssh pi-net
sudo nano /etc/caddy/Caddyfile
```

Add the following configuration:

```
jscraw.lan {
    reverse_proxy 192.168.50.158:8001
}
```

Reload Caddy:

```bash
sudo systemctl reload caddy
```

### DNS Configuration

Ensure `jscraw.lan` resolves to pi-net (192.168.50.70) on your local network:

- Add to `/etc/hosts` on local machines:
  ```
  192.168.50.70 jscraw.lan
  ```

- Or configure in your router's DNS settings to resolve `.lan` domains

### Testing Caddy Configuration

```bash
# Test DNS resolution
ping jscraw.lan

# Test HTTP access
curl http://jscraw.lan/api/stats

# Should return JSON response from the application
```

## Deployment Process

### Automatic Deployment

1. Push code to `main` branch:
   ```bash
   git add .
   git commit -m "Update application"
   git push origin main
   ```

2. GitHub Actions automatically:
   - Builds Docker image on pi-forge
   - Tags and pushes to registry
   - Workflow completes in ~2-5 minutes

3. On pi-forge, pull the new image:
   ```bash
   ssh pi-forge
   docker pull jscraw.lan/js-craw:latest
   docker-compose up -d job-crawler
   ```

### Manual Deployment

If you need to deploy manually:

```bash
# SSH to pi-forge
ssh pi-forge

# Navigate to project directory (if code is there)
cd /path/to/js-craw

# Pull latest code
git pull origin main

# Build image
docker build -t jscraw.lan/js-craw:latest .

# Tag with commit SHA
docker tag jscraw.lan/js-craw:latest jscraw.lan/js-craw:$(git rev-parse --short HEAD)

# Push to registry
docker push jscraw.lan/js-craw:latest
docker push jscraw.lan/js-craw:$(git rev-parse --short HEAD)

# Update running container
docker-compose pull job-crawler
docker-compose up -d job-crawler
```

## Updating docker-compose.yml

The `docker-compose.yml` file has been configured to use the registry image:

```yaml
job-crawler:
  image: jscraw.lan/js-craw:latest
  pull_policy: always
  # For local development, uncomment the line below and comment out the image line above
  # build: .
```

### Local Development

For local development, you can switch back to building locally:

1. Comment out the `image` line
2. Uncomment the `build: .` line
3. Run `docker-compose up -d --build`

## Troubleshooting

### GitHub Actions Fails

**SSH Connection Issues:**
- Verify SSH key is correctly added to GitHub secrets
- Test SSH connection manually: `ssh -i ~/.ssh/pi_forge_deploy admin@192.168.50.158`
- Check pi-forge SSH service: `ssh pi-forge "sudo systemctl status ssh"`

**Build Fails:**
- Check workflow logs in GitHub Actions
- Verify Docker is running on pi-forge: `ssh pi-forge "docker ps"`
- Check disk space on pi-forge: `ssh pi-forge "df -h"`

**Push Fails:**
- Verify Docker registry is running: `ssh pi-forge "docker ps | grep registry"`
- Check registry logs: `ssh pi-forge "docker logs registry"`
- Test registry manually: `docker push jscraw.lan/js-craw:test`

### Caddy Issues

**Domain Not Resolving:**
- Check `/etc/hosts` or DNS configuration
- Verify Caddy is running: `ssh pi-net "sudo systemctl status caddy"`
- Check Caddy logs: `ssh pi-net "sudo journalctl -u caddy -n 50"`

**Reverse Proxy Not Working:**
- Verify pi-forge service is running: `ssh pi-forge "docker ps | grep job-crawler"`
- Test direct connection: `curl http://192.168.50.158:8001/api/stats`
- Check Caddyfile syntax: `ssh pi-net "sudo caddy validate --config /etc/caddy/Caddyfile"`

### Docker Image Issues

**Image Not Found:**
- Verify image exists: `ssh pi-forge "docker images | grep jscraw"`
- Check registry connectivity: `ssh pi-forge "docker pull jscraw.lan/js-craw:latest"`

**Container Won't Start:**
- Check logs: `ssh pi-forge "docker-compose logs job-crawler"`
- Verify dependencies: `ssh pi-forge "docker-compose ps"`
- Check environment variables: `ssh pi-forge "docker-compose config"`

## Monitoring

### Check Application Status

```bash
# On pi-forge
ssh pi-forge
docker-compose ps
docker-compose logs -f job-crawler
```

### Check Workflow Status

- GitHub repository → Actions tab
- View latest workflow run
- Check for any errors or warnings

### View Application Logs

```bash
# Real-time logs
ssh pi-forge "docker-compose logs -f job-crawler"

# Last 100 lines
ssh pi-forge "docker-compose logs --tail=100 job-crawler"
```

## Security Considerations

1. **SSH Keys**: Keep private keys secure, never commit them to the repository
2. **Registry Access**: Restrict registry access to authorized networks
3. **Caddy HTTPS**: Consider enabling HTTPS for jscraw.lan domain
4. **Secrets**: Rotate GitHub secrets periodically
5. **Network**: Ensure pi-forge and pi-net are on a secure network

## Next Steps

- Set up automated deployment (pull latest image and restart container)
- Configure HTTPS for jscraw.lan domain in Caddy
- Set up monitoring and alerting
- Implement rollback strategy for failed deployments


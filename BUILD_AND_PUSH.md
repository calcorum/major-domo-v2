# Building and Pushing to Docker Hub

This guide covers building the Docker image and pushing it to Docker Hub for production deployment.

## Prerequisites

- Docker installed and running
- Docker Hub account (username: `manticorum67`)
- Write access to `manticorum67/major-domo-discordapp` repository

## Docker Hub Repository

**Repository**: `manticorum67/major-domo-discordapp`
**URL**: https://hub.docker.com/r/manticorum67/major-domo-discordapp

## Login to Docker Hub

```bash
# Login to Docker Hub
docker login

# Enter your username: manticorum67
# Enter your password/token: [your-password-or-token]
```

## Build and Push Workflow

### 1. Tag the Release

```bash
# Determine version number (use semantic versioning)
VERSION="2.0.0"

# Create git tag (optional but recommended)
git tag -a "v${VERSION}" -m "Release v${VERSION}"
git push origin "v${VERSION}"
```

### 2. Build the Image

```bash
# Build for production
docker build -t manticorum67/major-domo-discordapp:latest .

# Build with version tag
docker build -t manticorum67/major-domo-discordapp:${VERSION} .

# Or build both at once
docker build \
  -t manticorum67/major-domo-discordapp:latest \
  -t manticorum67/major-domo-discordapp:${VERSION} \
  .
```

### 3. Test the Image Locally

```bash
# Test with docker run
docker run --rm \
  --env-file .env \
  -v $(pwd)/data:/data:ro \
  -v $(pwd)/logs:/logs:rw \
  manticorum67/major-domo-discordapp:latest

# Or test with docker-compose (development)
docker-compose -f docker-compose.dev.yml up
```

### 4. Push to Docker Hub

```bash
# Push latest tag
docker push manticorum67/major-domo-discordapp:latest

# Push version tag
docker push manticorum67/major-domo-discordapp:${VERSION}

# Or push all tags
docker push manticorum67/major-domo-discordapp --all-tags
```

## Complete Build and Push Script

```bash
#!/bin/bash
# build-and-push.sh

set -e  # Exit on error

# Configuration
VERSION="${1:-latest}"  # Use argument or default to 'latest'
DOCKER_REPO="manticorum67/major-domo-discordapp"

echo "🔨 Building Docker image..."
echo "Version: ${VERSION}"
echo "Repository: ${DOCKER_REPO}"
echo ""

# Build image with both tags
docker build \
  -t ${DOCKER_REPO}:latest \
  -t ${DOCKER_REPO}:${VERSION} \
  .

echo ""
echo "✅ Build complete!"
echo ""
echo "📤 Pushing to Docker Hub..."

# Push both tags
docker push ${DOCKER_REPO}:latest
docker push ${DOCKER_REPO}:${VERSION}

echo ""
echo "✅ Push complete!"
echo ""
echo "🎉 Image available at:"
echo "   docker pull ${DOCKER_REPO}:latest"
echo "   docker pull ${DOCKER_REPO}:${VERSION}"
```

### Using the Build Script

```bash
# Make script executable
chmod +x build-and-push.sh

# Build and push with version
./build-and-push.sh 2.0.0

# Build and push as latest only
./build-and-push.sh
```

## Multi-Platform Builds (Optional)

To build for multiple architectures (amd64, arm64):

```bash
# Create a builder instance
docker buildx create --name multiarch --use

# Build and push for multiple platforms
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t manticorum67/major-domo-discordapp:latest \
  -t manticorum67/major-domo-discordapp:${VERSION} \
  --push \
  .
```

## Versioning Strategy

### Semantic Versioning

Use semantic versioning (MAJOR.MINOR.PATCH):

- **MAJOR**: Breaking changes
- **MINOR**: New features (backwards compatible)
- **PATCH**: Bug fixes

Examples:
- `2.0.0` - Major release with scorecard submission
- `2.1.0` - Added new command
- `2.1.1` - Fixed bug in existing command

### Tagging Strategy

Always maintain these tags:

1. **`:latest`** - Most recent stable release
2. **`:VERSION`** - Specific version (e.g., `2.0.0`)
3. **`:MAJOR.MINOR`** - Minor version (e.g., `2.0`) - optional
4. **`:MAJOR`** - Major version (e.g., `2`) - optional

### Example Tagging

```bash
VERSION="2.0.0"

# Tag with all versions
docker build \
  -t manticorum67/major-domo-discordapp:latest \
  -t manticorum67/major-domo-discordapp:2.0.0 \
  -t manticorum67/major-domo-discordapp:2.0 \
  -t manticorum67/major-domo-discordapp:2 \
  .

# Push all tags
docker push manticorum67/major-domo-discordapp --all-tags
```

## GitHub Actions (Optional)

Automate builds with GitHub Actions:

```yaml
# .github/workflows/docker-build.yml
name: Build and Push Docker Image

on:
  push:
    tags:
      - 'v*.*.*'

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v2

      - name: Login to Docker Hub
        uses: docker/login-action@v2
        with:
          username: ${{ secrets.DOCKERHUB_USERNAME }}
          password: ${{ secrets.DOCKERHUB_TOKEN }}

      - name: Extract version
        id: version
        run: echo "VERSION=${GITHUB_REF#refs/tags/v}" >> $GITHUB_OUTPUT

      - name: Build and push
        uses: docker/build-push-action@v4
        with:
          context: ./discord-app-v2
          push: true
          tags: |
            manticorum67/major-domo-discordapp:latest
            manticorum67/major-domo-discordapp:${{ steps.version.outputs.VERSION }}
```

## Production Deployment

After pushing to Docker Hub, deploy on production:

```bash
# On production server
cd /path/to/discord-app-v2

# Pull latest image
docker-compose pull

# Restart with new image
docker-compose up -d

# Verify it's running
docker-compose logs -f discord-bot
```

## Rollback to Previous Version

If a release has issues:

```bash
# Stop current version
docker-compose down

# Edit docker-compose.yml to use specific version
# Change: image: manticorum67/major-domo-discordapp:latest
# To:     image: manticorum67/major-domo-discordapp:2.0.0

# Pull and start old version
docker-compose pull
docker-compose up -d
```

Or use a specific version directly:

```bash
docker-compose down

docker pull manticorum67/major-domo-discordapp:2.0.0

docker run -d \
  --name major-domo-discord-bot-v2 \
  --env-file .env \
  -v $(pwd)/data:/data:ro \
  -v $(pwd)/logs:/logs:rw \
  manticorum67/major-domo-discordapp:2.0.0
```

## Image Size Optimization

The multi-stage build already optimizes size, but you can verify:

```bash
# Check image size
docker images manticorum67/major-domo-discordapp

# Expected size: ~150-200MB

# Inspect layers
docker history manticorum67/major-domo-discordapp:latest
```

## Troubleshooting

### Build Fails

```bash
# Build with verbose output
docker build --progress=plain -t manticorum67/major-domo-discordapp:latest .

# Check for errors in requirements.txt
docker build --no-cache -t manticorum67/major-domo-discordapp:latest .
```

### Push Fails

```bash
# Check if logged in
docker info | grep Username

# Re-login
docker logout
docker login

# Check repository permissions
docker push manticorum67/major-domo-discordapp:latest
```

### Image Won't Run

```bash
# Test image interactively
docker run -it --rm \
  --entrypoint /bin/bash \
  manticorum67/major-domo-discordapp:latest

# Inside container, check Python
python --version
pip list
ls -la /app
```

## Security Best Practices

1. **Use Docker Hub Access Tokens** instead of password
2. **Enable 2FA** on Docker Hub account
3. **Scan images** for vulnerabilities:
   ```bash
   docker scan manticorum67/major-domo-discordapp:latest
   ```
4. **Sign images** (optional):
   ```bash
   docker trust sign manticorum67/major-domo-discordapp:latest
   ```

## Cleanup

Remove old local images:

```bash
# Remove dangling images
docker image prune

# Remove all unused images
docker image prune -a

# Remove specific version
docker rmi manticorum67/major-domo-discordapp:1.0.0
```

## Additional Resources

- **Docker Hub**: https://hub.docker.com/r/manticorum67/major-domo-discordapp
- **Docker Documentation**: https://docs.docker.com/
- **Semantic Versioning**: https://semver.org/

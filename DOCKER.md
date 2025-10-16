# Docker Deployment Guide

This guide covers deploying the Discord Bot v2.0 using Docker and Docker Compose.

## Prerequisites

- Docker 20.10+ installed
- Docker Compose 2.0+ installed
- Google Sheets service account credentials JSON file
- Access to the database API (running on a separate host)

## Deployment Modes

### Production (Recommended)
Uses `docker-compose.yml` - pulls pre-built image from Docker Hub

### Development
Uses `docker-compose.dev.yml` - builds image locally from source

---

## Quick Start (Production)

Deploy using pre-built image from Docker Hub:

### 1. Prepare Configuration

```bash
# Copy the example environment file
cp .env.example .env

# Edit .env with your actual values
nano .env
```

**Required environment variables:**
- `BOT_TOKEN` - Your Discord bot token
- `API_TOKEN` - Database API authentication token
- `DB_URL` - Database API endpoint URL
- `GUILD_ID` - Your Discord server ID

### 2. Prepare Data Directory

```bash
# Create data directory for Google Sheets credentials
mkdir -p data

# Copy your Google Sheets credentials file
cp /path/to/your/credentials.json data/major-domo-service-creds.json

# Set proper permissions (read-only)
chmod 444 data/major-domo-service-creds.json
```

### 3. Create Logs Directory

```bash
# Create logs directory (will be mounted as volume)
mkdir -p logs
```

### 4. Pull and Run

```bash
# Pull latest image from Docker Hub
docker-compose pull

# Start the bot
docker-compose up -d

# View logs
docker-compose logs -f discord-bot
```

---

## Development Setup

Build and run locally with source code:

### 1. Complete steps 1-3 from Production setup above

### 2. Build and Run

```bash
# Build the Docker image locally
docker-compose -f docker-compose.dev.yml build

# Start the bot
docker-compose -f docker-compose.dev.yml up -d

# View logs
docker-compose -f docker-compose.dev.yml logs -f discord-bot
```

## Docker Commands

### Production Commands

```bash
# Pull latest image from Docker Hub
docker-compose pull

# Start in detached mode
docker-compose up -d

# Start in foreground (see logs)
docker-compose up

# Restart the bot
docker-compose restart discord-bot

# Stop the bot
docker-compose stop discord-bot

# Stop and remove container
docker-compose down
```

### Development Commands

```bash
# Build the image locally
docker-compose -f docker-compose.dev.yml build

# Build without cache (force rebuild)
docker-compose -f docker-compose.dev.yml build --no-cache

# Start in detached mode
docker-compose -f docker-compose.dev.yml up -d

# Start and rebuild if needed
docker-compose -f docker-compose.dev.yml up -d --build

# Restart the bot
docker-compose -f docker-compose.dev.yml restart discord-bot

# Stop and remove
docker-compose -f docker-compose.dev.yml down
```

### Monitoring Commands

```bash
# View logs (follow mode)
docker-compose logs -f discord-bot

# View last 100 lines of logs
docker-compose logs --tail=100 discord-bot

# Check container status
docker-compose ps

# Check resource usage
docker stats major-domo-discord-bot-v2

# Execute commands inside container
docker-compose exec discord-bot bash

# View bot process
docker-compose exec discord-bot ps aux
```

### Maintenance Commands

```bash
# Pull latest code and restart
git pull
docker-compose up -d --build

# Clear logs
docker-compose exec discord-bot sh -c "rm -rf /logs/*.log"

# Restart after configuration changes
docker-compose down && docker-compose up -d

# View container health status
docker inspect --format='{{.State.Health.Status}}' major-domo-discord-bot-v2
```

## Directory Structure

```
discord-app-v2/
├── Dockerfile                  # Multi-stage build configuration
├── docker-compose.yml          # Production: pulls from Docker Hub
├── docker-compose.dev.yml      # Development: builds locally
├── .dockerignore              # Files to exclude from image
├── .env                       # Environment configuration (not in git)
├── .env.example              # Environment template
├── DOCKER.md                 # This deployment guide
├── BUILD_AND_PUSH.md         # Guide for pushing to Docker Hub
├── data/                     # Google Sheets credentials (mounted volume)
│   └── major-domo-service-creds.json
├── logs/                     # Log files (mounted volume)
│   ├── discord_bot_v2.log
│   └── discord_bot_v2.json
└── ... (application code)
```

## Docker Hub Repository

**Repository**: `manticorum67/major-domo-discordapp`
**URL**: https://hub.docker.com/r/manticorum67/major-domo-discordapp

Production deployments pull from this repository. See `BUILD_AND_PUSH.md` for instructions on building and pushing new versions.

## Multi-Stage Build

The Dockerfile uses a multi-stage build for optimization:

### Stage 1: Builder
- Based on `python:3.13-slim`
- Installs build dependencies (gcc, g++)
- Compiles Python packages with C extensions
- Creates `.local` directory with all dependencies

### Stage 2: Runtime
- Based on `python:3.13-slim`
- Only includes runtime dependencies
- Copies compiled packages from builder
- Runs as non-root user (`botuser`)
- Final image size: ~150-200MB (vs ~500MB+ single-stage)

## Security Features

### Non-Root User
The bot runs as `botuser` (UID 1000) with restricted permissions:
```dockerfile
RUN groupadd -r botuser && \
    useradd -r -g botuser -u 1000 -m -s /bin/bash botuser
USER botuser
```

### Read-Only Credentials
Mount credentials as read-only:
```yaml
volumes:
  - ./data:/data:ro  # ro = read-only
```

### Resource Limits
Default resource limits in docker-compose.yml:
- CPU: 1.0 cores max, 0.25 cores reserved
- Memory: 512MB max, 256MB reserved

Adjust based on your server capacity:
```yaml
deploy:
  resources:
    limits:
      cpus: '2.0'      # Increase for heavy workloads
      memory: 1G       # Increase if needed
```

## Volume Mounts

### Data Volume (Read-Only)
Contains Google Sheets credentials:
```yaml
volumes:
  - ${SHEETS_CREDENTIALS_HOST_PATH:-./data}:/data:ro
```

### Logs Volume (Read-Write)
Persistent log storage:
```yaml
volumes:
  - ${LOGS_HOST_PATH:-./logs}:/logs:rw
```

### Development Mode
Mount source code for live development:
```yaml
volumes:
  - .:/app:ro  # Uncomment in docker-compose.yml
```

## Health Checks

The bot includes a health check that runs every 60 seconds:
```dockerfile
HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import sys; sys.exit(0)" || exit 1
```

Check health status:
```bash
docker inspect --format='{{.State.Health.Status}}' major-domo-discord-bot-v2
```

## Logging

### Container Logs
Docker captures stdout/stderr:
```bash
docker-compose logs -f discord-bot
```

### Application Logs
Persistent logs in mounted volume:
- `/logs/discord_bot_v2.log` - Human-readable logs
- `/logs/discord_bot_v2.json` - Structured JSON logs

### Log Rotation
Docker manages log rotation:
```yaml
logging:
  driver: "json-file"
  options:
    max-size: "10m"   # Max size per file
    max-file: "3"     # Keep 3 files
```

## Networking

The bot connects outbound to:
- Discord API (discord.com)
- Database API (configured via `DB_URL`)
- Google Sheets API (sheets.googleapis.com)

No inbound ports are exposed (bot initiates all connections).

### Custom Network
The compose file creates a bridge network:
```yaml
networks:
  major-domo-network:
    driver: bridge
```

## Troubleshooting

### Bot Won't Start

1. **Check logs:**
   ```bash
   docker-compose logs discord-bot
   ```

2. **Verify environment variables:**
   ```bash
   docker-compose exec discord-bot env | grep BOT_TOKEN
   ```

3. **Check credentials file:**
   ```bash
   docker-compose exec discord-bot ls -la /data/
   ```

### Permission Errors

If you see permission errors accessing `/data` or `/logs`:
```bash
# Fix data directory permissions
chmod -R 755 data/
chmod 444 data/major-domo-service-creds.json

# Fix logs directory permissions
chmod -R 755 logs/
```

### Database Connection Issues

Test database connectivity:
```bash
docker-compose exec discord-bot python -c "
import aiohttp
import asyncio
import os

async def test():
    url = os.getenv('DB_URL')
    token = os.getenv('API_TOKEN')
    async with aiohttp.ClientSession() as session:
        async with session.get(f'{url}/health',
                               headers={'Authorization': f'Bearer {token}'}) as resp:
            print(f'Status: {resp.status}')
            print(await resp.text())

asyncio.run(test())
"
```

### High Memory Usage

If the bot uses too much memory:

1. **Check current usage:**
   ```bash
   docker stats major-domo-discord-bot-v2
   ```

2. **Increase memory limit:**
   ```yaml
   # In docker-compose.yml
   deploy:
     resources:
       limits:
         memory: 1G  # Increase from 512M
   ```

3. **Restart with new limits:**
   ```bash
   docker-compose up -d
   ```

### Container Keeps Restarting

Check exit code and error:
```bash
docker-compose ps
docker logs major-domo-discord-bot-v2 --tail=50
```

Common issues:
- Invalid `BOT_TOKEN` - Check .env file
- Missing credentials - Check `/data` mount
- Database unreachable - Check `DB_URL`

## Production Deployment

### Best Practices

1. **Use specific image tags:**
   ```bash
   docker tag major-domo/discord-bot-v2:latest major-domo/discord-bot-v2:v2.0.0
   ```

2. **Enable auto-restart:**
   ```yaml
   restart: unless-stopped  # Already set in compose file
   ```

3. **Set production environment:**
   ```bash
   ENVIRONMENT=production
   LOG_LEVEL=INFO
   ```

4. **Monitor resource usage:**
   ```bash
   docker stats major-domo-discord-bot-v2
   ```

5. **Regular updates:**
   ```bash
   git pull
   docker-compose build --no-cache
   docker-compose up -d
   ```

### Backup Strategy

Backup critical data:
```bash
# Backup logs
tar -czf logs-backup-$(date +%Y%m%d).tar.gz logs/

# Backup configuration
cp .env .env.backup

# Backup credentials
cp data/major-domo-service-creds.json data/creds.backup.json
```

## Updates and Maintenance

### Update Bot Code (Production)

```bash
# 1. Pull latest image from Docker Hub
docker-compose pull

# 2. Restart with new image
docker-compose up -d

# 3. Verify it's running
docker-compose logs -f discord-bot
```

### Update Bot Code (Development)

```bash
# 1. Pull latest code
git pull

# 2. Rebuild image
docker-compose -f docker-compose.dev.yml build

# 3. Restart with new image
docker-compose -f docker-compose.dev.yml up -d

# 4. Verify it's running
docker-compose -f docker-compose.dev.yml logs -f discord-bot
```

### Update Dependencies

```bash
# 1. Update requirements.txt locally
pip install -U discord.py pydantic aiohttp
pip freeze > requirements.txt

# 2. Rebuild image with new dependencies
docker-compose build --no-cache

# 3. Restart
docker-compose up -d
```

### Database Migration

If the database API is updated:

```bash
# 1. Update DB_URL in .env if needed
nano .env

# 2. Restart bot to pick up new configuration
docker-compose restart discord-bot

# 3. Test connectivity
docker-compose logs -f discord-bot
```

## File Comparison: Production vs Development

### `docker-compose.yml` (Production)
- Pulls pre-built image from Docker Hub: `manticorum67/major-domo-discordapp:latest`
- Environment: `production`
- Log level: `INFO` (default)
- Resource limits: 512MB RAM, 1 CPU
- No source code mounting

### `docker-compose.dev.yml` (Development)
- Builds image locally from Dockerfile
- Environment: `development`
- Log level: `DEBUG` (default)
- Resource limits: 1GB RAM, 2 CPU (more generous)
- Optional source code mounting for live updates

### When to Use Each

**Use Production (`docker-compose.yml`)**:
- Production servers
- Staging environments
- Any deployment not modifying code
- Faster deployment (no build step)

**Use Development (`docker-compose.dev.yml`)**:
- Local development
- Testing code changes
- Building new features
- Debugging issues

## Additional Resources

- **Discord.py Documentation**: https://discordpy.readthedocs.io/
- **Docker Best Practices**: https://docs.docker.com/develop/dev-best-practices/
- **Python 3.13 Release Notes**: https://docs.python.org/3.13/whatsnew/

## Support

For issues or questions:
1. Check logs: `docker-compose logs discord-bot`
2. Review bot documentation in `CLAUDE.md` and command READMEs
3. Check health status: `docker inspect major-domo-discord-bot-v2`

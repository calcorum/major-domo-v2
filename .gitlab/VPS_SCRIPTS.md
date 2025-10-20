# VPS Helper Scripts

Collection of useful scripts for managing the Discord bot on your VPS.

---

## 📍 Script Locations

All scripts should be placed in `/opt/discord-bot/` on your VPS.

```bash
/opt/discord-bot/
├── docker-compose.yml
├── .env.production
├── rollback.sh          # Rollback to previous version
├── deploy-manual.sh     # Manual deployment script
├── health-check.sh      # Check bot health
├── logs-view.sh         # View logs easily
├── cleanup.sh           # Clean up old Docker images
└── deployments.log      # Auto-generated deployment history
```

---

## 🔄 rollback.sh

Already created during setup. For reference:

```bash
#!/bin/bash
set -e

COMPOSE_FILE="docker-compose.yml"
LOG_FILE="deployments.log"

echo "=== Discord Bot Rollback ==="
echo ""

# Show recent deployments
echo "Recent deployments:"
tail -n 10 $LOG_FILE | column -t -s '|'
echo ""

# Show current version
CURRENT=$(grep "image:" $COMPOSE_FILE | awk '{print $2}')
echo "Current version: $CURRENT"
echo ""

# Show last version
if [ -f .last_version ]; then
    LAST=$(cat .last_version)
    echo "Last version: $LAST"
    echo ""

    read -p "Rollback to this version? (y/N): " confirm
    if [ "$confirm" != "y" ]; then
        echo "Rollback cancelled."
        exit 0
    fi

    # Perform rollback
    echo "Rolling back..."
    sed -i "s|image:.*|image: $LAST|" $COMPOSE_FILE
    docker-compose up -d

    # Record rollback
    echo "$(date -Iseconds) | ROLLBACK | $LAST" >> $LOG_FILE

    echo "✅ Rollback complete!"
else
    echo "❌ No previous version found!"
    exit 1
fi
```

---

## 🚀 deploy-manual.sh

For manual deployments (bypassing GitLab):

```bash
#!/bin/bash
set -e

COMPOSE_FILE="docker-compose.yml"
LOG_FILE="deployments.log"
IMAGE="yourusername/discord-bot-v2"

echo "=== Manual Discord Bot Deployment ==="
echo ""

# Show available versions
echo "Available versions on Docker Hub:"
echo "(Showing last 10 tags)"
curl -s "https://hub.docker.com/v2/repositories/${IMAGE}/tags?page_size=10" | \
  grep -o '"name":"[^"]*' | \
  grep -o '[^"]*$'
echo ""

# Prompt for version
read -p "Enter version to deploy (or 'latest'): " VERSION

if [ -z "$VERSION" ]; then
    echo "❌ No version specified!"
    exit 1
fi

# Backup current version
docker inspect discord-bot --format='{{.Image}}' > .last_version || true

# Update docker-compose
sed -i "s|image: ${IMAGE}:.*|image: ${IMAGE}:${VERSION}|" $COMPOSE_FILE

# Pull and deploy
echo "Pulling ${IMAGE}:${VERSION}..."
docker-compose pull

echo "Deploying..."
docker-compose up -d

# Wait for health check
echo "Waiting for health check..."
sleep 10

if docker-compose ps | grep -q "Up (healthy)"; then
    echo "✅ Deployment successful!"
    echo "$(date -Iseconds) | MANUAL | ${VERSION} | Manual deployment" >> $LOG_FILE
    docker image prune -f
else
    echo "❌ Health check failed! Rolling back..."
    LAST_VERSION=$(cat .last_version)
    sed -i "s|image: ${IMAGE}:.*|image: ${LAST_VERSION}|" $COMPOSE_FILE
    docker-compose up -d
    exit 1
fi
```

**Usage:**
```bash
cd /opt/discord-bot
./deploy-manual.sh
```

---

## 🏥 health-check.sh

Comprehensive health check:

```bash
#!/bin/bash

echo "=== Discord Bot Health Check ==="
echo ""

# Container status
echo "📦 Container Status:"
docker-compose ps
echo ""

# Bot health
BOT_HEALTH=$(docker inspect discord-bot --format '{{.State.Health.Status}}' 2>/dev/null || echo "unknown")
echo "🤖 Bot Health: $BOT_HEALTH"

# Redis health
REDIS_HEALTH=$(docker exec discord-redis redis-cli ping 2>/dev/null || echo "unreachable")
echo "💾 Redis Health: $REDIS_HEALTH"
echo ""

# Uptime
BOT_STARTED=$(docker inspect discord-bot --format '{{.State.StartedAt}}' 2>/dev/null || echo "unknown")
echo "⏱️  Bot Started: $BOT_STARTED"
echo ""

# Resource usage
echo "💻 Resource Usage:"
docker stats --no-stream discord-bot discord-redis
echo ""

# Recent errors
echo "⚠️  Recent Errors (last 10):"
docker-compose logs --tail=100 bot 2>&1 | grep -i error | tail -10 || echo "No recent errors"
echo ""

# Deployment history
echo "📜 Recent Deployments:"
tail -5 deployments.log | column -t -s '|'
echo ""

# Summary
echo "=== Summary ==="
if [ "$BOT_HEALTH" = "healthy" ] && [ "$REDIS_HEALTH" = "PONG" ]; then
    echo "✅ All systems operational"
    exit 0
else
    echo "❌ Issues detected"
    exit 1
fi
```

**Usage:**
```bash
cd /opt/discord-bot
./health-check.sh
```

**Cron for daily checks:**
```bash
# Run health check daily at 6 AM
0 6 * * * /opt/discord-bot/health-check.sh | mail -s "Bot Health Report" you@email.com
```

---

## 📋 logs-view.sh

Easy log viewing:

```bash
#!/bin/bash

echo "Discord Bot Logs Viewer"
echo ""
echo "Select option:"
echo "1) Live bot logs (follow)"
echo "2) Last 100 bot logs"
echo "3) Last 50 error logs"
echo "4) All logs (bot + redis)"
echo "5) Deployment history"
echo "6) Search logs"
echo ""
read -p "Choice [1-6]: " choice

case $choice in
    1)
        echo "Following live logs (Ctrl+C to exit)..."
        docker-compose logs -f --tail=50 bot
        ;;
    2)
        docker-compose logs --tail=100 bot
        ;;
    3)
        docker-compose logs --tail=500 bot | grep -i error | tail -50
        ;;
    4)
        docker-compose logs --tail=100
        ;;
    5)
        cat deployments.log | column -t -s '|'
        ;;
    6)
        read -p "Search term: " term
        docker-compose logs bot | grep -i "$term" | tail -50
        ;;
    *)
        echo "Invalid option"
        exit 1
        ;;
esac
```

**Usage:**
```bash
cd /opt/discord-bot
./logs-view.sh
```

---

## 🧹 cleanup.sh

Clean up old Docker images and data:

```bash
#!/bin/bash
set -e

echo "=== Discord Bot Cleanup ==="
echo ""

# Show current disk usage
echo "💾 Current Disk Usage:"
df -h /var/lib/docker
echo ""

# Show Docker disk usage
echo "🐳 Docker Disk Usage:"
docker system df
echo ""

read -p "Proceed with cleanup? (y/N): " confirm
if [ "$confirm" != "y" ]; then
    echo "Cleanup cancelled."
    exit 0
fi

# Stop containers temporarily
echo "Stopping containers..."
docker-compose down

# Prune images (keep recent ones)
echo "Pruning old images..."
docker image prune -a -f --filter "until=720h"  # Keep images from last 30 days

# Prune volumes (be careful!)
# Uncomment if you want to clean volumes
# echo "Pruning unused volumes..."
# docker volume prune -f

# Prune build cache
echo "Pruning build cache..."
docker builder prune -f

# Restart containers
echo "Restarting containers..."
docker-compose up -d

# Show new disk usage
echo ""
echo "✅ Cleanup complete!"
echo ""
echo "💾 New Disk Usage:"
df -h /var/lib/docker
echo ""
docker system df
```

**Usage:**
```bash
cd /opt/discord-bot
./cleanup.sh
```

**Cron for monthly cleanup:**
```bash
# Run cleanup first Sunday of month at 3 AM
0 3 1-7 * 0 /opt/discord-bot/cleanup.sh
```

---

## 🔍 version-info.sh

Show detailed version information:

```bash
#!/bin/bash

echo "=== Version Information ==="
echo ""

# Docker image version
echo "🐳 Docker Image:"
docker inspect discord-bot --format '{{.Config.Image}}'
echo ""

# Image labels
echo "🏷️  Build Metadata:"
docker inspect discord-bot --format '{{json .Config.Labels}}' | jq '.'
echo ""

# Environment variables (version info only)
echo "🔧 Environment:"
docker inspect discord-bot --format '{{range .Config.Env}}{{println .}}{{end}}' | grep BOT_
echo ""

# Currently deployed
echo "📦 Currently Deployed:"
cat .deployed_version 2>/dev/null || echo "Unknown"
echo ""

# Last deployment
echo "📅 Last Deployment:"
tail -1 deployments.log | column -t -s '|'
echo ""

# Available for rollback
echo "⏮️  Available for Rollback:"
cat .last_version 2>/dev/null || echo "None"
```

**Usage:**
```bash
cd /opt/discord-bot
./version-info.sh
```

---

## 📊 status-dashboard.sh

Combined status dashboard:

```bash
#!/bin/bash

clear
echo "╔════════════════════════════════════════════╗"
echo "║     Discord Bot Status Dashboard           ║"
echo "╚════════════════════════════════════════════╝"
echo ""

# Version
echo "📦 Version: $(cat .deployed_version 2>/dev/null || echo 'Unknown')"
echo ""

# Health
BOT_HEALTH=$(docker inspect discord-bot --format '{{.State.Health.Status}}' 2>/dev/null || echo "down")
REDIS_HEALTH=$(docker exec discord-redis redis-cli ping 2>/dev/null || echo "DOWN")

if [ "$BOT_HEALTH" = "healthy" ]; then
    echo "✅ Bot: $BOT_HEALTH"
else
    echo "❌ Bot: $BOT_HEALTH"
fi

if [ "$REDIS_HEALTH" = "PONG" ]; then
    echo "✅ Redis: UP"
else
    echo "❌ Redis: $REDIS_HEALTH"
fi
echo ""

# Uptime
STARTED=$(docker inspect discord-bot --format '{{.State.StartedAt}}' 2>/dev/null || echo "unknown")
echo "⏱️  Uptime: $STARTED"
echo ""

# Resource usage
echo "💻 Resources:"
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}" discord-bot discord-redis
echo ""

# Recent deployments
echo "📜 Recent Deployments:"
tail -3 deployments.log | column -t -s '|'
echo ""

# Errors
ERROR_COUNT=$(docker-compose logs --tail=1000 bot 2>&1 | grep -ic error || echo 0)
echo "⚠️  Errors (last 1000 lines): $ERROR_COUNT"
echo ""

echo "╚════════════════════════════════════════════╝"
echo "Press Ctrl+C to exit, or run with 'watch' for live updates"
```

**Usage:**
```bash
# One-time view
cd /opt/discord-bot
./status-dashboard.sh

# Live updating (every 2 seconds)
watch -n 2 /opt/discord-bot/status-dashboard.sh
```

---

## 🚀 Quick Setup

Install all scripts at once:

```bash
ssh user@vps << 'EOF'
cd /opt/discord-bot

# Make scripts executable
chmod +x rollback.sh
chmod +x deploy-manual.sh
chmod +x health-check.sh
chmod +x logs-view.sh
chmod +x cleanup.sh
chmod +x version-info.sh
chmod +x status-dashboard.sh

echo "✅ All scripts are ready!"
ls -lah *.sh
EOF
```

---

## 🎯 Useful Aliases

Add to `~/.bashrc` on VPS:

```bash
# Discord Bot aliases
alias bot-status='cd /opt/discord-bot && ./status-dashboard.sh'
alias bot-logs='cd /opt/discord-bot && ./logs-view.sh'
alias bot-health='cd /opt/discord-bot && ./health-check.sh'
alias bot-rollback='cd /opt/discord-bot && ./rollback.sh'
alias bot-deploy='cd /opt/discord-bot && ./deploy-manual.sh'
alias bot-restart='cd /opt/discord-bot && docker-compose restart bot'
alias bot-down='cd /opt/discord-bot && docker-compose down'
alias bot-up='cd /opt/discord-bot && docker-compose up -d'

# Quick status
alias bs='bot-status'
alias bl='bot-logs'
```

Then:
```bash
source ~/.bashrc

# Now you can use:
bs        # Status dashboard
bl        # View logs
bot-health  # Health check
```

---

**Tip**: Create a `README.txt` in `/opt/discord-bot/` listing all available scripts and their purposes!

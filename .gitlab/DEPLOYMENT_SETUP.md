# GitLab CI/CD Deployment Setup Guide

This guide will help you set up the complete CI/CD pipeline for Discord Bot v2.0.

---

## 📋 Prerequisites

- GitLab account (free tier)
- Docker Hub account
- SSH access to your Ubuntu VPS
- Git repository with Discord Bot v2.0 code

---

## 🚀 Step 1: GitLab Setup (5 minutes)

### 1.1 Create GitLab Project

```bash
# Option A: Mirror from existing GitHub repo
git remote add gitlab git@gitlab.com:yourusername/discord-bot.git
git push gitlab main

# Option B: Create new GitLab repo and push
# 1. Go to gitlab.com
# 2. Click "New Project"
# 3. Name it "discord-bot"
# 4. Set visibility to "Private"
# 5. Create project
# 6. Follow instructions to push existing repository
```

### 1.2 Add CI/CD Variables

Go to: **Settings > CI/CD > Variables**

Add the following variables (all marked as "Protected" and "Masked"):

| Variable | Value | Description |
|----------|-------|-------------|
| `DOCKER_USERNAME` | your-docker-hub-username | Docker Hub login |
| `DOCKER_PASSWORD` | your-docker-hub-token | Docker Hub access token (NOT password) |
| `SSH_PRIVATE_KEY` | your-ssh-private-key | SSH key for VPS access (see below) |
| `VPS_HOST` | your.vps.ip.address | VPS IP or hostname |
| `VPS_USER` | your-vps-username | SSH username (usually `ubuntu` or `root`) |

**Important Notes:**
- For `DOCKER_PASSWORD`: Use a Docker Hub access token, not your password
  - Go to hub.docker.com > Account Settings > Security > New Access Token
- For `SSH_PRIVATE_KEY`: Copy your entire private key including headers
  - `cat ~/.ssh/id_rsa` (or whatever key you use)
  - Include `-----BEGIN OPENSSH PRIVATE KEY-----` and `-----END OPENSSH PRIVATE KEY-----`

---

## 🔑 Step 2: SSH Key Setup for VPS

### 2.1 Generate SSH Key (if you don't have one)

```bash
# On your local machine
ssh-keygen -t ed25519 -C "gitlab-ci@discord-bot" -f ~/.ssh/gitlab_ci_bot

# Copy public key to VPS
ssh-copy-id -i ~/.ssh/gitlab_ci_bot.pub your-user@your-vps-host
```

### 2.2 Add Private Key to GitLab

```bash
# Copy private key
cat ~/.ssh/gitlab_ci_bot

# Paste entire output (including headers) into GitLab CI/CD variable SSH_PRIVATE_KEY
```

### 2.3 Test SSH Access

```bash
ssh -i ~/.ssh/gitlab_ci_bot your-user@your-vps-host "echo 'Connection successful!'"
```

---

## 🐳 Step 3: Docker Hub Setup

### 3.1 Create Access Token

1. Go to https://hub.docker.com/settings/security
2. Click "New Access Token"
3. Name: "GitLab CI/CD"
4. Permissions: "Read, Write, Delete"
5. Copy token immediately (you won't see it again!)

### 3.2 Create Repository

1. Go to https://hub.docker.com/repositories
2. Click "Create Repository"
3. Name: "discord-bot-v2"
4. Visibility: Private or Public (your choice)
5. Create

---

## 🖥️ Step 4: VPS Setup

### 4.1 Create Directory Structure

```bash
# SSH into your VPS
ssh your-user@your-vps-host

# Create production directory
sudo mkdir -p /opt/discord-bot
sudo chown $USER:$USER /opt/discord-bot
cd /opt/discord-bot

# Create staging directory (optional)
sudo mkdir -p /opt/discord-bot-staging
sudo chown $USER:$USER /opt/discord-bot-staging
```

### 4.2 Create docker-compose.yml (Production)

```bash
cd /opt/discord-bot
nano docker-compose.yml
```

Paste:
```yaml
version: '3.8'

services:
  bot:
    image: yourusername/discord-bot-v2:latest
    container_name: discord-bot
    restart: unless-stopped
    env_file:
      - .env.production
    volumes:
      - ./logs:/app/logs
      - ./storage:/app/storage
    networks:
      - bot-network
    healthcheck:
      test: ["CMD", "python", "-c", "import discord; print('ok')"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

  redis:
    image: redis:7-alpine
    container_name: discord-redis
    restart: unless-stopped
    volumes:
      - redis-data:/data
    networks:
      - bot-network

volumes:
  redis-data:

networks:
  bot-network:
```

### 4.3 Create Environment File

```bash
nano .env.production
```

Paste:
```bash
BOT_TOKEN=your_discord_bot_token
API_TOKEN=your_database_api_token
DB_URL=http://your-api-url:8000
GUILD_ID=your_discord_server_id
LOG_LEVEL=INFO
REDIS_URL=redis://redis:6379
REDIS_CACHE_TTL=300
```

### 4.4 Create Rollback Script

```bash
nano rollback.sh
chmod +x rollback.sh
```

Paste:
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

### 4.5 Initialize Deployment Log

```bash
touch deployments.log
echo "$(date -Iseconds) | INIT | Manual Setup" >> deployments.log
```

---

## 📁 Step 5: Update Project Files

### 5.1 Copy GitLab CI Configuration

```bash
# On your local machine, in project root
cp discord-app-v2/.gitlab-ci.yml .gitlab-ci.yml

# Update DOCKER_IMAGE variable with your Docker Hub username
sed -i 's/yourusername/YOUR_ACTUAL_USERNAME/' .gitlab-ci.yml
```

### 5.2 Update Dockerfile

```bash
# Replace existing Dockerfile with versioned one
cd discord-app-v2
mv Dockerfile Dockerfile.old
cp Dockerfile.versioned Dockerfile
```

### 5.3 Add Version Command to Bot

Edit `discord-app-v2/bot.py` and add:

```python
import os

BOT_VERSION = os.getenv('BOT_VERSION', 'dev')
GIT_COMMIT = os.getenv('BOT_GIT_COMMIT', 'unknown')
BUILD_DATE = os.getenv('BOT_BUILD_DATE', 'unknown')

@bot.tree.command(name="version", description="Display bot version info")
async def version_command(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🤖 Bot Version Information",
        color=0x00ff00
    )
    embed.add_field(name="Version", value=BOT_VERSION, inline=False)
    embed.add_field(name="Git Commit", value=GIT_COMMIT[:8], inline=True)
    embed.add_field(name="Build Date", value=BUILD_DATE, inline=True)

    await interaction.response.send_message(embed=embed, ephemeral=True)
```

---

## 🧪 Step 6: Test the Pipeline

### 6.1 Initial Commit

```bash
git add .
git commit -m "Setup GitLab CI/CD pipeline"
git push gitlab main
```

### 6.2 Watch Pipeline Execute

1. Go to GitLab project page
2. Click "CI/CD > Pipelines"
3. Watch your pipeline run:
   - ✅ Test stage should run
   - ✅ Build stage should run
   - ⏸️ Deploy stage waits for manual trigger

### 6.3 Manual Production Deploy

1. In GitLab pipeline view, find "deploy:production" job
2. Click the "Play" button ▶️
3. Watch deployment execute
4. Verify on VPS:
   ```bash
   ssh your-user@your-vps-host
   cd /opt/discord-bot
   docker-compose ps
   tail -f logs/discord_bot_v2.log
   ```

---

## ✅ Step 7: Verify Everything Works

### 7.1 Check Bot Status

```bash
# On VPS
docker-compose ps

# Should show:
# NAME              STATUS
# discord-bot       Up (healthy)
# discord-redis     Up
```

### 7.2 Check Version in Discord

In your Discord server:
```
/version
```

Should show something like:
```
Version: v2.1.1
Git Commit: a1b2c3d4
Build Date: 2025-01-19T10:30:00Z
```

### 7.3 Check Deployment Log

```bash
# On VPS
cat /opt/discord-bot/deployments.log
```

---

## 🔄 Step 8: Create Development Workflow

### 8.1 Create Develop Branch

```bash
git checkout -b develop
git push gitlab develop
```

### 8.2 Set Up Branch Protection (Optional)

In GitLab:
1. Settings > Repository > Protected Branches
2. Protect `main`: Require merge requests, maintainers can push
3. Protect `develop`: Developers can push

---

## 🎯 Usage Workflows

### Regular Feature Development

```bash
# Create feature branch
git checkout -b feature/new-feature develop

# Make changes, commit
git add .
git commit -m "Add new feature"
git push gitlab feature/new-feature

# Merge to develop (auto-deploys to staging if configured)
git checkout develop
git merge feature/new-feature
git push gitlab develop

# After testing, merge to main
git checkout main
git merge develop
git push gitlab main

# In GitLab UI, manually trigger production deploy
```

### Hotfix

```bash
# Create from main
git checkout -b hotfix/critical-bug main

# Fix and commit
git add .
git commit -m "Fix critical bug"
git push gitlab hotfix/critical-bug

# Merge to main
git checkout main
git merge hotfix/critical-bug
git push gitlab main

# Manually deploy in GitLab
```

### Rollback

**Option 1 - GitLab UI:**
1. CI/CD > Pipelines
2. Find pipeline with working version
3. Click "Rollback" on deploy:production job

**Option 2 - VPS Script:**
```bash
ssh your-user@your-vps-host
cd /opt/discord-bot
./rollback.sh
```

**Option 3 - Manual Job:**
1. CI/CD > Pipelines > Latest
2. Click "Play" on rollback:production job

---

## 🐛 Troubleshooting

### Pipeline Fails at Build Stage

**Error**: "Cannot connect to Docker daemon"
**Fix**: GitLab runners need Docker-in-Docker enabled (already configured in `.gitlab-ci.yml`)

**Error**: "Permission denied for Docker Hub"
**Fix**: Check `DOCKER_USERNAME` and `DOCKER_PASSWORD` variables are correct

### Pipeline Fails at Deploy Stage

**Error**: "Permission denied (publickey)"
**Fix**:
1. Check `SSH_PRIVATE_KEY` variable includes headers
2. Verify public key is in VPS `~/.ssh/authorized_keys`
3. Test: `ssh -i ~/.ssh/gitlab_ci_bot your-user@your-vps-host`

**Error**: "docker-compose: command not found"
**Fix**: Install docker-compose on VPS:
```bash
sudo apt-get update
sudo apt-get install docker-compose-plugin
```

### Bot Doesn't Start on VPS

**Check logs:**
```bash
cd /opt/discord-bot
docker-compose logs -f bot
```

**Common issues:**
- Missing/wrong `.env.production` values
- Bot token expired
- Database API unreachable

---

## 📊 Version Bumping

Update version in `.gitlab-ci.yml`:

```yaml
variables:
  VERSION_MAJOR: "2"
  VERSION_MINOR: "1"  # ← Change this for new features
```

**Rules:**
- **Patch**: Auto-increments each pipeline
- **Minor**: Manual bump for new features
- **Major**: Manual bump for breaking changes

---

## 🎓 What You Get

✅ **Automated Testing**: Every push runs tests
✅ **Automated Builds**: Docker images built on CI
✅ **Semantic Versioning**: v2.1.X format
✅ **Manual Production Deploys**: Approval required
✅ **Automatic Rollback**: On health check failure
✅ **Quick Manual Rollback**: 3 methods available
✅ **Deployment History**: Full audit trail
✅ **Version Visibility**: `/version` command

---

## 📞 Support

If you get stuck:
1. Check GitLab pipeline logs
2. Check VPS docker logs: `docker-compose logs`
3. Check deployment log: `cat deployments.log`
4. Verify all CI/CD variables are set correctly

---

**Setup Time**: ~30 minutes
**Deployment Time After Setup**: ~2-3 minutes
**Rollback Time**: ~1-2 minutes

**You're all set! 🚀**

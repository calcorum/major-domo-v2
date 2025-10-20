# GitLab CI/CD Quick Reference

Quick commands and reminders for daily development.

---

## 🔄 Common Workflows

### Deploy Feature to Production

```bash
# 1. Develop feature
git checkout -b feature/my-feature develop
# ... make changes ...
git commit -m "Add my feature"
git push gitlab feature/my-feature

# 2. Merge to develop for staging test (optional)
git checkout develop
git merge feature/my-feature
git push gitlab develop
# → Auto-deploys to staging

# 3. Merge to main
git checkout main
git merge develop
git push gitlab main

# 4. In GitLab UI: CI/CD > Pipelines > Click ▶️ on deploy:production
```

### Emergency Rollback

```bash
# Option 1: VPS Script (fastest)
ssh user@vps "cd /opt/discord-bot && ./rollback.sh"

# Option 2: GitLab UI
# CI/CD > Pipelines > Click ▶️ on rollback:production

# Option 3: Manual
ssh user@vps
cd /opt/discord-bot
# Edit docker-compose.yml to previous version
docker-compose up -d
```

### Check Deployment Status

```bash
# Check running version on VPS
ssh user@vps "cd /opt/discord-bot && docker inspect discord-bot --format '{{.Config.Labels}}' | grep version"

# Check recent deployments
ssh user@vps "cd /opt/discord-bot && tail -10 deployments.log"

# Check bot health
ssh user@vps "cd /opt/discord-bot && docker-compose ps"
```

---

## 🏷️ Version Management

### Current Version Strategy

| Format | Example | Auto/Manual | When |
|--------|---------|-------------|------|
| Major | `v2.x.x` | Manual | Breaking changes |
| Minor | `v2.1.x` | Manual | New features |
| Patch | `v2.1.123` | Auto | Every build |

### Bump Version

Edit `.gitlab-ci.yml`:
```yaml
variables:
  VERSION_MAJOR: "2"
  VERSION_MINOR: "2"  # ← Change this
```

Then:
```bash
git add .gitlab-ci.yml
git commit -m "Bump version to v2.2.x"
git push gitlab main
```

---

## 🐳 Docker Tags Generated

Every build creates:
- `v2.1.123` - Full semantic version
- `a1b2c3d` - Git commit SHA
- `main-a1b2c3d` - Branch + SHA
- `latest` - Latest main branch (production)
- `staging` - Latest develop branch (staging)

---

## 🔍 Useful Commands

### Check Pipeline Status
```bash
# From CLI (requires gitlab-ci-lint or gitlab CLI)
gitlab-ci-lint .gitlab-ci.yml

# Or visit:
# https://gitlab.com/yourusername/discord-bot/-/pipelines
```

### View Logs
```bash
# Bot logs
ssh user@vps "cd /opt/discord-bot && docker-compose logs -f bot"

# Redis logs
ssh user@vps "cd /opt/discord-bot && docker-compose logs -f redis"

# Deployment history
ssh user@vps "cd /opt/discord-bot && cat deployments.log | column -t -s '|'"
```

### Test Locally Before Push
```bash
cd discord-app-v2
python -m pytest --tb=short -q
```

### Build Docker Image Locally
```bash
cd discord-app-v2
docker build \
  --build-arg VERSION="dev" \
  --build-arg GIT_COMMIT=$(git rev-parse --short HEAD) \
  --build-arg BUILD_DATE=$(date -u +"%Y-%m-%dT%H:%M:%SZ") \
  -t discord-bot-v2:local .
```

---

## 🎯 GitLab CI/CD Variables

**Required Variables** (Settings > CI/CD > Variables):

| Variable | Type | Example |
|----------|------|---------|
| `DOCKER_USERNAME` | Masked | `youruser` |
| `DOCKER_PASSWORD` | Masked | `dckr_pat_abc123...` |
| `SSH_PRIVATE_KEY` | Masked | `-----BEGIN OPENSSH...` |
| `VPS_HOST` | Plain | `123.456.789.0` |
| `VPS_USER` | Plain | `ubuntu` |

---

## 🚨 Emergency Procedures

### Build Failing

1. Check GitLab pipeline logs
2. Run tests locally: `pytest`
3. Check Docker build: `docker build ...`
4. Fix issues
5. Push again

### Deploy Failing

1. Check SSH access: `ssh user@vps`
2. Check docker-compose.yml exists
3. Check .env.production has all vars
4. Check VPS disk space: `df -h`
5. Check Docker is running: `docker ps`

### Bot Not Starting After Deploy

```bash
# SSH to VPS
ssh user@vps
cd /opt/discord-bot

# Check logs
docker-compose logs bot | tail -50

# Check health
docker-compose ps

# Restart
docker-compose restart bot

# Nuclear option: full restart
docker-compose down
docker-compose up -d
```

### Rollback Needed Immediately

```bash
# Fastest: VPS script
ssh user@vps "cd /opt/discord-bot && ./rollback.sh"

# Confirm version
ssh user@vps "cd /opt/discord-bot && docker-compose ps"
```

---

## 📊 Health Checks

### Bot Health
```bash
# Check if bot is healthy
ssh user@vps "docker inspect discord-bot --format '{{.State.Health.Status}}'"
# Should show: healthy

# Check Discord connection (in Discord)
/version
```

### Redis Health
```bash
ssh user@vps "docker exec discord-redis redis-cli ping"
# Should show: PONG
```

### Full System Check
```bash
ssh user@vps << 'EOF'
cd /opt/discord-bot
echo "=== Container Status ==="
docker-compose ps
echo ""
echo "=== Recent Logs ==="
docker-compose logs --tail=10 bot
echo ""
echo "=== Deployment History ==="
tail -5 deployments.log
EOF
```

---

## 🔐 Security Reminders

- ✅ Never commit `.env` files
- ✅ Use GitLab CI/CD variables for secrets
- ✅ Mark all secrets as "Masked" in GitLab
- ✅ Rotate SSH keys periodically
- ✅ Use Docker Hub access tokens, not passwords
- ✅ Keep VPS firewall enabled

---

## 📈 Monitoring

### Check Metrics
```bash
# If Prometheus is set up
curl http://vps-ip:8000/metrics

# Check bot uptime
ssh user@vps "docker inspect discord-bot --format '{{.State.StartedAt}}'"
```

### Watch Live Logs
```bash
ssh user@vps "cd /opt/discord-bot && docker-compose logs -f --tail=100"
```

---

## 🎓 Tips & Tricks

### Skip CI for Minor Changes
```bash
git commit -m "Update README [skip ci]"
```

### Test in Staging First
```bash
# Push to develop → auto-deploys to staging
git push gitlab develop

# Test thoroughly, then merge to main
```

### View All Available Versions
```bash
# On Docker Hub
docker search yourusername/discord-bot-v2

# On VPS
ssh user@vps "docker images yourusername/discord-bot-v2"
```

### Clean Up Old Images
```bash
# On VPS (run monthly)
ssh user@vps "docker image prune -a -f"
```

---

## 📞 Getting Help

1. **Check Logs**: Always start with logs
2. **GitLab Pipeline**: Look at failed job output
3. **Docker Logs**: `docker-compose logs`
4. **Deployment Log**: `cat deployments.log`

---

**Last Updated**: January 2025
**Bot Version**: v2.1.x
**CI/CD Platform**: GitLab CI/CD

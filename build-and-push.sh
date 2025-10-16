#!/bin/bash
# ============================================
# Build and Push Docker Image to Docker Hub
# ============================================
# Usage:
#   ./build-and-push.sh           # Build and push as 'latest'
#   ./build-and-push.sh 2.0.0     # Build and push as 'latest' and '2.0.0'

set -e  # Exit on error

# Configuration
VERSION="${1:-2.0.0}"
DOCKER_REPO="manticorum67/major-domo-discordapp"

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}======================================${NC}"
echo -e "${BLUE}Docker Build and Push${NC}"
echo -e "${BLUE}======================================${NC}"
echo ""
echo -e "${YELLOW}Repository:${NC} ${DOCKER_REPO}"
echo -e "${YELLOW}Version:${NC}    ${VERSION}"
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}❌ Error: Docker is not running${NC}"
    exit 1
fi

# Check if logged in to Docker Hub
if ! docker info 2>/dev/null | grep -q "Username"; then
    echo -e "${YELLOW}⚠️  Not logged in to Docker Hub${NC}"
    echo -e "${YELLOW}Please log in:${NC}"
    docker login
    echo ""
fi

# Build image
echo -e "${BLUE}🔨 Building Docker image...${NC}"
echo ""

if [ "$VERSION" = "latest" ]; then
    # Only tag as latest
    docker build -t ${DOCKER_REPO}:latest .
else
    # Tag as both latest and version
    docker build \
        -t ${DOCKER_REPO}:latest \
        -t ${DOCKER_REPO}:${VERSION} \
        .
fi

echo ""
echo -e "${GREEN}✅ Build complete!${NC}"
echo ""

# Confirm push
echo -e "${YELLOW}Ready to push to Docker Hub${NC}"
read -p "Continue? (y/n) " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}❌ Push cancelled${NC}"
    exit 0
fi

# Push image
echo ""
echo -e "${BLUE}📤 Pushing to Docker Hub...${NC}"
echo ""

docker push ${DOCKER_REPO}:latest

if [ "$VERSION" != "latest" ]; then
    docker push ${DOCKER_REPO}:${VERSION}
fi

echo ""
echo -e "${GREEN}✅ Push complete!${NC}"
echo ""
echo -e "${GREEN}🎉 Image available at:${NC}"
echo -e "   docker pull ${DOCKER_REPO}:latest"

if [ "$VERSION" != "latest" ]; then
    echo -e "   docker pull ${DOCKER_REPO}:${VERSION}"
fi

echo ""
echo -e "${BLUE}======================================${NC}"
echo -e "${GREEN}Done!${NC}"
echo -e "${BLUE}======================================${NC}"

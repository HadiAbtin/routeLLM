#!/bin/bash

# Script to build and push Docker images to Docker Hub
# Usage: ./scripts/build-and-push.sh [VERSION] [DOCKERHUB_USERNAME]
# Example: ./scripts/build-and-push.sh v1.0.0 myusername

set -e

VERSION=${1:-latest}
DOCKERHUB_USERNAME=${2:-${DOCKERHUB_USERNAME:-""}}

if [ -z "$DOCKERHUB_USERNAME" ]; then
    echo "❌ Error: Docker Hub username is required!"
    echo "Usage: $0 [VERSION] [DOCKERHUB_USERNAME]"
    echo "Or set DOCKERHUB_USERNAME environment variable"
    exit 1
fi

# Check if docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Error: Docker is not installed!"
    exit 1
fi

# Setup buildx if not exists
if ! docker buildx ls | grep -q "multiarch"; then
    echo "🔧 Setting up buildx builder..."
    docker buildx create --name multiarch --use --bootstrap || true
fi

# Use the builder
docker buildx use multiarch || docker buildx use default

echo "🔨 Building Docker images for linux/amd64 platform..."
echo "📦 Version: $VERSION"
echo "👤 Docker Hub Username: $DOCKERHUB_USERNAME"
echo ""

# Build backend image
echo "🏗️  Building backend image..."
docker buildx build \
    --platform linux/amd64 \
    --file deploy/docker/backend.Dockerfile \
    --tag ${DOCKERHUB_USERNAME}/route-llm-gateway-backend:${VERSION} \
    --tag ${DOCKERHUB_USERNAME}/route-llm-gateway-backend:latest \
    --push \
    .

echo "✅ Backend image built and pushed!"

# Build frontend image (requires VITE_API_BASE_URL)
VITE_API_BASE_URL=${VITE_API_BASE_URL:-http://localhost:8000}
echo "🏗️  Building frontend image with VITE_API_BASE_URL=${VITE_API_BASE_URL}..."
docker buildx build \
    --platform linux/amd64 \
    --file deploy/docker/frontend.Dockerfile \
    --build-arg VITE_API_BASE_URL=${VITE_API_BASE_URL} \
    --tag ${DOCKERHUB_USERNAME}/route-llm-gateway-frontend:${VERSION} \
    --tag ${DOCKERHUB_USERNAME}/route-llm-gateway-frontend:latest \
    --push \
    .

echo "✅ Frontend image built and pushed!"
echo ""
echo "🎉 All images built and pushed successfully!"
echo "📦 Images:"
echo "   - ${DOCKERHUB_USERNAME}/route-llm-gateway-backend:${VERSION}"
echo "   - ${DOCKERHUB_USERNAME}/route-llm-gateway-backend:latest"
echo "   - ${DOCKERHUB_USERNAME}/route-llm-gateway-frontend:${VERSION}"
echo "   - ${DOCKERHUB_USERNAME}/route-llm-gateway-frontend:latest"


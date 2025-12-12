#!/bin/bash
set -e

# Detect repository name from current directory
REPO_NAME=$(basename "$(pwd)" | tr '[:upper:]' '[:lower:]')
# Extract suffix (e.g., "latest" from "hafiscal-latest")
REPO_SUFFIX=$(echo "$REPO_NAME" | sed 's/^hafiscal-//' || echo "$REPO_NAME")

# Set image and container names
DOCKER_IMAGE="hafiscal-${REPO_SUFFIX}:latest"
DOCKER_CONTAINER="hafiscal-${REPO_SUFFIX}-container"

echo "Building Docker image: $DOCKER_IMAGE"
if ! docker build -t "$DOCKER_IMAGE" .; then
    echo "Build failed"
    exit 1
fi

# Check if container already exists and remove it
if docker ps -a --format '{{.Names}}' | grep -q "^${DOCKER_CONTAINER}$"; then
    echo "Removing existing container: $DOCKER_CONTAINER"
    docker rm -f "$DOCKER_CONTAINER" || true
fi

echo "Starting container: $DOCKER_CONTAINER"
docker run -d --name "$DOCKER_CONTAINER" \
  -p 8888:8888 -p 8866:8866 \
  "$DOCKER_IMAGE" tail -f /dev/null

echo ""
echo "Container started successfully"
echo "  Image: $DOCKER_IMAGE"
echo "  Container: $DOCKER_CONTAINER"
echo ""
echo "Connect with:"
echo "  docker exec -it $DOCKER_CONTAINER bash"
echo ""
echo "Stop container:"
echo "  docker stop $DOCKER_CONTAINER"
echo ""
echo "Remove container:"
echo "  docker rm $DOCKER_CONTAINER"




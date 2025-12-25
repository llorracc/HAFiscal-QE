#!/bin/bash
# Build, Test, and Push Docker Image
# This script builds a Docker image, tests it by running reproduce.sh --docs inside,
# and pushes to DockerHub if the test passes.

set -euo pipefail

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() { echo -e "${BLUE}ℹ️  $*${NC}"; }
log_success() { echo -e "${GREEN}✅ $*${NC}"; }
log_warning() { echo -e "${YELLOW}⚠️  $*${NC}"; }
log_error() { echo -e "${RED}❌ $*${NC}"; }

# Change to repository root (parent of reproduce/)
cd "$(dirname "$0")/.."
REPO_ROOT="$(pwd)"

# Detect repository name and set image details
REPO_NAME=$(basename "$REPO_ROOT" | tr '[:upper:]' '[:lower:]')
REPO_SUFFIX=${REPO_NAME#hafiscal-}

# Docker image details
DOCKER_USER="llorracc"
DOCKER_IMAGE_NAME="hafiscal-${REPO_SUFFIX}"
DOCKER_IMAGE_TAG="latest"
DOCKER_IMAGE="${DOCKER_USER}/${DOCKER_IMAGE_NAME}:${DOCKER_IMAGE_TAG}"
DOCKER_CONTAINER="test-${DOCKER_IMAGE_NAME}-$$"

echo ""
echo "=========================================="
echo "Docker Build, Test, and Push"
echo "=========================================="
echo ""
log_info "Repository: $REPO_ROOT"
log_info "Docker image: $DOCKER_IMAGE"
echo ""

# Step 0: Ensure Docker is running
log_info "Step 0: Ensuring Docker daemon is running..."
echo ""

# Check if Docker is already running
if ! docker info >/dev/null 2>&1; then
    log_warning "Docker daemon not running, attempting to start..."
    
    # Start Docker (macOS specific)
    if [[ "$OSTYPE" == "darwin"* ]]; then
        log_info "Starting Docker Desktop on macOS..."
        open -a Docker
        
        # Wait for Docker to start (max 60 seconds)
        log_info "Waiting for Docker daemon to be ready..."
        for i in {1..60}; do
            if docker info >/dev/null 2>&1; then
                log_success "Docker daemon is ready"
                break
            fi
            if [[ $i -eq 60 ]]; then
                log_error "Docker daemon failed to start within 60 seconds"
                echo ""
                echo "Debugging suggestions:"
                echo "  1. Manually start Docker Desktop: open -a Docker"
                echo "  2. Check Docker Desktop is installed: ls /Applications/Docker.app"
                echo "  3. Check system resources (Docker requires sufficient RAM/disk)"
                echo "  4. Restart Docker Desktop: killall Docker && open -a Docker"
                echo ""
                exit 1
            fi
            echo -n "."
            sleep 1
        done
        echo ""
    else
        log_error "Docker daemon not running and automatic start only supported on macOS"
        echo ""
        echo "Debugging suggestions:"
        echo "  1. Start Docker manually: sudo systemctl start docker"
        echo "  2. Enable Docker service: sudo systemctl enable docker"
        echo "  3. Check Docker installation: docker --version"
        echo ""
        exit 1
    fi
else
    log_success "Docker daemon is already running"
fi

echo ""

# Step 0.1: Stop all running containers
log_info "Step 0.1: Stopping all running containers..."
RUNNING_CONTAINERS=$(docker ps -q)
if [[ -n "$RUNNING_CONTAINERS" ]]; then
    log_info "Found running containers, stopping them..."
    docker stop "$RUNNING_CONTAINERS" || true
    log_success "All containers stopped"
else
    log_info "No running containers to stop"
fi

echo ""

# Step 0.2: Purge Docker storage
log_info "Step 0.2: Purging Docker storage to ensure space..."
echo ""
log_warning "This will remove:"
log_warning "  - All stopped containers"
log_warning "  - All networks not used by at least one container"
log_warning "  - All dangling images"
log_warning "  - All build cache"
echo ""

# Run docker system prune with force flag (no prompt)
if docker system prune -af --volumes; then
    log_success "Docker storage purged successfully"
    
    # Show disk usage after purge
    echo ""
    log_info "Docker disk usage after purge:"
    docker system df
else
    log_warning "Docker system prune had some issues, continuing anyway..."
fi

echo ""
log_success "Docker preparation complete"
echo ""

# Step 1: Verify Dockerfile exists
if [[ ! -f "Dockerfile" ]]; then
    log_error "Dockerfile not found in $REPO_ROOT"
    log_error "Cannot build Docker image without Dockerfile"
    exit 1
fi

log_success "Dockerfile found"

# Step 2: Build Docker image
log_info "Building Docker image: $DOCKER_IMAGE"
echo ""

if ! docker build -t "$DOCKER_IMAGE" .; then
    log_error "Docker build failed"
    echo ""
    echo "Debugging suggestions:"
    echo "  1. Check Dockerfile syntax: docker build --no-cache -t test ."
    echo "  2. Review build context size: du -sh ."
    echo "  3. Check for missing dependencies in Dockerfile"
    echo "  4. Verify base image is accessible: docker pull <base-image>"
    echo ""
    exit 1
fi

echo ""
log_success "Docker image built successfully"

# Get image size
IMAGE_SIZE=$(docker images "$DOCKER_IMAGE" --format "{{.Size}}" | head -1)
log_info "Image size: $IMAGE_SIZE"
echo ""

# Step 3: Test Docker image
log_info "Testing Docker image..."
echo ""

# Clean up any existing test container
docker rm -f "$DOCKER_CONTAINER" 2>/dev/null || true

# Create test container
log_info "Starting test container: $DOCKER_CONTAINER"
if ! docker run -d --name "$DOCKER_CONTAINER" "$DOCKER_IMAGE" tail -f /dev/null; then
    log_error "Failed to start test container"
    echo ""
    echo "Debugging suggestions:"
    echo "  1. Check if image was built correctly: docker images $DOCKER_IMAGE"
    echo "  2. Try running interactively: docker run -it $DOCKER_IMAGE bash"
    echo "  3. Check container logs: docker logs $DOCKER_CONTAINER"
    echo ""
    exit 1
fi

log_success "Test container started"

# Test 1: Check reproduce.sh exists and is executable
log_info "Test 1: Checking reproduce.sh..."
if ! docker exec "$DOCKER_CONTAINER" test -x /workspace/reproduce.sh; then
    log_error "reproduce.sh not found or not executable in container"
    docker rm -f "$DOCKER_CONTAINER" 2>/dev/null || true
    echo ""
    echo "Debugging suggestions:"
    echo "  1. Verify COPY commands in Dockerfile include reproduce.sh"
    echo "  2. Check file permissions: RUN chmod +x reproduce.sh"
    echo "  3. Verify WORKDIR is set correctly in Dockerfile (should be /workspace)"
    echo ""
    exit 1
fi
log_success "reproduce.sh found and executable"

# Test 2: Run reproduce.sh --docs to verify paper can be built
log_info "Test 2: Running reproduce.sh --docs in container..."
echo ""

# #region agent log
# Diagnostic pre-checks before running reproduce.sh
# NOTE: Critical guidelines
# - Do not write to absolute dev-machine paths (this script runs in many environments)
# - Prefer a temp file on the host running the docker commands

log_info "Running diagnostic checks..."

# Hypothesis A: Check PATH and TeX Live
echo "{\"location\":\"build-and-test-docker.sh:210\",\"message\":\"Hypothesis A: PATH check\",\"data\":{\"hypothesis\":\"A\"},\"timestamp\":$(date +%s)000,\"sessionId\":\"debug-session\"}" >> "$DEBUG_LOG"
PDFLATEX_PATH=$(docker exec "$DOCKER_CONTAINER" bash -c 'which pdflatex' 2>&1)
PDFLATEX_VERSION=$(docker exec "$DOCKER_CONTAINER" bash -c 'pdflatex --version 2>&1 | head -1' 2>&1)
BIBTEX_PATH=$(docker exec "$DOCKER_CONTAINER" bash -c 'which bibtex' 2>&1)
BIBTEX_VERSION=$(docker exec "$DOCKER_CONTAINER" bash -c 'bibtex --version 2>&1 | head -1' 2>&1)
echo "{\"location\":\"build-and-test-docker.sh:215\",\"message\":\"pdflatex and bibtex check\",\"data\":{\"hypothesis\":\"A\",\"pdflatex_path\":\"$PDFLATEX_PATH\",\"pdflatex_version\":\"$PDFLATEX_VERSION\",\"bibtex_path\":\"$BIBTEX_PATH\",\"bibtex_version\":\"$BIBTEX_VERSION\"},\"timestamp\":$(date +%s)000,\"sessionId\":\"debug-session\"}" >> "$DEBUG_LOG"

# Hypothesis B: Check TEXINPUTS and @local packages
TEXINPUTS_VAL=$(docker exec "$DOCKER_CONTAINER" bash -c 'echo $TEXINPUTS' 2>&1)
LOCAL_EXISTS=$(docker exec "$DOCKER_CONTAINER" bash -c 'test -d /workspace/@local && echo "EXISTS" || echo "MISSING"' 2>&1)
LOCAL_FILES=$(docker exec "$DOCKER_CONTAINER" bash -c 'ls /workspace/@local/ 2>&1 | head -10 | tr "\n" "," ' 2>&1)
echo "{\"location\":\"build-and-test-docker.sh:220\",\"message\":\"TEXINPUTS and @local check\",\"data\":{\"hypothesis\":\"B\",\"texinputs\":\"$TEXINPUTS_VAL\",\"local_dir\":\"$LOCAL_EXISTS\",\"local_files\":\"$LOCAL_FILES\"},\"timestamp\":$(date +%s)000,\"sessionId\":\"debug-session\"}" >> "$DEBUG_LOG"

# Hypothesis C: Check virtual environment activation
PYTHON_PATH=$(docker exec "$DOCKER_CONTAINER" bash -c 'which python' 2>&1)
PYTHON_VERSION=$(docker exec "$DOCKER_CONTAINER" bash -c 'python --version' 2>&1)
VENV_VAR=$(docker exec "$DOCKER_CONTAINER" bash -c 'echo $VIRTUAL_ENV' 2>&1)
echo "{\"location\":\"build-and-test-docker.sh:227\",\"message\":\"Python venv check\",\"data\":{\"hypothesis\":\"C\",\"python_path\":\"$PYTHON_PATH\",\"version\":\"$PYTHON_VERSION\",\"virtual_env\":\"$VENV_VAR\"},\"timestamp\":$(date +%s)000,\"sessionId\":\"debug-session\"}" >> "$DEBUG_LOG"

# Hypothesis D: Check critical files exist
TEX_EXISTS=$(docker exec "$DOCKER_CONTAINER" bash -c 'test -f /workspace/HAFiscal.tex && echo "EXISTS" || echo "MISSING"' 2>&1)
BIB_EXISTS=$(docker exec "$DOCKER_CONTAINER" bash -c 'test -f /workspace/HAFiscal.bib && echo "EXISTS" || echo "MISSING"' 2>&1)
echo "{\"location\":\"build-and-test-docker.sh:233\",\"message\":\"Critical files check\",\"data\":{\"hypothesis\":\"D\",\"hafiscal_tex\":\"$TEX_EXISTS\",\"hafiscal_bib\":\"$BIB_EXISTS\"},\"timestamp\":$(date +%s)000,\"sessionId\":\"debug-session\"}" >> "$DEBUG_LOG"

# Hypothesis E: Check write permissions
WORKSPACE_PERMS=$(docker exec "$DOCKER_CONTAINER" bash -c 'ls -ld /workspace' 2>&1)
LOGS_PERMS=$(docker exec "$DOCKER_CONTAINER" bash -c 'ls -ld /workspace/reproduce/logs 2>&1 || echo "MISSING"' 2>&1)
echo "{\"location\":\"build-and-test-docker.sh:238\",\"message\":\"Permissions check\",\"data\":{\"hypothesis\":\"E\",\"workspace\":\"$WORKSPACE_PERMS\",\"logs_dir\":\"$LOGS_PERMS\"},\"timestamp\":$(date +%s)000,\"sessionId\":\"debug-session\"}" >> "$DEBUG_LOG"

log_success "Diagnostics complete (saved to $DEBUG_LOG)"
# #endregion

# #region agent log
# Test if bash -i sources .bashrc and sets environment properly
log_info "Testing bash -i environment activation..."
INTERACTIVE_VENV=$(docker exec "$DOCKER_CONTAINER" bash -i -c 'echo $VIRTUAL_ENV' 2>&1)
INTERACTIVE_TEXINPUTS=$(docker exec "$DOCKER_CONTAINER" bash -i -c 'echo $TEXINPUTS' 2>&1)
echo "{\"location\":\"build-and-test-docker.sh:245\",\"message\":\"bash -i environment test\",\"data\":{\"virtual_env_i\":\"$INTERACTIVE_VENV\",\"texinputs_i\":\"$INTERACTIVE_TEXINPUTS\"},\"timestamp\":$(date +%s)000,\"sessionId\":\"debug-session\"}" >> "$DEBUG_LOG"
log_info "bash -i test: VIRTUAL_ENV=$INTERACTIVE_VENV TEXINPUTS=$INTERACTIVE_TEXINPUTS"
# #endregion

if docker exec "$DOCKER_CONTAINER" bash -c "source /home/vscode/.bashrc 2>/dev/null; cd /workspace && ./reproduce.sh --docs" > /tmp/docker-test-$$.log 2>&1; then
    log_success "reproduce.sh --docs completed successfully"
    
    # Check if PDF was generated
    if docker exec "$DOCKER_CONTAINER" test -f /workspace/HAFiscal.pdf; then
        PDF_SIZE=$(docker exec "$DOCKER_CONTAINER" ls -lh /workspace/HAFiscal.pdf | awk '{print $5}')
        log_success "HAFiscal.pdf generated ($PDF_SIZE)"
    else
        log_warning "reproduce.sh succeeded but HAFiscal.pdf not found"
    fi
else
    log_error "reproduce.sh --docs failed in container"
    echo ""
    
    # #region agent log
    # Capture failure details for analysis  
    # Save full log to temp file for analysis
    docker exec "$DOCKER_CONTAINER" cat /workspace/reproduce/logs/latest.log > /tmp/container-reproduce-log-$$.txt 2>&1 || echo "LOG_NOT_FOUND" > /tmp/container-reproduce-log-$$.txt
    
    # Extract LaTeX errors (lines with !) and surrounding context
    LATEX_ERRORS=$(grep -B2 -A2 "^!" /tmp/container-reproduce-log-$$.txt | head -50 | tr '\n' '|' | tr '"' "'" || echo "NO_LATEX_ERRORS")
    echo "{\"location\":\"build-and-test-docker.sh:257\",\"message\":\"LaTeX errors from log\",\"data\":{\"errors\":\"$LATEX_ERRORS\"},\"timestamp\":$(date +%s)000,\"sessionId\":\"debug-session\"}" >> "$DEBUG_LOG"
    
    # Also check for latexmk errors
    LATEXMK_ERRORS=$(grep -i "latexmk.*error\|rule.*failed" /tmp/container-reproduce-log-$$.txt | head -10 | tr '\n' '|' || echo "NO_LATEXMK_ERRORS")
    echo "{\"location\":\"build-and-test-docker.sh:262\",\"message\":\"Latexmk errors\",\"data\":{\"errors\":\"$LATEXMK_ERRORS\"},\"timestamp\":$(date +%s)000,\"sessionId\":\"debug-session\"}" >> "$DEBUG_LOG"
    
    # Check for missing files
    MISSING_FILES=$(grep -i "file.*not found\|cannot find\|no such file" /tmp/container-reproduce-log-$$.txt | head -10 | tr '\n' '|' || echo "NO_MISSING_FILES")
    echo "{\"location\":\"build-and-test-docker.sh:267\",\"message\":\"Missing files\",\"data\":{\"files\":\"$MISSING_FILES\"},\"timestamp\":$(date +%s)000,\"sessionId\":\"debug-session\"}" >> "$DEBUG_LOG"
    # #endregion
    
    echo "Last 50 lines of output:"
    tail -50 /tmp/docker-test-$$.log
    echo ""
    echo "Container reproduce log (last 30 lines):"
    docker exec "$DOCKER_CONTAINER" tail -30 /workspace/reproduce/logs/latest.log 2>&1 || echo "Could not read container log"
    echo ""
    docker rm -f "$DOCKER_CONTAINER" 2>/dev/null || true
    echo ""
    echo "Debugging suggestions:"
    echo "  1. Check LaTeX installation in Dockerfile: RUN apt-get install texlive-full"
    echo "  2. Verify all dependencies are installed: check environment.yml and pyproject.toml"
    echo "  3. Run interactively to debug: docker run -it $DOCKER_IMAGE bash"
    echo "  4. Check reproduce logs in container: docker exec $DOCKER_CONTAINER cat /workspace/reproduce/logs/latest.log"
    echo ""
    rm -f /tmp/docker-test-$$.log
    exit 1
fi

# Clean up test container
log_info "Cleaning up test container..."
docker rm -f "$DOCKER_CONTAINER" 2>/dev/null || true
rm -f /tmp/docker-test-$$.log
log_success "Test container removed"

echo ""
log_success "All tests passed"
echo ""

# Step 4: Tag for DockerHub
log_info "Tagging image for DockerHub: $DOCKER_IMAGE"

# Step 5: Push to DockerHub
log_info "Pushing to DockerHub..."
echo ""

if ! docker push "$DOCKER_IMAGE"; then
    log_error "Docker push failed"
    echo ""
    echo "Debugging suggestions:"
    echo "  1. Login to DockerHub: docker login"
    echo "  2. Verify credentials: cat ~/.docker/config.json"
    echo "  3. Check repository exists: https://hub.docker.com/r/$DOCKER_USER/$DOCKER_IMAGE_NAME"
    echo "  4. Try manual push: docker push $DOCKER_IMAGE"
    echo ""
    echo "To push manually after fixing:"
    echo "  docker push $DOCKER_IMAGE"
    echo ""
    exit 1
fi

echo ""
log_success "Docker image pushed successfully to DockerHub"
echo ""
echo "=========================================="
echo "Docker Build Complete"
echo "=========================================="
echo ""
echo "Image: $DOCKER_IMAGE"
echo "Size: $IMAGE_SIZE"
echo "DockerHub: https://hub.docker.com/r/$DOCKER_USER/$DOCKER_IMAGE_NAME"
echo ""
echo "To use this image:"
echo "  docker pull $DOCKER_IMAGE"
echo "  docker run -it $DOCKER_IMAGE bash"
echo ""



#!/bin/bash
# TeX Live Installation Method Comparison Benchmark
# This script tests multiple TeX Live installation methods and compares timing and size

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RESULTS_DIR="${PROJECT_ROOT}/.devcontainer/comparison-results"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "════════════════════════════════════════════════════════════════"
echo "  TeX Live Installation Method Comparison Benchmark"
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "This will test 3 installation methods:"
echo "  1. apt-method: Ubuntu APT (base + recommended)"
echo "  2. direct-basic: Direct TeX Live (scheme-basic + packages)"
echo "  3. direct-medium: Direct TeX Live (scheme-medium)"
echo ""
echo "Each test will:"
echo "  • Build devcontainer from scratch (--no-cache)"
echo "  • Measure build time"
echo "  • Record container size"
echo "  • Test LaTeX compilation"
echo "  • Measure compilation time"
echo ""
echo "Expected total time: 1-2 hours"
echo ""
read -r -p "Press Enter to continue or Ctrl+C to cancel..."
echo ""

# Initialize results directory
mkdir -p "$RESULTS_DIR"
RESULTS_FILE="${RESULTS_DIR}/results-${TIMESTAMP}.md"
CSV_FILE="${RESULTS_DIR}/results-${TIMESTAMP}.csv"

# Initialize CSV
echo "Method,Build Time (s),Image Size,Container Size (MB),Compile Time (s),Status" > "$CSV_FILE"

# Initialize Markdown results
cat > "$RESULTS_FILE" << HEADER
# TeX Live Installation Method Comparison Results

**Date**: $(date)
**System**: $(uname -s) $(uname -m)
**Docker**: $(docker --version)
**DevContainer CLI**: $(devcontainer --version 2>&1 | head -1)

---

HEADER

test_configuration() {
    local METHOD=$1
    local CONFIG_DIR="${PROJECT_ROOT}/.devcontainer/${METHOD}"
    local IMAGE_NAME="hafiscal-test-${METHOD}"
    
    echo ""
    echo -e "${BLUE}════════════════════════════════════════${NC}"
    echo -e "${BLUE}Testing: ${METHOD}${NC}"
    echo -e "${BLUE}════════════════════════════════════════${NC}"
    echo ""
    
    # Clean up any existing containers/images
    echo "🧹 Cleaning up previous test artifacts..."
    docker rm -f "$(docker ps -aq --filter "ancestor=${IMAGE_NAME}")" 2>/dev/null || true
    docker rmi -f "${IMAGE_NAME}" 2>/dev/null || true
    
    # Build container with timing
    echo "🔨 Building container (this may take several minutes)..."
    echo "   Config: ${CONFIG_DIR}/devcontainer.json"
    
    local BUILD_START=$(date +%s)
    local BUILD_LOG="${RESULTS_DIR}/${METHOD}-build-${TIMESTAMP}.log"
    
    if devcontainer build \
        --workspace-folder "$PROJECT_ROOT" \
        --config "${CONFIG_DIR}/devcontainer.json" \
        --image-name "${IMAGE_NAME}" \
        --no-cache 2>&1 | tee "$BUILD_LOG"; then
        
        local BUILD_END=$(date +%s)
        local BUILD_TIME=$((BUILD_END - BUILD_START))
        
        echo -e "${GREEN}✅ Build completed in ${BUILD_TIME}s${NC}"
        
        # Get image size
        local IMAGE_SIZE=$(docker images "${IMAGE_NAME}" --format "{{.Size}}" 2>/dev/null || echo "Unknown")
        local IMAGE_SIZE_MB=$(docker images "${IMAGE_NAME}" --format "{{.Size}}" 2>/dev/null | sed 's/GB/*1024/;s/MB//;s/KB\/1024/' | bc 2>/dev/null || echo "0")
        
        echo "📦 Image size: ${IMAGE_SIZE}"
        
        # Start container
        echo "🚀 Starting container..."
        if devcontainer up \
            --workspace-folder "$PROJECT_ROOT" \
            --config "${CONFIG_DIR}/devcontainer.json" 2>&1 | tee -a "$BUILD_LOG"; then
            
            # Test LaTeX compilation
            echo "📄 Testing LaTeX compilation..."
            local COMPILE_START=$(date +%s)
            local COMPILE_LOG="${RESULTS_DIR}/${METHOD}-compile-${TIMESTAMP}.log"
            
            if devcontainer exec \
                --workspace-folder "$PROJECT_ROOT" \
                --config "${CONFIG_DIR}/devcontainer.json" \
                bash -c "cd /workspaces/HAFiscal-Latest && ./reproduce.sh --docs main" 2>&1 | tee "$COMPILE_LOG"; then
                
                local COMPILE_END=$(date +%s)
                local COMPILE_TIME=$((COMPILE_END - COMPILE_START))
                
                echo -e "${GREEN}✅ Compilation successful in ${COMPILE_TIME}s${NC}"
                
                # Extract TeX Live installation time from logs if available
                local TEXLIVE_TIME=$(grep "TeX Live installation completed in" "$BUILD_LOG" | grep -oE '[0-9]+s' | tr -d 's' || echo "N/A")
                
                # Record results
                cat >> "$RESULTS_FILE" << RESULT

## ${METHOD}

**Status**: ✅ SUCCESS

### Timing
- **Total Build Time**: ${BUILD_TIME}s
- **TeX Live Install Time**: ${TEXLIVE_TIME}s
- **First Compilation Time**: ${COMPILE_TIME}s

### Size
- **Image Size**: ${IMAGE_SIZE}
- **Image Size (MB)**: ${IMAGE_SIZE_MB}

### Logs
- Build log: \`${METHOD}-build-${TIMESTAMP}.log\`
- Compile log: \`${METHOD}-compile-${TIMESTAMP}.log\`

RESULT
                
                # Add to CSV
                echo "${METHOD},${BUILD_TIME},${IMAGE_SIZE},${IMAGE_SIZE_MB},${COMPILE_TIME},SUCCESS" >> "$CSV_FILE"
                
                echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
                echo -e "${GREEN}${METHOD} test completed successfully!${NC}"
                echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
                
            else
                echo -e "${RED}❌ Compilation failed${NC}"
                echo "${METHOD},${BUILD_TIME},${IMAGE_SIZE},${IMAGE_SIZE_MB},N/A,COMPILE_FAILED" >> "$CSV_FILE"
                
                cat >> "$RESULTS_FILE" << RESULT

## ${METHOD}

**Status**: ❌ COMPILE_FAILED

- Build Time: ${BUILD_TIME}s
- Image Size: ${IMAGE_SIZE}

See logs for details.

RESULT
            fi
        else
            echo -e "${RED}❌ Container start failed${NC}"
            echo "${METHOD},${BUILD_TIME},${IMAGE_SIZE},${IMAGE_SIZE_MB},N/A,START_FAILED" >> "$CSV_FILE"
        fi
    else
        local BUILD_END=$(date +%s)
        local BUILD_TIME=$((BUILD_END - BUILD_START))
        echo -e "${RED}❌ Build failed after ${BUILD_TIME}s${NC}"
        echo "${METHOD},${BUILD_TIME},N/A,N/A,N/A,BUILD_FAILED" >> "$CSV_FILE"
        
        cat >> "$RESULTS_FILE" << RESULT

## ${METHOD}

**Status**: ❌ BUILD_FAILED

- Build Time: ${BUILD_TIME}s

See build log for details: \`${METHOD}-build-${TIMESTAMP}.log\`

RESULT
    fi
    
    echo ""
}

# Run tests for each method
test_configuration "apt-method"
test_configuration "direct-basic"
test_configuration "direct-medium"

# Generate summary
echo ""
echo "════════════════════════════════════════════════════════════════"
echo "  Benchmark Complete!"
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "Results saved to:"
echo "  📄 ${RESULTS_FILE}"
echo "  📊 ${CSV_FILE}"
echo ""
echo "Summary:"
echo "--------"
column -t -s ',' "$CSV_FILE"
echo ""

# Create comparison chart in markdown
cat >> "$RESULTS_FILE" << 'SUMMARY'

---

## Summary Comparison

| Method | Build Time | Image Size | Compile Time | Status |
|--------|-----------|------------|--------------|--------|
SUMMARY

tail -n +2 "$CSV_FILE" | while IFS=',' read -r method build_time image_size size_mb compile_time status; do
    echo "| $method | ${build_time}s | $image_size | ${compile_time}s | $status |" >> "$RESULTS_FILE"
done

cat >> "$RESULTS_FILE" << 'FOOTER'

---

## Recommendations

Based on the test results above, consider:

1. **For minimum container size**: Choose the method with smallest image size
2. **For fastest setup**: Choose the method with shortest build time
3. **For ease of maintenance**: Ubuntu APT method is typically easier
4. **For cutting-edge packages**: Direct TeX Live gets latest versions

## Notes

- Build times include full container creation from base image
- Image sizes are for the final container image
- Compile times are for first compilation (includes any warm-up overhead)
- All tests performed with `--no-cache` for fair comparison

FOOTER

echo "✅ Full report generated!"
echo ""


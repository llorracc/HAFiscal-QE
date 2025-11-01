#!/bin/bash
#
# HAFiscal Reproduction Benchmarking Wrapper
#
# This script wraps the reproduce.sh script to capture detailed timing
# and system information for benchmarking purposes.
#
# Usage:
#   ./reproduce/benchmarks/benchmark.sh [reproduce.sh arguments]
#   ./reproduce/benchmarks/benchmark.sh --docs
#   ./reproduce/benchmarks/benchmark.sh --comp min
#   ./reproduce/benchmarks/benchmark.sh --comp full --notes "Testing optimization"
#

set -euo pipefail

# Get absolute paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
RESULTS_DIR="$SCRIPT_DIR/results"
CAPTURE_SCRIPT="$SCRIPT_DIR/capture_system_info.py"
REPRODUCE_SCRIPT="$PROJECT_ROOT/reproduce.sh"

# Ensure results directory exists
mkdir -p "$RESULTS_DIR"

# Parse arguments
REPRODUCE_ARGS=()
BENCHMARK_NOTES=""
while [[ $# -gt 0 ]]; do
    case $1 in
        --notes)
            BENCHMARK_NOTES="$2"
            shift 2
            ;;
        *)
            REPRODUCE_ARGS+=("$1")
            shift
            ;;
    esac
done

# Generate benchmark ID
TIMESTAMP=$(date -u +"%Y-%m-%dT%H-%M-%SZ")
OS=$(uname -s | tr '[:upper:]' '[:lower:]')
ARCH=$(uname -m)
MODE="${REPRODUCE_ARGS[*]}"
MODE_SLUG=$(echo "$MODE" | tr ' ' '-' | tr -d '=' | sed 's/--//g')
BENCHMARK_ID="${TIMESTAMP}_${MODE_SLUG}_${OS}-${ARCH}"
OUTPUT_FILE="$RESULTS_DIR/${BENCHMARK_ID}.json"

# Determine reproduction mode for JSON
REPRODUCTION_MODE="unknown"
if [[ " ${REPRODUCE_ARGS[*]} " =~ " --docs " ]] || [[ " ${REPRODUCE_ARGS[*]} " =~ " -d " ]]; then
    REPRODUCTION_MODE="docs"
elif [[ " ${REPRODUCE_ARGS[*]} " =~ " --comp " ]] || [[ " ${REPRODUCE_ARGS[*]} " =~ " -c " ]]; then
    if [[ " ${REPRODUCE_ARGS[*]} " =~ " min " ]]; then
        REPRODUCTION_MODE="comp-min"
    elif [[ " ${REPRODUCE_ARGS[*]} " =~ " all " ]]; then
        REPRODUCTION_MODE="comp-all"
    else
        REPRODUCTION_MODE="comp"
    fi
elif [[ " ${REPRODUCE_ARGS[*]} " =~ " --all " ]] || [[ " ${REPRODUCE_ARGS[*]} " =~ " -a " ]]; then
    REPRODUCTION_MODE="all"
fi

echo "========================================"
echo "HAFiscal Reproduction Benchmark"
echo "========================================"
echo ""
echo "Benchmark ID: $BENCHMARK_ID"
echo "Mode: $REPRODUCTION_MODE"
echo "Output: $OUTPUT_FILE"
if [[ -n "$BENCHMARK_NOTES" ]]; then
    echo "Notes: $BENCHMARK_NOTES"
fi
echo ""
echo "Capturing system information..."

# Capture system info
python3 "$CAPTURE_SCRIPT" --output /tmp/hafiscal_sysinfo_$$.json --pretty

echo "Starting reproduction..."
echo "========================================"
echo ""

# Record start time
START_TIME=$(date +%s)
START_ISO=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Run reproduction and capture exit status
EXIT_STATUS=0
if [[ ${#REPRODUCE_ARGS[@]} -eq 0 ]]; then
    "$REPRODUCE_SCRIPT" || EXIT_STATUS=$?
else
    "$REPRODUCE_SCRIPT" "${REPRODUCE_ARGS[@]}" || EXIT_STATUS=$?
fi

# Record end time
END_TIME=$(date +%s)
END_ISO=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
DURATION=$((END_TIME - START_TIME))

echo ""
echo "========================================"
echo "Reproduction completed"
echo "========================================"
echo ""
echo "Duration: ${DURATION}s ($(printf '%d:%02d:%02d' $((DURATION/3600)) $((DURATION%3600/60)) $((DURATION%60))))"
echo "Exit status: $EXIT_STATUS"
echo ""

# Build final JSON
echo "Generating benchmark report..."

# Read system info
SYSTEM_INFO=$(cat /tmp/hafiscal_sysinfo_$$.json)

# Get username
USER_NAME="${USER:-unknown}"

# Build JSON
cat > "$OUTPUT_FILE" << EOF
{
  "benchmark_version": "1.0.0",
  "benchmark_id": "$BENCHMARK_ID",
  "timestamp": "$START_ISO",
  "timestamp_end": "$END_ISO",
  "reproduction_mode": "$REPRODUCTION_MODE",
  "reproduction_args": $(printf '%s\n' "${REPRODUCE_ARGS[@]}" | jq -R . | jq -s .),
  "exit_status": $EXIT_STATUS,
  "duration_seconds": $DURATION,
$(echo "$SYSTEM_INFO" | sed 's/^/  /' | sed '1d; $d'),
  "metadata": {
    "user": "$USER_NAME",
    "session_id": "$$",
    "ci": ${CI:-false},
    "notes": $(echo "$BENCHMARK_NOTES" | jq -R .)
  }
}
EOF

# Clean up temp file
rm -f /tmp/hafiscal_sysinfo_$$.json

echo "✅ Benchmark report saved: $OUTPUT_FILE"
echo ""

# Create/update latest symlink
ln -sf "$BENCHMARK_ID.json" "$RESULTS_DIR/latest.json"
echo "📊 Latest benchmark: $RESULTS_DIR/latest.json"
echo ""

# Display summary
echo "========================================"
echo "Benchmark Summary"
echo "========================================"
echo ""
echo "Mode:     $REPRODUCTION_MODE"
echo "Duration: $(printf '%d:%02d:%02d' $((DURATION/3600)) $((DURATION%3600/60)) $((DURATION%60))) ($DURATION seconds)"
if [ $EXIT_STATUS -eq 0 ]; then
    echo "Status:   ✅ Success"
else
    echo "Status:   ❌ Failed (exit $EXIT_STATUS)"
fi
echo "OS:       $(uname -s) $(uname -r)"
echo "Arch:     $(uname -m)"
echo ""
echo "View full report:"
echo "  cat $OUTPUT_FILE | jq ."
echo ""
echo "View system info:"
echo "  cat $OUTPUT_FILE | jq '.system'"
echo ""

exit $EXIT_STATUS




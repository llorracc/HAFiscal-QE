#!/usr/bin/env bash
# benchmark_results.sh - Display benchmark results in a neat table
#
# Usage: ./benchmark_results.sh [docs|comp|data|envt|all]
#
# Displays benchmark results from JSON files in reproduce/benchmarks/results/
# in a formatted table showing key metrics.

set -euo pipefail

# Colors for output
BOLD="\033[1m"
DIM="\033[2m"
RESET="\033[0m"
GREEN="\033[32m"
RED="\033[31m"
YELLOW="\033[33m"

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RESULTS_DIR="$SCRIPT_DIR/results"

# Parse arguments
MODE="${1:-all}"

show_help() {
    cat << EOF
Usage: ./benchmark_results.sh [MODE]

Display benchmark results in a formatted table.

MODES:
  docs    Show document compilation benchmarks
  comp    Show computational benchmarks
  data    Show data processing benchmarks
  envt    Show environment testing benchmarks
  all     Show all benchmarks (default)

EXAMPLES:
  ./benchmark_results.sh docs     # Show only document compilations
  ./benchmark_results.sh comp     # Show only computational runs
  ./benchmark_results.sh          # Show all benchmarks

EOF
}

format_duration() {
    local seconds=$1
    # Always return seconds with 's' suffix
    printf "%ds" "$seconds"
}

format_timestamp() {
    local iso_timestamp=$1
    # Convert ISO timestamp to readable format (macOS/Linux compatible)
    if date --version &>/dev/null 2>&1; then
        # GNU date
        date -d "$iso_timestamp" "+%b %d %H:%M" 2>/dev/null || echo "$iso_timestamp"
    else
        # BSD date (macOS)
        date -j -f "%Y-%m-%dT%H:%M:%SZ" "$iso_timestamp" "+%b %d %H:%M" 2>/dev/null || echo "$iso_timestamp"
    fi
}

# Check arguments
if [[ "$MODE" == "--help" || "$MODE" == "-h" ]]; then
    show_help
    exit 0
fi

if [[ ! "$MODE" =~ ^(docs|comp|data|envt|all)$ ]]; then
    echo "Error: Invalid mode '$MODE'"
    echo "Must be one of: docs, comp, data, envt, all"
    echo ""
    show_help
    exit 1
fi

# Check if results directory exists
if [[ ! -d "$RESULTS_DIR" ]]; then
    echo "Error: Results directory not found: $RESULTS_DIR"
    exit 1
fi

# Check if jq is available
if ! command -v jq &> /dev/null; then
    echo "Error: jq is required but not installed."
    echo "Install with: brew install jq  (macOS) or  apt-get install jq  (Linux)"
    exit 1
fi

# Find JSON files (exclude symlinks like latest.json)
mapfile -t json_files < <(find "$RESULTS_DIR" -name "*.json" -type f | sort -r)

if [[ ${#json_files[@]} -eq 0 ]]; then
    echo "No benchmark results found in $RESULTS_DIR"
    exit 0
fi

# Validate and filter JSON files
filtered_files=()
broken_files=0
for file in "${json_files[@]}"; do
    # Skip if not valid JSON
    if ! jq empty "$file" 2>/dev/null; then
        ((broken_files++)) || true
        continue
    fi
    
    # Filter by mode if not 'all'
    if [[ "$MODE" == "all" ]]; then
        filtered_files+=("$file")
    else
        file_mode=$(jq -r '.reproduction_mode // "unknown"' "$file" 2>/dev/null || echo "unknown")
        if [[ "$file_mode" == "$MODE" ]]; then
            filtered_files+=("$file")
        fi
    fi
done

if [[ ${#filtered_files[@]} -eq 0 ]]; then
    echo "No benchmark results found for mode: $MODE"
    exit 0
fi

# Header
echo ""
echo -e "${BOLD}HAFiscal Benchmark Results${RESET}"
if [[ "$MODE" != "all" ]]; then
    echo -e "${DIM}Filtering by mode: $MODE${RESET}"
fi
echo ""

# Table header (total width: ~118 chars to stay under 120)
printf "${BOLD}%-13s %-6s %-8s %-18s %-6s %7s %6s  %-30s${RESET}\n" \
    "DATE" "MODE" "SCOPE" "HARDWARE" "RAM" "DUR(s)" "STATUS" "NOTES"
printf "%.118s\n" "$(printf '%0.s─' {1..118})"

# Process each file
for file in "${filtered_files[@]}"; do
    # Extract data using jq
    timestamp=$(jq -r '.timestamp // "unknown"' "$file" 2>/dev/null || echo "unknown")
    mode=$(jq -r '.reproduction_mode // "?"' "$file" 2>/dev/null || echo "?")
    scope=$(jq -r '.reproduction_scope // "?"' "$file" 2>/dev/null || echo "?")
    duration=$(jq -r '.duration_seconds // 0' "$file" 2>/dev/null || echo "0")
    exit_status=$(jq -r '.exit_status // 1' "$file" 2>/dev/null || echo "1")
    notes=$(jq -r '.metadata.notes // ""' "$file" 2>/dev/null || echo "")
    
    # Extract system info
    cpu_model=$(jq -r '.system.cpu.model // ""' "$file" 2>/dev/null || echo "")
    cpu_cores=$(jq -r '.system.cpu.cores_physical // ""' "$file" 2>/dev/null || echo "")
    ram_gb=$(jq -r '.system.memory.total_gb // ""' "$file" 2>/dev/null || echo "")
    
    # Format timestamp
    date_str=$(format_timestamp "$timestamp")
    
    # Format duration
    duration_str=$(format_duration "$duration")
    
    # Format status
    if [[ "$exit_status" == "0" ]]; then
        status="${GREEN}✓ OK${RESET}"
    else
        status="${RED}✗ FAIL${RESET}"
    fi
    
    # Format HARDWARE (CPU model)
    if [[ -n "$cpu_model" && "$cpu_model" != "null" ]]; then
        # Shorten common CPU model names to fit in column
        hardware_str="$cpu_model"
        # Truncate if too long
        if [[ ${#hardware_str} -gt 16 ]]; then
            hardware_str="${hardware_str:0:16}"
        fi
    else
        hardware_str="-"
    fi
    
    # Format RAM
    if [[ -n "$ram_gb" && "$ram_gb" != "null" ]]; then
        # Round to nearest integer
        ram_int=$(printf "%.0f" "$ram_gb")
        ram_str="${ram_int}GB"
    else
        ram_str="-"
    fi
    
    # Truncate notes if too long
    if [[ ${#notes} -gt 28 ]]; then
        notes="${notes:0:25}..."
    fi
    
    # Print row
    printf "%-13s %-6s %-8s %-18s %-6s %7s " \
        "$date_str" "$mode" "$scope" "$hardware_str" "$ram_str" "$duration_str"
    printf "${status}  %-30s\n" "$notes"
done

# Footer
echo ""
printf "%.118s\n" "$(printf '%0.s─' {1..118})"
echo -e "${DIM}Total: ${#filtered_files[@]} benchmark(s)${RESET}"
if [[ $broken_files -gt 0 ]]; then
    echo -e "${YELLOW}⚠️  Skipped $broken_files broken/malformed JSON file(s)${RESET}"
    echo -e "${DIM}   (These were likely created before a bug fix. Delete with: rm results/*_202510[2-9]*.json)${RESET}"
fi
echo ""
echo -e "${BOLD}Additional Data:${RESET}"
echo "  Each JSON file contains system info, arguments, and detailed metadata."
echo ""
echo -e "${BOLD}To view full details:${RESET}"
echo "  cat $RESULTS_DIR/latest.json | jq ."
echo "  cat $RESULTS_DIR/<filename>.json | jq '.metadata'"
echo ""
echo -e "${BOLD}To analyze results:${RESET}"
echo "  jq '.duration_seconds' $RESULTS_DIR/*.json    # List all durations"
echo "  jq -s 'map(.duration_seconds) | add/length' $RESULTS_DIR/*.json    # Average duration"
echo ""


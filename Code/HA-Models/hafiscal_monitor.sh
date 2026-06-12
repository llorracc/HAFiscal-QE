#!/usr/bin/env bash
#
# HAFiscal Progress Monitor
# 
# A comprehensive monitoring tool for HAFiscal computational reproduction.
# Provides status, progress tracking, and bottleneck analysis.
#
# Usage (this file lives at Code/HA-Models/hafiscal_monitor.sh; the repo root
# symlinks it as ./monitor.sh — from the repo root, substitute ./monitor.sh):
#   ./hafiscal_monitor.sh          # Interactive menu
#   ./hafiscal_monitor.sh status   # Show current status
#   ./hafiscal_monitor.sh tail     # Tail progress log
#   ./hafiscal_monitor.sh check    # Check for hangs
#   ./hafiscal_monitor.sh report   # Show profiling report
#   ./hafiscal_monitor.sh watch    # Auto-refresh status every 10s

set -euo pipefail

# Files
PROGRESS_LOG="/tmp/hafiscal_progress.log"
STATUS_FILE="/tmp/hafiscal_status.json"
HEARTBEAT_FILE="/tmp/hafiscal_heartbeat"
PROFILE_FILE="/tmp/hafiscal_profile.json"
TIMING_FILE="/tmp/hafiscal_timing.json"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# Check if a file exists and is recent
is_recent() {
    local file="$1"
    local max_age_seconds="${2:-600}"  # Default 10 minutes
    
    if [[ ! -f "$file" ]]; then
        return 1
    fi
    
    local file_age=$(($(date +%s) - $(stat -c %Y "$file" 2>/dev/null || stat -f %m "$file" 2>/dev/null)))
    [[ $file_age -lt $max_age_seconds ]]
}

# Print a header
print_header() {
    echo -e "\n${BOLD}${CYAN}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${BOLD}${CYAN}  $1${NC}"
    echo -e "${BOLD}${CYAN}═══════════════════════════════════════════════════════════════${NC}\n"
}

# Show current status
show_status() {
    print_header "HAFiscal Execution Status"
    
    if [[ ! -f "$STATUS_FILE" ]]; then
        echo -e "${YELLOW}No active run detected (status file not found)${NC}"
        echo ""
        echo "To monitor a running reproduction:"
        echo "  tail -f $PROGRESS_LOG"
        return 1
    fi
    
    # Check if process is still alive
    if is_recent "$HEARTBEAT_FILE" 300; then
        echo -e "${GREEN}● Process is ACTIVE${NC}"
    elif is_recent "$HEARTBEAT_FILE" 600; then
        echo -e "${YELLOW}● Process may be computing (no update in 5-10 min)${NC}"
    else
        echo -e "${RED}● Process may be STUCK or COMPLETED${NC}"
    fi
    
    echo ""
    
    # Parse status file (using Python for JSON parsing)
    python3 << 'PYTHON'
import json
import sys
from datetime import datetime
from pathlib import Path

status_file = Path("/tmp/hafiscal_status.json")
if not status_file.exists():
    print("  Status file not found")
    sys.exit(1)

try:
    status = json.loads(status_file.read_text())
except Exception as e:
    print(f"  Error reading status: {e}")
    sys.exit(1)

print(f"  Run ID:        {status.get('run_id', 'unknown')}")
print(f"  Current Step:  {status.get('current_step', '?')}/{status.get('total_steps', '?')}")
print(f"  Substep:       {status.get('current_substep', 'N/A')}")
print(f"  Elapsed:       {status.get('elapsed_formatted', 'unknown')}")
print(f"  Memory:        {status.get('memory_mb', 0):.0f} MB")
print(f"  Last Update:   {status.get('last_update', 'unknown')}")

if status.get('active_loop'):
    loop = status['active_loop']
    print(f"\n  Active Loop:   {loop['name']}")
    print(f"    Progress:    {loop['progress']} ({loop['pct']:.1f}%)")
    print(f"    ETA:         {loop['eta_formatted']}")
    if loop.get('last_metrics'):
        metrics_str = ", ".join(f"{k}={v:.4f}" for k, v in loop['last_metrics'].items())
        print(f"    Metrics:     {metrics_str}")

if status.get('call_stack'):
    print(f"\n  Call Stack:    {' → '.join(status['call_stack'])}")

PYTHON
    
    echo ""
}

# Check for hangs
check_hang() {
    print_header "Hang Detection"
    
    if [[ ! -f "$HEARTBEAT_FILE" ]]; then
        echo -e "${YELLOW}No heartbeat file found - process may not be running${NC}"
        return 1
    fi
    
    local heartbeat_time=$(head -1 "$HEARTBEAT_FILE")
    local last_msg=$(tail -1 "$HEARTBEAT_FILE")
    local current_time=$(date +%s)
    
    # Handle both integer and float timestamps
    local diff=$(python3 -c "print(int($current_time - float('$heartbeat_time')))")
    
    if [[ $diff -gt 1800 ]]; then  # 30 minutes
        echo -e "${RED}⚠️  CRITICAL: No progress in $((diff / 60)) minutes${NC}"
        echo -e "   Last activity: $last_msg"
        echo ""
        echo "   Consider checking if the process is truly stuck:"
        echo "   - Check CPU usage: top -p \$(pgrep -f 'reproduce')"
        echo "   - Check log: tail -50 $PROGRESS_LOG"
        return 2
    elif [[ $diff -gt 600 ]]; then  # 10 minutes
        echo -e "${YELLOW}⚠️  Warning: No progress in $((diff / 60)) minutes${NC}"
        echo -e "   Last activity: $last_msg"
        echo ""
        echo "   This may be normal for CPU-intensive operations."
        return 1
    else
        echo -e "${GREEN}✓ Process is active (last update: ${diff}s ago)${NC}"
        echo -e "   Last: $last_msg"
        return 0
    fi
}

# Show profiling report
show_report() {
    print_header "Profiling Report"
    
    if [[ ! -f "$PROFILE_FILE" ]]; then
        echo -e "${YELLOW}No profile data available. Run a reproduction first.${NC}"
        return 1
    fi
    
    python3 << 'PYTHON'
import json
from pathlib import Path

profile_file = Path("/tmp/hafiscal_profile.json")
if not profile_file.exists():
    print("No profile data found")
    exit(1)

data = json.loads(profile_file.read_text())

print(f"Run ID: {data.get('run_id', 'unknown')}")
total_sec = data.get('total_duration', 0)
print(f"Total Duration: {total_sec/3600:.2f} hours ({total_sec/60:.1f} minutes)")
print()

# Step summary
if data.get('steps'):
    print("STEP SUMMARY")
    print("-" * 60)
    for step_id, step in sorted(data.get('steps', {}).items()):
        duration_min = step.get('duration_seconds', 0) / 60
        print(f"  Step {step_id}: {step.get('description', 'Unknown')}")
        print(f"          Duration: {duration_min:.1f} minutes")
    print()

# Top time consumers
print("TOP TIME CONSUMERS")
print("-" * 60)
funcs = sorted(data.get('functions', {}).values(), 
               key=lambda x: x.get('total_time', 0), reverse=True)
for i, f in enumerate(funcs[:15], 1):
    if f.get('total_time', 0) < 1:
        continue
    total_min = f['total_time'] / 60
    pct = f['total_time'] / max(total_sec, 1) * 100
    print(f"  {i:2}. {f['name']}")
    print(f"      {total_min:.1f} min ({pct:.1f}%) | {f.get('call_count', 0)} calls")
print()

# Bottlenecks
if data.get('bottlenecks'):
    print("IDENTIFIED BOTTLENECKS")
    print("-" * 60)
    for bn in data.get('bottlenecks', [])[:10]:
        priority = bn.get('priority', 'UNKNOWN')
        if priority == 'CRITICAL':
            marker = '🔴'
        elif priority == 'HIGH':
            marker = '🟠'
        elif priority == 'MEDIUM':
            marker = '🟡'
        else:
            marker = '⚪'
        print(f"  {marker} [{priority:8}] {bn.get('operation', 'Unknown')}")
        print(f"     {bn.get('total_formatted', 'N/A')} ({bn.get('pct_of_total', 0):.1f}% of total)")
    print()

# Optimization opportunities
if data.get('opportunities'):
    print("OPTIMIZATION OPPORTUNITIES")
    print("-" * 60)
    seen = set()
    for opp in data.get('opportunities', [])[:5]:
        key = (opp.get('location', ''), opp.get('category', ''))
        if key in seen:
            continue
        seen.add(key)
        print(f"  [{opp.get('priority', 'MEDIUM')}] {opp.get('category', '').upper()}: {opp.get('location', 'Unknown')}")
        print(f"      {opp.get('description', '')}")
        print(f"      Estimated speedup: {opp.get('estimated_speedup', 'Unknown')}")
        print()

PYTHON
}

# Tail the progress log
tail_log() {
    if [[ ! -f "$PROGRESS_LOG" ]]; then
        echo -e "${YELLOW}Progress log not found at $PROGRESS_LOG${NC}"
        echo "The reproduction may not have started yet."
        return 1
    fi
    
    local lines="${1:-50}"
    echo -e "${CYAN}Showing last $lines lines of $PROGRESS_LOG${NC}"
    echo -e "${CYAN}Press Ctrl+C to stop following${NC}\n"
    tail -n "$lines" -f "$PROGRESS_LOG"
}

# Watch status with auto-refresh
watch_status() {
    local interval="${1:-10}"
    
    echo -e "${CYAN}Auto-refreshing every ${interval}s. Press Ctrl+C to stop.${NC}"
    
    while true; do
        clear
        show_status
        echo ""
        check_hang
        echo -e "\n${CYAN}[Refreshing in ${interval}s... Press Ctrl+C to stop]${NC}"
        sleep "$interval"
    done
}

# Show help/menu
show_help() {
    print_header "HAFiscal Monitor"
    
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  status       Show current execution status"
    echo "  tail [N]     Follow progress log (last N lines, default 50)"
    echo "  check        Check if process might be hung"
    echo "  report       Show profiling report with bottlenecks"
    echo "  watch [N]    Auto-refresh status every N seconds (default 10)"
    echo "  help         Show this help message"
    echo ""
    echo "Quick monitoring:"
    echo "  tail -f /tmp/hafiscal_progress.log   # Real-time log"
    echo "  python Code/HA-Models/hafiscal_progress.py --status"
    echo ""
}

# Interactive menu
interactive_menu() {
    while true; do
        print_header "HAFiscal Monitor - Interactive Menu"
        
        echo "1) Show current status"
        echo "2) Check for hangs"
        echo "3) Show profiling report"
        echo "4) Tail progress log"
        echo "5) Watch status (auto-refresh)"
        echo "6) Open log in less"
        echo "q) Quit"
        echo ""
        read -p "Select option: " choice
        
        case "$choice" in
            1) show_status; read -p "Press Enter to continue..." ;;
            2) check_hang; read -p "Press Enter to continue..." ;;
            3) show_report; read -p "Press Enter to continue..." ;;
            4) tail_log 100 ;;
            5) watch_status 10 ;;
            6) less "$PROGRESS_LOG" 2>/dev/null || echo "Log not found" ;;
            q|Q) exit 0 ;;
            *) echo "Invalid option" ;;
        esac
    done
}

# Main entry point
main() {
    local cmd="${1:-}"
    
    case "$cmd" in
        status)
            show_status
            ;;
        check|hang)
            check_hang
            ;;
        report)
            show_report
            ;;
        tail)
            tail_log "${2:-50}"
            ;;
        watch)
            watch_status "${2:-10}"
            ;;
        help|--help|-h)
            show_help
            ;;
        "")
            interactive_menu
            ;;
        *)
            echo "Unknown command: $cmd"
            show_help
            exit 1
            ;;
    esac
}

main "$@"

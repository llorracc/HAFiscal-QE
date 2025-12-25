#!/bin/bash

# HAFiscal Reproduction Script
# This script provides options for reproducing different aspects of the HAFiscal project

set -eo pipefail

# ============================================================================
# DEBUG MODE INSTRUMENTATION (Cursor)
# ============================================================================

# region agent log
# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

# Track script start time
SCRIPT_START_TIME=$(date +%s)

# Initialize log variables (files created later if needed)
LOG_DIR="./reproduce/logs"
LOG_FILE=""
LATEST_LOG="$LOG_DIR/latest.log"
LOGGING_ENABLED=false

# Logging function with timestamps
log() {
    local level="$1"
    shift
    local message="$*"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    local log_line="[$timestamp] [$level] $message"
    
    # Print to stdout with color
    case "$level" in
        INFO)
            echo "ℹ️  $message" ;;
        SUCCESS)
            echo "✅ $message" ;;
        WARNING)
            echo "⚠️  $message" ;;
        ERROR)
            echo "❌ $message" >&2 ;;
        PROGRESS)
            echo "🔄 $message" ;;
        STEP)
            echo "📍 $message" ;;
        *)
            echo "$message" ;;
    esac
    
    # Write to log file only if logging is enabled
    if [[ "$LOGGING_ENABLED" == true && -n "$LOG_FILE" ]]; then
        echo "$log_line" >> "$LOG_FILE"
    fi
}

# Function to initialize logging (called only for actual reproduction actions)
init_logging() {
    local action="$1"
    local scope="$2"
    
    # Create log directory
    mkdir -p "$LOG_DIR"
    
    # Build filename: {kind}_{vers}_{opts}_YYYYMMDD-HHMM.log
    # This matches the benchmark file naming pattern (without duration since log starts at beginning)
    local timestamp=$(date +%Y%m%d-%H%M)
    local filename="${action}"
    
    # Add scope (vers) to filename
    if [[ -n "$scope" ]]; then
        filename="${filename}_${scope}"
    fi
    
    # Add options (opts) to filename if applicable
    if [[ "$DRY_RUN" == "true" ]]; then
        filename="${filename}_dry-run"
    fi
    
    # Add verbose/debug indicator to filename if enabled
    if [[ "${VERBOSE:-false}" == "true" ]] || [[ "${DEBUG:-false}" == "true" ]]; then
        filename="${filename}_verbose"
    fi
    
    # Add timestamp
    filename="${filename}_${timestamp}.log"
    
    LOG_FILE="$LOG_DIR/$filename"
    LOGGING_ENABLED=true
    
    # Symlink to latest log
    ln -sf "$(basename "$LOG_FILE")" "$LATEST_LOG"
    
    # Write initial log entries
    log INFO "==================================="
    log INFO "HAFiscal Reproduction Script Started"
    log INFO "Command: $0 $*"
    log INFO "Working directory: $(pwd)"
    log INFO "Log file: $LOG_FILE"
    log INFO "==================================="
    log INFO "Command tracing enabled - all commands will be logged"
    
    # Enable command tracing (set -x) to log all executed commands
    # This will show every command before it's executed
    set -x
    
    # Redirect trace output based on verbose/debug mode
    # In verbose/debug mode: send to both terminal and log file
    # Otherwise: send only to log file (quieter terminal output)
    if [[ "${VERBOSE:-false}" == "true" ]] || [[ "${DEBUG:-false}" == "true" ]]; then
        # Verbose mode: show tracing in terminal and log file
        exec 2> >(tee -a "$LOG_FILE" >&2)
        log INFO "Verbose mode: command tracing will appear in terminal"
    else
        # Quiet mode: send tracing only to log file
        exec 2>> "$LOG_FILE"
        log INFO "Quiet mode: command tracing logged to file only (use --verbose to see in terminal)"
    fi
}

# ============================================================================
# ERROR HANDLER: Enhanced error reporting with context
# ============================================================================
error_handler() {
    local exit_code=$?
    local line_number=$1
    local bash_lineno=$2
    local command="$3"
    
    log ERROR "Script failed with exit code $exit_code at line $line_number"
    log ERROR "Failed command: $command"
    log ERROR "Bash line: $bash_lineno"
    log ERROR "==================================="
    
    if [[ -n "$LOG_FILE" ]]; then
        log ERROR "Reproduction FAILED - check log: $LOG_FILE"
        
        # Show last 30 lines of log for context
        echo ""
        echo "════════════════════════════════════════"
        echo "Last 30 log entries (for debugging):"
        echo "════════════════════════════════════════"
        tail -30 "$LOG_FILE" 2>/dev/null || echo "(Unable to read log file)"
        echo "════════════════════════════════════════"
        echo ""
        echo "Full log available at: $LOG_FILE"
    else
        log ERROR "Reproduction FAILED"
    fi
    
    # Don't call cleanup/benchmark here - let EXIT trap handle it
}

# ============================================================================
# SUMMARY FUNCTION: Print final summary and statistics
# ============================================================================
print_summary() {
    local exit_code=$1
    
    # Only print summary if logging was enabled (actual reproduction ran)
    if [[ "$LOGGING_ENABLED" != true ]]; then
        return 0
    fi
    
    local duration=$(($(date +%s) - SCRIPT_START_TIME))
    
    echo ""
    log INFO "==================================="
    log INFO "Reproduction Script Summary"
    log INFO "==================================="
    log INFO "Exit code: $exit_code"
    log INFO "Total duration: $(printf '%d:%02d:%02d' $((duration/3600)) $((duration%3600/60)) $((duration%60)))"
    
    if [[ -n "$LOG_FILE" ]]; then
        log INFO "Log file: $LOG_FILE"
        log INFO "Latest log symlink: $LATEST_LOG"
    fi
    
    if [[ $exit_code -eq 0 ]]; then
        log SUCCESS "All operations completed successfully"
    else
        log ERROR "Script failed - check log for details"
        if [[ -n "$LOG_FILE" ]]; then
            log ERROR "To review errors: cat $LOG_FILE | grep ERROR"
        fi
    fi
    log INFO "==================================="
}

# ============================================================================
# CLEANUP FUNCTION: Remove backup and temporary files on exit
# ============================================================================
cleanup_temp_files() {
    echo ""
    log INFO "Cleaning up backup and temporary files..."
    
    # Remove backup files (*.bak, *.bak~, etc.)
    REMOVED_BAK=$(find . -type f -name "*.bak*" 2>/dev/null | wc -l | tr -d " ")
    if [ "$REMOVED_BAK" -gt 0 ]; then
        find . -type f -name "*.bak*" -delete 2>/dev/null
        log INFO "Removed $REMOVED_BAK backup file(s) (*.bak*)"
    fi
    
    # Remove brief files (*.brf, used by some LaTeX packages)
    REMOVED_BRF=$(find . -type f -name "*.brf*" 2>/dev/null | wc -l | tr -d " ")
    if [ "$REMOVED_BRF" -gt 0 ]; then
        find . -type f -name "*.brf*" -delete 2>/dev/null
        log INFO "Removed $REMOVED_BRF brief file(s) (*.brf*)"
    fi
    
    if [ "$REMOVED_BAK" -eq 0 ] && [ "$REMOVED_BRF" -eq 0 ]; then
        log INFO "No backup or brief files found"
    fi
    
    log SUCCESS "Cleanup complete"
}


# ============================================================================
# CLEANUP FUNCTION: Remove backup and temporary files on successful exit
# ============================================================================
cleanup_temp_files() {
    # Only run cleanup if script is exiting successfully (exit code 0)
    if [ $? -eq 0 ]; then
        echo ""
        echo "Cleaning up backup and temporary files..."
        
        # Remove backup files (*.bak, *.bak~, etc.)
        REMOVED_BAK=$(find . -type f -name "*.bak*" 2>/dev/null | wc -l | tr -d " ")
        if [ "$REMOVED_BAK" -gt 0 ]; then
            find . -type f -name "*.bak*" -delete 2>/dev/null
            echo "  Removed $REMOVED_BAK backup file(s) (*.bak*)"
        fi
        
        # Remove brief files (*.brf, used by some LaTeX packages)
        REMOVED_BRF=$(find . -type f -name "*.brf*" 2>/dev/null | wc -l | tr -d " ")
        if [ "$REMOVED_BRF" -gt 0 ]; then
            find . -type f -name "*.brf*" -delete 2>/dev/null
            echo "  Removed $REMOVED_BRF brief file(s) (*.brf*)"
        fi
        
        if [ "$REMOVED_BAK" -eq 0 ] && [ "$REMOVED_BRF" -eq 0 ]; then
            echo "  No backup or brief files found"
        fi
        
        echo "✅ Cleanup complete"
    fi
}

# Register cleanup function to run on successful exit
trap cleanup_temp_files EXIT

# ============================================================================
# CHECK FOR WINDOWS (NON-WSL) ENVIRONMENT
# ============================================================================
case "$(uname -s)" in
    CYGWIN*|MINGW*|MSYS*)
        echo "================================================================"
        echo "❌ ERROR: Windows Native Environment Detected"
        echo "================================================================"
        echo ""
        echo "This script requires a Unix-like environment and cannot run"
        echo "directly on Windows."
        echo ""
        echo "Please use Windows Subsystem for Linux 2 (WSL2) instead:"
        echo ""
        echo "1. Install WSL2 (if not already installed):"
        echo "   https://docs.microsoft.com/en-us/windows/wsl/install"
        echo ""
        echo "2. Open a WSL2 terminal (Ubuntu recommended)"
        echo ""
        echo "3. Clone this repository in the Linux file system in WSL2"
        echo ""
        echo "4. Run this script again from within WSL2"
        echo ""
        echo "Note: WSL1 is not supported. You must use WSL2."
        echo ""
        exit 1
        ;;
esac

# ============================================================================
# CHECK FOR BROKEN SYMLINKS (Git clone from Windows)
# ============================================================================
# If the repository was cloned in Windows and then accessed from WSL2,
# symlinks will be broken (converted to text files). Check for this.
check_symlinks() {
    # Symlink check disabled for QE distribution
    # This repository intentionally has dereferenced symlinks (real files)
    # created by rsync -L during QE package preparation
    :
}
# Run the symlink check
check_symlinks

# ============================================================================
# CHECK FOR LIMITED TERMINAL CAPABILITIES (e.g., Emacs Shell)
# ============================================================================
# Emacs shell (M-x shell) and other limited terminals don't properly handle
# subprocess output. Detect based on actual terminal capabilities, not just
# environment variables (which may be inherited from parent processes).
#
# Detection strategy:
# - Check TERM value for "dumb" (line-oriented terminals)
# - Verify terminal actually supports basic capabilities
# - Auto-fix for automation environments (Docker, CI, DevContainer)
# - Detect specific known-capable terminals even if TERM=dumb
# - Note: Environment variables like INSIDE_EMACS or EDITOR=emacs don't
#   necessarily mean we're in Emacs shell mode - user may have launched
#   a proper terminal from within Emacs, or have emacs as their EDITOR

# Detect if we're running in WSL2
is_wsl2() {
    # Check /proc/version for WSL indicators
    # WSL2 specifically has both "microsoft" and "WSL2" in version string
    # WSL1 only has "Microsoft" without "WSL2" - we want to exclude WSL1
    if [[ -r /proc/version ]]; then
        local version
        version=$(cat /proc/version 2>/dev/null || echo "")
        # Check for both "microsoft" (case-insensitive) AND "WSL2" (case-insensitive)
        if [[ "$version" =~ [Mm]icrosoft ]] && [[ "$version" =~ WSL2|wsl2 ]]; then
            return 0
        fi
    fi
    return 1
}

# Detect automation/container environments where TERM=dumb is expected
is_automation_environment() {
    # Docker container
    [[ -f /.dockerenv ]] && return 0
    [[ -f /proc/1/cgroup ]] && grep -q docker /proc/1/cgroup 2>/dev/null && return 0
    
    # CI environments
    [[ "${CI:-false}" == "true" ]] && return 0
    [[ -n "${GITHUB_ACTIONS:-}" ]] && return 0
    [[ -n "${GITLAB_CI:-}" ]] && return 0
    [[ -n "${CIRCLECI:-}" ]] && return 0
    
    # DevContainer / Remote Containers
    [[ -n "${REMOTE_CONTAINERS:-}" ]] && return 0
    [[ "${VSCODE_INJECTION:-}" == "1" ]] && return 0
    
    # Not an automation environment
    return 1
}

# Detect if we're in a known-capable terminal that just has TERM set wrong
is_capable_terminal() {
    # iTerm detection
    [[ -n "${ITERM_SESSION_ID:-}" ]] && return 0
    [[ -n "${ITERM_PROFILE:-}" ]] && return 0
    [[ "${LC_TERMINAL:-}" == "iTerm2" ]] && return 0
    
    # VSCode integrated terminal (capable)
    [[ "${TERM_PROGRAM:-}" == "vscode" ]] && return 0
    
    # Cursor integrated terminal (capable)
    [[ "${LC_TERMINAL:-}" == "Cursor" ]] && return 0
    
    # Kitty terminal
    [[ "${TERM:-}" == "xterm-kitty" ]] && return 0
    [[ -n "${KITTY_WINDOW_ID:-}" ]] && return 0
    
    # Alacritty terminal
    [[ "${TERM:-}" == "alacritty" ]] && return 0
    
    # Test if ANSI escape codes work (even if TERM=dumb)
    if echo -e "\033[31mtest\033[0m" 2>/dev/null | grep -q "test"; then
        # Terminal renders escape codes - likely capable
        return 0
    fi
    
    # Not a known capable terminal
    return 1
}

# Detect specifically Emacs comint mode (M-x shell), which is limited
is_emacs_comint() {
    # INSIDE_EMACS with ",comint" suffix indicates M-x shell mode
    # BUT: Check if we're actually running under Emacs, not just if the env var is set
    # (The env var can be inherited from parent processes even when not in Emacs)
    if [[ "${INSIDE_EMACS:-}" == *",comint"* ]]; then
        # Check if the parent process is actually Emacs
        local parent_cmd=$(ps -p $PPID -o comm= 2>/dev/null | tr '[:upper:]' '[:lower:]')
        if [[ "$parent_cmd" == *"emacs"* ]]; then
            return 0
        fi
    fi
    return 1
}

# Check if we're in a truly limited terminal (TERM=dumb is the key indicator)
if [[ "${TERM:-}" == "dumb" ]]; then
    # First check: Is this a known capable terminal with TERM set wrong?
    if is_capable_terminal; then
        # Capable terminal but TERM=dumb - auto-fix it
        export TERM=xterm-256color
        echo "ℹ️  Auto-fixing: Detected capable terminal with TERM=dumb"
        echo "   Setting TERM=xterm-256color"
        # Add note if running in Emacs comint (informational only)
        if is_emacs_comint; then
            echo "   Note: Running in Emacs shell mode - if you see display issues,"
            echo "         consider using M-x ansi-term instead"
        fi
        echo ""
    # Second check: Is this an automation environment?
    elif is_automation_environment; then
        # We're in a container/CI environment - auto-fix TERM for better output
        export TERM=xterm-256color
    # Third check: Are we in WSL2? (often has TERM issues but is capable)
    elif is_wsl2; then
        # WSL2 terminals can have TERM=dumb but are usually capable
        # Auto-fix TERM to avoid ioctl errors from tput
        export TERM=xterm-256color
        # Note: tput may still generate ioctl errors in WSL2, but we'll suppress them
    # Fourth check: Does tput report color support despite TERM=dumb?
    # (Suppress stderr to avoid ioctl errors in WSL2 and other environments)
    elif command -v tput >/dev/null 2>&1; then
        # Try tput but suppress all output (including stderr for ioctl errors)
        local tput_result
        tput_result=$(tput colors 2>/dev/null 2>&1 || echo "0")
        if [[ "$tput_result" =~ ^[0-9]+$ ]] && [[ "$tput_result" -ge 8 ]]; then
            # Terminal claims to be dumb but supports colors - probably fine
            :
        fi
    else
        # Truly limited terminal (not Emacs, not known-capable, no color support)
        echo "================================================================"
        echo "❌ ERROR: Limited Terminal Detected (TERM=dumb)"
        echo "================================================================"
        echo ""
        echo "This script requires a full terminal emulator with proper"
        echo "capabilities (colors, cursor control, interactive input)."
        echo ""
        echo "Current terminal:"
        echo "  • TERM=$TERM"
        if [[ -n "${TERM_PROGRAM:-}" ]]; then
            echo "  • TERM_PROGRAM=$TERM_PROGRAM"
        fi
        if [[ -n "${LC_TERMINAL:-}" ]]; then
            echo "  • LC_TERMINAL=$LC_TERMINAL"
        fi
        echo ""
        echo "SOLUTIONS:"
        echo ""
        echo "Option 1: Use a full terminal emulator (Recommended)"
        echo "  • macOS: Terminal.app, iTerm2, Alacritty, Kitty"
        echo "  • Linux: gnome-terminal, konsole, xterm"
        echo "  • Windows: WSL2 terminal, Windows Terminal"
        echo "  • IDE: Cursor/VSCode integrated terminal"
        echo ""
        echo "Option 2: Override terminal detection (may work)"
        echo "  export TERM=xterm-256color"
        echo "  # Then run this script again"
        echo ""
        echo "For debugging, run: ./test_terminal_detection.sh"
        echo ""
        exit 1
    fi
fi


# ============================================================================
# BENCHMARKING CONFIGURATION
# Benchmarking is ON by default. Set BENCHMARK=false to disable.
# ============================================================================
BENCHMARK_ENABLED="${BENCHMARK:-true}"
BENCHMARK_START_TIME=""
BENCHMARK_START_ISO=""

benchmark_start() {
    if [[ "$BENCHMARK_ENABLED" == "true" ]]; then
        BENCHMARK_START_TIME=$(date +%s)
        BENCHMARK_START_ISO=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
        log INFO "Benchmarking enabled - timing started"
    fi
}

benchmark_end() {
    if [[ "$BENCHMARK_ENABLED" != "true" ]]; then
        return 0
    fi
    
    # Skip if benchmarking was never started (no action specified)
    if [[ -z "$BENCHMARK_START_TIME" ]]; then
        return 0
    fi
    
    local exit_status=$1
    
    # Only save benchmarks for successful runs (exit status 0)
    if [[ "$exit_status" -ne 0 ]]; then
        return 0
    fi
    
    local end_time=$(date +%s)
    local end_iso=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    local duration=$((end_time - BENCHMARK_START_TIME))
    
    # Build filename: [kind]_[vers]_[opts]_YYYYMMDD-HHMM_[duration]s.json
    local kind="unknown"
    local vers=""
    local opts=""
    
    # Determine kind and version
    if [[ -n "${ACTION}" ]]; then
        case "$ACTION" in
            docs)
                kind="docs"
                vers="${DOCS_SCOPE:-main}"
                ;;
            comp)
                kind="comp"
                vers="${COMP_SCOPE:-min}"
                ;;
            envt)
                kind="envt"
                vers="${ENVT_SCOPE:-both}"
                # If testing comp environment and UV is detected, use comp_uv
                if [[ "$vers" == "comp" && "${ENVT_USING_UV:-false}" == "true" ]]; then
                    vers="comp_uv"
                fi
                ;;
            all)
                kind="all"
                vers="full"
                ;;
            *)
                kind="${ACTION}"
                ;;
        esac
    fi
    
    # Add options
    if [[ "$DRY_RUN" == "true" ]]; then
        opts="dry-run"
    fi
    
    # Build filename with underscores, timestamp, and 5-digit zero-padded duration
    local filename="${kind}"
    [[ -n "$vers" ]] && filename="${filename}_${vers}"
    [[ -n "$opts" ]] && filename="${filename}_${opts}"
    
    # Add timestamp (YYYYMMDD-HHMM format)
    local timestamp=$(date -d "@$BENCHMARK_START_TIME" '+%Y%m%d-%H%M' 2>/dev/null || date -r "$BENCHMARK_START_TIME" '+%Y%m%d-%H%M')
    filename="${filename}_${timestamp}"
    
    # Format duration as 6-digit zero-padded with 's' suffix
    local duration_str=$(printf "%06d" "$duration")
    filename="${filename}_${duration_str}s.json"
    
    # Ensure benchmarks directory exists (write to auto/ subdirectory)
    local benchmark_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/reproduce/benchmarks/results/auto"
    mkdir -p "$benchmark_dir"
    
    # Capture system info and create benchmark
    local capture_script="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/reproduce/benchmarks/capture_system_info.py"
    if [[ -f "$capture_script" ]]; then
        local temp_sysinfo="/tmp/hafiscal_bench_$$_sysinfo.json"
        python3 "$capture_script" --pretty --output "$temp_sysinfo" 2>/dev/null || true
        
        local output_file="$benchmark_dir/$filename"
        local sysinfo=""
        
        # Try to read system info if file exists and is valid
        if [[ -f "$temp_sysinfo" && -s "$temp_sysinfo" ]]; then
            # Validate it's actual JSON by checking for opening brace
            if grep -q "^{" "$temp_sysinfo" 2>/dev/null; then
                sysinfo=$(sed 's/^/  /' "$temp_sysinfo" | sed '1d; $d')
            fi
        fi
        
        # Create benchmark JSON
        if [[ -n "$sysinfo" ]]; then
            # Include system info
            cat > "$output_file" << EOF
{
  "benchmark_version": "1.0.0",
  "benchmark_id": "${kind}-${vers:-unknown}_${timestamp}",
  "timestamp": "$BENCHMARK_START_ISO",
  "timestamp_end": "$end_iso",
  "reproduction_mode": "${kind}",
  "reproduction_scope": "${vers:-unknown}",
  "reproduction_args": [$(printf '"%s"' "${@}" | sed 's/" "/", "/g')],
  "exit_status": $exit_status,
  "duration_seconds": $duration,
${sysinfo},
  "metadata": {
    "user": "${USER:-unknown}",
    "session_id": "$$",
    "ci": ${CI:-false},
    "dry_run": ${DRY_RUN:-false},
    "notes": ""
  }
}
EOF
        else
            # System info unavailable - create minimal benchmark
            cat > "$output_file" << EOF
{
  "benchmark_version": "1.0.0",
  "benchmark_id": "${kind}-${vers:-unknown}_${timestamp}",
  "timestamp": "$BENCHMARK_START_ISO",
  "timestamp_end": "$end_iso",
  "reproduction_mode": "${kind}",
  "reproduction_scope": "${vers:-unknown}",
  "reproduction_args": [$(printf '"%s"' "${@}" | sed 's/" "/", "/g')],
  "exit_status": $exit_status,
  "duration_seconds": $duration,
  "metadata": {
    "user": "${USER:-unknown}",
    "session_id": "$$",
    "ci": ${CI:-false},
    "dry_run": ${DRY_RUN:-false},
    "notes": "System info unavailable"
  }
}
EOF
        fi
        
        # Create/update latest symlink in auto/ directory
        ln -sf "$filename" "$benchmark_dir/latest.json"
        
        # Also create convenience symlink in parent directory
        local parent_dir="$(dirname "$benchmark_dir")"
        ln -sf "auto/$filename" "$parent_dir/latest.json"
        
        echo ""
        log INFO "Benchmark saved: reproduce/benchmarks/results/auto/$filename"
        log INFO "Duration: $(printf '%d:%02d:%02d' $((duration/3600)) $((duration%3600/60)) $((duration%60))) ($duration seconds)"
        
        # Cleanup
        rm -f "$temp_sysinfo"
        
        # Final confirmation message (visible in logs to indicate clean completion)
        log INFO "Benchmark cleanup completed"
    fi
}

# Set up error trap with detailed context - triggers on command failure
trap 'error_handler ${LINENO} ${BASH_LINENO} "$BASH_COMMAND"' ERR

# Trap to ensure benchmark is saved and summary is printed on exit
# shellcheck disable=SC2154  # exit_code is assigned from $? in the trap
trap 'exit_code=$?; print_summary $exit_code; cleanup_temp_files; benchmark_end $exit_code; [[ "$LOGGING_ENABLED" == true ]] && log INFO "Script execution completed (exit code: $exit_code)"' EXIT

show_help() {
    cat << EOF
HAFiscal Reproduction Script

This script provides multiple reproduction options and includes environment testing.

USAGE:
    ./reproduce.sh [OPTION]

OPTIONS:
    --help, -h          Show this help message
    --envt, -e          Test environment setup (TeX Live + Python/computational)
    --data [SCOPE]      Reproduce empirical data or figures from results
                         SCOPE: scf|IMPC|LP|all (default: scf)
                         scf: empirical data moments from SCF 2004 (~1 minute + download time)
                         IMPC: Intertemporal MPC figures from pre-computed results
                         LP: Lorenz Points figures from pre-computed results
                         all: all figures from results (IMPC + LP)
    --comp, -c [SCOPE]  Reproduce computational results (SCOPE: min|full|max, default: min)
                         min: minimal computational results (~1 hour)
                         full: all computational results needed for the printed document (4-5 days on a high-end 2025 laptop)
                         max: full results + robustness (Step 3: Splurge=0 for Online Appendix) (~6 days on a high-end 2025 laptop)
    --docs, -d [SCOPE]  Reproduce LaTeX documents (SCOPE: main|all|figures|tables|subfiles, default: main)
                         main: only the paper --- HAFiscal.tex
                         all: the paper + individual Figures/ + Tables/ + Subfiles/
                         figures: the paper + Figures/
                         tables: the paper + Tables/
                         subfiles: the paper + Subfiles/
    --use-latest-scf-data  Download latest SCF 2004 data from Fed and auto-adjust to 2013$
                         Downloads 2022$ data, divides by 1.1587 to convert to 2013$
                         Results will match paper exactly. Use with --data flag
                         ⚠️  WARNING: Assumes downloaded data is in 2022 dollars.
                            When Fed updates inflation adjustments, update the
                            inflation factor in adjust_scf_inflation.py
                         See docs/SCF_DATA_VINTAGE.md for details
    --all, -a           Reproduce everything: data moments, all computational results + all documents
    --interactive, -i   Show interactive menu (delegates to reproduce.py)
    --dry-run           Show commands that would be executed (only with --docs)
    --verbose, -v       Show detailed command tracing in terminal (set -x output)
                        By default, command tracing is logged to file only
    --showlabels        Show equation/figure/table labels in margins (for review)
    --no-labels         Hide labels in margins (for publication)
    --stop-on-error     Stop compilation on first error (useful for debugging, only with --docs)

ENVIRONMENT TESTING:
    Use --envt to test your environment setup (TeX Live and/or Python).
    For environment issues, see README.md for setup instructions.

LOGGING:
    All script execution is automatically logged with timestamps.
    - Logs are saved to: reproduce/logs/reproduce_YYYYMMDD_HHMMSS.log
    - Latest log symlink: reproduce/logs/latest.log
    - Logs include: progress updates, errors, timings, and command execution
    - View latest log: cat reproduce/logs/latest.log
    - Monitor in real-time: tail -f reproduce/logs/latest.log
    - Search for errors: grep ERROR reproduce/logs/latest.log

ENVIRONMENT VARIABLES:
    REPRODUCE_TARGETS   Comma-separated list of targets to reproduce (non-interactive mode)
                       Valid values: docs, comp, all
                       Examples:
                         REPRODUCE_TARGETS=docs
                         REPRODUCE_TARGETS=comp,docs  
                         REPRODUCE_TARGETS=all
    
    BENCHMARK          Enable/disable automatic benchmarking (default: true)
                       Examples:
                         BENCHMARK=false ./reproduce.sh --docs    # Disable benchmarking
                         BENCHMARK=true ./reproduce.sh --comp min # Enable (default)

EXAMPLES:
    ./reproduce.sh                           # Show quick examples (this help)
    ./reproduce.sh --interactive             # Show interactive menu
    ./reproduce.sh --envt                    # Test both TeX Live and computational environments
    ./reproduce.sh --envt texlive            # Test TeX Live environment only
    ./reproduce.sh --envt comp_uv            # Test computational (UV) environment only
    ./reproduce.sh --docs                    # Compile repo root documents (default: main scope)
    ./reproduce.sh --docs main               # Compile only repo root documents  
    ./reproduce.sh --docs all                # Compile root + Figures/ + Tables/ + Subfiles/
    ./reproduce.sh --docs figures            # Compile repo root + Figures/
    ./reproduce.sh --docs tables             # Compile repo root + Tables/
    ./reproduce.sh --docs subfiles           # Compile repo root + Subfiles/
    ./reproduce.sh --docs all --stop-on-error # Stop on first compilation error
    ./reproduce.sh --comp min                # Minimal computational results (~1 hour)
    ./reproduce.sh --comp full               # All computational results for printed document (4-5 days on a high-end 2025 laptop)
    ./reproduce.sh --comp max                # Maximum computational results including robustness (~6 days on a high-end 2025 laptop)
    ./reproduce.sh --data                    # Empirical data moments from SCF 2004 (~1 minute + download)
    ./reproduce.sh --data scf                # Empirical data moments (default)
    ./reproduce.sh --data IMPC               # Generate IMPC figures from results
    ./reproduce.sh --data LP                 # Generate Lorenz Points figures
    ./reproduce.sh --data all                # Generate all figures from results
    ./reproduce.sh --data --use-latest-scf-data  # Download latest Fed data, auto-adjust to 2013$ (matches paper)
    ./reproduce.sh --all                     # Everything: all documents + all computational results
    
    # Advanced examples:
    BENCHMARK=false ./reproduce.sh --docs main   # Disable benchmarking

EOF
}

show_interactive_menu() {
    echo "========================================"
    echo "   HAFiscal Reproduction Options"
    echo "========================================"
    echo ""
    echo "Please select what you would like to reproduce:"
    echo ""
    echo "1) LaTeX Documents"
    echo "   - Compiles all PDF documents from LaTeX source"
    echo "   - Estimated time: A few minutes"
    echo ""
    echo "2) Subfiles"
    echo "   - Compiles all .tex files in Subfiles/ directory"
    echo "   - Estimated time: A few minutes"
    echo ""
    echo "3) Minimal Computational Results"
    echo "   - Reproduces a subset of computational results"
    echo "   - Estimated time: ~1 hour"
    echo "   - Good for testing and quick verification"
    echo ""
    echo "4) All Computational Results"
    echo "   - Reproduces all computational results from the paper"
    echo "   - ⚠️  WARNING: This may take 4-5 DAYS on a high-end 2025 laptop"
    echo "   - Requires significant computational resources"
    echo ""
    echo "5) Everything"
    echo "   - All documents + all computational results"
    echo "   - ⚠️  WARNING: This may take 4-5 DAYS on a high-end 2025 laptop"
    echo "   - Complete reproduction of the entire project"
    echo ""
    echo "6) Exit"
    echo ""
    echo -n "Enter your choice (1-6): "
}

reproduce_documents() {
    log PROGRESS "Starting document reproduction (scope: ${DOCS_SCOPE:-main})"
    log INFO "========================================"
    log INFO "Reproducing LaTeX Documents..."
    log INFO "========================================"
    echo ""
    
    if [[ -f "./reproduce/reproduce_documents.sh" ]]; then
        local args=()
        
        # Add --verbose flag only if VERBOSE is explicitly set
        if [[ "${VERBOSE:-false}" == "true" ]] || [[ "${DEBUG:-false}" == "true" ]]; then
            args+=("--verbose")
        fi
        
        # Add scope-specific arguments
        args+=("--scope" "${DOCS_SCOPE:-main}")
        
        if [[ "${DRY_RUN:-false}" == true ]]; then
            args+=("--dry-run")
        fi
        
        if [[ "${STOP_ON_ERROR:-false}" == true ]]; then
            args+=("--stop-on-error")
        fi
        
        log INFO "Executing: ./reproduce/reproduce_documents.sh ${args[*]}"
        
        # Conditionally use tee based on verbose mode
        if [[ "${VERBOSE:-false}" == "true" ]] || [[ "${DEBUG:-false}" == "true" ]]; then
            # Verbose mode: show output in terminal and log file
            if ./reproduce/reproduce_documents.sh "${args[@]}" 2>&1 | tee -a "$LOG_FILE"; then
                log SUCCESS "Document reproduction completed successfully"
                return 0
            else
                local exit_code=$?
                log ERROR "Document reproduction failed with exit code $exit_code"
                return $exit_code
            fi
        else
            # Quiet mode: show progress indicators but send detailed output to log file
            log PROGRESS "Compilation in progress... (output logged to: $LOG_FILE)"
            
            # Run in background and show periodic progress updates
            (
                ./reproduce/reproduce_documents.sh "${args[@]}" >> "$LOG_FILE" 2>&1
                echo $? > /tmp/reproduce_exit_code.$$
            ) &
            local bg_pid=$!
            
            # Show progress dots while waiting
            local dots=0
            while kill -0 "$bg_pid" 2>/dev/null; do
                sleep 2
                dots=$((dots + 1))
                if [ $((dots % 15)) -eq 0 ]; then
                    # Every 30 seconds, show a status update
                    log PROGRESS "Still compiling... ($((dots * 2))s elapsed)"
                else
                    # Show a dot every 2 seconds
                    echo -n "."
                fi
            done
            echo ""  # New line after dots
            
            # Get exit code
            local exit_code=$(cat /tmp/reproduce_exit_code.$$ 2>/dev/null || echo "1")
            rm -f /tmp/reproduce_exit_code.$$
            
            if [ "$exit_code" -eq 0 ]; then
                log SUCCESS "Document reproduction completed successfully"
                return 0
            else
                log ERROR "Document reproduction failed with exit code $exit_code"
                log INFO "Check log file for details: $LOG_FILE"
                return "$exit_code"
            fi
        fi
    else
        log ERROR "./reproduce/reproduce_documents.sh not found"
        log ERROR "Please run from the project root directory"
        return 1
    fi
}

reproduce_subfiles() {
    echo "========================================"
    echo "Compiling All Subfiles..."
    echo "========================================"
    echo ""
    
    # Check if Subfiles directory exists
    if [[ ! -d "Subfiles" ]]; then
        echo "ERROR: Subfiles/ directory not found"
        return 1
    fi
    
    # Find all .tex files in Subfiles directory (exclude hidden files starting with .)
    local tex_files=()
    while IFS= read -r -d '' file; do
        tex_files+=("$file")
    done < <(find Subfiles -maxdepth 1 -name "*.tex" -type f ! -name ".*" -print0 | sort -z)
    
    if [[ ${#tex_files[@]} -eq 0 ]]; then
        echo "No .tex files found in Subfiles/ directory"
        return 1
    fi
    
    echo "Found ${#tex_files[@]} .tex files to compile:"
    for file in "${tex_files[@]}"; do
        echo "  - $(basename "$file")"
    done
    echo ""
    
    # Compile each subfile
    local success_count=0
    local total_count=${#tex_files[@]}
    
    for file in "${tex_files[@]}"; do
        local filename
        local basename_no_ext
        filename=$(basename "$file")
        basename_no_ext=$(basename "$file" .tex)
        
        echo "📄 Compiling $filename..."
        
        # Change to Subfiles directory for compilation
        if (cd Subfiles && latexmk -c "$filename" >/dev/null 2>&1 && latexmk "$filename" >/dev/null 2>&1); then
            if [[ -f "Subfiles/${basename_no_ext}.pdf" ]]; then
                echo "✅ Successfully created ${basename_no_ext}.pdf"
                ((success_count++))
            else
                echo "❌ PDF not created for $filename"
            fi
        else
            echo "❌ Error compiling $filename"
        fi
        echo ""
    done
    
    # Summary
    echo "========================================"
    echo "Subfiles Compilation Summary"
    echo "========================================"
    echo "Successfully compiled: $success_count/$total_count files"
    
    if [[ $success_count -eq $total_count ]]; then
        echo "🎉 All subfiles compiled successfully!"
        return 0
    else
        echo "⚠️  Some subfiles failed to compile"
        return 1
    fi
}

reproduce_all_results() {
    local total_steps=3
    local start_time=$(date +%s)
    
    log INFO "========================================"
    log INFO "Complete Reproduction: All Computational Results + Documents"
    log INFO "========================================"
    echo ""
    log WARNING "This process may take 4-5 DAYS on a high-end 2025 laptop"
    log INFO "This will reproduce (in order):"
    log INFO "  1. All computational results"
    log INFO "  2. All figures from results (IMPC + Lorenz Points)"
    log INFO "  3. All documents (LaTeX compilation)"
    echo ""
    log INFO "Make sure you have:"
    log INFO "- Sufficient computational resources"
    log INFO "- Stable power supply" 
    log INFO "- No other intensive processes running"
    echo ""
    
    if is_interactive; then
        echo -n "Are you sure you want to continue? (y/N): "
        read -r confirm
        
        if [[ "$confirm" =~ ^[Yy]$ ]]; then
            echo ""
            log INFO "Starting complete reproduction..."
        else
            log INFO "Cancelled by user."
            return 0
        fi
    else
        log INFO "Running in non-interactive mode - proceeding with complete reproduction..."
        echo ""
    fi
    
    local step=1
    
    # Step 1: All computational results (DO COMPUTATION FIRST)
    log STEP "Step $step/$total_steps: Reproducing all computational results..."
    log INFO "Step start time: $(date '+%Y-%m-%d %H:%M:%S')"
    log INFO "========================================"
    if reproduce_all_computational_results; then
        local elapsed=$(($(date +%s) - start_time))
        log SUCCESS "Step $step/$total_steps completed successfully"
        log INFO "Step duration: $(printf '%d:%02d:%02d' $((elapsed/3600)) $((elapsed%3600/60)) $((elapsed%60)))"
    else
        log ERROR "Step $step/$total_steps FAILED"
        return 1
    fi
    echo ""
    ((step++))
    
    # Step 2: All figures from results (FIGURES DEPEND ON COMPUTATION)
    log STEP "Step $step/$total_steps: Generating all figures from results..."
    log INFO "Step start time: $(date '+%Y-%m-%d %H:%M:%S')"
    log INFO "========================================"
    local step_start=$(date +%s)
    if ./reproduce/reproduce_figures_from_results.sh all 2>&1 | tee -a "$LOG_FILE"; then
        local elapsed=$(($(date +%s) - step_start))
        log SUCCESS "Step $step/$total_steps completed successfully"
        log INFO "Step duration: $(printf '%d:%02d:%02d' $((elapsed/3600)) $((elapsed%3600/60)) $((elapsed%60)))"
    else
        log ERROR "Step $step/$total_steps FAILED"
        return 1
    fi
    echo ""
    ((step++))
    
    # Step 3: All documents (DOCUMENTS DEPEND ON COMPUTATION AND FIGURES)
    log STEP "Step $step/$total_steps: Reproducing all documents..."
    log INFO "Step start time: $(date '+%Y-%m-%d %H:%M:%S')"
    log INFO "========================================"
    step_start=$(date +%s)
    # Save current DOCS_SCOPE and set to all temporarily
    local saved_docs_scope="${DOCS_SCOPE:-}"
    DOCS_SCOPE="all"
    if reproduce_documents; then
        local elapsed=$(($(date +%s) - step_start))
        log SUCCESS "Step $step/$total_steps completed successfully"
        log INFO "Step duration: $(printf '%d:%02d:%02d' $((elapsed/3600)) $((elapsed%3600/60)) $((elapsed%60)))"
    else
        log ERROR "Step $step/$total_steps FAILED"
        DOCS_SCOPE="$saved_docs_scope"  # Restore original scope
        return 1
    fi
    DOCS_SCOPE="$saved_docs_scope"  # Restore original scope
    echo ""
    
    local total_elapsed=$(($(date +%s) - start_time))
    log SUCCESS "Complete reproduction finished successfully"
    log INFO "Total time: $(printf '%d:%02d:%02d' $((total_elapsed/3600)) $((total_elapsed%3600/60)) $((total_elapsed%60)))"
}

reproduce_minimal_results() {
    local start_time=$(date +%s)
    
    log PROGRESS "Starting minimal computational results reproduction"
    log INFO "========================================"
    log INFO "Reproducing Minimal Computational Results..."
    log INFO "========================================"
    echo ""
    log INFO "This will reproduce a subset of results (~1 hour)"
    log INFO "Start time: $(date '+%Y-%m-%d %H:%M:%S')"
    echo ""
    
    if [[ -f "./reproduce/reproduce_computed_min.sh" ]]; then
        log INFO "Executing: ./reproduce/reproduce_computed_min.sh"
        
        if ./reproduce/reproduce_computed_min.sh 2>&1 | tee -a "$LOG_FILE"; then
            local elapsed=$(($(date +%s) - start_time))
            log SUCCESS "Minimal computational results completed successfully"
            log INFO "Duration: $(printf '%d:%02d:%02d' $((elapsed/3600)) $((elapsed%3600/60)) $((elapsed%60)))"
            return 0
        else
            local exit_code=$?
            log ERROR "Minimal computational results failed with exit code $exit_code"
            return $exit_code
        fi
    else
        log ERROR "./reproduce/reproduce_computed_min.sh not found"
        return 1
    fi
}


reproduce_all_computational_results() {
    local start_time=$(date +%s)
    
    log PROGRESS "Starting full computational results reproduction"
    log INFO "========================================"
    log INFO "Reproducing All Computational Results..."
    log INFO "========================================"
    echo ""
    log WARNING "This process may take 4-5 DAYS on a high-end 2025 laptop"
    log INFO "Make sure you have:"
    log INFO "- Sufficient computational resources"
    log INFO "- Stable power supply"
    log INFO "- No other intensive processes running"
    log INFO "Start time: $(date '+%Y-%m-%d %H:%M:%S')"
    echo ""
    
    if is_interactive; then
        echo -n "Are you sure you want to continue? (y/N): "
        read -r confirm
        
        if [[ "$confirm" =~ ^[Yy]$ ]]; then
            echo ""
            log INFO "Starting full computational reproduction..."
        else
            log INFO "Cancelled by user."
            return 0
        fi
    else
        log INFO "Running in non-interactive mode - proceeding with full reproduction..."
        echo ""
    fi
    
    if [[ -f "./reproduce/reproduce_computed.sh" ]]; then
        log INFO "Executing: ./reproduce/reproduce_computed.sh"
        
        if ./reproduce/reproduce_computed.sh 2>&1 | tee -a "$LOG_FILE"; then
            local elapsed=$(($(date +%s) - start_time))
            log SUCCESS "All computational results completed successfully"
            log INFO "Duration: $(printf '%d:%02d:%02d' $((elapsed/3600)) $((elapsed%3600/60)) $((elapsed%60)))"
            return 0
        else
            local exit_code=$?
            log ERROR "All computational results failed with exit code $exit_code"
            return $exit_code
        fi
    else
        log ERROR "./reproduce/reproduce_computed.sh not found"
        return 1
    fi
}

test_environment_comprehensive() {
    local scope="${1:-both}"
    
    log PROGRESS "Starting environment testing (scope: $scope)"
    log INFO "========================================"
    log INFO "Testing HAFiscal Environment Setup"
    log INFO "========================================"
    echo ""
    
    case "$scope" in
        texlive)
            log INFO "Testing: TeX Live environment only"
            ;;
        comp)
            log INFO "Testing: Computational environment only"
            ;;
        both)
            log INFO "Testing: Both TeX Live and computational environments"
            ;;
    esac
    echo ""
    
    local overall_status=0
    
    # Test TeX Live environment (if requested)
    if [[ "$scope" == "texlive" || "$scope" == "both" ]]; then
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "1️⃣  Testing TeX Live Environment"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo ""

        # Check TeX Live version (platform-independent)
        TEXLIVE_VERSION=$(get_texlive_version)
        if [[ "$TEXLIVE_VERSION" -lt 2023 ]]; then
            if [[ "$TEXLIVE_VERSION" -eq 0 ]]; then
                echo "⚠️  WARNING: TeX Live not found (pdflatex not in PATH)"
            else
                echo "⚠️  WARNING: TeX Live $TEXLIVE_VERSION detected"
            fi
            echo "    This project requires TeX Live 2023 or later for optimal compatibility."
            echo ""

            if is_interactive; then
                # Interactive mode: ask user if they want to continue
                echo -n "Do you want to continue anyway? (y/N): "
                read -r response
                echo ""

                if [[ ! "$response" =~ ^[Yy]$ ]]; then
                    echo "Installation cancelled."
                    echo ""
                    echo "To install TeX Live 2023 or later:"
                    echo ""
                    echo "  macOS:"
                    echo "    - Download MacTeX from https://www.tug.org/mactex/"
                    echo "    - Or use Homebrew: brew install --cask mactex"
                    echo ""
                    echo "  Linux:"
                    echo "    - Download installer from https://www.tug.org/texlive/"
                    echo "    - Or use package manager (may have older version):"
                    echo "      sudo apt-get install texlive-full  (Debian/Ubuntu)"
                    echo "      sudo dnf install texlive-scheme-full  (Fedora)"
                    echo ""
                    echo "After installing TeX Live 2023+, rerun: ./reproduce.sh --envt texlive"
                    echo ""
                    return 1
                fi

                echo "Continuing with TeX Live $TEXLIVE_VERSION (not recommended)..."
                echo ""
            else
                # Non-interactive mode: fail by default (safe for CI/CD)
                echo "❌ ERROR: TeX Live $TEXLIVE_VERSION is too old (requires 2023+)"
                echo ""
                echo "Running in non-interactive mode - cannot prompt for confirmation."
                echo "This project requires TeX Live 2023 or later for compatibility."
                echo ""
                echo "To install TeX Live 2023 or later:"
                echo ""
                echo "  macOS:"
                echo "    - Download MacTeX from https://www.tug.org/mactex/"
                echo "    - Or use Homebrew: brew install --cask mactex"
                echo ""
                echo "  Linux:"
                echo "    - Download installer from https://www.tug.org/texlive/"
                echo "    - Or use package manager (may have older version):"
                echo "      sudo apt-get install texlive-full  (Debian/Ubuntu)"
                echo "      sudo dnf install texlive-scheme-full  (Fedora)"
                echo ""
                return 1
            fi
        else
            echo "✅ TeX Live $TEXLIVE_VERSION detected"
            echo ""
        fi

        if [[ -f "./reproduce/reproduce_environment_texlive.sh" ]]; then
            if ./reproduce/reproduce_environment_texlive.sh 2>&1; then
                echo ""
                echo "✅ TeX Live environment: PASSED"
            else
                echo ""
                echo "❌ TeX Live environment: FAILED"
                overall_status=1
            fi
        else
            echo "⚠️  TeX Live test script not found"
            overall_status=1
        fi
        echo ""
    fi
    
    # Test Computational environment (if requested)
    if [[ "$scope" == "comp" || "$scope" == "both" ]]; then
        # Check if environment was already verified (look for any timestamped marker)
        local comp_marker=""
        local script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
        
        if [[ "$scope" == "both" ]]; then
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            echo "2️⃣  Testing Computational Environment"
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        else
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            echo "Testing Computational Environment"
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        fi
        echo ""

        # Check for UV environment first (platform and architecture-specific)
        # Get platform and architecture-specific venv path
        local check_venv_path
        check_venv_path=$(get_platform_venv_path)

        # Also check legacy .venv for backwards compatibility
        if [[ ! -d "$check_venv_path" ]] && [[ -d "$script_dir/.venv" ]]; then
            check_venv_path="$script_dir/.venv"
        fi
        
        if [[ -d "$check_venv_path" ]] && [[ -f "pyproject.toml" ]]; then
            # Check for existing comp_uv verification marker
            comp_marker=$(find "$script_dir/reproduce" -name "reproduce_environment_comp_uv_*.verified" -type f 2>/dev/null | head -1)
            if [[ -n "$comp_marker" ]]; then
                echo "✅ Computational (UV) environment already verified (marker file exists)"
                echo "   To force re-verification, remove: $comp_marker"
                echo ""
                # Skip detailed tests since we have a marker
            else
                echo "🔍 Checking UV environment ($(basename "$check_venv_path"))..."
                # Set flag for benchmark filename generation
                export ENVT_USING_UV="true"
                if [[ -f "$check_venv_path/bin/python" ]]; then
                    echo "  ✅ UV environment exists"
                    
                    # Test key packages
                    if "$check_venv_path/bin/python" -c "import numpy, scipy, pandas, matplotlib; print('✅ Key packages available')" 2>/dev/null; then
                        echo "  ✅ Core scientific packages installed"
                    else
                        echo "  ⚠️  Some packages may be missing"
                        overall_status=1
                    fi
                    
                    # Check for HARK/econ-ark
                    if "$check_venv_path/bin/python" -c "import HARK; print(f'  ✅ HARK {HARK.__version__} installed')" 2>/dev/null; then
                        :
                    else
                        echo "  ⚠️  HARK (econ-ark) not installed"
                        echo "     Run: ./reproduce/reproduce_environment_comp_uv.sh"
                        overall_status=1
                    fi
                else
                    echo "  ❌ UV environment incomplete"
                    echo "     Run: ./reproduce/reproduce_environment_comp_uv.sh"
                    overall_status=1
                fi
            fi
        # Check for conda environment
        elif [[ -n "${CONDA_DEFAULT_ENV:-}" ]] || command -v conda >/dev/null 2>&1; then
            echo "🔍 Checking Conda environment..."
            
            if [[ -f "./reproduce/reproduce_environment.sh" ]]; then
                if ./reproduce/reproduce_environment.sh; then
                    echo "  ✅ Conda environment: PASSED"
                else
                    echo "  ❌ Conda environment: FAILED"
                    overall_status=1
                fi
            else
                echo "  ⚠️  Conda test script not found"
                overall_status=1
            fi
        else
            echo "❌ No Python environment detected"
            echo ""
            echo "Please set up an environment:"
            echo "  Option 1 (Recommended): ./reproduce/reproduce_environment_comp_uv.sh"
            echo "  Option 2 (Traditional):  conda env create -f environment.yml"
            overall_status=1
        fi
        echo ""
    fi
    
    # Summary
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "Environment Test Summary"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    
    if [[ $overall_status -eq 0 ]]; then
        echo "✅ ${GREEN}All environment tests PASSED${RESET}"
        echo ""
        
        # Create verification marker file for successful comp_uv tests
        if [[ "$scope" == "comp" && "${ENVT_USING_UV:-false}" == "true" && -z "$comp_marker" ]]; then
            local timestamp=$(date '+%Y%m%d-%H%M')
            local marker_file="$script_dir/reproduce_environment_comp_uv_${timestamp}.verified"
            touch "$marker_file"
            echo "ℹ️  Created verification marker: reproduce_environment_comp_uv_${timestamp}.verified"
            echo "   (Future runs will skip verification unless this file is removed)"
            echo ""
        fi
        
        echo "Your system is ready to reproduce HAFiscal results!"
        echo ""
        echo "Next steps:"
        echo "  ./reproduce.sh --docs      # Compile documents"
        echo "  ./reproduce.sh --comp min  # Run minimal computation"
    else
        echo "❌ ${RED}Some environment tests FAILED${RESET}"
        echo ""
        echo "Please fix the issues above before proceeding."
        echo ""
        echo "For help, see:"
        echo "  README.md - Setup instructions"
        echo "  README/INSTALLATION.md - Platform-specific guides"
        echo "  README/TROUBLESHOOTING.md - Common issues"
    fi
    echo ""
    
    return $overall_status
}

run_interactive_menu() {
    while true; do
        show_interactive_menu
        read -r choice
        echo ""
        
        case $choice in
            1)
                reproduce_documents
                break
                ;;
            2)
                DOCS_SCOPE="subfiles"
                reproduce_documents
                break
                ;;
            3)
                reproduce_minimal_results
                break
                ;;
            4)
                reproduce_all_computational_results
                break
                ;;
            5)
                reproduce_all_results
                break
                ;;
            6)
                echo "Exiting..."
                exit 0
                ;;
            *)
                echo "Invalid choice. Please enter 1, 2, 3, 4, 5, or 6."
                echo ""
                ;;
        esac
    done
}

# Function to test environment setup
test_environment() {
    echo "========================================"
    echo "Environment Testing"
    echo "========================================"
    echo ""
    
    # Check if UV is available and recommend it
    if command -v uv >/dev/null 2>&1; then
        echo "✅ UV detected (recommended environment manager)"
        echo ""
        echo "Quick setup with UV (recommended):"
        echo "  ./reproduce/reproduce_environment_comp_uv.sh"
        echo ""
        echo "This creates a platform-specific venv automatically."
        echo ""
    else
        echo "ℹ️  UV not detected. Using conda environment."
        echo ""
        echo "For faster setup, consider installing UV:"
        echo "  curl -LsSf https://astral.sh/uv/install.sh | sh"
        echo ""
    fi
    
    echo "🔍 Checking required dependencies..."
    
    local env_ok=true
    local missing_deps=()
    
    # Test basic commands
    echo "• Checking basic tools..."
    if ! command -v latexmk >/dev/null 2>&1; then
        missing_deps+=("latexmk")
        env_ok=false
    fi
    
    if ! command -v pdflatex >/dev/null 2>&1; then
        missing_deps+=("pdflatex") 
        env_ok=false
    fi
    
    if ! command -v bibtex >/dev/null 2>&1; then
        missing_deps+=("bibtex")
        env_ok=false
    fi
    
    if ! command -v python3 >/dev/null 2>&1; then
        missing_deps+=("python3")
        env_ok=false
    fi
    
    # Test LaTeX environment using existing script
    echo "• Checking LaTeX environment..."
    if [[ -f "./reproduce/reproduce_environment_texlive.sh" ]]; then
        if ! ./reproduce/reproduce_environment_texlive.sh >/dev/null 2>&1; then
            missing_deps+=("LaTeX packages (see reproduce_environment_texlive.sh)")
            env_ok=false
        fi
    else
        echo "  ⚠️  Cannot verify LaTeX packages (reproduce_environment_texlive.sh not found)"
    fi
    
    # Test computational environment if available
    echo "• Checking computational environment..."

    # Check for UV environment first (platform and architecture-specific)
    # Use get_platform_venv_path() for consistent detection
    local check_venv_path
    check_venv_path="$(get_platform_venv_path)"

    # Also check legacy .venv for backwards compatibility
    if [[ ! -d "$check_venv_path" ]] && [[ -d ".venv" ]]; then
        check_venv_path=".venv"
    fi
    
    if [[ -d "$check_venv_path" ]] && [[ -f "pyproject.toml" ]]; then
        if [[ -f "$check_venv_path/bin/python" ]]; then
            echo "  ✅ UV environment detected and appears valid ($(basename "$check_venv_path"))"
        else
            echo "  ⚠️  UV environment incomplete. Run: ./reproduce/reproduce_environment_comp_uv.sh"
        fi
    # Fall back to conda check
    elif [[ -f "./reproduce/reproduce_environment.sh" ]]; then
        if ./reproduce/reproduce_environment.sh >/dev/null 2>&1; then
            echo "  ✅ Python/Conda environment OK"
        else
            echo "  ⚠️  Python/Conda environment needs setup (non-critical for document reproduction)"
        fi
    else
        echo "  ⚠️  No environment detected. Run one of:"
        echo "     ./reproduce/reproduce_environment_comp_uv.sh  (recommended, fast)"
        echo "     conda env create -f environment.yml      (traditional)"
    fi
    
    # Report results
    echo ""
    if [[ "$env_ok" == "true" ]]; then
        echo "✅ Environment testing passed!"
        echo "All essential dependencies are available."
        echo ""
        return 0
    else
        echo "❌ Environment testing failed!"
        echo ""
        echo "Missing dependencies:"
        for dep in "${missing_deps[@]}"; do
            echo "  • $dep"
        done
        echo ""
        echo "📖 For setup instructions, please see:"
        echo "   README.md - General setup guide"
        echo "   reproduce/reproduce_environment_texlive.sh - LaTeX setup"
        echo "   reproduce/reproduce_environment.sh - Python/Conda setup"
        echo ""
        echo "You can still run specific components if their dependencies are met:"
        echo "   ./reproduce.sh --docs      # Requires LaTeX tools"
        echo "   ./reproduce.sh --docs subfiles  # Requires LaTeX tools" 
        echo "   ./reproduce.sh --comp min  # Requires Python environment"
        echo "   ./reproduce.sh --all       # Requires Python environment"
        echo ""
        return 1
    fi
}

# Function to run full automatic reproduction (non-interactive mode)
run_automatic_reproduction() {
    echo "========================================"
    echo "Automatic Full Reproduction"
    echo "========================================"
    echo ""
    echo "Running complete reproduction sequence:"
    echo "  1. Documents (LaTeX compilation)"
    echo "  2. Subfiles (standalone LaTeX files)"
    echo "  3. Minimal computational results"
    echo "  4. All computational results"
    echo ""
    
    local step=1
    local total_steps=4
    
    # Step 1: Documents
    echo ">>> Step $step/$total_steps: Reproducing LaTeX documents..."
    echo "========================================"
    if reproduce_documents; then
        echo "✅ Step $step/$total_steps completed successfully"
    else
        echo "❌ Step $step/$total_steps failed"
        return 1
    fi
    echo ""
    ((step++))
    
    # Step 2: Subfiles  
    echo ">>> Step $step/$total_steps: Compiling subfiles..."
    echo "========================================"
    # Save current DOCS_SCOPE and set to subfiles temporarily
    local saved_docs_scope="${DOCS_SCOPE:-}"
    DOCS_SCOPE="subfiles"
    if reproduce_documents; then
        echo "✅ Step $step/$total_steps completed successfully"
    else
        echo "❌ Step $step/$total_steps failed"
        DOCS_SCOPE="$saved_docs_scope"  # Restore original scope
        return 1
    fi
    DOCS_SCOPE="$saved_docs_scope"  # Restore original scope
    echo ""
    ((step++))
    
    # Step 3: Minimal computational results
    echo ">>> Step $step/$total_steps: Reproducing minimal computational results..."
    echo "========================================"
    if reproduce_minimal_results; then
        echo "✅ Step $step/$total_steps completed successfully"
    else
        echo "❌ Step $step/$total_steps failed"
        return 1
    fi
    echo ""
    ((step++))
    
    # Step 4: All computational results  
    echo ">>> Step $step/$total_steps: Reproducing all computational results..."
    echo "========================================"
    echo "⚠️  WARNING: This final step may take 4-5 DAYS on a high-end 2025 laptop!"
    if reproduce_all_results; then
        echo "✅ Step $step/$total_steps completed successfully"
    else
        echo "❌ Step $step/$total_steps failed"
        return 1
    fi
    echo ""
    
    echo "========================================"
    echo "🎉 Automatic Full Reproduction Complete!"
    echo "========================================"
    echo ""
    echo "All steps completed successfully:"
    echo "  ✅ Documents compiled"
    echo "  ✅ Subfiles compiled"  
    echo "  ✅ Minimal computational results generated"
    echo "  ✅ All computational results generated"
    echo ""
}

is_interactive() {
    # Check if both stdin and stdout are terminals
    [[ -t 0 && -t 1 ]]
}

process_reproduce_targets() {
    local targets="${REPRODUCE_TARGETS:-}"
    
    if [[ -z "$targets" ]]; then
        echo "ERROR: REPRODUCE_TARGETS environment variable not set"
        echo "Valid values: docs, comp, all (comma-separated)"
        echo "Example: REPRODUCE_TARGETS=docs,comp"
        return 1
    fi
    
    # Replace commas with spaces for simple iteration
    local targets_spaced
    targets_spaced=$(echo "$targets" | tr ',' ' ')
    
    local has_error=false
    local executed_targets=""
    
    # Validate all targets first
    for target in $targets_spaced; do
        # Trim whitespace
        target=$(echo "$target" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
        case "$target" in
            docs|comp|all)
                # Valid target
                ;;
            *)
                echo "ERROR: Invalid target '$target'"
                echo "Valid targets: docs, comp, all"
                has_error=true
                ;;
        esac
    done
    
    if [[ "$has_error" == true ]]; then
        return 1
    fi
    
    # Execute targets in a logical order: docs, comp, all
    for ordered_target in docs comp all; do
        for target in $targets_spaced; do
            target=$(echo "$target" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
            if [[ "$target" == "$ordered_target" ]]; then
                # Check if we've already executed this target
                if [[ "$executed_targets" != *"$target"* ]]; then
                    echo "Executing target: $target"
                    case "$target" in
                        docs)
                            reproduce_documents || return 1
                            ;;
                        comp)
                            # Default to min scope for comp
                            ;;
                        all)
                            reproduce_all_results || return 1
                            ;;
                    esac
                    if [[ -z "$executed_targets" ]]; then
                        executed_targets="$target"
                    else
                        executed_targets="$executed_targets $target"
                    fi
                fi
            fi
        done
    done
    
    echo ""
    if [[ -n "$executed_targets" ]]; then
        echo "Completed targets: $executed_targets"
    else
        echo "No targets were executed"
    fi
}

# Parse command line arguments
DRY_RUN=false
VERBOSE=false
DEBUG=false
ACTION=""
DOCS_SCOPE="main"  # default scope for --docs
COMP_SCOPE="min"   # default scope for --comp
DATA_SCOPE="scf"   # default scope for --data
ENVT_SCOPE="both"  # default scope for --envt
SHOW_LABELS="${SHOW_LABELS:-}"  # default: use .tex file default

# Parse all arguments first
while [[ $# -gt 0 ]]; do
    case $1 in
        --help|-h)
            show_help
            exit 0
            ;;
        --envt|-e)
            ACTION="envt"
            shift
            # Check if next argument is a scope specifier
            if [[ $# -gt 0 && "$1" =~ ^(texlive|comp|comp_uv|both)$ ]]; then
                ENVT_SCOPE="$1"
                # Map comp_uv to comp for the test, but set UV flag
                if [[ "$1" == "comp_uv" ]]; then
                    ENVT_SCOPE="comp"
                    export ENVT_USING_UV="true"
                fi
                shift
            else
                # Default to both if no scope specified
                ENVT_SCOPE="both"
            fi
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --stop-on-error)
            STOP_ON_ERROR=true
            shift
            ;;
        --verbose|-v)
            VERBOSE=true
            export VERBOSE=true
            shift
            ;;
        --debug)
            DEBUG=true
            VERBOSE=true
            export DEBUG=true
            export VERBOSE=true
            shift
            ;;
        --docs|-d)
            ACTION="docs"
            shift
            # Check if next argument is a scope specifier
            if [[ $# -gt 0 && "$1" =~ ^(main|all|figures|tables|subfiles)$ ]]; then
                DOCS_SCOPE="$1"
                shift
            fi
            ;;
        --comp|-c)
            ACTION="comp"
            shift
            # Check if next argument is a scope specifier
            if [[ $# -gt 0 && "$1" =~ ^(min|full|max)$ ]]; then
                COMP_SCOPE="$1"
                shift
            else
                # Default to min if no scope specified
                COMP_SCOPE="min"
            fi
            ;;
        --data)
            ACTION="data"
            shift
            # Check if next argument is a scope specifier
            if [[ $# -gt 0 && "$1" =~ ^(scf|IMPC|LP|all)$ ]]; then
                DATA_SCOPE="$1"
                shift
            else
                # Default to scf if no scope specified
                DATA_SCOPE="scf"
            fi
            ;;
        --use-latest-scf-data)
            USE_LATEST_SCF_DATA=true
            shift
            ;;
        --all|-a)
            ACTION="all"
            shift
            ;;
        --min|-m)
            # Legacy option - provide deprecation warning but still work
            echo "⚠️  WARNING: --min is deprecated. Use '--comp min' instead."
            echo "   This will be removed in a future version."
            ACTION="comp"
            COMP_SCOPE="min"
            shift
            ;;
        --showlabels|--show-labels)
            SHOW_LABELS=true
            shift
            ;;
        --no-labels|--hide-labels)
            SHOW_LABELS=false
            shift
            ;;
        --interactive|-i)
            ACTION="interactive"
            shift
            ;;
        *)
            if [[ -z "$ACTION" && -z "$1" ]]; then
                # Empty argument, treat as no arguments
                break
            else
                echo "Unknown option: $1"
                echo "Run with --help for available options"
                exit 1
            fi
            ;;
    esac
done

# Export SHOW_LABELS for build scripts
export SHOW_LABELS

# ============================================================================
# ENVIRONMENT ACTIVATION CHECK
# Ensure we're running in the uv .venv environment
# ============================================================================

# Platform and architecture-specific venv detection
# Returns the appropriate venv directory name based on the current platform and architecture
# Supports cross-platform development (macOS <-> Linux DevContainer)
# Supports cross-architecture development (Intel <-> ARM on same platform)
# Uses robust hardware detection to avoid Rosetta/conda confusion
get_platform_venv_path() {
    local script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
    local platform=""
    local arch=""

    # Detect platform
    case "$(uname -s)" in
        Darwin)
            platform="darwin"
            ;;
        Linux)
            platform="linux"
            ;;
        *)
            # Fallback to generic .venv for unknown platforms
            platform=""
            ;;
    esac

    # Detect architecture - use hardware detection, not process architecture
    if [[ "$(uname -s)" == "Darwin" ]]; then
        # macOS: Check actual hardware, not Rosetta-reported arch
        if sysctl -n hw.optional.arm64 2>/dev/null | grep -q 1; then
            arch="arm64"  # Apple Silicon
        else
            arch="x86_64"  # Intel Mac
        fi
    else
        # Linux/other: use uname
        arch="$(uname -m)"
    fi

    # Normalize architecture names
    case "$arch" in
        arm64) normalized_arch="arm64" ;;      # macOS ARM
        aarch64) normalized_arch="aarch64" ;;  # Linux ARM
        x86_64) normalized_arch="x86_64" ;;    # Both
        *) normalized_arch="$arch" ;;           # Other (e.g., i386, i686)
    esac

    # Return architecture-specific venv path (using - separator to match .gitignore)
    if [[ -n "$platform" ]] && [[ -n "$normalized_arch" ]]; then
        echo "$script_dir/.venv-$platform-$normalized_arch"
    elif [[ -n "$platform" ]]; then
        echo "$script_dir/.venv-$platform"
    else
        echo "$script_dir/.venv"
    fi
}

get_texlive_version() {
    # Platform-independent TeX Live version detection
    # Returns the year (e.g., 2023, 2025) or 0 if not found

    if ! command -v pdflatex >/dev/null 2>&1; then
        echo "0"  # TeX Live not found
        return
    fi

    # Extract year from "TeX Live YYYY" in version output
    local version=$(pdflatex --version 2>/dev/null | grep -oE "TeX Live [0-9]{4}" | grep -oE "[0-9]{4}")

    if [[ -n "$version" ]]; then
        echo "$version"
    else
        echo "0"
    fi
}

ensure_uv_environment() {
    # Deactivate conda if active to prevent interference with uv venv
    # Conda (especially x86_64 via Rosetta on Apple Silicon) can cause architecture mismatches
    if command -v conda >/dev/null 2>&1; then
        if [ -n "${CONDA_DEFAULT_ENV:-}" ] || [ -n "${CONDA_PREFIX:-}" ]; then
            log INFO "Deactivating conda environment for clean UV venv activation"
            # Deactivate conda (may need multiple calls to fully exit nested envs)
            for i in $(seq 1 5); do
                conda deactivate 2>/dev/null || true
                [ -z "${CONDA_DEFAULT_ENV:-}" ] && break
            done
            
            # Unset conda environment variables
            unset CONDA_DEFAULT_ENV 2>/dev/null || true
            unset CONDA_PREFIX 2>/dev/null || true
            unset CONDA_PYTHON_EXE 2>/dev/null || true
            unset CONDA_SHLVL 2>/dev/null || true
            unset CONDA_EXE 2>/dev/null || true
            unset _CE_CONDA 2>/dev/null || true
            unset _CE_M 2>/dev/null || true
        fi
    fi

    # Detect if we're running in Docker/container environment
    local in_docker=false
    if [[ -f /.dockerenv ]] || [[ -f /proc/1/cgroup ]] && grep -q docker /proc/1/cgroup 2>/dev/null; then
        in_docker=true
    fi
    
    # Get the expected venv path (platform-specific)
    local script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
    local expected_venv
    expected_venv=$(get_platform_venv_path)
    
    # Also check for legacy .venv (for backward compatibility during migration)
    local legacy_venv="$script_dir/.venv"
    
    # Remove .venv symlink if it exists (no longer needed, script uses platform-specific paths directly)
    if [[ -L "$script_dir/.venv" ]]; then
        local symlink_target=$(readlink "$script_dir/.venv" 2>/dev/null || echo "unknown")
        log INFO "Removing obsolete .venv symlink (pointed to: $symlink_target)"
        rm -f "$script_dir/.venv"
        log SUCCESS "Symlink removed - script now uses platform-specific venv paths directly"
    fi

    # Helper variables for user-friendly error messages
    local current_dir="$(pwd -P)"
    local dir_name="$(basename "$script_dir")"
    local already_in_dir=false
    if [[ "$current_dir" == "$script_dir" ]]; then
        already_in_dir=true
    fi
    
    # Check if platform-specific venv exists, or fallback to legacy .venv
    # In Docker, if venv directory exists but is incomplete, try to recreate it
    if [[ "$in_docker" == true ]] && [[ -d "$expected_venv" ]] && [[ ! -f "$expected_venv/bin/python" ]]; then
        log WARNING "Detected incomplete venv in Docker: $expected_venv"
        log INFO "Attempting to recreate virtual environment..."
        cd "$script_dir"
        if [[ -f "./reproduce/reproduce_environment_comp_uv.sh" ]]; then
            bash ./reproduce/reproduce_environment_comp_uv.sh || {
                log ERROR "Failed to recreate venv in Docker"
                exit 1
            }
        else
            log ERROR "reproduce_environment_comp_uv.sh not found - cannot recreate venv"
            exit 1
        fi
    fi
    
    if [[ ! -d "$expected_venv" ]] && [[ ! -d "$legacy_venv" ]]; then
        log WARNING "Virtual environment not found: $(basename "$expected_venv")"
        log INFO "Attempting to create it automatically using reproduce_environment_comp_uv.sh"
        cd "$script_dir"
        if [[ -f "./reproduce/reproduce_environment_comp_uv.sh" ]]; then
            bash ./reproduce/reproduce_environment_comp_uv.sh || {
                log ERROR "Failed to create virtual environment automatically"
                exit 1
            }
        else
            log ERROR "reproduce_environment_comp_uv.sh not found - cannot create venv"
            exit 1
        fi
        # After creation, continue and let activation logic run below.
    fi
    
    # If legacy .venv exists but platform-specific doesn't, suggest migration
    if [[ ! -d "$expected_venv" ]] && [[ -d "$legacy_venv" ]]; then
        echo "========================================"
        echo "ℹ️  Legacy Virtual Environment Detected"
        echo "========================================"
        echo ""
        echo "Found legacy .venv directory. For cross-platform development,"
        echo "consider migrating to platform-specific venvs:"
        echo ""
        echo "Option 1 (Recommended - Automatic migration):"
        echo "  ./reproduce/migrate_to_platform_venvs.sh"
        echo ""
        echo "Option 2 (Manual migration):"
        echo "  mv .venv $(basename "$expected_venv")"
        echo "  ./reproduce/reproduce_environment_comp_uv.sh  # Create venv for other platform if needed"
        echo ""
        echo "Continuing with legacy .venv for now..."
        echo ""
        expected_venv="$legacy_venv"
    fi
    
    # Check if we're in the correct venv
    if [[ -n "${VIRTUAL_ENV:-}" ]]; then
        # Normalize both paths for comparison
        local normalized_venv="$(cd "$VIRTUAL_ENV" 2>/dev/null && pwd -P || echo "$VIRTUAL_ENV")"
        local normalized_expected="$(cd "$expected_venv" 2>/dev/null && pwd -P || echo "$expected_venv")"
        
        if [[ "$normalized_venv" == "$normalized_expected" ]]; then
            # Correct venv is active - validate packages before proceeding
            if ! python3 -c "import numpy, pandas" 2>/dev/null; then
                # Check if it's an architecture mismatch
                ARCH_ERROR=$(python3 -c "import numpy" 2>&1 | grep -E "incompatible architecture|mach-o file" || true)
                if [ -n "$ARCH_ERROR" ]; then
                    log ERROR "Architecture mismatch detected in virtual environment"
                    echo ""
                    echo "The virtual environment has packages compiled for a different architecture."
                    echo "This typically happens when $(basename "$expected_venv") was created on a different machine or"
                    echo "with a different Python architecture (ARM64 vs x86_64)."
                    echo ""
                    echo "To fix this, recreate the venv for the current architecture:"
                    if [[ "$already_in_dir" == false ]]; then
                        echo "  cd <path-to>/$dir_name  # Navigate to the $dir_name directory"
                    fi
                    echo "  rm -rf $(basename "$expected_venv")"
                    echo "  ./reproduce/reproduce_environment_comp_uv.sh"
                    echo ""
                    echo "This will create a platform-specific venv automatically."
                    echo ""
                    exit 1
                else
                    log WARNING "Key packages (numpy, pandas) not available in venv"
                    log INFO "This may be OK if you're only running document reproduction"
                fi
            else
                log SUCCESS "Key packages (numpy, pandas) validated successfully"
            fi
            
            # Export environment variables
            export HAFISCAL_PYTHON="$expected_venv/bin/python"
            export HAFISCAL_PYTHON3="$expected_venv/bin/python3"
            log INFO "UV environment already active: $VIRTUAL_ENV"
            return 0
        fi
        
        # Wrong venv is active - could be stale from different machine
        log WARNING "Virtual environment mismatch detected"
        log INFO "Current VIRTUAL_ENV: $VIRTUAL_ENV"
        log INFO "Expected venv:       $expected_venv"
        log INFO "Attempting to activate expected venv automatically"

        # Attempt to activate the expected venv even if another venv is active.
        # This avoids hard-failing when the user has an unrelated venv active.
        if [[ -f "$expected_venv/bin/activate" ]]; then
            # shellcheck disable=SC1091
            source "$expected_venv/bin/activate"
            export PATH="$expected_venv/bin:$PATH"
            hash -r 2>/dev/null || true

            local actual_python
            actual_python=$(command -v python3 2>/dev/null || command -v python 2>/dev/null || echo "")
            local expected_python="$expected_venv/bin/python"

            if [[ "$actual_python" == "$expected_python"* ]]; then
                log SUCCESS "Switched to expected virtual environment"
                log INFO "Python: $actual_python"
                export HAFISCAL_PYTHON="$expected_venv/bin/python"
                export HAFISCAL_PYTHON3="$expected_venv/bin/python3"
                return 0
            fi
        fi

        echo "========================================"
        echo "❌ Virtual Environment Path Mismatch"
        echo "========================================"
        echo ""
        echo "A virtual environment is active, but it appears to be from a different location."
        echo ""
        echo "Current VIRTUAL_ENV: $VIRTUAL_ENV"
        echo "Expected path:       $expected_venv"
        echo ""
        echo "Automatic switching to the expected venv failed."
        echo "To fix:"
        echo "  1. Close this terminal"
        echo "  2. Open a fresh terminal"
        if [[ "$already_in_dir" == false ]]; then
            echo "  3. cd <path-to>/$dir_name"
        fi
        echo "  4. source $(basename "$expected_venv")/bin/activate"
        echo "  5. $0 $*"
        echo ""
        exit 1
    fi
    
    # No venv active but .venv exists - auto-activate it (PLAN A)
    if [[ -f "$expected_venv/bin/python" ]] || [[ -f "$expected_venv/bin/python3" ]]; then
        log INFO "Activating UV environment: $expected_venv"
        
        # Warn if conda is active
        if [[ -n "${CONDA_DEFAULT_ENV:-}" ]]; then
            log WARNING "Conda environment detected: $CONDA_DEFAULT_ENV"
            log INFO "The project $(basename "$expected_venv") will be activated (conda remains in background)"
        fi
        
        # shellcheck disable=SC1091
        source "$expected_venv/bin/activate"
        # Defensive: ensure expected venv bin precedes any other venv in PATH.
        export PATH="$expected_venv/bin:$PATH"
        hash -r 2>/dev/null || true
        
        # Validate correct Python is in use
        local actual_python
        actual_python=$(command -v python3 2>/dev/null || command -v python 2>/dev/null || echo "")
        local expected_python="$expected_venv/bin/python"
        
        if [[ "$actual_python" == "$expected_python"* ]]; then
            log SUCCESS "UV environment activated successfully"
            log INFO "Python: $actual_python"
            
            # Validate that key packages can be imported (catches architecture mismatches)
            if ! python3 -c "import numpy, pandas" 2>/dev/null; then
                # Check if it's an architecture mismatch
                ARCH_ERROR=$(python3 -c "import numpy" 2>&1 | grep -E "incompatible architecture|mach-o file" || true)
                if [ -n "$ARCH_ERROR" ]; then
                    log ERROR "Architecture mismatch detected in virtual environment"
                    echo ""
                    echo "The virtual environment has packages compiled for a different architecture."
                    echo "This typically happens when $(basename "$expected_venv") was created on a different machine or"
                    echo "with a different Python architecture (ARM64 vs x86_64)."
                    echo ""
                    echo "To fix this, recreate the venv for the current architecture:"
                    if [[ "$already_in_dir" == false ]]; then
                        echo "  cd <path-to>/$dir_name  # Navigate to the $dir_name directory"
                    fi
                    echo "  rm -rf $(basename "$expected_venv")"
                    echo "  ./reproduce/reproduce_environment_comp_uv.sh"
                    echo ""
                    echo "This will create a platform-specific venv automatically."
                    echo ""
                    exit 1
                else
                    log WARNING "Key packages (numpy, pandas) not available in venv"
                    log INFO "This may be OK if you're only running document reproduction"
                fi
            else
                log SUCCESS "Key packages (numpy, pandas) validated successfully"
            fi
            
            # Export environment variables for subscripts
            export HAFISCAL_PYTHON="$expected_venv/bin/python"
            export HAFISCAL_PYTHON3="$expected_venv/bin/python3"
            
            return 0
        else
            log ERROR "Environment activation failed - wrong Python in use"
            log ERROR "Expected: $expected_python"
            log ERROR "Actual:   $actual_python"
            echo ""
            echo "This may indicate:"
            echo "  • PATH is not updated correctly"
            echo "  • Shell configuration overriding activation"
            echo "  • Conflicting environment still active"
            echo ""
            echo "To fix:"
            echo "  1. Close this terminal"
            echo "  2. Open a fresh terminal"
            if [[ "$already_in_dir" == false ]]; then
                echo "  3. cd <path-to>/$dir_name  # Navigate to the $dir_name directory"
            fi
            echo "  4. source $(basename "$expected_venv")/bin/activate"
            echo "  5. $0 $*"
            echo ""
            exit 1
        fi
    fi
    
    # Platform-specific venv directory exists but seems broken/incomplete
    # In Docker, try to recreate it automatically
    if [[ "$in_docker" == true ]]; then
        log WARNING "Detected incomplete venv in Docker: $(basename "$expected_venv")"
        log INFO "Attempting to recreate virtual environment..."
        cd "$script_dir"
        if [[ -f "./reproduce/reproduce_environment_comp_uv.sh" ]]; then
            bash ./reproduce/reproduce_environment_comp_uv.sh || {
                log ERROR "Failed to recreate venv in Docker"
                exit 1
            }
            # Re-check after recreation
            if [[ -f "$expected_venv/bin/python" ]] || [[ -f "$legacy_venv/bin/python" ]]; then
                log SUCCESS "Virtual environment recreated successfully"
            fi
        fi
    fi
    
    log WARNING "Virtual environment appears incomplete: $(basename "$expected_venv")"
    log INFO "Attempting to recreate it automatically using reproduce_environment_comp_uv.sh"
    cd "$script_dir"
    if [[ -f "./reproduce/reproduce_environment_comp_uv.sh" ]]; then
        rm -rf "$expected_venv" 2>/dev/null || true
        bash ./reproduce/reproduce_environment_comp_uv.sh || {
            log ERROR "Failed to recreate virtual environment automatically"
            exit 1
        }
        # Activate immediately after recreation so downstream steps have correct PATH.
        if [[ -f "$expected_venv/bin/activate" ]]; then
            # shellcheck disable=SC1091
            source "$expected_venv/bin/activate"
            export PATH="$expected_venv/bin:$PATH"
            hash -r 2>/dev/null || true

            local actual_python
            actual_python=$(command -v python3 2>/dev/null || command -v python 2>/dev/null || echo "")
            local expected_python="$expected_venv/bin/python"
            if [[ "$actual_python" == "$expected_python"* ]]; then
                log SUCCESS "UV environment activated successfully after recreation"
                log INFO "Python: $actual_python"
                export HAFISCAL_PYTHON="$expected_venv/bin/python"
                export HAFISCAL_PYTHON3="$expected_venv/bin/python3"
                return 0
            fi
        fi
        log ERROR "Virtual environment recreated but activation still failed"
        exit 1
    fi
    log ERROR "reproduce_environment_comp_uv.sh not found - cannot recreate venv"
    exit 1

}

    # Save all arguments to pass through
    SCRIPT_ARGS=("$@")
    
    # Restore original arguments since we consumed them in parsing
    # We need to reconstruct them for the re-exec
    ARGS_FOR_REEXEC=()
    [[ "$DRY_RUN" == true ]] && ARGS_FOR_REEXEC+=("--dry-run")
    [[ -n "$ACTION" ]] && {
        case "$ACTION" in
            envt) ARGS_FOR_REEXEC+=("--envt" "$ENVT_SCOPE") ;;
            docs) ARGS_FOR_REEXEC+=("--docs" "$DOCS_SCOPE") ;;
            comp) ARGS_FOR_REEXEC+=("--comp" "$COMP_SCOPE") ;;
            all) ARGS_FOR_REEXEC+=("--all") ;;
            interactive) ARGS_FOR_REEXEC+=("--interactive") ;;
        esac
    }
    
    ensure_uv_environment "${ARGS_FOR_REEXEC[@]}"

# Start benchmarking (only if an action is specified)
if [[ -n "$ACTION" ]]; then
    benchmark_start
fi

# Handle dry-run mode
if [[ "$DRY_RUN" == true ]]; then
    if [[ "$ACTION" == "docs" ]]; then
        # Dry-run is supported for docs - pass the flag
        echo "========================================"
        echo "🔍 DRY RUN MODE: Documents"
        echo "========================================"
        echo "The following commands would be executed:"
        echo ""
        DRY_RUN=true reproduce_documents
        exit $?
    elif [[ -n "$ACTION" ]]; then
        # Dry-run requested for other actions - show polite message
        echo "========================================"
        echo "ℹ️  Dry-run mode information"
        echo "========================================"
        echo ""
        echo "The --dry-run flag is currently only supported with the --docs flag."
        echo ""
        echo "To see what documents would be compiled, use:"
        echo "  ./reproduce.sh --docs --dry-run"
        echo ""
        echo "For other operations (--comp, --all), the reproduction"
        echo "scripts execute complex computational workflows that are not easily"
        echo "represented as simple commands that can be copy-pasted."
        echo ""
        exit 0
    else
        echo "ERROR: --dry-run requires one of: --docs, --comp, --all"
        echo "Currently, dry-run mode is only supported with --docs"
        exit 1
    fi
fi

# Execute the requested action
case "$ACTION" in
    envt)
        init_logging "envt" "$ENVT_SCOPE"
        log INFO "Action: Environment testing (scope: $ENVT_SCOPE)"
        # Set flag so environment setup script knows it's being called from reproduce.sh
        # Export it so child processes inherit it
        export REPRODUCE_SCRIPT_CONTEXT="true"
        test_environment_comprehensive "$ENVT_SCOPE"
        test_exit_code=$?
        # Auto-activate environment after successful test
        if [[ $test_exit_code -eq 0 ]]; then
            script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
            platform=""
            arch="$(uname -m)"
            case "$(uname -s)" in
                Darwin) platform="darwin" ;;
                Linux) platform="linux" ;;
            esac
            if [[ -n "$platform" ]] && [[ -n "$arch" ]]; then
                expected_venv="$script_dir/.venv-$platform-$arch"
            elif [[ -n "$platform" ]]; then
                expected_venv="$script_dir/.venv-$platform"
            else
                expected_venv="$script_dir/.venv"
            fi
            
            if [[ -d "$expected_venv" ]] && [[ -f "$expected_venv/bin/activate" ]]; then
                if [[ -z "${VIRTUAL_ENV:-}" ]] || [[ "$VIRTUAL_ENV" != "$expected_venv"* ]]; then
                    # Activate in script's subshell (for any subprocesses)
                    source "$expected_venv/bin/activate"
                    export HAFISCAL_PYTHON="$expected_venv/bin/python"
                    export HAFISCAL_PYTHON3="$expected_venv/bin/python3"
                    
                    # Note: This activation doesn't persist to user's shell after script exits
                    # User needs to manually activate if they want it in their shell
                    if [[ -t 1 ]] && [[ -z "${CI:-}" ]]; then
                        echo ""
                        echo "ℹ️  Note: Environment was activated in script context."
                        if [[ -n "${CONDA_DEFAULT_ENV:-}" ]]; then
                            echo "   Conda '${CONDA_DEFAULT_ENV}' is still active in your shell."
                            echo "   To use the UV venv in your shell, run:"
                            echo "     conda deactivate"
                            echo "     source $(basename "$expected_venv")/bin/activate"
                        else
                            echo "   To activate in your shell, run:"
                            echo "     source $(basename "$expected_venv")/bin/activate"
                        fi
                        echo ""
                    fi
                fi
            fi
        fi
        exit $test_exit_code
        ;;
    docs)
        init_logging "docs" "$DOCS_SCOPE"
        log INFO "Action: Document reproduction (scope: $DOCS_SCOPE)"
        reproduce_documents
        exit $?
        ;;
    comp)
        init_logging "comp" "$COMP_SCOPE"
        log INFO "Action: Computational reproduction (scope: $COMP_SCOPE)"
        case "$COMP_SCOPE" in
            min)
                reproduce_minimal_results
                exit $?
                ;;
            full)
                reproduce_all_computational_results
                exit $?
                ;;
            max)
                # Set environment variable to enable Step 3 (robustness with Splurge=0)
                log INFO "Maximum scope enabled - includes Step 3 robustness checks"
                export HAFISCAL_RUN_STEP_3="true"
                reproduce_all_computational_results
                exit $?
                ;;
            *)
                log ERROR "Unknown computational scope: $COMP_SCOPE"
                log ERROR "Valid scopes: min, full, max"
                exit 1
                ;;
        esac
        ;;
    data)
        init_logging "data" "$DATA_SCOPE"
        case "$DATA_SCOPE" in
            scf)
                log PROGRESS "Starting empirical data moments reproduction"
                log INFO "========================================"
                log INFO "Reproducing Empirical Data Moments..."
                log INFO "========================================"
                echo ""
                if [[ "$USE_LATEST_SCF_DATA" == "true" ]]; then
                    log WARNING "⚠️  IMPORTANT: Using latest SCF data from Federal Reserve"
                    log WARNING "   Assumption: Downloaded data is in 2022 dollars"
                    log WARNING "   Inflation adjustment: 1.1587 (2022$ → 2013$)"
                    log WARNING "   ⚠️  When Fed updates inflation adjustments:"
                    log WARNING "      1. Update inflation factor in adjust_scf_inflation.py"
                    log WARNING "      2. Verify factor by comparing to archived version"
                    log WARNING "      3. Update documentation"
                    log INFO ""
                    log INFO "Using latest SCF data with auto-adjustment to 2013$"
                    log INFO "Executing: ./reproduce/reproduce_data_moments.sh --use-latest-scf-data"
                    ./reproduce/reproduce_data_moments.sh --use-latest-scf-data 2>&1 | tee -a "$LOG_FILE"
                else
                    log INFO "Executing: ./reproduce/reproduce_data_moments.sh"
                    ./reproduce/reproduce_data_moments.sh 2>&1 | tee -a "$LOG_FILE"
                fi
                exit $?
                ;;
            IMPC)
                log PROGRESS "Generating IMPC figures from results"
                log INFO "Executing: ./reproduce/reproduce_figures_from_results.sh IMPC"
                ./reproduce/reproduce_figures_from_results.sh IMPC 2>&1 | tee -a "$LOG_FILE"
                exit $?
                ;;
            LP)
                log PROGRESS "Generating Lorenz Points figures from results"
                log INFO "Executing: ./reproduce/reproduce_figures_from_results.sh LP"
                ./reproduce/reproduce_figures_from_results.sh LP 2>&1 | tee -a "$LOG_FILE"
                exit $?
                ;;
            all)
                log PROGRESS "Generating all figures from results"
                log INFO "Executing: ./reproduce/reproduce_figures_from_results.sh all"
                ./reproduce/reproduce_figures_from_results.sh all 2>&1 | tee -a "$LOG_FILE"
                exit $?
                ;;
            *)
                log ERROR "Unknown data scope: $DATA_SCOPE"
                log ERROR "Valid scopes: scf, IMPC, LP, all"
                exit 1
                ;;
        esac
        ;;
    all)
        init_logging "all" "full"
        log INFO "Action: Complete reproduction (all computational results + documents)"
        reproduce_all_results
        exit $?
        ;;
    interactive)
        init_logging "interactive" "menu"
        log INFO "Action: Interactive menu (delegating to reproduce.py)"
        # Use Python script for interactive menu (SST)
        if [[ -f "./reproduce.py" ]]; then
            python3 ./reproduce.py
            exit $?
        else
            log ERROR "reproduce.py not found"
            log ERROR "The interactive menu requires reproduce.py"
            exit 1
        fi
        ;;
    "")
        # No arguments provided - show helpful examples (no logging for this)
        echo "========================================"
        echo "HAFiscal Reproduction Script"
        echo "========================================"
        echo ""
        echo "Run with arguments to reproduce different parts of the project."
        echo ""
        echo "📖 QUICK EXAMPLES:"
        echo ""
        echo "  # Environment testing:"
        echo "  ./reproduce.sh --envt               # Test both environments"
        echo "  ./reproduce.sh --envt texlive       # Test LaTeX only"
        echo "  ./reproduce.sh --envt comp_uv       # Test Python/UV only"
        echo ""
        echo "  # Empirical data:"
        echo "  ./reproduce.sh --data               # SCF 2004 moments (~1 min)"
        echo ""
        echo "  # Computational results:"
        echo "  ./reproduce.sh --comp min           # Quick test (~1 hour)"
        echo "  ./reproduce.sh --comp full          # Full results (4-5 days)"
        echo ""
        echo "  # LaTeX documents:"
        echo "  ./reproduce.sh --docs main          # Compile paper only"
        echo "  ./reproduce.sh --docs all           # Include figures, tables, subfiles"
        echo ""
        echo "  # Interactive mode:"
        echo "  ./reproduce.sh --interactive        # Show menu (uses reproduce.py)"
        echo "  ./reproduce.py                      # Python interactive menu (SST)"
        echo ""
        echo "  # Help:"
        echo "  ./reproduce.sh --help               # Full documentation"
        echo ""
        echo "========================================"
        echo ""
        echo "💡 TIP: Start with './reproduce.sh --docs main' to test your LaTeX setup"
        echo "        or './reproduce.sh --help' for complete documentation."
        echo ""
        echo "📝 NOTE: All commands are automatically logged to reproduce/logs/"
        echo "         Monitor progress: tail -f reproduce/logs/latest.log"
        echo ""
        exit 0
        ;;
    *)
        log ERROR "Unknown action: $ACTION"
        log ERROR "Run with --help for available options"
        exit 1
        ;;
esac

# Script execution continues and will eventually trigger the EXIT trap
# which calls print_summary, cleanup_temp_files, and benchmark_end

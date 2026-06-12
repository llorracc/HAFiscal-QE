#!/bin/bash
# Interactive Validation Runner for HAFiscal 0.14.1 vs 0.17.0
#
# This script provides an easy interface to run step-by-step validation
# with immediate feedback and the ability to pause on discrepancies.
#
# Usage:
#   ./run_interactive_validation.sh setup     # Set up environments
#   ./run_interactive_validation.sh step N    # Run step N
#   ./run_interactive_validation.sh all       # Run all steps (stops on first discrepancy)
#   ./run_interactive_validation.sh status    # Show status
#   ./run_interactive_validation.sh diagnose N # Diagnose step N

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Activate python environment if needed
export PYTHONPATH="$SCRIPT_DIR:$PYTHONPATH"

case "$1" in
    setup)
        echo "Setting up validation environments..."
        python3 interactive_validation.py setup
        ;;
    
    step)
        if [ -z "$2" ]; then
            echo "Usage: $0 step N"
            exit 1
        fi
        echo "Running step $2..."
        python3 interactive_validation.py step "$2"
        exit_code=$?
        
        if [ $exit_code -eq 0 ]; then
            echo ""
            echo "✅ Step $2 completed successfully - results match!"
            echo "   Run next step with: $0 step $((${2}+1))"
        elif [ $exit_code -eq 1 ]; then
            echo ""
            echo "⚠️  Step $2 completed but DIVERGENCE DETECTED!"
            echo "   Diagnose with: $0 diagnose $2"
            echo "   The AI should now investigate the cause."
        else
            echo ""
            echo "❌ Step $2 failed to run"
            echo "   Check error logs in: $SCRIPT_DIR/interactive_results/"
        fi
        exit $exit_code
        ;;
    
    all)
        echo "Running all validation steps (will stop on first discrepancy)..."
        echo ""
        
        for step in 1 2 3; do
            echo "=========================================="
            echo "Running step $step..."
            echo "=========================================="
            
            python3 interactive_validation.py step "$step"
            exit_code=$?
            
            if [ $exit_code -eq 1 ]; then
                echo ""
                echo "⚠️  VALIDATION PAUSED at step $step due to divergence"
                echo "   The AI should investigate before continuing."
                echo "   Diagnose with: $0 diagnose $step"
                exit 1
            elif [ $exit_code -ne 0 ]; then
                echo ""
                echo "❌ Step $step failed. Check logs."
                exit $exit_code
            fi
            
            echo ""
        done
        
        echo "=========================================="
        echo "✅ ALL STEPS COMPLETED SUCCESSFULLY!"
        echo "=========================================="
        ;;
    
    status)
        python3 interactive_validation.py status
        ;;
    
    diagnose)
        if [ -z "$2" ]; then
            echo "Usage: $0 diagnose N"
            exit 1
        fi
        python3 interactive_validation.py diagnose "$2"
        ;;
    
    *)
        echo "Interactive Validation for HAFiscal 0.14.1 vs 0.17.0"
        echo ""
        echo "Usage:"
        echo "  $0 setup       - Set up validation environments"
        echo "  $0 step N      - Run step N and compare results"
        echo "  $0 all         - Run all steps (stops on divergence)"
        echo "  $0 status      - Show current validation status"
        echo "  $0 diagnose N  - Show detailed diagnosis for step N"
        echo ""
        echo "Steps:"
        echo "  1 - Estimation_BetaNablaSplurge"
        echo "  2 - EstimAggFiscalMAIN"
        echo "  3 - Simulate_Base"
        ;;
esac

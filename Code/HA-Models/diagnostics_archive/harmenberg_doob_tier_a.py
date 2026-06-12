"""Cascade-gate Tier (a): HS only × 7 β each, Baseline parametrization."""
import sys
sys.argv = ['harmenberg_doob_tier_a']
from harmenberg_doob_tier1 import main
if __name__ == "__main__":
    main(parametrization='Baseline', edTypes=(1,), N_MC=200_000)

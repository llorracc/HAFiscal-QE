"""Tier (a) follow-up: HS Baseline 7-β with expanded grid (aMax=5000, A=500).

Tests whether the high-β (β≈0.99) Doob bias is a grid-coverage artifact.
If grid expansion shrinks the high-β bias → confirms grid-coverage cause.
"""
import sys
sys.argv = ['harmenberg_doob_tier_a_wide']
from harmenberg_doob_tier1 import main
if __name__ == "__main__":
    main(parametrization='Baseline', edTypes=(1,), N_MC=200_000,
         aCount=500, aMax=5000)

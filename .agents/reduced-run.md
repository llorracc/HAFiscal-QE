# Reduced Run Agent

Runs the reduced-run pipeline for faster development iteration.

## Purpose

`AggFiscalMAIN_reduced.py` provides a fast entry point with configurable acceleration flags. This agent runs it and reports results, useful for smoke tests and quick validation during development.

## Usage

```bash
cd Code/HA-Models/FromPandemicCode/

# Default reduced run (N=5000, tm_mCount=50)
python AggFiscalMAIN_reduced.py

# Fast reproduce (coarser TM grid: tm_mCount=40)
python AggFiscalMAIN_reduced.py --fast-reproduce

# Minimal mode (single college type, point β, 3Q recession, TM only)
python AggFiscalMAIN_reduced.py --glp1

# Dual-measure Monte Carlo
python AggFiscalMAIN_reduced.py --dual-mc

# Smoke test (N=100, crash/wiring check only)
python AggFiscalMAIN_reduced.py --smoke-test
```

## Key Files

- `AggFiscalMAIN_reduced.py` — Entry point with CLI flags
- `reproduce_min.py` — Meta-script orchestrating Steps 4–5 of the full pipeline
- `Simulate.py` — Simulation orchestrator (`sim_method` parameter)

## Flag Combinations

- `--smoke-test` is the fastest option (~seconds), good for checking imports and wiring
- `--glp1` is the fastest meaningful run (~minutes), good for single-type TM validation
- `--fast-reproduce` is a middle ground, suitable for quick multi-type checks
- Default (no flags) runs the standard reduced configuration

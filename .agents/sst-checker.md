# SST Checker Agent

Verifies single-source-of-truth (SST) income process consistency across the HAFiscal codebase.

## Purpose

The SST module (`income_process_sst.py`) centralizes all income process parameters. This agent checks that all consuming modules agree with the SST definitions, preventing drift between TM and MC income specifications.

## Usage

```bash
# SST unit tests
pytest Code/HA-Models/FromPandemicCode/test_sst_income_process.py -v

# SST integration tests (cross-module consistency)
pytest Code/HA-Models/FromPandemicCode/test_sst_integration.py -v
```

## Key Files

- `income_process_sst.py` — Authoritative source: `build_PermGroFac_micro()`, `effective_pLvl_growth()`, `build_unemployed_inc_shk_dstn()`, `tile_PermGroFac_composite()`
- `test_sst_income_process.py` — Unit tests for SST helpers
- `test_sst_integration.py` — Integration tests ensuring Parameters.py, AggFiscalModel.py, tm_methods.py, and Simulate.py all consume SST consistently

## What to Check

1. `PermGroFac` micro-state values match between TM grid construction and MC agent initialization
2. Unemployment shock distributions use the same 4-mode configuration (perm×transitory on/off)
3. Population-weighted effective growth rates are consistent across measures (P and Q)
4. `tile_PermGroFac_composite()` output matches the full Markov state-space layout

# TM Validator Agent

Validates transition matrix (TM) results against Monte Carlo (MC) baselines for the HAFiscal project.

## Purpose

Runs four-way comparisons (MC-P, MC-Q, TM-P, TM-Q) on **mean aggregate consumption per capita** (economy `AggCons` ÷ `AgentCount`) and checks that all methods agree within specified tolerances. Reports init stability metrics (early-period drift, variance of log mNrm/pLvl, employment shares).

## Usage

Run from `Code/HA-Models/FromPandemicCode/`:

```bash
# Four-way verification
python verify_four_methods_agreement.py

# Specific TM baseline test
pytest test_tm_baseline.py -v

# Full TM test suite
pytest test_tm_building_blocks.py test_tm_baseline.py test_tm_microsteps.py test_tm_recession_single.py -v
```

## Key Files

- `verify_four_methods_agreement.py` — Four-way gatekeeper (CLI + library)
- `test_verify_four_methods_agreement.py` — Pytest wrapper (marked `@pytest.mark.slow`)
- `tm_methods.py` — TM engine: `run_experiment_tm()`, `run_ad_tm()`, ergodic solvers
- `test_tm_baseline.py`, `test_tm_building_blocks.py` — Unit/integration tests

## Parameters

- Default: N=20k agents, T=100 periods, m_count=100 TM grid points
- Tolerance: methods should agree within ~2% (default `rtol`) on **per-capita** mean consumption; NPV objects elsewhere may still be economy totals
- `tm_neutral_measure=True` enables Harmenberg Q-measure for TM aggregation

## Notes

- `sys.argv` must be patched before importing Parameters.py in test contexts
- `economy.agents[i]` maps 1:1 to `baseline_tm_data[i]` — never merge education types

# Plan: quick MC Baseline (CRRA2) under splurge-in-budget vs QE-published

**Purpose.** Get a first-pass apples-to-apples comparison of the paper's main Multiplier table (CRRA2 Baseline, the target of `Tables/CRRA2/Multiplier.tex`) with splurge-in-budget active in MC, accepting 1-3% sampling error to trade speed for time.

This is the Baseline analog of the Reduced_Run MC run that just completed (`splurge-accounting-preliminary-MC-results.md`), but at the paper's actual 21-type calibration.

## Speed lever: reduce `AgentCountTotal`

Default is `Parameters.py:254:AgentCountTotal = 10000`, then distributed across 21 agent-types by education share and discount-factor probability. This gives roughly 50-1500 agents per type. The full Baseline MC run in the background is using this default and is projected at 3-5h.

For a quick run: set `AgentCountTotal = 2500` (1/4 of default). Each of the 21 types still gets ≥12 agents (types with tiny probability mass) up to ~400 agents (major types). Expected sampling error on aggregate NPV multipliers: ~2-4% per quantity. Expected wall clock: ~60-90 min (simulation phase is ~4× faster; solve phase unchanged).

## Procedure

1. **Prerequisite**: ensure current branch (`_matsya` or a fresh checkout) has the splurge-in-budget `get_poststates` override on `AggFiscalType`. Verified earlier; no additional code changes needed.

2. **Parametrization override**: override `AgentCountTotal` without modifying the committed file. Two clean options:
    - **(a)** Runtime override via environment variable (if the code supports it) — it does not at present; skip.
    - **(b)** A thin runner script that imports `AggFiscalMAIN_reduced.py` logic but sets a smaller `AgentCountTotal` before Simulate runs. Easiest: temporarily edit `Parameters.py` line 254 to `AgentCountTotal = 2500`, run, then revert via `git checkout`. Or create a wrapper script:

   ```python
   # plan/quick_mc_baseline_runner.py
   import os, sys
   os.chdir(os.path.dirname(os.path.abspath(__file__)) + '/../Code/HA-Models/FromPandemicCode')
   os.environ['MPLBACKEND'] = 'Agg'
   os.environ['MATPLOTLIB_BACKEND'] = 'agg'
   os.environ['HAFISCAL_NO_FORK'] = '1'
   os.environ['HAFISCAL_SIM_METHOD'] = 'MC'
   sys.argv = ['runner']
   sys.path.insert(0, '.')

   # Monkey-patch AgentCountTotal before Simulate imports
   import Parameters
   _orig = Parameters.return_parameters
   def _patched(**kw):
       res = list(_orig(**kw))
       # replace AgentCountTotal (index 6 per return_parameters signature)
       # ... inspect return tuple to find index
       return tuple(res)
   # Simpler: import EstimParameters and patch there
   import EstimParameters
   EstimParameters.AgentCountTotal = 2500
   import Parameters
   Parameters.AgentCountTotal = 2500

   from time import time
   from Simulate import Simulate
   from Output_Results import Output_Results

   Run_Dict = dict(
       Run_Baseline=True, Run_Recession=True,
       Run_Check_Recession=True, Run_UB_Ext_Recession=True, Run_TaxCut_Recession=True,
       Run_Check=True, Run_UB_Ext=True, Run_TaxCut=True,
       Run_AD=True, Run_1stRoundAD=False, Run_NonAD=True,
       sim_method='MC', tm_neutral_measure=True, tm_mCount=100,
   )
   fig_base = os.path.abspath('.') + '/Figures/Baseline_quickMC/'
   tab_base = os.path.abspath('.') + '/Tables/Baseline_quickMC/'
   os.makedirs(fig_base, exist_ok=True); os.makedirs(tab_base, exist_ok=True)

   t0 = time()
   Simulate(Run_Dict, fig_base, Parametrization='Baseline')
   Output_Results(fig_base, fig_base, tab_base, Parametrization='Baseline')
   print(f'Done in {(time()-t0)/60:.1f} min')
   ```

3. **Execute** (~60-90 min):

   ```bash
   cd /Volumes/Sync/GitHub/llorracc/HAFiscal-Latest
   /Volumes/Sync/GitHub/llorracc/HAFiscal-Latest/.venv-darwin-arm64/bin/python \
       plan/quick_mc_baseline_runner.py > /tmp/mc_optD_baseline_quick.log 2>&1 &
   ```

   The output goes to `Tables/Baseline_quickMC/Multiplier.tex` to keep separate from the full-resolution Baseline that's also running.

4. **Extract + compare**:

   ```bash
   cat Code/HA-Models/FromPandemicCode/Tables/Baseline_quickMC/Multiplier.tex
   echo "=== vs QE published ==="
   cat /Volumes/Sync/GitHub/llorracc/HAFiscal-QE/Code/HA-Models/FromPandemicCode/Tables/CRRA2/Multiplier.tex
   ```

5. **Report**: append a section to `BUGS_private/HAFiscal_splurge_budget_inconsistency/splurge-accounting-preliminary-MC-results.md` with the 6-row comparison table (Check/UI/TC × NoAD/AD) and the ranking comparison. Same format as the existing Reduced_Run section. Flag sampling-error caveat prominently.

## Acceptance criteria

- Run completes successfully (`Multiplier.tex` written in `Tables/Baseline_quickMC/`).
- Output format matches the existing `Tables/CRRA2/Multiplier.tex` format (10y-horizon NoAD + AD; share rows).
- Comparison table committed to the preliminary-results doc.
- **Sampling-error caveat stated explicitly**: "with AgentCountTotal=2500 (25% of default), individual multipliers are expected to have sampling error in the ±1-3% range; overall direction and ranking should be reliable but exact magnitudes will be noisy relative to a full 10000-agent run."

## Expected outcome (hypothesis)

Based on the Reduced_Run MC result (−2.8% Check AD, −4.2% UI AD, +2.3% TC AD; ranking preserved), the quick Baseline MC should show similar-magnitude shifts at CRRA2 — possibly slightly larger in magnitude because the paper's Baseline is the same CRRA=2 model but with per-education discount factors giving somewhat different MPC composition.

**Predicted order of magnitude** (with ±3% noise):
- Check AD: 1.228 → ~1.19 (Δ ≈ −3%)
- UI AD:    1.209 → ~1.16 (Δ ≈ −4%)
- TC AD:    0.975 → ~0.99 (Δ ≈ +1-2%)

Policy ranking UI > Check > TC expected to hold.

## Fall-back if quick run is still too slow

If `AgentCountTotal=2500` still takes too long (e.g., solve phase dominates with 21 types at HARK 0.17), options are:
- Reduce `T_sim` below 400 (currently sets total years; cutting to 200 halves simulation time).
- Skip recession+1stRoundAD experiments (already disabled).
- Skip non-recession policy experiments (`Run_NonAD=False`) — these don't feed the headline Multiplier table.
- As a last resort: solo-rec style (1 type, GLP-1) — but that's too reduced to be comparable to CRRA2 Baseline.

## Relation to the full Baseline MC in flight

The full Baseline MC at `AgentCountTotal=10000` is running in the background (launched 14:28, ETA 17:30-19:30). The quick run here is NOT a replacement — it's a way to get a rough answer faster while the authoritative full run completes. Compare: quick run should match full run within ±3% per multiplier; larger discrepancies indicate a bug.

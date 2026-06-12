"""Goodness-of-fit metrics for HAFiscal.

Per `plans/20260503-1030h_results-registry-and-impc-gof.md` §"Always-computed
GoF metrics" — every Step-5-eligible run records the following:

  1. iMPC-Fagereng (Figure 2 of Fagereng et al. 2021) — L2, L1, max-abs,
     plus per-horizon arrays.
  2. Wealth share by education (D, HS, C) vs SCF 2004.
  3. Wealth share by wealth quartile (Q1 richest → Q4 poorest) vs SCF 2004.
  4. MPC by wealth quartile — model only; with sanity check that
     mpc[poorest] > mpc[richest] (catches the WQ-MPC table-flip bug).
  5. Median LW/PI per cohort vs SCF 2004 — Step-2 targeted moment fit.

The `compute_all_gof(allresults_path)` function parses the AllResults_*.txt
file produced by `EstimAggFiscalMAIN.py` and returns a dict keyed by
metric_name, suitable for `_registry.record_metrics(run_id, metrics)`.

All data targets are sourced from the existing codebase (see references in
each section's docstring) — no values hardcoded here that aren't already
the canonical reference elsewhere.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import numpy as np


# ---------- Data targets (sourced from existing codebase) ----------

# From Estimation_BetaNablaSplurge.py:212 — Fagereng et al. Figure 2.
# Year 0 (lottery year) through year 4 average lottery-MPC.
DATA_IMPC_FAGERENG = np.array([0.5056845, 0.1759051, 0.1035106, 0.0444222, 0.0336616])

# HAFiscal-QE-Jan-2026 baseline (git tag v2026-01-09-18-17) — the version
# sent to the QE journal in early January. Used as the comparison benchmark
# for any GoF metric: a "current" L2 isn't interpretable in isolation; it
# must be compared to QE_JAN_IMPC's GoF to know whether the current cal is
# better, worse, or comparable. (Per user feedback 2026-05-03.)
QE_JAN_IMPC = np.array([0.53, 0.176, 0.071, 0.039, 0.026])
QE_JAN_WEALTH_SHARE_BY_ED = np.array([1.202, 17.484, 81.314])
QE_JAN_WEALTH_SHARE_BY_WQ = np.array([0.12, 1.01, 3.90, 94.96])
# QE-Jan MPC by WQ (poorest-to-richest, then population): [0.733, 0.598, 0.469, 0.321, 0.53]
QE_JAN_MPC_BY_WQ_WITH_POP = np.array([0.733, 0.598, 0.469, 0.321, 0.53])
# QE-Jan median LW/PI per cohort: [4.18, 31.89, 112.56]
QE_JAN_MEDIAN_LWPI = np.array([4.18, 31.89, 112.56])
# QE-Jan average LW/PI per cohort: [115.09, 131.18, 568.27]
QE_JAN_AVG_LWPI = np.array([115.09, 131.18, 568.27])
# QE-Jan total LW/total PI per cohort: [125.73, 137.98, 605.85]
QE_JAN_TOTAL_LWPI = np.array([125.73, 137.98, 605.85])
# QE-Jan population Lorenz: [0.0554, 0.5649, 2.1005, 6.9419] (from the 4th
# Lorenz Points line in QE-Jan AllResults — population-aggregate after the
# per-cohort Lorenz Points lines).
QE_JAN_POPULATION_LORENZ = np.array([0.0554, 0.5649, 2.1005, 6.9419])
# QE-Jan calibration source — use this when comparing Step-2 fit metrics.
# The targets DATA_* are the data; QE_JAN_* are how well the QE-Jan model
# matches them. A current model with worse fit than QE-Jan is regressing.

# From EstimParameters.py:33 — SCF 2004 wealth share by education.
# Order: [Dropout, Highschool, College] in PERCENT (sums to 100).
DATA_WEALTH_SHARE_BY_ED = np.array([0.8, 17.9, 81.2])

# From nonTargetedMoments_tabular_generate.py:101 — SCF 2004 wealth share
# by wealth quartile, in PERCENT.
# Order matches the table convention: [WQ4, WQ3, WQ2, WQ1] = [poorest...richest].
DATA_WEALTH_SHARE_BY_WQ = np.array([0.14, 1.60, 8.51, 89.76])

# From EstimParameters.py:28 — SCF 2004 weighted median liquid-wealth-to-
# permanent-income ratio (in PERCENT, multiplied by 4 for quarterly).
DATA_MEDIAN_LWPI = np.array([4.64, 30.2, 112.8])

# From EstimParameters.py:24 — SCF 2004 average LW/PI per cohort (PERCENT,
# *4 quarterly→annual). Format: [D, HS, C].
DATA_AVG_LWPI = np.array([15.7, 47.7, 111]) * 4   # → [62.8, 190.8, 444]

# From EstimParameters.py:26 — SCF 2004 total LW / total PI per cohort (PERCENT,
# *4 quarterly→annual). Format: [D, HS, C].
DATA_TOTAL_LWPI = np.array([28.1, 59.6, 162]) * 4  # → [112.4, 238.4, 648]

# From EstimParameters.py:22 — SCF 2004 population-aggregate Lorenz curve
# 20/40/60/80 percentile points (PERCENT). Format: [p20, p40, p60, p80].
DATA_POPULATION_LORENZ = np.array([0.03, 0.35, 1.84, 7.42])

# Suggested L2 thresholds for iMPC-Fagereng GoF (from the registry plan):
#   l2 < 0.05  → excellent
#   l2 < 0.10  → acceptable
#   l2 ≥ 0.10  → flag for investigation


# ---------- AllResults parser ----------

class AllResultsParser:
    """Parses an AllResults_*.txt file produced by EstimAggFiscalMAIN.py.

    The file is line-oriented; we look for specific labelled lines.
    Each parser method returns None if the line is missing.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)
        if not self.path.exists():
            raise FileNotFoundError(f"AllResults file not found: {self.path}")
        self.text = self.path.read_text()

    def _find_array(self, label: str, n_expected: int | None = None) -> np.ndarray | None:
        """Find a line `<label> = [a, b, c, ...]` and return as numpy array."""
        m = re.search(rf"{re.escape(label)}\s*=\s*\[([\d.,\s\-eE+]+)\]", self.text)
        if m is None:
            return None
        nums = [float(x.strip()) for x in m.group(1).split(",")]
        arr = np.array(nums)
        if n_expected is not None and arr.size != n_expected:
            raise ValueError(f"{label}: expected {n_expected} values, got {arr.size}")
        return arr

    def _find_per_cohort_kv(self, prefix: str) -> np.ndarray | None:
        """Find a line `<prefix>: D = X H = Y C = Z` and return [X, Y, Z]."""
        m = re.search(
            rf"{re.escape(prefix)}\s*:\s*D\s*=\s*([\d.\-eE+]+)\s+H\s*=\s*([\d.\-eE+]+)\s+C\s*=\s*([\d.\-eE+]+)",
            self.text,
        )
        if m is None:
            return None
        return np.array([float(m.group(i)) for i in (1, 2, 3)])

    def impc_over_time(self) -> np.ndarray | None:
        """5-element model iMPC time path: [year0, year1, ..., year4]."""
        return self._find_array("IMPCs over time", n_expected=5)

    def wealth_share_by_ed(self) -> np.ndarray | None:
        """3-element wealth share by education in PERCENT: [D, HS, C]."""
        return self._find_array("Wealth shares by Ed.", n_expected=3)

    def wealth_share_by_wq(self) -> np.ndarray | None:
        """4-element wealth share by wealth quartile in PERCENT: [WQ4 (poor), ..., WQ1 (rich)].

        Source array in AllResults is documented as poorest-to-richest
        (see EstimAggFiscalMAIN.py:626 + WealthQsAll construction).
        """
        return self._find_array("Wealth Shares by Wealth Q", n_expected=4)

    def mpc_lottery_by_wq(self) -> np.ndarray | None:
        """5-element MPC by wealth quartile in [0,1]: [WQ4 (poor), ..., WQ1 (rich), Population].

        Reads the `Average lottery-win-year MPCs by Wealth (incl. splurge)` line
        (NOT the 'simple' variant).
        """
        m = re.search(
            r"Average lottery-win-year MPCs by Wealth \(incl\. splurge\)\s*=\s*\[([\d.,\s\-eE+]+)\]",
            self.text,
        )
        if m is None:
            return None
        nums = [float(x.strip()) for x in m.group(1).split(",")]
        return np.array(nums)

    def median_lwpi(self) -> np.ndarray | None:
        """3-element median LW/PI per cohort in PERCENT: [D, HS, C]."""
        return self._find_per_cohort_kv("Median LW/PI-ratios")

    def avg_lwpi_by_ed(self) -> np.ndarray | None:
        """3-element average LW/PI per cohort in PERCENT: [D, HS, C].

        Reads `Average LW/PI-ratios: D = X H = Y C = Z` line.
        """
        return self._find_per_cohort_kv("Average LW/PI-ratios")

    def total_lwpi_by_ed(self) -> np.ndarray | None:
        """3-element total LW / total PI per cohort in PERCENT: [D, HS, C].

        Reads `Total LW/Total PI: D = X H = Y C = Z` line.
        """
        return self._find_per_cohort_kv("Total LW/Total PI")

    def population_lorenz(self) -> np.ndarray | None:
        """4-element population-aggregate Lorenz curve [p20, p40, p60, p80] in PERCENT.

        AllResults emits multiple `Lorenz Points = [...]` lines: 3 per-cohort
        followed by a final population-aggregate one (after a "Population
        calculations:" header). Returns the 4th occurrence.
        """
        matches = re.findall(r"Lorenz Points\s*=\s*\[([\d.,\s\-eE+]+)\]", self.text)
        if len(matches) < 4:
            return None
        nums = [float(x.strip()) for x in matches[3].split(",")]
        return np.array(nums)


# ---------- GoF computations ----------

def _per_horizon_block(model: np.ndarray, data: np.ndarray) -> dict[str, Any]:
    """Build the per-horizon delta + scalar summary block for any vector GoF."""
    delta = model - data
    nonzero = data != 0
    pct = np.full_like(delta, np.nan)
    pct[nonzero] = 100 * delta[nonzero] / data[nonzero]
    return {
        "data": data.tolist(),
        "model": model.tolist(),
        "delta": delta.tolist(),
        "pct_error": pct.tolist(),
        "l2": float(np.sqrt(np.sum(delta ** 2))),
        "l1": float(np.sum(np.abs(delta))),
        "max_abs": float(np.max(np.abs(delta))),
    }


def gof_impc_fagereng(model_impc: np.ndarray) -> dict[str, Any]:
    """iMPC-Fagereng goodness-of-fit. Returns dict with scalars + arrays."""
    block = _per_horizon_block(model_impc, DATA_IMPC_FAGERENG)
    block["data_horizons_year"] = [0, 1, 2, 3, 4]
    return block


def gof_wealth_share_by_ed(model_pct: np.ndarray) -> dict[str, Any]:
    """Wealth share by education (D, HS, C) — model vs SCF 2004."""
    return _per_horizon_block(model_pct, DATA_WEALTH_SHARE_BY_ED)


def gof_wealth_share_by_wq(model_pct: np.ndarray) -> dict[str, Any]:
    """Wealth share by wealth quartile (poorest → richest) — model vs SCF 2004."""
    return _per_horizon_block(model_pct, DATA_WEALTH_SHARE_BY_WQ)


def gof_mpc_by_wq(model_mpc_with_pop: np.ndarray) -> dict[str, Any]:
    """MPC by wealth quartile — model only; sanity-check ordering.

    `model_mpc_with_pop` is 5 elements: [poorest, ..., richest, population].
    Returns the per-quartile values + a `pattern_correct` bool.
    """
    if model_mpc_with_pop.size != 5:
        raise ValueError(f"mpc_by_wq expects 5 elements (4 WQ + pop); got {model_mpc_with_pop.size}")
    by_wq = model_mpc_with_pop[:4]
    pop = float(model_mpc_with_pop[4])
    pattern_correct = bool(by_wq[0] > by_wq[3])  # poorest > richest
    return {
        "by_wq_poorest_to_richest": by_wq.tolist(),
        "population": pop,
        "pattern_correct": pattern_correct,
        "ratio_poor_to_rich": float(by_wq[0] / by_wq[3]) if by_wq[3] > 0 else None,
    }


def gof_median_lwpi(model_pct: np.ndarray) -> dict[str, Any]:
    """Median LW/PI per cohort — model vs SCF 2004 (targeted moment fit quality)."""
    return _per_horizon_block(model_pct, DATA_MEDIAN_LWPI)


def gof_avg_lwpi_by_ed(model_pct: np.ndarray) -> dict[str, Any]:
    """Average LW/PI per cohort — model vs SCF 2004 (non-targeted)."""
    return _per_horizon_block(model_pct, DATA_AVG_LWPI)


def gof_total_lwpi_by_ed(model_pct: np.ndarray) -> dict[str, Any]:
    """Total LW / Total PI per cohort — model vs SCF 2004 (non-targeted)."""
    return _per_horizon_block(model_pct, DATA_TOTAL_LWPI)


def gof_population_lorenz(model_pct: np.ndarray) -> dict[str, Any]:
    """Population-aggregate Lorenz curve — model vs SCF 2004 (non-targeted)."""
    return _per_horizon_block(model_pct, DATA_POPULATION_LORENZ)


# ---------- Top-level: parse + compute all ----------

def compute_all_gof(allresults_path: str | Path) -> dict[str, Any]:
    """Parse AllResults file and compute every always-recorded GoF metric.

    Returns a dict suitable for `_registry.record_metrics(run_id, metrics)`.

    Scalar metrics use direct `metric_name → float` mapping; complex
    blocks (per-horizon arrays etc.) use a json-suffixed name like
    `impc_fagereng_full`. The registry's record_metrics auto-detects
    type and stores accordingly.
    """
    parser = AllResultsParser(allresults_path)
    out: dict[str, Any] = {}

    # iMPC-Fagereng
    impc = parser.impc_over_time()
    if impc is not None:
        block = gof_impc_fagereng(impc)
        out["impc_fagereng_l2"] = block["l2"]
        out["impc_fagereng_l1"] = block["l1"]
        out["impc_fagereng_max_abs"] = block["max_abs"]
        out["impc_fagereng_full"] = block

    # Wealth share by Ed
    wse = parser.wealth_share_by_ed()
    if wse is not None:
        block = gof_wealth_share_by_ed(wse)
        for i, label in enumerate(("d", "h", "c")):
            out[f"wealth_share_by_ed_pct_error_{label}"] = block["delta"][i]
        out["wealth_share_by_ed_l2"] = block["l2"]
        out["wealth_share_by_ed_full"] = block

    # Wealth share by WQ
    wsw = parser.wealth_share_by_wq()
    if wsw is not None:
        block = gof_wealth_share_by_wq(wsw)
        # WQ4 = poorest in the table convention; q1=poorest in the metric naming
        # (so q4=richest matches the table's WQ1).
        for i, q_idx in enumerate((1, 2, 3, 4)):
            out[f"wealth_share_by_wq_pct_error_q{q_idx}"] = block["delta"][i]
        out["wealth_share_by_wq_l2"] = block["l2"]
        out["wealth_share_by_wq_full"] = block

    # MPC by WQ
    mpc = parser.mpc_lottery_by_wq()
    if mpc is not None:
        block = gof_mpc_by_wq(mpc)
        for i, q_idx in enumerate((1, 2, 3, 4)):
            out[f"mpc_by_wq_q{q_idx}"] = block["by_wq_poorest_to_richest"][i]
        out["mpc_by_wq_population"] = block["population"]
        out["mpc_by_wq_pattern_correct"] = 1.0 if block["pattern_correct"] else 0.0
        out["mpc_by_wq_full"] = block

    # Median LW/PI
    mlwpi = parser.median_lwpi()
    if mlwpi is not None:
        block = gof_median_lwpi(mlwpi)
        for i, label in enumerate(("d", "h", "c")):
            out[f"median_lwpi_pct_error_{label}"] = block["pct_error"][i]
        out["median_lwpi_l2"] = block["l2"]
        out["median_lwpi_full"] = block

    # Average LW/PI by Ed
    avgl = parser.avg_lwpi_by_ed()
    if avgl is not None:
        block = gof_avg_lwpi_by_ed(avgl)
        for i, label in enumerate(("d", "h", "c")):
            out[f"avg_lwpi_by_ed_pct_error_{label}"] = block["pct_error"][i]
        out["avg_lwpi_by_ed_l2"] = block["l2"]
        out["avg_lwpi_by_ed_full"] = block

    # Total LW / Total PI by Ed
    tlwpi = parser.total_lwpi_by_ed()
    if tlwpi is not None:
        block = gof_total_lwpi_by_ed(tlwpi)
        for i, label in enumerate(("d", "h", "c")):
            out[f"total_lwpi_by_ed_pct_error_{label}"] = block["pct_error"][i]
        out["total_lwpi_by_ed_l2"] = block["l2"]
        out["total_lwpi_by_ed_full"] = block

    # Population Lorenz curve
    poplor = parser.population_lorenz()
    if poplor is not None:
        block = gof_population_lorenz(poplor)
        for i, label in enumerate(("p20", "p40", "p60", "p80")):
            out[f"population_lorenz_pct_error_{label}"] = block["pct_error"][i]
        out["population_lorenz_l2"] = block["l2"]
        out["population_lorenz_full"] = block

    return out


# ---------- Pretty-print summary ----------

def _qe_block_for(name: str) -> dict[str, Any]:
    """Return the QE-Jan GoF block for the named metric (so format_summary
    can show side-by-side comparison without having to recompute)."""
    if name == "impc_fagereng":
        return _per_horizon_block(QE_JAN_IMPC, DATA_IMPC_FAGERENG)
    if name == "wealth_share_by_ed":
        return _per_horizon_block(QE_JAN_WEALTH_SHARE_BY_ED, DATA_WEALTH_SHARE_BY_ED)
    if name == "wealth_share_by_wq":
        return _per_horizon_block(QE_JAN_WEALTH_SHARE_BY_WQ, DATA_WEALTH_SHARE_BY_WQ)
    if name == "median_lwpi":
        return _per_horizon_block(QE_JAN_MEDIAN_LWPI, DATA_MEDIAN_LWPI)
    if name == "avg_lwpi_by_ed":
        return _per_horizon_block(QE_JAN_AVG_LWPI, DATA_AVG_LWPI)
    if name == "total_lwpi_by_ed":
        return _per_horizon_block(QE_JAN_TOTAL_LWPI, DATA_TOTAL_LWPI)
    if name == "population_lorenz":
        return _per_horizon_block(QE_JAN_POPULATION_LORENZ, DATA_POPULATION_LORENZ)
    return {}


def format_summary(metrics: dict[str, Any]) -> str:
    """Multi-line summary per metric; ALWAYS includes QE-Jan baseline comparison
    so a current L2 is interpretable (better or worse than QE).

    Per user feedback 2026-05-03: per-year iMPC values must be visible;
    GoF metrics in isolation are useless without the QE benchmark.
    """
    lines = []

    # ---- iMPC-Fagereng ----
    if "impc_fagereng_full" in metrics:
        m = metrics["impc_fagereng_full"]
        qe = _qe_block_for("impc_fagereng")
        lines.append("  iMPC-Fagereng (year-by-year, model vs data):")
        lines.append(f"    {'horizon':>10} {'data':>9} {'current':>9} {'Δ':>9} {'%err':>9}    {'QE-Jan':>9} {'QE-Δ':>9}")
        for i, year in enumerate(m["data_horizons_year"]):
            lines.append(
                f"    year {year:>4}: {m['data'][i]:>9.4f} {m['model'][i]:>9.4f} "
                f"{m['delta'][i]:>+9.4f} {m['pct_error'][i]:>+8.1f}%    "
                f"{qe['model'][i]:>9.4f} {qe['delta'][i]:>+9.4f}"
            )
        cur_l2, cur_l1 = m["l2"], m["l1"]
        qe_l2, qe_l1 = qe["l2"], qe["l1"]
        cur_flag = "✓ excellent" if cur_l2 < 0.05 else ("ok" if cur_l2 < 0.10 else "⚠ flag")
        cmp = "BETTER" if cur_l2 < qe_l2 else ("WORSE" if cur_l2 > qe_l2 * 1.10 else "comparable")
        lines.append(f"    summary: current L2={cur_l2:.4f}  L1={cur_l1:.4f}  [{cur_flag}]")
        lines.append(f"             QE-Jan  L2={qe_l2:.4f}  L1={qe_l1:.4f}  → current is {cmp} than QE-Jan")

    # ---- Wealth share by Ed ----
    if "wealth_share_by_ed_full" in metrics:
        m = metrics["wealth_share_by_ed_full"]
        qe = _qe_block_for("wealth_share_by_ed")
        lines.append("\n  Wealth share by Ed (model vs data):")
        lines.append(f"    {'cohort':>6} {'data':>9} {'current':>9} {'Δ':>9}    {'QE-Jan':>9} {'QE-Δ':>9}")
        for i, label in enumerate(("D", "HS", "C")):
            lines.append(
                f"    {label:>6}  {m['data'][i]:>9.2f} {m['model'][i]:>9.2f} "
                f"{m['delta'][i]:>+9.2f}    {qe['model'][i]:>9.2f} {qe['delta'][i]:>+9.2f}"
            )
        cmp = "BETTER" if m["l2"] < qe["l2"] else ("WORSE" if m["l2"] > qe["l2"] * 1.10 else "comparable")
        lines.append(f"    summary: current L2={m['l2']:.2f}pp  vs QE-Jan L2={qe['l2']:.2f}pp  → current is {cmp}")

    # ---- Wealth share by WQ ----
    if "wealth_share_by_wq_full" in metrics:
        m = metrics["wealth_share_by_wq_full"]
        qe = _qe_block_for("wealth_share_by_wq")
        lines.append("\n  Wealth share by WQ (poorest → richest; model vs data):")
        lines.append(f"    {'quartile':>10} {'data':>9} {'current':>9} {'Δ':>9}    {'QE-Jan':>9} {'QE-Δ':>9}")
        for i, label in enumerate(("q1 poor", "q2", "q3", "q4 rich")):
            lines.append(
                f"    {label:>10}  {m['data'][i]:>9.2f} {m['model'][i]:>9.2f} "
                f"{m['delta'][i]:>+9.2f}    {qe['model'][i]:>9.2f} {qe['delta'][i]:>+9.2f}"
            )
        cmp = "BETTER" if m["l2"] < qe["l2"] else ("WORSE" if m["l2"] > qe["l2"] * 1.10 else "comparable")
        lines.append(f"    summary: current L2={m['l2']:.2f}pp  vs QE-Jan L2={qe['l2']:.2f}pp  → current is {cmp}")

    # ---- MPC by WQ ----
    if "mpc_by_wq_full" in metrics:
        m = metrics["mpc_by_wq_full"]
        ok = m.get("pattern_correct", False)
        ratio = m.get("ratio_poor_to_rich")
        lines.append("\n  MPC by WQ (lottery-win-year; model only):")
        lines.append(f"    {'quartile':>10} {'current':>9}    {'QE-Jan':>9}")
        for i, label in enumerate(("q1 poor", "q2", "q3", "q4 rich")):
            lines.append(
                f"    {label:>10}  {m['by_wq_poorest_to_richest'][i]:>9.3f}    {QE_JAN_MPC_BY_WQ_WITH_POP[i]:>9.3f}"
            )
        lines.append(f"    Population:  {m['population']:>9.3f}    {QE_JAN_MPC_BY_WQ_WITH_POP[4]:>9.3f}")
        lines.append(f"    sanity: pattern_correct (poor MPC > rich MPC)={ok}  ratio current={ratio:.2f}  QE={QE_JAN_MPC_BY_WQ_WITH_POP[0]/QE_JAN_MPC_BY_WQ_WITH_POP[3]:.2f}")

    # ---- Median LW/PI ----
    if "median_lwpi_full" in metrics:
        m = metrics["median_lwpi_full"]
        qe = _qe_block_for("median_lwpi")
        lines.append("\n  Median LW/PI per cohort (Step-2 targeted; model vs data):")
        lines.append(f"    {'cohort':>6} {'data':>9} {'current':>9} {'%err':>9}    {'QE-Jan':>9} {'QE-%err':>9}")
        for i, label in enumerate(("D", "HS", "C")):
            lines.append(
                f"    {label:>6}  {m['data'][i]:>9.2f} {m['model'][i]:>9.2f} "
                f"{m['pct_error'][i]:>+8.1f}%    {qe['model'][i]:>9.2f} {qe['pct_error'][i]:>+8.1f}%"
            )

    # ---- Avg LW/PI by Ed (NON-targeted) ----
    if "avg_lwpi_by_ed_full" in metrics:
        m = metrics["avg_lwpi_by_ed_full"]
        qe = _qe_block_for("avg_lwpi_by_ed")
        lines.append("\n  Avg LW/PI per cohort (non-targeted; model vs data, in PERCENT × 4):")
        lines.append(f"    {'cohort':>6} {'data':>9} {'current':>9} {'%err':>9}    {'QE-Jan':>9} {'QE-%err':>9}")
        for i, label in enumerate(("D", "HS", "C")):
            lines.append(
                f"    {label:>6}  {m['data'][i]:>9.2f} {m['model'][i]:>9.2f} "
                f"{m['pct_error'][i]:>+8.1f}%    {qe['model'][i]:>9.2f} {qe['pct_error'][i]:>+8.1f}%"
            )
        cmp = "BETTER" if m["l2"] < qe["l2"] else ("WORSE" if m["l2"] > qe["l2"] * 1.10 else "comparable")
        lines.append(f"    summary: current L2={m['l2']:.2f}  vs QE-Jan L2={qe['l2']:.2f}  → current is {cmp}")

    # ---- Total LW / Total PI by Ed (NON-targeted) ----
    if "total_lwpi_by_ed_full" in metrics:
        m = metrics["total_lwpi_by_ed_full"]
        qe = _qe_block_for("total_lwpi_by_ed")
        lines.append("\n  Total LW / Total PI per cohort (non-targeted; model vs data, in PERCENT × 4):")
        lines.append(f"    {'cohort':>6} {'data':>9} {'current':>9} {'%err':>9}    {'QE-Jan':>9} {'QE-%err':>9}")
        for i, label in enumerate(("D", "HS", "C")):
            lines.append(
                f"    {label:>6}  {m['data'][i]:>9.2f} {m['model'][i]:>9.2f} "
                f"{m['pct_error'][i]:>+8.1f}%    {qe['model'][i]:>9.2f} {qe['pct_error'][i]:>+8.1f}%"
            )
        cmp = "BETTER" if m["l2"] < qe["l2"] else ("WORSE" if m["l2"] > qe["l2"] * 1.10 else "comparable")
        lines.append(f"    summary: current L2={m['l2']:.2f}  vs QE-Jan L2={qe['l2']:.2f}  → current is {cmp}")

    # ---- Population Lorenz (NON-targeted) ----
    if "population_lorenz_full" in metrics:
        m = metrics["population_lorenz_full"]
        qe = _qe_block_for("population_lorenz")
        lines.append("\n  Population Lorenz curve (non-targeted; model vs data, in PERCENT):")
        lines.append(f"    {'pct':>6} {'data':>9} {'current':>9} {'Δ':>9}    {'QE-Jan':>9} {'QE-Δ':>9}")
        for i, label in enumerate(("p20", "p40", "p60", "p80")):
            lines.append(
                f"    {label:>6}  {m['data'][i]:>9.4f} {m['model'][i]:>9.4f} "
                f"{m['delta'][i]:>+9.4f}    {qe['model'][i]:>9.4f} {qe['delta'][i]:>+9.4f}"
            )
        cmp = "BETTER" if m["l2"] < qe["l2"] else ("WORSE" if m["l2"] > qe["l2"] * 1.10 else "comparable")
        lines.append(f"    summary: current L2={m['l2']:.4f}pp  vs QE-Jan L2={qe['l2']:.4f}pp  → current is {cmp}")

    return "\n".join(lines) if lines else "  (no GoF metrics computed — AllResults parse failures?)"


# ---------- CLI for ad-hoc use ----------

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python _gof.py <path-to-AllResults.txt>")
        sys.exit(1)
    metrics = compute_all_gof(sys.argv[1])
    print(format_summary(metrics))
    print()
    print("Detailed metrics dict (truncated):")
    for k, v in metrics.items():
        if isinstance(v, (int, float)):
            print(f"  {k}: {v}")

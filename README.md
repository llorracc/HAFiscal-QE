# HAFiscal Replication Package

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.17861977.svg)](https://doi.org/10.5281/zenodo.17861977)
[![Docker Image](https://img.shields.io/badge/Docker-llorracc%2Fhafiscal--public-2496ED?logo=docker&logoColor=white)](https://hub.docker.com/r/llorracc/hafiscal-public)
[![Powered by Econ-ARK](./@resources/econ-ark/PoweredByEconARK.png)](https://econ-ark.org)
[![License](https://img.shields.io/badge/License-See%20LICENSE%20file-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.9-blue.svg)](README/INSTALLATION.md)
[![Launch Dashboard](https://img.shields.io/badge/Launch-Interactive%20Dashboard-orange?logo=jupyter)](https://mybinder.org/v2/gh/llorracc/HAFiscal-Public/HEAD?urlpath=voila%2Frender%2Fdashboard%2Fapp.ipynb)

**Paper**: *Welfare and Spending Effects of Consumption Stimulus Policies*  
**Authors**: Christopher D. Carroll, Edmund Crawley, William Du, Ivan Frankovic, Hakon Tretvoll  
**Keywords**: heterogeneous agents, fiscal policy, stimulus checks, iMPCs, HANK, consumption, welfare, QE replication

---

## Instant Results (No Installation Required)

**Want to explore fiscal policy effects right now?**

[![Launch Interactive Dashboard](https://img.shields.io/badge/Launch-Interactive%20Dashboard-orange?style=for-the-badge&logo=jupyter)](https://mybinder.org/v2/gh/llorracc/HAFiscal-Public/HEAD?urlpath=voila%2Frender%2Fdashboard%2Fapp.ipynb)

The **interactive dashboard** lets you:

- Compare stimulus checks, UI extensions, and tax cuts
- Adjust model parameters in real-time
- Visualize fiscal multipliers under different monetary policies
- See results in seconds (no 100+ hour computation needed)

**No installation required** — runs entirely in your browser via MyBinder.

For local installation, see [dashboard/DASHBOARD_README.md](dashboard/DASHBOARD_README.md) or [README/DASHBOARD.md](README/DASHBOARD.md).

---

## Quick Start

**New to HAFiscal?** Start with the [Getting Started Guide](README/GETTING-STARTED.md) for navigation and workflow guidance.

For detailed documentation, see the [README/](README/) directory.

The README/ directory contains:

- **[GETTING-STARTED.md](README/GETTING-STARTED.md)** — Navigation guide and workflow overview (start here if new)
- **Detailed README** — Complete replication instructions and documentation
- [INSTALLATION.md](README/INSTALLATION.md) — Installation and setup instructions
- [CONTRIBUTING.md](README/CONTRIBUTING.md) — Contribution guidelines
- [QUICK-REFERENCE.md](README/QUICK-REFERENCE.md) — Quick reference guide
- [TROUBLESHOOTING.md](README/TROUBLESHOOTING.md) — Common issues and solutions

---

## Research Questions and Contributions

### Primary Research Questions

1. **What are the welfare and spending effects of different consumption stimulus policies** (stimulus checks, tax cuts, unemployment insurance extensions) across the income and wealth distribution?

2. **How do heterogeneous-agent mechanisms** (liquidity constraints, sticky expectations, splurge behavior) affect the distributional and aggregate impacts of fiscal stimulus?

3. **What is the optimal design of stimulus policies** when accounting for household heterogeneity in marginal propensities to consume (MPCs)?

### Key Contributions

1. **Comprehensive HANK model calibration**: Extends heterogeneous-agent New Keynesian (HANK) models to match both microeconomic evidence on intertemporal MPCs (iMPCs) and macroeconomic evidence on aggregate consumption dynamics, using Survey of Consumer Finances (SCF) 2004 data.

2. **Novel behavioral mechanisms**: Implements and quantifies the role of:
   - **Sticky expectations** (following Carroll et al. 2020, `cAndCwithStickyE` in bibliography)
   - **Splurge behavior** (lumpy consumption responses to windfalls)
   - **Liquidity constraints** and heterogeneous wealth distributions

3. **Distributional welfare analysis**: Provides systematic welfare comparisons across alternative stimulus designs, highlighting how policy effectiveness varies dramatically across households with different liquid wealth positions.

4. **Methodological extension**: Builds on the computational framework of Auclert et al. (2021, `Auclert2021`) and extends the two-asset HANK literature (Kaplan & Violante 2014, `kaplan2014model`; Fagereng et al. 2021, `fagereng-mpc-2021`) to incorporate additional behavioral frictions.

---

## Literature Connections

### Core Methodological Foundations

**HANK Models and Computational Methods**:

- **Auclert et al. (2021)** [`Auclert2021`]: Sequence-space Jacobian methods for solving heterogeneous-agent models (computational framework extended here)
- **Kaplan & Violante (2014)** [`kaplan2014model`]: Two-asset model with liquid/illiquid assets and high MPCs for hand-to-mouth households (calibration strategy extended)
- **Carroll et al. (2017)** [`cstwMPC`]: Distribution of wealth and MPCs in heterogeneous-agent models (empirical targets extended)

**Sticky Expectations and Consumption Dynamics**:

- **Carroll et al. (2020)** [`cAndCwithStickyE`]: Sticky expectations model explaining aggregate consumption persistence (mechanism implemented here)
- **Lian (2023)** [`Lian2023-ca`]: Future consumption mistakes and high MPCs (related behavioral mechanism)

### Empirical Evidence on MPCs and Consumption Responses

**Microeconomic MPC Estimates**:

- **Fagereng et al. (2021)** [`fagereng-mpc-2021`]: Norwegian lottery data showing MPC heterogeneity by liquid assets (empirical target)
- **Kotsogiannis & Sakellaris (2024)** [`kotsogiannisMPCs`]: Tax lottery estimates of iMPCs (complementary evidence)
- **Boehm et al. (2025)** [`boehm2025fivefacts`]: Randomized experiment on MPCs (recent empirical evidence)
- **Parker et al. (2013)** [`parker2013consumer`]: Economic stimulus payments of 2008 (empirical benchmark)

**Consumption During Unemployment**:

- **Ganong & Noel (2019)** [`ganongConsumer2019`]: Consumer spending during unemployment (UI extension analysis relates)
- **Graves (2024)** [`gravesUnemployment`]: Unemployment risk and consumption dynamics (related mechanism)

### Fiscal Multipliers and Policy Analysis

**Fiscal Multipliers in HANK Models**:

- **Broer et al. (2023)** [`broer2023fiscalmultipliers`]: Fiscal multipliers from heterogeneous-agent perspective (complementary analysis)
- **Broer et al. (2025)** [`broer2025stimulus`]: Stimulus effects of common fiscal policies (recent related work)
- **Hagedorn et al. (2019)** [`hagedorn2019fiscal`]: Fiscal multiplier in HANK models (methodological connection)

**Automatic Stabilizers and Welfare**:

- **McKay & Reis (2016, 2021)** [`mckay2016role`, `mckay2021optimal`]: Role of automatic stabilizers and optimal design (welfare analysis relates)
- **Phan (2024)** [`phan2024welfare`]: Welfare consequences of countercyclical fiscal transfers (related welfare analysis)

### Behavioral Mechanisms

**Near-Rationality and Bounded Rationality**:

- **Andre et al. (2025)** [`ansQuickfix`]: Near-rationality in consumption and savings (related behavioral mechanism)
- **Akerlof & Yellen (1985)** [`akerlof1985near`]: Near-rational model of business cycle (foundational work)
- **Ilut & Valchev (2022)** [`ilutEconomic`]: Economic agents as imperfect problem solvers (related framework)

**Present Bias and Mental Accounting**:

- **Laibson et al. (2024)** [`lmmPresentBias`]: Present bias amplifies balance-sheet channels (related mechanism)
- **Graham & McDowall (2024)** [`graham2024mental`]: Mental accounts and consumption sensitivity (related behavioral feature)

### Related HANK Literature

**Unemployment and Business Cycles**:

- **Ravn & Sterk (2017, 2021)** [`Ravn2017`, `Ravn2021`]: Job uncertainty, HANK & SAM models (related HANK extensions)
- **Christiano et al. (2016)** [`Christiano2016`]: Unemployment and business cycles (search-and-matching framework)
- **Graves (2024)** [`gravesUnemployment`]: Unemployment risk affects business cycle dynamics (related mechanism)

**Distributional Effects of Monetary Policy**:

- **Gornemann et al. (2021)** [`Gornemann2021`]: Distributional consequences of systematic monetary policy (related distributional analysis)

### Data and Calibration

**SCF Data and Wealth Distribution**:

- **SCF 2004** [`SCF2004`]: Survey of Consumer Finances 2004 (primary data source)
- **Kaplan et al. (2014)** [`kaplan2014model`]: Liquid wealth construction methodology (followed here)

**Income Process Calibration**:

- **Crawley et al. (2024)** [`crawley2024parsimonious`]: Parsimonious model of idiosyncratic income (income process specification)

---

## What This Repository Provides (AI- and search-friendly summary)

- **Replication code and data** for the HAFiscal paper, built on Econ-ARK tools, with a Heterogeneous Agent New Keynesian (HANK) model calibrated to U.S. micro data.

- **Consumption stimulus policy analysis**: effects of stimulus checks, tax cuts, and UI extensions on spending, iMPCs, and welfare across the income and wealth distribution.

- **Model artifacts**: code for sticky expectations, splurge behavior, and robustness appendices (HTML/PDF links in appendices).

- **Data**: SCF-based liquid wealth and income moments (paper uses 2013-dollar SCF vintage; scripts document 2022→2013 inflation adjustment using CPI-U-RS and the 1.1587 factor).

- **Outputs**: paper PDFs, slides, tables, and figures for direct reuse in scholarly work or derivative projects.

---

## How to Reproduce

1) **Environment**: see [README/INSTALLATION.md](README/INSTALLATION.md) for Python/LaTeX setup (requires Python 3.9.x).  
2) **Data & code**: run `./reproduce.sh --data` from repo root to build the paper with the git-versioned SCF data (2013$).  
3) **Optional SCF QA**: `./reproduce.sh --data --use-latest-scf-data` adjusts current Fed SCF (2022$) back to 2013$ using the documented CPI anchors and 1.1587 factor.  
4) **Outputs**: compiled paper in `HAFiscal.pdf`, tables/figures in `Tables/` and `Figures/`.  

---

## Key Findings (Summary)

1. **Heterogeneous MPCs drive policy effectiveness**: Stimulus policies have dramatically different effects depending on how transfers are distributed across households with different liquid wealth positions.

2. **Behavioral mechanisms matter**: Sticky expectations and splurge behavior significantly affect both aggregate and distributional consumption responses to fiscal stimulus.

3. **Welfare implications vary substantially**: Optimal stimulus design depends critically on policy objectives (aggregate demand vs. distributional equity).

4. **Model matches micro and macro evidence**: The calibrated HANK model successfully reconciles high microeconomic MPCs with realistic aggregate wealth levels and macroeconomic consumption dynamics.

---

## Citation

If you use this repository, please cite the paper and the Econ-ARK toolkit:

```
Carroll, C.D., Crawley, E., Du, W., Frankovic, I., & Tretvoll, H. (2025).
Welfare and Spending Effects of Consumption Stimulus Policies.
```

Econ-ARK: [https://econ-ark.org](https://econ-ark.org)

---

## Repository Structure (high level)

- `HAFiscal.tex` and `Subfiles/` — main manuscript and appendices.
- `Code/` — model code, data processing, and empirical scripts (SCF workflows).
- `Figures/`, `Tables/` — generated outputs.
- `README/` — detailed documentation, install, quick reference, troubleshooting.

---

**Last Updated**: December 2025

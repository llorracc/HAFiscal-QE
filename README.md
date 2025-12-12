# HAFiscal Replication Package

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.17861977.svg)](https://doi.org/10.5281/zenodo.17861977)

**Paper**: Welfare and Spending Effects of Consumption Stimulus Policies
**Authors**: Christopher D. Carroll, Edmund Crawley, William Du, Ivan Frankovic, Hakon Tretvoll
**Journal**: Quantitative Economics
**Submission Repository**: https://github.com/llorracc/HAFiscal-QE

**Repository Version**: 952721e4
**Generated**: 2025-12-12

---

## Overview

This repository contains the complete replication package for "Welfare and Spending Effects of Consumption Stimulus Policies", submitted to Quantitative Economics.

**What's included**:
- LaTeX source for the paper (HAFiscal.tex)
- All code for computational results (Python, HARK framework)
- Data files and download scripts
- Complete reproduction workflow
- Computational environment specifications

**Estimated time to reproduce**:
- Minimal verification: ~1 hour
- Full replication: 4-5 days (computational)
- Paper compilation: 5-10 minutes

---

## Quick Start

### Build the Paper

```bash
# Compile paper PDF from existing results
./reproduce.sh --docs

# Note: Manual pdflatex/bibtex commands won't work because .bib files
# are excluded from QE submission (only .bbl files are included).
# Always use the reproduce.sh script to build documents.
```

### Minimal Reproduction (Verify Code Runs)

```bash
./reproduce.sh --comp min    # Minimal computational verification (~1 hour)
./reproduce.sh --docs        # Rebuild paper from results
```

### Full Replication (Reproduce All Results)

```bash
./reproduce.sh --comp full   # Full computational replication (4-5 days)
./reproduce.sh --docs        # Rebuild all documents
```

---


# HAFiscal-QE

This repository contains the Quantitative Economics (QE) submission preparation for HAFiscal.

## Purpose

This is a **downstream-only** repository that:
- Takes outputs from HAFiscal-make and HAFiscal-Latest
- Transforms them to meet QE submission requirements
- Does NOT modify any upstream repositories

## Source Dependencies

This repository depends on:
- `HAFiscal-make/` - Build scripts and infrastructure
- `HAFiscal-Latest/` - Primary source content
- `HAFiscal-Public/` - (Optional) Published version reference

## Tracking

Each build records the exact commit IDs from source repositories:
- See `build-info/` for provenance of each QE preparation
- Synchronized commits across repositories use matching tags

## Structure

```
HAFiscal-QE/
├── README.md                 # This file
├── scripts/                  # QE-specific transformation scripts
├── prompts/                  # Documentation and prompts for QE preparation
├── build-info/              # Source commit tracking
├── submission/              # Final QE submission materials
│   ├── manuscript/          # Main paper files
│   ├── supplementary/       # Online appendix and additional materials
│   └── metadata/            # Submission metadata and forms
└── working/                 # Intermediate files during preparation
```

## Usage

1. Ensure HAFiscal-make and HAFiscal-Latest are up to date
2. Run preparation scripts from `scripts/`
3. Review output in `submission/`
4. Submit materials from `submission/` to QE

## Important Notes

- This repository is **read-only** with respect to upstream repos
- All modifications are applied as transformations, not source edits
- Original build systems remain completely unchanged 
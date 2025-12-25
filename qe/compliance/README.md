# Compliance Verification Documents

This directory contains compliance verification documents for Quantitative Economics journal submission.

---

## Quick Access

**Always read**: [QE-COMPLIANCE-REPORT-LATEST.md](QE-COMPLIANCE-REPORT-LATEST.md)

This is a symlink to the most recent detailed compliance report.

**Quick summary**: [QE-COMPLIANCE-CHECKLIST-LATEST.md](QE-COMPLIANCE-CHECKLIST-LATEST.md)

One-line-per-requirement summary with links to detailed report sections.

---

## Document Organization

### Symlinks (Predictable URLs)

- `QE-COMPLIANCE-REPORT-LATEST.md` → always points to latest detailed report
- `QE-COMPLIANCE-CHECKLIST-LATEST.md` → always points to latest checklist

### Timestamped Files (Historical Record)

- `QE-COMPLIANCE-REPORT_YYYYMMDD-HHMMh.md` - Detailed reports
- `QE-COMPLIANCE-CHECKLIST_YYYYMMDD-HHMMh.md` - Abbreviated checklists

Timestamped files provide a historical record of compliance checks. The LATEST symlinks are updated to point to the most recent versions.

---

## Document Types

### REPORT (Detailed)

Comprehensive verification with:

- Full evidence for each requirement
- Command outputs and file excerpts
- Detailed findings and recommendations
- Complete audit trail

### CHECKLIST (Abbreviated)

Quick reference with:

- One line per requirement
- Status indicator (✅⚠️❌)
- Links to detailed sections in REPORT

### SPEC (Requirements)

Canonical specification of all requirements:

- Located in `../requirements/QE-COMPLIANCE-SPEC.md`
- Single source of truth for what to check
- Used by automated checker and manual review

---

## For QE Editors

1. Start with [QE-COMPLIANCE-CHECKLIST-LATEST.md](QE-COMPLIANCE-CHECKLIST-LATEST.md) for quick overview
2. Click requirement links to see detailed evidence in REPORT
3. All documents reference the same tested commit

---

## Testing Methodology

- **Automated checks**: `check-qe-compliance.py` script
- **Docker testing**: Verifies reproducibility in clean environment
- **Manual verification**: Expert review of quality requirements
- **Excluded directories**: Subfiles/, Figures/, Tables/ (standalone versions for inspection)

**Note on excluded directories**: These contain standalone versions of paper sections and elements that are inlined during document generation. They may not compile with correct cross-references but are provided for convenient inspection of individual components.

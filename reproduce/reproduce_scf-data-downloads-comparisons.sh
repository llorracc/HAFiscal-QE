#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# Compare rscfp2004.dta from multiple online sources against a
# local reference copy.
#
# Usage:
#   ./compare_rscfp2004_sources.sh /path/to/local/rscfp2004.dta
#
# If no argument is given, defaults to ./rscfp2004_local.dta
# ============================================================

REF_LOCAL="${1:-./rscfp2004_local.dta}"

if [[ ! -f "$REF_LOCAL" ]]; then
  echo "ERROR: Reference file not found: $REF_LOCAL" >&2
  exit 1
fi

echo "Reference file: $REF_LOCAL"
mkdir -p downloads/tmp

# ---------- helper: strict comparison ----------
strict_compare() {
  local ref="$1"
  local cand="$2"
  local label="$3"

  if [[ ! -f "$cand" ]]; then
    echo "[$label] Candidate file missing: $cand"
    return
  fi

  echo "[$label] Strict comparison:"
  echo "  Paths:"
  echo "    ref  : $ref"
  echo "    cand : $cand"

  local ref_sha cand_sha
  ref_sha=$(sha256sum "$ref"  | awk '{print $1}')
  cand_sha=$(sha256sum "$cand" | awk '{print $1}')
  echo "  SHA256:"
  echo "    ref  : $ref_sha"
  echo "    cand : $cand_sha"

  if cmp -s "$ref" "$cand"; then
    echo "  RESULT: BYTE-IDENTICAL"
  else
    echo "  RESULT: DIFFERENT (bytes differ)"
  fi
  echo
}

# ---------- helper: looser comparison via Python ----------
loose_compare() {
  local ref="$1"
  local cand="$2"
  local label="$3"

  if [[ ! -f "$cand" ]]; then
    echo "[$label] Skipping loose comparison (candidate missing)"
    echo
    return
  fi

  echo "[$label] Loose comparison (structure + simple moments):"

  python3 << 'EOF'
import sys, os
import numpy as np
import pyreadstat

ref_path = os.environ.get("REF_PATH")
cand_path = os.environ.get("CAND_PATH")
label = os.environ.get("LABEL")

def load_meta(path):
    try:
        df, meta = pyreadstat.read_dta(path)
        return df, meta
    except Exception as e:
        print(f"  [pyreadstat] Failed to read {path}: {e}")
        return None, None

print(f"  Comparing reference vs candidate ({label})")
print(f"    ref : {ref_path}")
print(f"    cand: {cand_path}")

ref_df, ref_meta  = load_meta(ref_path)
cand_df, cand_meta = load_meta(cand_path)

if ref_df is None or cand_df is None:
    sys.exit(0)

print(f"  Dimensions:")
print(f"    ref : {ref_df.shape[0]} obs, {ref_df.shape[1]} vars")
print(f"    cand: {cand_df.shape[0]} obs, {cand_df.shape[1]} vars")

# variable names
ref_vars  = list(ref_df.columns)
cand_vars = list(cand_df.columns)

common = [v for v in ref_vars if v in cand_vars]
only_ref = [v for v in ref_vars  if v not in cand_vars]
only_cand= [v for v in cand_vars if v not in ref_vars]

print(f"  Variable name intersection: {len(common)}")
print(f"  Variables only in ref  : {len(only_ref)}")
print(f"  Variables only in cand : {len(only_cand)}")

# Show a few differences if any
if only_ref[:5]:
    print("    (example only-in-ref vars):", ", ".join(only_ref[:5]))
if only_cand[:5]:
    print("    (example only-in-cand vars):", ", ".join(only_cand[:5]))

# Simple moments for key variables, if present
for var in ["networth", "income", "Y1", "yy1"]:
    in_ref  = var in ref_df.columns
    in_cand = var in cand_df.columns
    if not (in_ref and in_cand):
        continue
    rv = ref_df[var]
    cv = cand_df[var]
    rmed = float(rv.replace([np.inf, -np.inf], np.nan).dropna().median()) if rv.notna().any() else np.nan
    cmed = float(cv.replace([np.inf, -np.inf], np.nan).dropna().median()) if cv.notna().any() else np.nan
    rmean = float(rv.replace([np.inf, -np.inf], np.nan).dropna().mean()) if rv.notna().any() else np.nan
    cmean = float(cv.replace([np.inf, -np.inf], np.nan).dropna().mean()) if cv.notna().any() else np.nan
    print(f"  Variable '{var}':")
    print(f"    ref  median/mean: {rmed:,.2f} / {rmean:,.2f}")
    print(f"    cand median/mean: {cmed:,.2f} / {cmean:,.2f}")
    if all(np.isfinite(x) for x in [rmed, cmed]):
        diff = cmed - rmed
        rel  = diff / rmed if rmed != 0 else np.nan
        print(f"    median diff (cand-ref): {diff:,.2f} (rel: {rel:.4%} if defined)")

print()
EOF
}

# ============================================================
# 1. Federal Reserve: current summary extract (scfp2004s.zip)
#    This is the "official" 2022-dollar summary extract.
# ============================================================

FED_ZIP_URL="https://www.federalreserve.gov/econres/files/scfp2004s.zip"
FED_ZIP_PATH="downloads/scfp2004s_fed.zip"
FED_DTA_PATH="downloads/rscfp2004_fed.dta"

echo "== Downloading from Federal Reserve (summary extract zip) =="
if curl -fSL "$FED_ZIP_URL" -o "$FED_ZIP_PATH"; then
  echo "  Downloaded Fed scfp2004s.zip -> $FED_ZIP_PATH"
  # Extract any .dta inside; prefer rscfp2004.dta if present
  rm -f "$FED_DTA_PATH"
  unzip -j -o "$FED_ZIP_PATH" "*.dta" -d downloads/tmp >/dev/null 2>&1 || true
  CANDIDATE=""
  if ls downloads/tmp/rscfp2004.dta >/dev/null 2>&1; then
    CANDIDATE="downloads/tmp/rscfp2004.dta"
  else
    # fall back to any .dta extracted
    first_dta=$(ls downloads/tmp/*.dta 2>/dev/null | head -n1 || true)
    if [[ -n "$first_dta" ]]; then
      CANDIDATE="$first_dta"
    fi
  fi

  if [[ -n "${CANDIDATE:-}" ]]; then
    cp "$CANDIDATE" "$FED_DTA_PATH"
    echo "  Extracted candidate DTA -> $FED_DTA_PATH"
    strict_compare "$REF_LOCAL" "$FED_DTA_PATH" "FED_scfp2004s"
    REF_PATH="$REF_LOCAL" CAND_PATH="$FED_DTA_PATH" LABEL="FED_scfp2004s" loose_compare "$REF_LOCAL" "$FED_DTA_PATH" "FED_scfp2004s"
  else
    echo "  WARNING: No .dta found inside Fed scfp2004s.zip"
  fi
else
  echo "  WARNING: Failed to download Fed scfp2004s.zip"
fi
echo

# ============================================================
# 2. openICPSR: Generational Wealth replication
#    ECIN Replication Package (E226964V5) -> rscfp2004.dta
#    NOTE: may require login for curl to get data instead of HTML.
# ============================================================

OPENICPSR_GEN_URL="https://www.openicpsr.org/openicpsr/project/226964/version/V5/view?path=%2Fopenicpsr%2F226964%2Ffcr%3Aversions%2FV5%2F1.2-Raw-Data%2FSCF_bulletin%2Frscfp2004.dta&type=file"
OPENICPSR_GEN_PATH="downloads/rscfp2004_openicpsr_genwealth.dta"

echo "== Downloading from openICPSR (Generational Wealth replication) =="
echo "   (You may need to be logged in; if curl retrieves HTML, comparisons will fail.)"
if curl -fSL "$OPENICPSR_GEN_URL" -o "$OPENICPSR_GEN_PATH"; then
  file_type=$(file -b "$OPENICPSR_GEN_PATH")
  echo "  Saved to $OPENICPSR_GEN_PATH (file type: $file_type)"
  strict_compare "$REF_LOCAL" "$OPENICPSR_GEN_PATH" "openICPSR_GenerationalWealth"
  REF_PATH="$REF_LOCAL" CAND_PATH="$OPENICPSR_GEN_PATH" LABEL="openICPSR_GenerationalWealth" loose_compare "$REF_LOCAL" "$OPENICPSR_GEN_PATH" "openICPSR_GenerationalWealth"
else
  echo "  WARNING: Failed to download from openICPSR Generational Wealth URL"
fi
echo

# ============================================================
# 3. openICPSR: Public Education Inequality & Intergenerational Mobility
#    SCF_precompiled/scfp2004s.zip -> contains 2004 summary extract
# ============================================================

OPENICPSR_EDU_ZIP_URL="https://www.openicpsr.org/openicpsr/project/122884/version/V1/view?path=%2Fopenicpsr%2F122884%2Ffcr%3Aversions%2FV1%2Fraw%2FSCF_precompiled%2Fscfp2004s.zip&type=file"
OPENICPSR_EDU_ZIP_PATH="downloads/scfp2004s_openicpsr_edu.zip"
OPENICPSR_EDU_DTA_PATH="downloads/rscfp2004_openicpsr_edu.dta"

echo "== Downloading from openICPSR (Education Inequality SCF_precompiled) =="
echo "   (Again, may require login for curl to retrieve binary zip.)"
if curl -fSL "$OPENICPSR_EDU_ZIP_URL" -o "$OPENICPSR_EDU_ZIP_PATH"; then
  echo "  Saved zip to $OPENICPSR_EDU_ZIP_PATH"
  rm -f downloads/tmp/*.dta
  unzip -j -o "$OPENICPSR_EDU_ZIP_PATH" "*.dta" -d downloads/tmp >/dev/null 2>&1 || true
  CANDIDATE=""
  if ls downloads/tmp/rscfp2004.dta >/dev/null 2>&1; then
    CANDIDATE="downloads/tmp/rscfp2004.dta"
  else
    first_dta=$(ls downloads/tmp/*.dta 2>/dev/null | head -n1 || true)
    if [[ -n "$first_dta" ]]; then
      CANDIDATE="$first_dta"
    fi
  fi
  if [[ -n "${CANDIDATE:-}" ]]; then
    cp "$CANDIDATE" "$OPENICPSR_EDU_DTA_PATH"
    echo "  Extracted candidate DTA -> $OPENICPSR_EDU_DTA_PATH"
    strict_compare "$REF_LOCAL" "$OPENICPSR_EDU_DTA_PATH" "openICPSR_EduIneq_scfp2004s"
    REF_PATH="$REF_LOCAL" CAND_PATH="$OPENICPSR_EDU_DTA_PATH" LABEL="openICPSR_EduIneq_scfp2004s" loose_compare "$REF_LOCAL" "$OPENICPSR_EDU_DTA_PATH" "openICPSR_EduIneq_scfp2004s"
  else
    echo "  WARNING: No .dta extracted from openICPSR scfp2004s.zip"
  fi
else
  echo "  WARNING: Failed to download openICPSR scfp2004s.zip"
fi
echo

echo "=== Done. Check above for STRICT and LOOSE comparison outcomes. ==="

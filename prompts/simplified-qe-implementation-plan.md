# Simplified QE BUILD_MODE Implementation Plan

## Overview
Much simpler approach: Create a QE metadata file in HAFiscal-Latest that can be directly included in the QE build. No Python parsing needed!

## Step 1: Add QE Metadata to HAFiscal-Latest

Create `HAFiscal-Latest/@local/qe-metadata.tex` with all QE-specific formatting (see `create-qe-metadata-file.md`).

## Step 2: Simplified QE Build Process

### Location: HAFiscal-make/scripts/qe/build-qe-submission.sh
```bash
#!/bin/bash
# Simplified QE transformation pipeline

source scripts/utils/logger.sh

WORK_DIR="${SOURCE_DIR}/.qe-build"
mkdir -p "$WORK_DIR"

log_info "Building QE submission from ${SOURCE_DIR}"

# Step 1: Copy all files
cp -r "${SOURCE_DIR}"/* "$WORK_DIR/"
cd "$WORK_DIR"

# Step 2: Install QE class files
cp "${SCRIPT_DIR}/resources/qe/"*.{cls,cfg,bst} .

# Step 3: Copy QE template
cp "${SCRIPT_DIR}/resources/qe/HAFiscal-QE.tex" .

# Step 4: Consolidate subfiles into single content file
python3 "${SCRIPT_DIR}/scripts/qe/consolidate-subfiles.py" . HAFiscal-QE-content.tex

# Step 5: Simple fixes for QE compatibility
# - Remove \onlyinsubfile{} and similar commands
# - Fix any package conflicts
# - Ensure proper structure
sed -i '' 's/\\onlyinsubfile{[^}]*}//g' HAFiscal-QE-content.tex
sed -i '' 's/\\notinsubfile{\\(.*\\)}/\\1/g' HAFiscal-QE-content.tex

# Step 6: Compile with QE class
latexmk -pdf HAFiscal-QE.tex

# Step 7: Copy output
cp HAFiscal-QE.pdf "${OUTPUT_DIR}/"

# Cleanup
cd ..
rm -rf "$WORK_DIR"

log_success "Created ${OUTPUT_DIR}/HAFiscal-QE.pdf"
```

## Step 3: Minimal Consolidation Script

The consolidate-subfiles.py script just needs to:
1. Read HAFiscal.tex
2. Find all \subfile{} commands
3. Extract content from each subfile (removing subfile boilerplate)
4. Write consolidated content to HAFiscal-QE-content.tex

No metadata extraction needed!

## Step 4: The QE Template

Already defined in `HAFiscal-make/resources/qe/HAFiscal-QE.tex`:
- Uses QE document class
- Includes `@local/qe-metadata` for all frontmatter
- Includes `HAFiscal-QE-content` for body
- Uses `qe` bibliography style

## Benefits of Simplified Approach

1. **Pure LaTeX solution** - No complex Python parsing
2. **Single metadata file** - Easy to maintain in `@local/qe-metadata.tex`
3. **Reuses existing infrastructure** - Works with current path system
4. **Minimal transformation** - Just consolidate and compile
5. **Easy to debug** - Can manually compile intermediate files

## Usage

```bash
# After running makePublic-master.sh:
BUILD_QE=true ./makePublic-master.sh

# Or standalone:
./makePDF-QE.sh
```

## What We DON'T Need Anymore

- ❌ extract-metadata.py - Deleted!
- ❌ Complex metadata parsing
- ❌ Structured \Author{} commands in titlepage
- ❌ Python regex for metadata extraction

## What We DO Need

- ✅ `@local/qe-metadata.tex` in HAFiscal-Latest
- ✅ Simple consolidation script
- ✅ QE template that includes the metadata
- ✅ Basic shell script to orchestrate

This is MUCH simpler! 
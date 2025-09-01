# Complete Implementation Plan for QE BUILD_MODE

## Overview
Add QE as a BUILD_MODE to HAFiscal-make that transforms HAFiscal-Public into a Quantitative Economics submission-ready PDF.

## Prerequisites
1. **Update HAFiscal-Latest** with structured metadata commands (see separate prompts)
2. **Run makePublic-master.sh** to ensure HAFiscal-Public is up to date

## Implementation Steps

### 1. Move QE Resources to HAFiscal-make
```bash
# Create directory structure
mkdir -p HAFiscal-make/resources/qe/
mkdir -p HAFiscal-make/scripts/qe/transform/

# Copy QE class files
cp HAFiscal-QE/resources/qe-templates/{econsocart.cls,econsocart.cfg,qe.bst} \
   HAFiscal-make/resources/qe/

# Move transformation scripts
mv HAFiscal-QE/scripts/qe/* HAFiscal-make/scripts/qe/
```

### 2. Create makePDF-QE.sh
Location: `HAFiscal-make/makePDF-QE.sh`
```bash
#!/bin/bash
# Build QE submission version from HAFiscal-Public

cd "$(dirname "$0")"
source scripts/utils/logger.sh

# Verify HAFiscal-Public exists
PUBLIC_DIR="../HAFiscal-Public"
if [[ ! -d "$PUBLIC_DIR" ]]; then
    log_error "HAFiscal-Public not found. Run makePublic-master.sh first."
    exit 1
fi

# Run QE transformation
export BUILD_MODE=QE
export SOURCE_DIR="$PUBLIC_DIR"
export OUTPUT_DIR="$PUBLIC_DIR"

./scripts/qe/build-qe-submission.sh
```

### 3. Create QE Build Pipeline
Location: `HAFiscal-make/scripts/qe/build-qe-submission.sh`
```bash
#!/bin/bash
# Main QE transformation pipeline

source scripts/utils/logger.sh

WORK_DIR="${SOURCE_DIR}/.qe-build"
mkdir -p "$WORK_DIR"

log_info "Building QE submission from ${SOURCE_DIR}"

# Step 1: Copy source files
cp -r "${SOURCE_DIR}"/{*.tex,*.bib,Figures,Tables,Code} "$WORK_DIR/"

# Step 2: Install QE class files
cp resources/qe/{econsocart.cls,econsocart.cfg,qe.bst} "$WORK_DIR/"

# Step 3: Extract metadata and generate QE template
python3 scripts/qe/extract-metadata.py \
    "$WORK_DIR/HAFiscal.tex" \
    "$WORK_DIR/qe-frontmatter.tex"

# Step 4: Transform content
python3 scripts/qe/transform/consolidate-subfiles.py "$WORK_DIR"
python3 scripts/qe/transform/adapt-for-qe.py "$WORK_DIR"
python3 scripts/qe/transform/fix-bibliography.py "$WORK_DIR"

# Step 5: Compile
cd "$WORK_DIR"
latexmk -pdf HAFiscal-QE.tex

# Step 6: Copy output
cp HAFiscal-QE.pdf "${OUTPUT_DIR}/"

# Cleanup
cd ..
rm -rf "$WORK_DIR"

log_success "Created ${OUTPUT_DIR}/HAFiscal-QE.pdf"
```

### 4. Create QE Document Template
Location: `HAFiscal-make/scripts/qe/templates/HAFiscal-QE.tex`
```latex
% QE Submission Version
\documentclass[qe,nameyear,draft]{econsocart}
\RequirePackage[colorlinks,citecolor=blue,urlcolor=blue]{hyperref}

\startlocaldefs
% Import adapted preamble
\input{qe-preamble}
\endlocaldefs

\begin{document}

\begin{frontmatter}
% Include generated frontmatter
\input{qe-frontmatter}

% Abstract from original
\begin{abstract}
\input{HAFiscal-Abstract.txt}
\end{abstract}

\end{frontmatter}

% Main content
\input{HAFiscal-QE-content}

% Bibliography
\bibliographystyle{qe}
\bibliography{HAFiscal}

\end{document}
```

### 5. Update makePublic-master.sh
Add at the end:
```bash
# Build QE version if requested
if [[ "${BUILD_QE:-false}" == "true" ]]; then
    log_minor_section "Building QE Submission Version"
    ./makePDF-QE.sh
fi
```

### 6. Key Transformation Scripts

#### adapt-for-qe.py
- Reads consolidated content
- Removes incompatible commands
- Adapts package usage for QE class
- Maintains appendix structure (full first, stub second)

#### fix-bibliography.py  
- Converts from econark to qe.bst style
- Ensures all citations are resolved
- Formats bibliography entries per QE requirements

## Usage

```bash
# Standard workflow
./makeEverything.sh          # Build HAFiscal-Latest
./makePublic-master.sh       # Copy to HAFiscal-Public

# Build QE version
./makePDF-QE.sh              # Creates HAFiscal-QE.pdf

# Or all at once
BUILD_QE=true ./makePublic-master.sh
```

## Benefits
1. **No modifications to existing build system** - QE is a separate post-process
2. **Metadata in source** - Easier to maintain than separate files
3. **Reproducible** - Same inputs always produce same QE output
4. **No version tracking in PDF** - Avoids spurious "modifications"

## Testing Plan
1. Add metadata commands to HAFiscal-Latest
2. Run full build pipeline
3. Verify HAFiscal-QE.pdf compiles without errors
4. Check formatting matches QE requirements
5. Ensure appendices appear correctly 
# HAFiscal-QE Development Roadmap

## Current Status

✅ **Completed:**
- Created HAFiscal-QE repository structure
- Downloaded official QE LaTeX templates
- Documented QE submission requirements
- Created initial transformation script framework
- Established downstream-only workflow

## Phase 1: Analysis and Planning (Next Steps)

### 1.1 Analyze HAFiscal Structure
- [ ] Examine HAFiscal.tex main document structure
- [ ] Map all \subfile{} dependencies
- [ ] Inventory all packages used
- [ ] Document current author/affiliation format
- [ ] List all bibliography files and entries

### 1.2 Create Transformation Specifications
- [ ] Define precise mapping from HAFiscal to QE format
- [ ] Identify content for main manuscript vs supplementary
- [ ] Plan bibliography consolidation strategy
- [ ] Document package compatibility issues

## Phase 2: Implementation

### 2.1 Core Transformation Scripts
- [ ] `scripts/transform/consolidate-subfiles.py` - Merge all subfiles into single document
- [ ] `scripts/transform/convert-authors.py` - Reformat author information for QE
- [ ] `scripts/transform/process-bibliography.py` - Apply QE bibliography style
- [ ] `scripts/transform/separate-supplementary.py` - Extract supplementary content

### 2.2 Build Automation
- [ ] Update `prepare-qe-submission.sh` to call transformation scripts
- [ ] Add validation checks for QE requirements
- [ ] Create PDF compilation workflow
- [ ] Implement error handling and logging

## Phase 3: Testing and Refinement

### 3.1 Compilation Testing
- [ ] Test compilation with QE document class
- [ ] Resolve all LaTeX errors and warnings
- [ ] Verify bibliography formatting
- [ ] Check figure/table references

### 3.2 Content Validation
- [ ] Compare QE output with original HAFiscal PDF
- [ ] Verify no content is lost in transformation
- [ ] Check mathematical notation consistency
- [ ] Validate all cross-references

## Phase 4: Submission Preparation

### 4.1 Final Documents
- [ ] Generate camera-ready main manuscript PDF
- [ ] Create supplementary materials PDF
- [ ] Prepare submission metadata
- [ ] Create cover letter template

### 4.2 Quality Assurance
- [ ] Run through QE submission checklist
- [ ] Verify Econometric Society membership requirement
- [ ] Test upload to Editorial Express system
- [ ] Document any manual adjustments needed

## Future Enhancements

### Automation Goals
- Automatic detection of HAFiscal format changes
- Smart content classification (main vs supplementary)
- Bibliography entry validation and completion
- Automated QE compliance checking

### Integration Ideas
- GitHub Actions for continuous validation
- Diff tools to track changes between versions
- Automated commit synchronization across repos
- Version tagging for submission milestones

## Key Decisions Needed

1. **Content Division**: What belongs in main manuscript vs supplementary materials?
2. **Author Order**: Confirm author order and affiliations for QE submission
3. **Bibliography**: Which entries to include, how to handle duplicates
4. **Timing**: When to switch from `draft` to `final` mode

## Resources

- QE Submission Portal: https://editorialexpress.com/qe
- QE LaTeX Documentation: `resources/qe-templates/qe_sample.pdf`
- Transformation Guide: `prompts/transform-hafiscal-to-qe.md`

## Contact

For questions about the QE submission process:
- Journal Email: qe@econometricsociety.org
- Technical Support: latex-support@vtex.lt

---

*This roadmap is a living document and will be updated as the project progresses.* 
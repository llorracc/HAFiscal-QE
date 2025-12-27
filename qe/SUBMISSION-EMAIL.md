# QE Submission Email Message - Draft

**Purpose**: Draft email message to accompany submission to Quantitative Economics data editor.

**Usage**: Customize this template before sending with your submission.

---

## Email Draft: Submission Cover Letter

**Subject**: Replication Package Submission - "Welfare and Spending Effects of Consumption Stimulus Policies"

**To**: Quantitative Economics Data Editor

**From**: Hakon Tretvoll (corresponding author)

---

Dear Data Editor,

We are submitting the replication package for our manuscript "Welfare and Spending Effects of Consumption Stimulus Policies" (MS 2442) by Christopher D. Carroll, Edmund Crawley, William Du, Ivan Frankovic, and Hakon Tretvoll.

**Repository**: <https://github.com/llorracc/HAFiscal-QE>

The `./reproduce.sh` script in the repository root will reproduce all of the paper's quantitative results and documents. To get started, run `./reproduce.sh --help` in a Unix shell to view available reproduction options.

**Compliance Verification**:
- Checklist: <https://github.com/llorracc/HAFiscal-QE/blob/main/qe/compliance/QE-COMPLIANCE-CHECKLIST-LATEST.md>
- Detailed Report: <https://github.com/llorracc/HAFiscal-QE/blob/main/qe/compliance/QE-COMPLIANCE-REPORT-LATEST.md>

**Branch Strategy**: The repository uses a dual-branch structure:
- **`main` branch**: Complete source-based reproduction (4-5 days for full computation; ~1 hour for minimal verification)
- **`with-precomputed-artifacts` branch** (default): Document compilation from precomputed results (~5-10 minutes)

The `with-precomputed-artifacts` branch preserves computationally expensive intermediate outputs to enable efficient reproducibility testing while maintaining full source-based reproduction capability on the main branch. Complete documentation, including detailed timing information, computational requirements, data availability, and reproduction instructions, is available in the repository README.md.  

This branch structure follows best practices from the Social Science Data Editors' community: version control for source code and documentation, while providing computed artifacts for efficient verification. The strategy is documented in the repository README.md and compliance reports.

**Pregenerated Content Marking**: Rather than deleting pregenerated figures and tables from the main branch, we have applied visible "PREGENERATED" watermarks to all such content. These watermarks clearly indicate which figures and tables are precomputed artifacts rather than outputs from fresh computational runs. When the computational code is executed to regenerate results, these watermarks will not appear on the newly generated figures and tables, making it straightforward to distinguish between pregenerated and freshly computed content.


**Contact**: Hakon Tretvoll <hakon.tretvoll@gmail.com>

Please let us know if you need any additional information or clarification.

Best regards,

Hakon Tretvoll
*On behalf of all authors*

---

## Customization Checklist

Before sending, verify and customize:

- [ ] Verify repository URL is correct
- [ ] Verify compliance document links are accessible

---
---

## Email Sending Checklist

Before sending:


1. **Test Links**:
   - [ ] Click all repository links to verify they work
   - [ ] Verify compliance document links are accessible
   - [ ] Check that branch links resolve correctly

---

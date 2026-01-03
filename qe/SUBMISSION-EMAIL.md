# QE Submission Email Message - Draft

**Purpose**: Draft email message to accompany submission to Quantitative Economics data editor.

**Usage**: Customize this template before sending with your submission.

---

## Email Draft: Submission Cover Letter

**Subject**: Replication Package for MS 2442 - "Welfare and Spending Effects of Consumption Stimulus Policies"

**To**: Quantitative Economics Data Editor

**From**: Hakon Tretvoll (corresponding author)

---

Dear Data Editor,

The replication package for "Welfare and Spending Effects of Consumption Stimulus Policies" (MS 2442) by Christopher D. Carroll, Edmund Crawley, William Du, Ivan Frankovic, and Hakon Tretvoll is available at:

**Repository**: <https://github.com/llorracc/HAFiscal-QE>

We'd like to add you as a 'collaborator' so you can directly propose modifications to the repo (if that's the way you want to interact). 

It is also available at the Zenodo DOI 10.5281/zenodo.18132886.

The only tricky thing about the repo is that it contains both a 'main' branch (which rigorously satisfies your requirement that no precomputed material should be present) and a 'with-precomputed-artifacts' branch (which has those artifacts in case you want to compare them to what you get when you execute `./reproduce.sh --comp full` from the root directory in the main branch).

Strictly speaking, from that main branch position, you should need only to run 
`./reproduce.sh --envt` to generate the computational environment
`./reproduce.sh --data` to make computations with the data
`./reproduce.sh --comp full` to produce all the computational results

`./reproduce.sh --help` shows other options, some of which require the precomputed data (like, `./reproduce.sh --docs main` requires the `HAFiscal.bib` file), so the required artifacts are temporarily retrieved from the online `with-precomputed-artifacts` branch. 

The most useful of these to you might be 

`./reproduce.sh --comp min` 

which takes only ~1 hr and gives a workout to the computational machinery that will be required for `./reproduce.sh --comp full`.  If `./reproduce.sh --comp min` does not work, `.reproduce.sh --comp full` will probably not work either, but you can find out in 1 hr rather than 5 days.

The Zenodo DOI contains an archive ONLY of the 'main' branch, without the precomputed arifacts branch, in part to satisfy the size requirements of Zenodo.

**Compliance Verification**:

- Checklist: <https://github.com/llorracc/HAFiscal-QE/blob/main/qe/compliance/QE-COMPLIANCE-CHECKLIST-LATEST.md>
- Detailed Report: <https://github.com/llorracc/HAFiscal-QE/blob/main/qe/compliance/QE-COMPLIANCE-REPORT-LATEST.md>

**Contact**: Hakon Tretvoll <hakon.tretvoll@gmail.com>

Please let us know if you need any additional information or clarification.

Best regards,

Hakon Tretvoll
*On behalf of all authors*

---

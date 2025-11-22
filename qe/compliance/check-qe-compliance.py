#!/usr/bin/env python3
"""
QE Compliance Checker for HAFiscal-QE Repository

This script automatically checks compliance of a HAFiscal-QE repository
against Quantitative Economics journal submission requirements.

Usage:
    python3 check-qe-compliance.py /path/to/HAFiscal-QE

Output:
    JSON structure with compliance status for each requirement
"""

import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime


# Path constants - override with command line arguments
import os
import sys
from pathlib import Path

# Dynamically determine repository paths
SCRIPT_DIR = Path(__file__).parent.absolute()
LATEST_ROOT = SCRIPT_DIR.parent
REPOS_PARENT = LATEST_ROOT.parent
PUBLIC_ROOT = REPOS_PARENT / "HAFiscal-Public"
QE_ROOT = REPOS_PARENT / "HAFiscal-QE"
MAKE_ROOT = REPOS_PARENT / "HAFiscal-make"


def check_file_exists(qe_root: Path, filename: str) -> Dict[str, Any]:
    """Check if a file exists in the QE repository."""
    filepath = qe_root / filename
    return {
        "exists": filepath.exists(),
        "path": str(filepath) if filepath.exists() else None,
        "size": filepath.stat().st_size if filepath.exists() else 0
    }


def search_in_file(filepath: Path, pattern: str, max_lines: int = None) -> List[Dict[str, Any]]:
    """Search for a pattern in a file and return matches with line numbers."""
    matches = []
    if not filepath.exists():
        return matches
    
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            for line_num, line in enumerate(f, 1):
                if max_lines and line_num > max_lines:
                    break
                if re.search(pattern, line):
                    matches.append({
                        "line": line_num,
                        "content": line.strip()
                    })
    except Exception as e:
        return [{"error": str(e)}]
    
    return matches


def count_files_in_dir(qe_root: Path, directory: str, pattern: str = "*") -> int:
    """Count files matching a pattern in a directory."""
    dirpath = qe_root / directory
    if not dirpath.exists():
        return 0
    
    count = 0
    for filepath in dirpath.glob(pattern):
        if filepath.is_file():
            count += 1
    return count


def check_a1_document_class(qe_root: Path) -> Dict[str, Any]:
    """A1: Check if manuscript uses econsocart.cls with QE options."""
    main_tex = qe_root / "HAFiscal.tex"
    matches = search_in_file(main_tex, r'\\documentclass.*econsocart', max_lines=50)
    
    status = "compliant" if matches else "non_compliant"
    evidence = [f"{main_tex.name} line {m['line']}: {m['content']}" for m in matches]
    
    return {
        "requirement_id": "A.1",
        "requirement": "Manuscript uses econsocart.cls with QE options",
        "status": status,
        "evidence": evidence if evidence else ["Document class declaration not found"],
        "files_checked": [str(main_tex)],
        "recommendation": "None required" if status == "compliant" else 
                         "Action needed: Add \\documentclass[qe]{econsocart} to main .tex file"
    }


def check_a2_bibliography_style(qe_root: Path) -> Dict[str, Any]:
    """A2: Check if bibliography uses qe.bst style."""
    main_tex = qe_root / "HAFiscal.tex"
    matches = search_in_file(main_tex, r'\\bibliographystyle\{.*qe.*\}')
    
    status = "compliant" if matches else "non_compliant"
    evidence = [f"{main_tex.name} line {m['line']}: {m['content']}" for m in matches]
    
    # Also check if qe.bst exists
    qe_bst_exists = (qe_root / "qe" / "qe.bst").exists()
    if qe_bst_exists:
        evidence.append("qe.bst file verified in qe/ directory")
    
    return {
        "requirement_id": "A.2",
        "requirement": "Bibliography uses qe.bst style",
        "status": status,
        "evidence": evidence if evidence else ["Bibliography style declaration not found"],
        "files_checked": [str(main_tex)],
        "recommendation": "None required" if status == "compliant" else
                         "Action needed: Add \\bibliographystyle{qe/qe} to main .tex file"
    }


def check_a3_jel_keywords(qe_root: Path) -> Dict[str, Any]:
    """A3: Check for JEL codes and keywords in titlepage."""
    titlepage = qe_root / "Subfiles" / "HAFiscal-titlepage.tex"
    if not titlepage.exists():
        titlepage = qe_root / "HAFiscal.tex"
    
    jel_matches = search_in_file(titlepage, r'\\jelclass\{')
    keyword_matches = search_in_file(titlepage, r'\\keywords\{')
    
    # Check if they appear to be placeholders
    placeholder_patterns = [r'D\.\.', r'E\.\.', r'XXX', r'TODO', r'\{\s*\}']
    has_placeholder = False
    for match in jel_matches:
        for pattern in placeholder_patterns:
            if re.search(pattern, match['content']):
                has_placeholder = True
                break
    
    if not jel_matches:
        status = "non_compliant"
    elif has_placeholder:
        status = "warning"
    else:
        status = "compliant"
    
    evidence = []
    evidence.extend([f"{titlepage.name} line {m['line']}: {m['content']}" for m in jel_matches])
    evidence.extend([f"{titlepage.name} line {m['line']}: {m['content']}" for m in keyword_matches])
    
    if has_placeholder:
        evidence.append("WARNING: JEL codes appear to be placeholders")
    
    return {
        "requirement_id": "A.3",
        "requirement": "JEL codes and keywords included",
        "status": status,
        "evidence": evidence if evidence else ["JEL codes and keywords not found"],
        "files_checked": [str(titlepage)],
        "recommendation": "None required" if status == "compliant" else
                         "Action needed: Add specific JEL codes (e.g., E21, E62, H31, D15) and keywords"
    }


def check_a4_figures(qe_root: Path) -> Dict[str, Any]:
    """A4: Check for Figure files (LaTeX wrappers) in Figures/ directory.
    
    CRITICAL DISTINCTION: Figures ≠ images
    - Figures are .tex files in Figures/ containing complete LaTeX structure
    - Images are raw visual files (.pdf, .png, .svg) in images/ directory
    - The checker should count .tex files in Figures/, NOT image files
    """
    # Count LaTeX Figure files (the actual "Figures")
    tex_count = count_files_in_dir(qe_root, "Figures", "*.tex")
    
    # Optional: Check if images/ directory exists and has content
    images_dir = qe_root / "images"
    image_count = 0
    if images_dir.exists():
        for ext in ["*.pdf", "*.png", "*.svg", "*.jpg", "*.jpeg"]:
            image_count += len(list(images_dir.glob(ext)))
    
    if tex_count > 0:
        status = "compliant"
    else:
        status = "non_compliant"
    
    evidence = [
        f"Figure files (.tex) in Figures/: {tex_count} files"
    ]
    
    # Add informational note about images
    if image_count > 0:
        evidence.append(f"Raw image files in images/: {image_count} files (referenced by Figures/*.tex)")
    elif tex_count > 0:
        evidence.append("Note: Image files should be in images/ directory (referenced by Figure .tex files)")
    
    return {
        "requirement_id": "A.4",
        "requirement": "Figures exist as LaTeX files (Figures/*.tex with proper structure)",
        "status": status,
        "evidence": evidence,
        "files_checked": [str(qe_root / "Figures"), str(qe_root / "images")],
        "recommendation": "None required" if status == "compliant" else
                         f"Action needed: Add Figure .tex files to Figures/ directory (found {tex_count} files)"
    }


def check_a5_readme(qe_root: Path) -> Dict[str, Any]:
    """A5: Check for comprehensive README.md."""
    readme = qe_root / "README.md"
    file_info = check_file_exists(qe_root, "README.md")
    
    if not file_info["exists"]:
        return {
            "requirement_id": "A.5",
            "requirement": "README.md exists with comprehensive documentation",
            "status": "non_compliant",
            "evidence": ["README.md not found"],
            "files_checked": [str(readme)],
            "recommendation": "Action needed: Create README.md with reproduction instructions"
        }
    
    # Count lines
    with open(readme, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        line_count = len(lines)
    
    # Check for key sections
    content = ''.join(lines)
    has_installation = bool(re.search(r'installation|setup|environment', content, re.IGNORECASE))
    has_reproduction = bool(re.search(r'reproduction|replicate|reproduce', content, re.IGNORECASE))
    has_structure = bool(re.search(r'structure|directory|contents', content, re.IGNORECASE))
    
    key_sections = sum([has_installation, has_reproduction, has_structure])
    
    if line_count > 100 and key_sections >= 2:
        status = "compliant"
    elif line_count > 50:
        status = "warning"
    else:
        status = "non_compliant"
    
    evidence = [
        f"README.md: {line_count} lines",
        f"Installation/Setup section: {'✓' if has_installation else '✗'}",
        f"Reproduction section: {'✓' if has_reproduction else '✗'}",
        f"Structure section: {'✓' if has_structure else '✗'}"
    ]
    
    return {
        "requirement_id": "A.5",
        "requirement": "README.md exists with comprehensive documentation",
        "status": status,
        "evidence": evidence,
        "files_checked": [str(readme)],
        "recommendation": "None required" if status == "compliant" else
                         "Action needed: Expand README.md with more details"
    }


def check_a6_readme_pdf(qe_root: Path) -> Dict[str, Any]:
    """A6: Check for README.pdf."""
    file_info = check_file_exists(qe_root, "README.pdf")
    
    status = "compliant" if file_info["exists"] else "warning"
    evidence = [f"README.pdf exists: {file_info['exists']}"]
    
    if file_info["exists"]:
        evidence.append(f"Size: {file_info['size']} bytes")
    
    return {
        "requirement_id": "A.6",
        "requirement": "README.pdf provided for convenience",
        "status": status,
        "evidence": evidence,
        "files_checked": [str(qe_root / "README.pdf")],
        "recommendation": "None required" if status == "compliant" else
                         "Recommended: Generate README.pdf using pandoc"
    }


def check_b1_reproduce_script(qe_root: Path) -> Dict[str, Any]:
    """B1: Check for reproduction script."""
    reproduce_sh = qe_root / "reproduce.sh"
    reproduce_py = qe_root / "reproduce.py"
    
    has_script = reproduce_sh.exists() or reproduce_py.exists()
    
    evidence = []
    if reproduce_sh.exists():
        evidence.append(f"reproduce.sh found ({reproduce_sh.stat().st_size} bytes)")
    if reproduce_py.exists():
        evidence.append(f"reproduce.py found ({reproduce_py.stat().st_size} bytes)")
    if not has_script:
        evidence.append("No reproduction script found")
    
    status = "compliant" if has_script else "non_compliant"
    
    return {
        "requirement_id": "B.1",
        "requirement": "Reproduction script provided (reproduce.sh or reproduce.py)",
        "status": status,
        "evidence": evidence,
        "files_checked": [str(reproduce_sh), str(reproduce_py)],
        "recommendation": "None required" if status == "compliant" else
                         "Action needed: Create reproduce.sh or reproduce.py script"
    }


def check_b2_data_files(qe_root: Path) -> Dict[str, Any]:
    """B2: Check for data files."""
    data_dirs = ["Data", "Code/Empirical", "data", "Data-Raw"]
    data_files = []
    
    for data_dir in data_dirs:
        dirpath = qe_root / data_dir
        if dirpath.exists():
            for ext in ["*.dta", "*.csv", "*.xlsx", "*.txt", "*.dat"]:
                data_files.extend(list(dirpath.rglob(ext)))
    
    status = "compliant" if len(data_files) > 0 else "warning"
    
    evidence = [f"Found {len(data_files)} data files"]
    for f in data_files[:5]:  # Show first 5
        evidence.append(f"  - {f.relative_to(qe_root)}")
    if len(data_files) > 5:
        evidence.append(f"  ... and {len(data_files) - 5} more")
    
    return {
        "requirement_id": "B.2",
        "requirement": "Data files included or access instructions provided",
        "status": status,
        "evidence": evidence if data_files else ["No data files found"],
        "files_checked": [str(qe_root / d) for d in data_dirs],
        "recommendation": "None required" if status == "compliant" else
                         "Check: Verify data access instructions in README if no data files present"
    }


def check_b3_license(qe_root: Path) -> Dict[str, Any]:
    """B3: Check for LICENSE file."""
    license_files = ["LICENSE", "LICENSE.md", "LICENSE.txt", "LICENSE.rst"]
    found = None
    
    for lic in license_files:
        if (qe_root / lic).exists():
            found = lic
            break
    
    status = "compliant" if found else "non_compliant"
    
    evidence = []
    if found:
        with open(qe_root / found, 'r', encoding='utf-8') as f:
            first_line = f.readline().strip()
        evidence.append(f"{found} found: {first_line[:100]}")
    else:
        evidence.append("No LICENSE file found")
    
    return {
        "requirement_id": "B.3",
        "requirement": "Open license applied (CC BY, MIT, Apache, etc.)",
        "status": status,
        "evidence": evidence,
        "files_checked": [str(qe_root / lic) for lic in license_files],
        "recommendation": "None required" if status == "compliant" else
                         "Action needed: Add LICENSE file (e.g., Apache 2.0, MIT, CC BY 4.0)"
    }


def check_b4_zenodo_doi(qe_root: Path) -> Dict[str, Any]:
    """B4: Check for Zenodo DOI in README or titlepage."""
    readme = qe_root / "README.md"
    titlepage = qe_root / "Subfiles" / "HAFiscal-titlepage.tex"
    
    doi_pattern = r'10\.5281/zenodo\.\d+'
    
    readme_matches = search_in_file(readme, doi_pattern)
    titlepage_matches = search_in_file(titlepage, doi_pattern)
    
    found = len(readme_matches) > 0 or len(titlepage_matches) > 0
    status = "compliant" if found else "non_compliant"
    
    evidence = []
    for m in readme_matches:
        evidence.append(f"README.md line {m['line']}: {m['content'][:100]}")
    for m in titlepage_matches:
        evidence.append(f"titlepage line {m['line']}: {m['content'][:100]}")
    if not found:
        evidence.append("Zenodo DOI not found (expected after upload to Zenodo)")
    
    return {
        "requirement_id": "B.4",
        "requirement": "Zenodo DOI for replication package",
        "status": status,
        "evidence": evidence,
        "files_checked": [str(readme), str(titlepage)],
        "recommendation": "None required" if status == "compliant" else
                         "Action needed: Upload to Zenodo and add DOI to README and titlepage"
    }


def check_b5_environment_spec(qe_root: Path) -> Dict[str, Any]:
    """B5: Check for environment specification files."""
    env_files = ["environment.yml", "pyproject.toml", "requirements.txt", "Pipfile"]
    found_files = []
    
    for env_file in env_files:
        if (qe_root / env_file).exists():
            found_files.append(env_file)
    
    status = "compliant" if found_files else "warning"
    
    evidence = [f"Environment specification files: {', '.join(found_files) if found_files else 'None'}"]
    
    return {
        "requirement_id": "B.5",
        "requirement": "Software dependencies specified (environment.yml, requirements.txt, etc.)",
        "status": status,
        "evidence": evidence,
        "files_checked": [str(qe_root / f) for f in env_files],
        "recommendation": "None required" if status == "compliant" else
                         "Recommended: Add environment.yml or requirements.txt"
    }


def check_d1_supplementary_appendix(qe_root: Path) -> Dict[str, Any]:
    """D1: Check for supplementary appendix files."""
    appendix_files = list((qe_root / "Subfiles").glob("Appendix-*.tex")) if (qe_root / "Subfiles").exists() else []
    
    status = "compliant" if appendix_files else "warning"
    
    evidence = []
    for f in appendix_files:
        evidence.append(f"Appendix file: {f.name}")
    if not appendix_files:
        evidence.append("No supplementary appendix files found (may not be required)")
    
    return {
        "requirement_id": "D.1",
        "requirement": "Supplementary appendix files (if applicable)",
        "status": status,
        "evidence": evidence,
        "files_checked": [str(qe_root / "Subfiles")],
        "recommendation": "None required" if status == "compliant" or not appendix_files else
                         "Optional: Add supplementary appendix if needed"
    }


def run_all_checks(qe_root_path: str) -> List[Dict[str, Any]]:
    """Run all compliance checks and return results."""
    qe_root = Path(qe_root_path)
    
    if not qe_root.exists():
        return [{
            "error": f"QE root directory not found: {qe_root_path}",
            "recommendation": "Ensure HAFiscal-QE repository exists at specified path"
        }]
    
    results = []
    
    # Section A: Manuscript Formatting
    results.append(check_a1_document_class(qe_root))
    results.append(check_a2_bibliography_style(qe_root))
    results.append(check_a3_jel_keywords(qe_root))
    results.append(check_a4_figures(qe_root))
    results.append(check_a5_readme(qe_root))
    results.append(check_a6_readme_pdf(qe_root))
    
    # Section B: Replication Package
    results.append(check_b1_reproduce_script(qe_root))
    results.append(check_b2_data_files(qe_root))
    results.append(check_b3_license(qe_root))
    results.append(check_b4_zenodo_doi(qe_root))
    results.append(check_b5_environment_spec(qe_root))
    
    # Section D: Post-Acceptance
    results.append(check_d1_supplementary_appendix(qe_root))
    
    return results


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        qe_root_path = QE_ROOT
        print(f"No path provided, using default: {qe_root_path}", file=sys.stderr)
    else:
        qe_root_path = sys.argv[1]
    
    results = run_all_checks(qe_root_path)
    
    # Add metadata
    output = {
        "metadata": {
            "generated": datetime.now().isoformat(),
            "qe_root": qe_root_path,
            "checker_version": "1.0"
        },
        "results": results
    }
    
    # Output JSON
    print(json.dumps(output, indent=2))
    
    # Return exit code based on compliance
    has_non_compliant = any(r.get("status") == "non_compliant" for r in results if "status" in r)
    sys.exit(1 if has_non_compliant else 0)


if __name__ == "__main__":
    main()


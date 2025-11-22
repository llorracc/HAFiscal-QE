#!/usr/bin/env python3
"""
README-QE.md Generator

This script generates the HAFiscal-QE compliance checklist document
by running the compliance checker and formatting results as markdown.

Usage:
    python3 generate-hafiscal-qe.py /path/to/HAFiscal-QE

Output:
    Creates README-QE.md in HAFiscal-Latest/ directory
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any


# Path constants
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


STATUS_ICONS = {
    "compliant": "✅",
    "non_compliant": "❌",
    "warning": "⚠️",
    "pending": "⏳"
}


def run_compliance_checker(qe_root_path: str) -> Dict[str, Any]:
    """Run the compliance checker and return JSON results."""
    checker_script = Path(LATEST_ROOT) / "qe" / "check-qe-compliance.py"
    
    if not checker_script.exists():
        print(f"ERROR: Compliance checker not found: {checker_script}", file=sys.stderr)
        sys.exit(1)
    
    try:
        result = subprocess.run(
            ["python3", str(checker_script), qe_root_path],
            capture_output=True,
            text=True
        )
        
        # Parse JSON output (checker may exit with code 1 if non-compliant)
        return json.loads(result.stdout)
    except json.JSONDecodeError as e:
        print(f"ERROR: Failed to parse compliance checker output: {e}", file=sys.stderr)
        print(f"Output was: {result.stdout}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Failed to run compliance checker: {e}", file=sys.stderr)
        sys.exit(1)


def get_status_icon(status: str) -> str:
    """Get the emoji icon for a status."""
    return STATUS_ICONS.get(status, "❓")


def count_by_status(results: List[Dict[str, Any]]) -> Dict[str, int]:
    """Count requirements by status."""
    counts = {
        "compliant": 0,
        "non_compliant": 0,
        "warning": 0,
        "pending": 0
    }
    
    for result in results:
        status = result.get("status", "pending")
        if status in counts:
            counts[status] += 1
    
    return counts


def get_critical_items(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Get non-compliant items that require action."""
    return [r for r in results if r.get("status") == "non_compliant"]


def format_requirement_section(result: Dict[str, Any]) -> str:
    """Format a single requirement as a markdown section."""
    req_id = result.get("requirement_id", "?")
    requirement = result.get("requirement", "Unknown requirement")
    status = result.get("status", "pending")
    evidence = result.get("evidence", [])
    recommendation = result.get("recommendation", "No recommendation")
    files_checked = result.get("files_checked", [])
    
    icon = get_status_icon(status)
    status_label = status.replace("_", " ").title()
    
    # Create section header
    section = f"\n### {req_id}: {requirement} {icon}\n\n"
    
    # Add status
    section += f"**Status**: {icon} **{status_label}**\n\n"
    
    # Add evidence
    if evidence:
        section += "**Evidence**:\n"
        for e in evidence:
            section += f"- {e}\n"
        section += "\n"
    
    # Add files checked (as collapsible details)
    if files_checked and len(files_checked) <= 3:
        section += "**Files Checked**: "
        section += ", ".join([f"`{Path(f).name}`" for f in files_checked])
        section += "\n\n"
    
    # Add recommendation
    section += f"**Recommendation**: {recommendation}\n"
    
    return section


def organize_by_category(results: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Organize results by category (A, B, C, D, E)."""
    categories = {
        "A": {"title": "Manuscript Formatting", "items": []},
        "B": {"title": "Replication Package", "items": []},
        "C": {"title": "Submission", "items": []},
        "D": {"title": "Post-Acceptance & Production", "items": []},
        "E": {"title": "Final Verification", "items": []},
    }
    
    for result in results:
        req_id = result.get("requirement_id", "?")
        category = req_id.split(".")[0] if "." in req_id else "E"
        
        if category in categories:
            categories[category]["items"].append(result)
    
    return categories


def generate_markdown(compliance_data: Dict[str, Any], qe_root_path: str) -> str:
    """Generate the complete README-QE.md markdown document."""
    metadata = compliance_data.get("metadata", {})
    results = compliance_data.get("results", [])
    
    # Get summary statistics
    counts = count_by_status(results)
    critical_items = get_critical_items(results)
    
    # Start building markdown
    md = "# HAFiscal-QE Submission Compliance Checklist\n\n"
    
    # Metadata
    md += f"**Generated**: {metadata.get('generated', 'Unknown')}\n"
    md += f"**HAFiscal-QE Location**: `{qe_root_path}`\n"
    md += f"**Checker Version**: {metadata.get('checker_version', '1.0')}\n\n"
    
    md += "---\n\n"
    
    # Quick Status Dashboard
    md += "## 📊 Quick Status Dashboard\n\n"
    
    total_items = sum(counts.values())
    md += f"| Status | Count | Percentage |\n"
    md += f"|--------|-------|------------|\n"
    md += f"| ✅ Compliant | {counts['compliant']} | {counts['compliant']/total_items*100:.0f}% |\n"
    md += f"| ⚠️ Warning | {counts['warning']} | {counts['warning']/total_items*100:.0f}% |\n"
    md += f"| ❌ Non-Compliant | {counts['non_compliant']} | {counts['non_compliant']/total_items*100:.0f}% |\n"
    md += f"| ⏳ Pending | {counts['pending']} | {counts['pending']/total_items*100:.0f}% |\n"
    md += f"| **TOTAL** | **{total_items}** | **100%** |\n\n"
    
    # Critical Items
    if critical_items:
        md += f"### 🔴 Critical Items Requiring Action ({len(critical_items)})\n\n"
        for item in critical_items:
            req_id = item.get("requirement_id", "?")
            requirement = item.get("requirement", "Unknown")
            md += f"- **{req_id}**: {requirement}\n"
        md += "\n"
    else:
        md += "### ✨ No Critical Issues Found\n\n"
        md += "All essential requirements are met or need only minor improvements.\n\n"
    
    md += "---\n\n"
    
    # Organize and display by category
    categories = organize_by_category(results)
    
    for cat_id in sorted(categories.keys()):
        category = categories[cat_id]
        items = category["items"]
        
        if not items:
            continue
        
        # Category header
        md += f"## {cat_id}. {category['title']}\n\n"
        
        # Category summary
        cat_counts = count_by_status(items)
        md += f"**Status**: "
        md += f"✅ {cat_counts['compliant']} | "
        md += f"⚠️ {cat_counts['warning']} | "
        md += f"❌ {cat_counts['non_compliant']} | "
        md += f"⏳ {cat_counts['pending']}\n\n"
        
        # Individual requirements
        for item in sorted(items, key=lambda x: x.get("requirement_id", "?")):
            md += format_requirement_section(item)
        
        md += "---\n\n"
    
    # Critical Path to Submission
    if critical_items or counts['warning'] > 0:
        md += "## 🎯 Critical Path to Submission\n\n"
        
        action_count = 1
        for item in critical_items:
            req_id = item.get("requirement_id", "?")
            recommendation = item.get("recommendation", "No recommendation")
            md += f"{action_count}. ❌ **{req_id}**: {recommendation}\n"
            action_count += 1
        
        # Add warnings as lower priority
        warning_items = [r for r in results if r.get("status") == "warning"]
        for item in warning_items[:3]:  # Show top 3 warnings
            req_id = item.get("requirement_id", "?")
            recommendation = item.get("recommendation", "No recommendation")
            md += f"{action_count}. ⚠️ **{req_id}**: {recommendation}\n"
            action_count += 1
        
        md += "\n---\n\n"
    
    # References
    md += "## 📚 References\n\n"
    md += "- [QE Data & Code Policy](https://www.econometricsociety.org/publications/es-data-editor-website/data-and-code-availability-policy)\n"
    md += "- [Zenodo ES Repository](https://zenodo.org/communities/es-replication-repository/)\n"
    md += "- [QE LaTeX Template](https://github.com/vtex-soft/texsupport.econometricsociety-qe)\n"
    md += "- [Editorial Express](https://editorialexpress.com/cgi-bin/e-editor/e-submit_v21.cgi?dbase=qe)\n\n"
    
    md += "---\n\n"
    
    # Footer
    md += f"**Checklist Version**: 1.0\n"
    md += f"**Generated by**: `qe/generate-hafiscal-qe.py`\n"
    md += f"**Source Requirements**: `Private/Submissions/QE/00-final-submission-checklist_UPDATED_20251012.md`\n"
    md += f"**Compliance Checker**: `qe/check-qe-compliance.py`\n\n"
    
    md += "---\n\n"
    
    md += "## How to Update This Checklist\n\n"
    md += "To regenerate this checklist after making changes:\n\n"
    md += "```bash\n"
    md += "cd HAFiscal-Latest/qe\n"
    md += "./deploy-hafiscal-qe-compliance.sh\n"
    md += "```\n\n"
    md += "The script will:\n"
    md += "1. Archive the old version to `old/HAFiscal-QE_<timestamp>.md`\n"
    md += "2. Run the compliance checker on HAFiscal-QE/\n"
    md += "3. Generate a new README-QE.md\n"
    md += "4. Deploy it to both HAFiscal-Latest/ and HAFiscal-QE/\n"
    
    return md


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        qe_root_path = QE_ROOT
        print(f"No path provided, using default: {qe_root_path}", file=sys.stderr)
    else:
        qe_root_path = sys.argv[1]
    
    print(f"Running compliance checker on: {qe_root_path}", file=sys.stderr)
    
    # Run compliance checker
    compliance_data = run_compliance_checker(qe_root_path)
    
    print(f"Generating markdown document...", file=sys.stderr)
    
    # Generate markdown
    markdown = generate_markdown(compliance_data, qe_root_path)
    
    # Write to output file
    output_file = Path(LATEST_ROOT) / "README-QE.md"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(markdown)
    
    print(f"✓ Generated: {output_file}", file=sys.stderr)
    print(f"✓ {len(markdown)} characters written", file=sys.stderr)
    
    # Also print to stdout for piping
    print(markdown)


if __name__ == "__main__":
    main()


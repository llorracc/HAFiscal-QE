#!/usr/bin/env python3
"""
clean-qe-document.py

Cleans up the consolidated QE document to remove HAFiscal-specific commands
that are incompatible with the QE document class.
"""

import re
import sys
from pathlib import Path

def clean_qe_document(input_path: Path, output_path: Path) -> None:
    """
    Clean up QE document by removing incompatible commands.
    
    Args:
        input_path: Path to input consolidated file
        output_path: Path to output cleaned file
    """
    with open(input_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Remove \ifdefined\HAFShortVersion blocks
    content = re.sub(r'\\ifdefined\\HAFShortVersion.*?\\fi', '', content, flags=re.DOTALL)
    
    # Remove \ifthenelse{\boolean{Web}} blocks more carefully
    # Pattern 1: \ifthenelse{\boolean{Web}}{...}{...} with balanced braces
    def remove_ifthenelse_web(text):
        while True:
            match = re.search(r'\\ifthenelse\{\\boolean\{Web\}\}', text)
            if not match:
                break
            start_pos = match.start()
            pos = match.end()
            
            # Skip first brace group (condition already matched)
            # Find second brace group (true branch)
            brace_count = 0
            true_start = pos
            while pos < len(text):
                if text[pos] == '{':
                    if brace_count == 0:
                        true_start = pos + 1
                    brace_count += 1
                elif text[pos] == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        true_end = pos
                        break
                pos += 1
            
            # Find third brace group (false branch)
            pos += 1
            brace_count = 0
            false_start = pos
            while pos < len(text):
                if text[pos] == '{':
                    if brace_count == 0:
                        false_start = pos + 1
                    brace_count += 1
                elif text[pos] == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        false_end = pos
                        break
                pos += 1
            
            # Replace with false branch content
            false_content = text[false_start:false_end]
            text = text[:start_pos] + false_content + text[pos+1:]
        
        return text
    
    content = remove_ifthenelse_web(content)
    
    # Remove any remaining Web boolean references
    content = re.sub(r'\\boolean\{Web\}', 'false', content)
    
    # Remove \hypertarget{...}{} commands (redundant with proper sectioning)
    content = re.sub(r'\\hypertarget\{[^}]*\}\{\}', '', content)
    
    # Remove \input commands that reference missing files
    content = re.sub(r'\\input\{@resources/[^}]*\}', '', content)
    content = re.sub(r'\\input\{@local/[^}]*\}', '', content)
    content = re.sub(r'\\input\{.*?\.econtexRoot\}', '', content)
    
    # Handle verbatimwrite blocks - replace with direct content
    def process_verbatimwrite(match):
        # Extract the content between begin and end verbatimwrite
        content_between = match.group(2)
        # Return just the content without the verbatimwrite wrapper
        return content_between
    
    # Pattern to match \begin{verbatimwrite}{filename}...content...\end{verbatimwrite}\input{filename}
    pattern = r'\\begin\{verbatimwrite\}\{([^}]+)\}(.*?)\\end\{verbatimwrite\}\s*\\input\{[^}]+\}'
    content = re.sub(pattern, process_verbatimwrite, content, flags=re.DOTALL)
    
    # Remove any remaining \EqDir references
    content = re.sub(r'\\input\{\\EqDir/[^}]*\}', '', content)
    
    # Remove extra standalone closing braces on their own lines
    content = re.sub(r'^\s*\}\s*$', '', content, flags=re.MULTILINE)
    content = re.sub(r'^\s*\}\s*\}\s*$', '', content, flags=re.MULTILINE)
    
    # Fix extra closing braces at the end
    # Count opening and closing braces to ensure balance
    brace_count = 0
    for char in content:
        if char == '{':
            brace_count += 1
        elif char == '}':
            brace_count -= 1
    
    # Remove extra closing braces if needed
    if brace_count < 0:
        # Remove trailing closing braces
        content = content.rstrip()
        while brace_count < 0 and content.endswith('}'):
            content = content[:-1].rstrip()
            brace_count += 1
    
    # Ensure bibliography command is present before \appendix
    if '\\bibliography{' not in content:
        # Find where to insert bibliography (before appendix section)
        appendix_match = re.search(r'(\\appendix|\\section\{No Splurge Appendix\})', content)
        if appendix_match:
            insert_pos = appendix_match.start()
            bibliography_cmd = '\n% Bibliography\n\\bibliography{HAFiscal}\n\n'
            content = content[:insert_pos] + bibliography_cmd + content[insert_pos:]
    
    # Add JEL classification if missing
    if '\\begin{keyword}[class=JEL]' not in content:
        # Find where to insert JEL codes (after regular keywords)
        keyword_match = re.search(r'\\end\{keyword\}', content)
        if keyword_match:
            insert_pos = keyword_match.end()
            jel_section = '\n\n\\begin{keyword}[class=JEL]\n\\kwd{E21}\n\\kwd{E62}\n\\kwd{H31}\n\\end{keyword}'
            content = content[:insert_pos] + jel_section + content[insert_pos:]
    
    # Clean up any \endinput commands that might interfere
    content = re.sub(r'\\endinput\s*', '', content)
    
    # Ensure document ends properly
    if not content.rstrip().endswith('\\end{document}'):
        content = content.rstrip() + '\n\n\\end{document}\n'
    
    # Write cleaned content
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"Document cleaned and saved to: {output_path}")

def main():
    """Main entry point."""
    # Default paths
    script_dir = Path(__file__).parent
    qe_root = script_dir.parent.parent
    input_file = qe_root / "working" / "HAFiscal-QE-consolidated.tex"
    output_file = qe_root / "working" / "HAFiscal-QE-clean.tex"
    
    # Allow command line override
    if len(sys.argv) > 1:
        input_file = Path(sys.argv[1])
    if len(sys.argv) > 2:
        output_file = Path(sys.argv[2])
    
    print(f"Input: {input_file}")
    print(f"Output: {output_file}")
    
    if not input_file.exists():
        print(f"Error: Input file not found at {input_file}")
        sys.exit(1)
    
    clean_qe_document(input_file, output_file)

if __name__ == "__main__":
    main() 
#!/usr/bin/env python3
"""
extract-metadata.py

Extracts structured metadata from HAFiscal LaTeX files for QE submission.
Parses the custom \Title, \Author, etc. commands and generates QE-formatted output.
"""

import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple

class MetadataExtractor:
    def __init__(self):
        self.metadata = {
            'title': '',
            'runtitle': '',
            'authors': [],
            'addresses': {},
            'keywords': [],
            'jel': [],
            'funding': ''
        }
    
    def extract_from_file(self, filepath: Path) -> None:
        """Extract metadata from a LaTeX file."""
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Extract Title
        title_match = re.search(r'\\Title\{(.+?)\}', content, re.DOTALL)
        if title_match:
            self.metadata['title'] = title_match.group(1).strip()
        
        # Extract RunTitle
        runtitle_match = re.search(r'\\RunTitle\{(.+?)\}', content, re.DOTALL)
        if runtitle_match:
            self.metadata['runtitle'] = runtitle_match.group(1).strip()
        
        # Extract Authors
        author_pattern = r'\\Author\{([^}]+)\}\{([^}]+)\}\{([^}]+)\}\{([^}]+)\}'
        for match in re.finditer(author_pattern, content):
            self.metadata['authors'].append({
                'fnms': match.group(1).strip(),
                'snm': match.group(2).strip(),
                'email': match.group(3).strip(),
                'affil': match.group(4).strip()
            })
        
        # Extract Addresses
        address_pattern = r'\\Address\{([^}]+)\}\{([^}]*)\}\{([^}]+)\}'
        for match in re.finditer(address_pattern, content):
            addr_id = match.group(1).strip()
            self.metadata['addresses'][addr_id] = {
                'div': match.group(2).strip(),
                'org': match.group(3).strip()
            }
        
        # Extract Keywords
        keywords_match = re.search(r'\\Keywords\{(.+?)\}', content, re.DOTALL)
        if keywords_match:
            # Split by semicolon and clean up
            keywords_text = keywords_match.group(1).strip()
            # Remove newlines and extra spaces
            keywords_text = ' '.join(keywords_text.split())
            self.metadata['keywords'] = [k.strip() for k in keywords_text.split(';')]
        
        # Extract JEL codes
        jel_match = re.search(r'\\JEL\{(.+?)\}', content, re.DOTALL)
        if jel_match:
            jel_text = jel_match.group(1).strip()
            self.metadata['jel'] = [j.strip() for j in jel_text.split(';')]
        
        # Extract Funding
        funding_match = re.search(r'\\Funding\{(.+?)\}', content, re.DOTALL)
        if funding_match:
            funding_text = funding_match.group(1).strip()
            # Clean up newlines
            self.metadata['funding'] = ' '.join(funding_text.split())
    
    def generate_qe_frontmatter(self) -> str:
        """Generate QE-formatted frontmatter from extracted metadata."""
        lines = []
        
        # Title
        lines.append(f"\\title{{{self.metadata['title']}}}")
        lines.append(f"\\runtitle{{{self.metadata['runtitle']}}}")
        lines.append("")
        
        # Authors
        lines.append("\\begin{aug}")
        for i, author in enumerate(self.metadata['authors'], 1):
            affil = author['affil']
            lines.append(f"\\author[{affil}]{{\\fnms{{{author['fnms']}}}~\\snm{{{author['snm']}}}\\ead[label=e{i}]{{{author['email']}}}}}")
        lines.append("")
        
        # Addresses
        lines.append("% Addresses")
        for addr_id, addr in self.metadata['addresses'].items():
            lines.append(f"\\address[{addr_id}]{{%")
            if addr['div']:
                lines.append(f"\\orgdiv{{{addr['div']}}},")
            lines.append(f"\\orgname{{{addr['org']}}}}}")
            lines.append("")
        
        lines.append("\\end{aug}")
        lines.append("")
        
        # Funding
        if self.metadata['funding']:
            lines.append("\\begin{funding}")
            lines.append(self.metadata['funding'])
            lines.append("\\end{funding}")
            lines.append("")
        
        # Keywords
        if self.metadata['keywords']:
            lines.append("\\begin{keyword}")
            for kw in self.metadata['keywords']:
                lines.append(f"\\kwd{{{kw}}}")
            lines.append("\\end{keyword}")
            lines.append("")
        
        # JEL codes
        if self.metadata['jel']:
            lines.append("\\begin{JEL}")
            for jel in self.metadata['jel']:
                lines.append(f"\\jel{{{jel}}}")
            lines.append("\\end{JEL}")
        
        return '\n'.join(lines)

def main():
    """Main entry point."""
    if len(sys.argv) < 3:
        print("Usage: extract-metadata.py <input_tex_file> <output_file>")
        sys.exit(1)
    
    input_file = Path(sys.argv[1])
    output_file = Path(sys.argv[2])
    
    if not input_file.exists():
        print(f"Error: Input file {input_file} not found")
        sys.exit(1)
    
    extractor = MetadataExtractor()
    
    # Extract from main file and titlepage if it exists
    extractor.extract_from_file(input_file)
    
    # Also check titlepage if it's a separate file
    titlepage = input_file.parent / "Subfiles" / "HAFiscal-titlepage.tex"
    if titlepage.exists():
        extractor.extract_from_file(titlepage)
    
    # Generate QE frontmatter
    qe_frontmatter = extractor.generate_qe_frontmatter()
    
    # Write output
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(qe_frontmatter)
    
    print(f"Metadata extracted and QE frontmatter written to {output_file}")

if __name__ == "__main__":
    main() 
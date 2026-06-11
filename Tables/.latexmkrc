# -*- mode: perl; -*-
# Simple .latexmkrc that loads the necessary configuration files using Perl's 'do' command
use File::Basename;
use Cwd qw(abs_path);

# Find $latexmkroot by searching upward for @resources/latexmk
# This works whether this file is:
#   - The root .latexmkrc (finds @resources/ immediately)
#   - A symlink in a subdirectory pointing to root (symlink resolved, finds immediately)
#   - A materialized copy in a subdirectory (searches upward to find root)
our $latexmkroot = dirname(abs_path(__FILE__));
for (1..5) {
    last if -d "$latexmkroot/\@resources/latexmk";
    $latexmkroot = dirname($latexmkroot);
}

# Set PDF mode as default (use pdflatex, not latex/DVI)
# This ensures all compilations produce PDF directly and can include PDF/PNG/JPG images
$pdf_mode = 1;  # 1=pdflatex, 2=ps2pdf, 3=dvipdf, 4=lualatex, 5=xelatex


# Load the circular crossrefs handler
do "$latexmkroot/\@resources/latexmk/latexmkrc/latexmkrc_for-projects-with-circular-crossrefs";

# Load the bibtex wrapper (also loaded by circular-crossrefs, but explicit here for clarity)
# do "$latexmkroot/\@resources/latexmk/latexmkrc/latexmkrc_using_bibtex_wrapper";

# Load the environment variable injection (for BUILD_MODE, etc.)
do "$latexmkroot/\@resources/latexmk/latexmkrc/latexmkrc_env_variable_injection";

# Load PDF viewer management (quit viewers before compilation)
do "$latexmkroot/.latexmkrc_quit-pdf-viewers-on-latexmk_-c";
# DEBUGGED: 20250904-1813h PDF viewer management infrastructure completed - enhanced performance, cross-platform compatibility

# -*- mode: perl; -*-
# Simple .latexmkrc that loads the necessary configuration files using Perl's 'do' command

# Load the circular crossrefs handler
do './@resources/latexmk/latexmkrc/latexmkrc_for-projects-with-circular-crossrefs';

# Load the bibtex wrapper
do './@resources/latexmk/latexmkrc/latexmkrc_using_bibtex_wrapper';

# Load the environment variable injection (for BUILD_MODE, etc.)
do './@resources/latexmk/latexmkrc/latexmkrc_env_variable_injection';

# Load PDF viewer management (quit viewers before compilation)
do './.latexmkrc_quit-pdf-viewers-on-latexmk_-c';
# DEBUGGED: 20250904-1813h PDF viewer management infrastructure completed - enhanced performance, cross-platform compatibility

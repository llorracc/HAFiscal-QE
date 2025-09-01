# Add Metadata Commands to HAFiscal-Latest/@local/local.sty

Add the following commands to the end of `HAFiscal-Latest/@local/local.sty`:

```latex
% ==============================================================================
% Structured Metadata Commands for Journal Submissions
% ==============================================================================
% These commands provide structured metadata that can be parsed for various
% journal submission formats (e.g., Quantitative Economics).
% In the standard build, these are no-ops that don't affect the output.

% Internal storage command (not for direct use)
\newcommand{\Metadata}[1]{} % No-op for regular builds

% Document metadata
\newcommand{\Title}[1]{\Metadata{title={#1}}}
\newcommand{\RunTitle}[1]{\Metadata{runtitle={#1}}}

% Author metadata - fnms=first names, snm=surname, email, affil=affiliation label
\newcommand{\Author}[4]{\Metadata{author={fnms=#1,snm=#2,email=#3,affil=#4}}}

% Address metadata - id=label, div=division/department, org=organization
\newcommand{\Address}[3]{\Metadata{addr={id=#1,div=#2,org=#3}}}

% Subject classification
\newcommand{\Keywords}[1]{\Metadata{keywords={#1}}}
\newcommand{\JEL}[1]{\Metadata{jel={#1}}}

% Funding/acknowledgments
\newcommand{\Funding}[1]{\Metadata{funding={#1}}}

% ==============================================================================
```

These commands will:
- Be invisible in normal builds (no-op)
- Provide structured data for the QE transformation scripts to parse
- Be maintainable alongside the regular document content
- Support future journal submission formats 
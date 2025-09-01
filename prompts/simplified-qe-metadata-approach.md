# Simplified Metadata Approach

## Add to HAFiscal-Latest/@local/local.sty

```latex
% ==============================================================================
% Journal Metadata (only used when BUILD_MODE=QE)
% ==============================================================================

% Define conditional for QE mode
\newif\ifQEMode
\QEModefalse  % Default: not in QE mode

% Check if BuildMode is QE
\ifdefined\BuildMode
  \ifnum\pdfstrcmp{\BuildMode}{QE}=0
    \QEModetrue
  \fi
\fi

% QE-specific metadata (always defined but only used in QE mode)
\newcommand{\QEtitle}{Welfare and Spending Effects of Consumption Stimulus Policies}
\newcommand{\QEruntitle}{Heterogeneous Agent Fiscal Policy}

% QE author block (ready to use in QE template)
\newcommand{\QEauthorblock}{%
\begin{aug}
\author[jhu-econ]{\fnms{Christopher D.}~\snm{Carroll}\ead[label=e1]{ccarroll@jhu.edu}}
\author[fed]{\fnms{Edmund}~\snm{Crawley}\ead[label=e2]{edmund.s.crawley@frb.gov}}
\author[jhu-econ]{\fnms{William}~\snm{Du}\ead[label=e3]{wdu9@jhu.edu}}
\author[bundesbank]{\fnms{Ivan}~\snm{Frankovic}\ead[label=e4]{ivan.frankovic@bundesbank.de}}
\author[ssb-hofimar]{\fnms{H{\aa}kon}~\snm{Tretvoll}\ead[label=e5]{Hakon.Tretvoll@ssb.no}}

\address[jhu-econ]{%
\orgdiv{Department of Economics},
\orgname{Johns Hopkins University}}

\address[fed]{%
\orgname{Federal Reserve Board}}

\address[bundesbank]{%
\orgname{Deutsche Bundesbank}}

\address[ssb-hofimar]{%
\orgname{Statistics Norway and HOFIMAR at BI Norwegian Business School}}
\end{aug}
}

% QE keywords block
\newcommand{\QEkeywords}{%
\begin{keyword}
\kwd{Fiscal Policy}
\kwd{Heterogeneous Agents}
\kwd{Marginal Propensity to Consume}
\kwd{Consumption Stimulus}
\kwd{Unemployment Insurance}
\end{keyword}
}

% QE JEL codes
\newcommand{\QEJEL}{%
\begin{JEL}
\jel{E62}
\jel{H31}
\jel{D14}
\jel{E21}
\end{JEL}
}

% QE funding/acknowledgments
\newcommand{\QEfunding}{%
\begin{funding}
The views expressed in this paper are those of the authors and do not necessarily 
represent those of the Federal Reserve Board, the Deutsche Bundesbank and the 
Eurosystem, or Statistics Norway. This project has received funding from the 
European Research Council (ERC) under the European Union's Horizon 2020 research 
and innovation programme (grant agreement No. 851891) and from the Research 
Council of Norway (grant No. 326419).
\end{funding}
}

% QE abstract (pulls from the existing abstract file)
\newcommand{\QEabstract}{%
\begin{abstract}
\input{HAFiscal-Abstract.txt}
\end{abstract}
}
```

## Then HAFiscal-QE.tex becomes very simple:

```latex
% QE Submission Version
\documentclass[qe,nameyear,draft]{econsocart}
\RequirePackage[colorlinks,citecolor=blue,urlcolor=blue]{hyperref}

% Load all the HAFiscal packages and definitions
\usepackage{@local/local}

% Load any additional QE-specific packages
\startlocaldefs
% ... any QE-specific setup ...
\endlocaldefs

\begin{document}

\begin{frontmatter}

\title{\QEtitle}
\runtitle{\QEruntitle}

\QEauthorblock

\QEabstract

\QEkeywords

\QEJEL

\QEfunding

\end{frontmatter}

% Main content (consolidated from subfiles)
\input{HAFiscal-QE-content}

% Bibliography
\bibliographystyle{qe}
\bibliography{HAFiscal}

\end{document}
```

## Benefits

1. **No Python parsing needed** - Everything is in LaTeX
2. **Single source of truth** - Metadata lives with the document
3. **Easy to maintain** - Just update local.sty when metadata changes
4. **Clean separation** - QE metadata only used when building QE version
5. **Reusable** - Could add similar blocks for other journals 
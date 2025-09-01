# Update HAFiscal-titlepage.tex with Metadata Commands

Add the following metadata commands to `HAFiscal-Latest/Subfiles/HAFiscal-titlepage.tex` after line 10 (after the `\ifthenelse{\boolean{Web}}` block):

```latex
% ==============================================================================
% Structured Metadata for Journal Submissions
% ==============================================================================
\Title{Welfare and Spending Effects of Consumption Stimulus Policies}
\RunTitle{Heterogeneous Agent Fiscal Policy}

% Authors (first names, surname, email, affiliation label)
\Author{Christopher D.}{Carroll}{ccarroll@jhu.edu}{jhu-econ}
\Author{Edmund}{Crawley}{edmund.s.crawley@frb.gov}{fed}
\Author{William}{Du}{wdu9@jhu.edu}{jhu-econ}
\Author{Ivan}{Frankovic}{ivan.frankovic@bundesbank.de}{bundesbank}
\Author{H{\aa}kon}{Tretvoll}{Hakon.Tretvoll@ssb.no}{ssb-hofimar}

% Affiliations (label, department, organization)
\Address{jhu-econ}{Department of Economics}{Johns Hopkins University}
\Address{fed}{}{Federal Reserve Board}
\Address{bundesbank}{}{Deutsche Bundesbank}
\Address{ssb-hofimar}{}{Statistics Norway and HOFIMAR at BI Norwegian Business School}

% Keywords and JEL codes
\Keywords{Fiscal Policy; Heterogeneous Agents; Marginal Propensity to Consume; 
         Consumption Stimulus; Unemployment Insurance; Tax Policy}
\JEL{E62; H31; D14; E21}

% Funding acknowledgment
\Funding{This project has received funding from the European Research Council (ERC) 
under the European Union's Horizon 2020 research and innovation programme 
(grant agreement No. 851891) and from the Research Council of Norway (grant No. 326419).}
% ==============================================================================

% Continue with existing \title command...
```

Note: 
- Keep the existing `\title` and `\author` commands unchanged - they control the actual display
- The new metadata commands are purely for structured data extraction
- Update the JEL codes from "D.., E.." to proper codes like "E62; H31; D14; E21"
- The keywords should be semicolon-separated for easy parsing 
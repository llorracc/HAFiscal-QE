# Code to Produce empirical results

## Quick Start

### Download Data
```bash
./download_scf_data.sh
```

### Run Analysis
```bash
# Python version (recommended)
python3 make_liquid_wealth.py

# Or Stata version
stata -b make_liquid_wealth.do
```

## Files in this directory

### Analysis Scripts

- **make_liquid_wealth.py**: Python script that produces the empirical numbers used in the paper from the 2004 SCF. Equivalent to the Stata version but doesn't require Stata.

- **make_liquid_wealth.do**: Original Stata script that produces the numbers we use in the paper from the 2004 wave of the Survey of Consumer Finance.

- **download_scf_data.sh**: Shell script to automatically download the required SCF 2004 data files from the Federal Reserve website.

### Data Files

- **rscfp2004.dta**: The summary extract data for SCF 2004 in Stata format. 
- **rscfp2004.csv**: The summary extract data for SCF 2004 in csv format. 

- **ccbal_answer.dta**: Small file created from the full public data set (main survey data) in Stata format. 
- **ccbal_answer.csv**: Small file created from the full public data set (main survey data) in csv format. 


The data is also available from the website of the Board of Governors of the Federal Reserve System at this link:

[Federal Reserve Board - 2004 Survey of Consumer Finances](https://www.federalreserve.gov/econres/scf_2004.htm)

Download and unzip the following files to reproduce our results:

- Main survey data: Stata version - **scf2004s.zip** $\Rightarrow$ **p04i6.dta**

- Summary Extract Data set: Stata format - **scfp2004s.zip** $\Rightarrow$ **rscfp2004.dta**

Place these .dta files in the same directory as **make_liquid_wealth.do** before running the file.

**Note**: When releasing new waves of the SCF, the summary extract data for older versions are inflation-adjusted. At the time of writing, downloading the data gives a file where all dollar variables are inflation-adjusted to 2022 dollars. With an adjusted version of **rscfp2004.dta** the numbers marked **USD** below will not replicate the numbers used in the paper. 

## Empirical results

The file **make_liquid_wealth.do** creates a measure of liquid wealth and produces the following numbers referred to in the paper:

- Percent of population in each education group (Table 2, Panel B)

- Percent of liquid wealth held by each education group (Table 5, Panel A)

- **USD**: Average quarterly permanent income (PI) of "newborn" agents (Table 2, Panel B)

- Standard deviation of log(quarterly PI) of "newborn" agents (Table 2, Panel B)

- Median liquid wealth / quarterly PI in each education group (Table 4, Panel B)

- 20th, 40th, 60th and 80th percentile points of the Lorenz curve of liquid wealth for the entire population and for each education group separately
  (**Note**: These points are not reported in the paper, but they appear in the plots in Figure 2.)

- Percent of liquid wealth held by four wealth quartiles (Table 5, Panel B)

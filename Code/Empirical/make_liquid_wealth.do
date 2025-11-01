// File to construct liquid wealth from 2004 SCF dataset 

clear 
cd C:/Github/HAFiscal-Latest/Code/Empirical // Point to directory containing this file and data files

// First: Create the file ccbal_answer if it does not exist 
// Assumption: The file p04i6.dta exists in this directory.
if !fileexists("ccbal_answer.dta") {
	// Create file with answer to how often total balance is paid: 
	use Y1 X432 using p04i6, replace 
	rename Y1 y1
	rename X432 x432
	save ccbal_answer, replace
}

scalar do_plots = 0 	// = 1: produce plots of Lorenz curves in Stata (note: Stata plots are not used in the paper)
						// = 0: no plots, just the numbers that appear in the paper/code
// Load data: 
use yy1 y1 wgt age educ edcl norminc liq cds nmmf stocks bond ccbal install veh_inst using rscfp2004, replace  

merge 1:1 y1 using ccbal_answer
replace ccbal = 0 if x432 == 1
drop x432 _merge 

// Sample selection: 
bysort yy1: egen meanAge = mean(age)
drop age 
rename meanAge age 
drop if age < 25 | 62 < age 
drop if norminc < 0 

// Generate liquid wealth: 
gen tempLiqWealthInst = liq*1.05 + cds + nmmf + stocks + bond - ccbal - (install-veh_inst)
gen tempLiqWealthKaplan = liq*1.05 + cds + nmmf + stocks + bond - ccbal
// Cash adjustment: see Kaplan et al. (2014, Eca), appendix B1
drop liq cds nmmf stocks bond ccbal install veh_inst

// Generate education classifications:
gen myEd = 1*(edcl==1) + 2*(edcl==2 | edcl ==3) + 3*(edcl==4)
// 1=no high school, 2=high school/some college, 3=college 
gen myEdText = "No high school" if myEd == 1
replace myEdText = "High school/some college" if myEd == 2
replace myEdText = "College" if myEd == 3
drop educ edcl 

bysort yy1: egen liqWealthInst = mean(tempLiqWealthInst)
bysort yy1: egen liqWealthKaplan = mean(tempLiqWealthKaplan)
bysort yy1: egen permInc = mean(norminc)
bysort yy1: egen weight = mean(wgt*5)
drop tempLiqWealthInst tempLiqWealthKaplan norminc wgt
keep if mod(y1,5)==1 
drop y1

// More sample selection - lowest percentile of permInc 
egen totalWeight = sum(weight)
gen normweight = weight/totalWeight
sort permInc 
gen sumW = sum(normweight)
drop if sumW < 0.05
drop totalWeight normweight sumW 

// *****************************************************************************
// Before proceeding, decide which liquid wealth measure to use: 
scalar includeInstallmentDebt = 0
if includeInstallmentDebt == 1 {
	gen liqWealth = liqWealthInst	
} 
else {	// Measure of liquid wealth used in the paper
	gen liqWealth = liqWealthKaplan
}
drop if liqWealth < 0
//gen liqWealth_byPI = liqWealth/permInc	// may want to use liquid wealth scaled by permanent income

egen totalWeight = total(weight)  // need to redo this after dropping observations
gen normweight = weight/totalWeight
format totalWeight normweight %12.0g
bysort myEd: egen edfrac = total(normweight)
gen edWeight = normweight/edfrac  // weight within this education group

// *****************************************************************************
sort liqWealth yy1
gen sumNormW = sum(normweight)*100
egen totLiqWealth = total(normweight*liqWealth)  // egen -> sum gives total sum, use total instead	
bysort myEd: egen totLiqWealth_ed = total(normweight*liqWealth)
bysort myEd: gen fracLiqWealth_ed = round(totLiqWealth_ed/totLiqWealth, 0.001)*100

// *****************************************************************************
// Display percent of population and wealth share in each education group
bysort myEd: gen edfrac_display = round(edfrac, 0.001)*100
bysort myEd: su edfrac_display
bysort myEd: su fracLiqWealth_ed
//drop edfrac_display fracLiqWealth_ed

// *****************************************************************************
// Mean and standard deviation of distribution of initial PI at age 25
gen permIncQ = permInc/4
gen logPermIncQ = log(permIncQ)

// Assume log-normal distribution, but report exp(mean) to get number in $1000
gen mean_initial_income = .	
gen sdev_initial_logIncome = . 
quietly forval ii=1/3 {
	su logPermIncQ [w=edWeight] if myEd==`ii' & age==25, detail
	replace mean_initial_income = exp(r(mean)) if myEd==`ii' & age==25
	replace sdev_initial_logIncome = r(sd) if myEd==`ii' & age==25
}
bysort myEd: gen mean_initial_income_display = round(mean_initial_income/1000,0.1)
bysort myEd: gen sdev_initial_logIncome_display = round(sdev_initial_logIncome,0.01)

bysort myEd: su mean_initial_income_display if age==25
bysort myEd: su sdev_initial_logIncome_display if age==25
//drop mean_initial_income sdev_initial_logIncome

// *****************************************************************************
// Estimation targets for liquid wealth distribution

// Individual liquid wealth/PI:
gen indLWoPI = liqWealth/permInc 

// Weighted median liquid wealth/PI by education: 
gen wtMedLWoPI = . 
quietly forval ii=1/3 {
    su indLWoPI [w=edWeight] if myEd==`ii', detail 
	replace wtMedLWoPI = r(p50) if myEd == `ii'
}
bysort myEd: gen wtMedLWoPI_display = round(wtMedLWoPI,0.0001)*100
bysort myEd: su wtMedLWoPI_display
gen wtMedLWoPIquarterly = wtMedLWoPI_display * 4
bysort myEd: su wtMedLWoPIquarterly

// Lorenz curve for all households (not an estimation target)
sort liqWealth yy1 
gen weightedLW_all = normweight*liqWealth
egen totWeightedLW_all = total(weightedLW_all)
gen sumLWall = sum(weightedLW_all/totWeightedLW_all)*100

if do_plots == 1 {
	grstyle init
	grstyle set grid
	if includeInstallmentDebt == 1 {
		twoway line sumLWall sumNormW, title("Lorenz curves (inst.)") note("") name(LorenzAll, replace) ///
		xtitle("Cumulative fraction of population") ytitle("Cumulative fraction of liquid wealth") /// 
		ylabel(#5) xlabel(#5)
	}
	else {
		twoway line sumLWall sumNormW, title("Lorenz curves") note("") name(LorenzAll, replace) ///
		xtitle("Cumulative fraction of population") ytitle("Cumulative fraction of liquid wealth") /// 
		ylabel(#5) xlabel(#5)
	}
}
preserve 
keep if sumNormW < 80
quietly su sumLWall, detail 
gen LC_all_80 = round(r(max), 0.01)
keep if sumNormW < 60
quietly su sumLWall, detail 
gen LC_all_60 = round(r(max), 0.01)
keep if sumNormW < 40 
quietly su sumLWall, detail 
gen LC_all_40 = round(r(max), 0.01)
keep if sumNormW < 20
quietly su sumLWall, detail 
gen LC_all_20 = round(r(max), 0.01)
su LC_all_20 LC_all_40 LC_all_60 LC_all_80
restore 

// Save to .csv for plots
outsheet yy1 myEd sumNormW sumLWall using ../../Figures/Data/LorenzAll.csv, replace  

// Lorenz curves for each education group
bysort myEd: gen weightedLW = edWeight*liqWealth
bysort myEd: egen totWeightedLW = total(weightedLW)
bysort myEd (liqWealth yy1): gen sumLW = sum(weightedLW/totWeightedLW)*100
bysort myEd (liqWealth yy1): gen sumEdW = sum(edWeight)*100  

if do_plots == 1 {
	grstyle init 
	grstyle set grid
	if includeInstallmentDebt == 1 {
		twoway line sumLW sumEdW, sort by(myEdText, title("Lorenz curves (inst.)") note("")) name(LorCombined, replace) ///
		xtitle("Cumulative fraction of population") ytitle("Cumulative fraction of liquid wealth") /// 
		ylabel(#5) xlabel(#5)
	}
	else {
		twoway line sumLW sumEdW, sort by(myEdText, title("Lorenz curves") note("")) name(LorCombined, replace) ///
		xtitle("Cumulative fraction of population") ytitle("Cumulative fraction of liquid wealth") /// 
		ylabel(#5) xlabel(#5)
	}
}
forvalues xx = 1/3 {
	preserve 
	keep if myEd == `xx'
	display myEdText
	keep if sumEdW < 80
	quietly su sumLW, detail 
	gen LC_ed_80 = round(r(max), 0.01)
	keep if sumEdW < 60
	quietly su sumLW, detail 
	gen LC_ed_60 = round(r(max), 0.01)
	keep if sumEdW < 40 
	quietly su sumLW, detail 
	gen LC_ed_40 = round(r(max), 0.01)
	keep if sumEdW < 20
	quietly su sumLW, detail 
	gen LC_ed_20 = round(r(max), 0.01)
	su LC_ed_20 LC_ed_40 LC_ed_60 LC_ed_80
	restore 
}

// Save to .csv for plots
outsheet yy1 myEd sumEdW sumLW using ../../Figures/Data/LorenzEd.csv, replace 


// *****************************************************************************
// Calculate wealth in each wealth quartile 
xtile quartileW = weightedLW_all, nq(4)
egen sum_byWQ = total(weightedLW_all), by(quartileW)
gen pct_byWQ = round(sum_byWQ/totWeightedLW_all*100, 0.01)
tabulate quartileW, summarize(pct_byWQ)


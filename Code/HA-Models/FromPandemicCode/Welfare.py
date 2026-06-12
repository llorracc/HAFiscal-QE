# -*- coding: utf-8 -*-
"""
Welfare calculations for HAFiscal policy experiments.

Math reference (shorthand "math-derive"):
    history/20260331-mathematical-derivations-TM-MC-convergence.md
Appendix reference (shorthand "math-derive-appendix"):
    history/20260331-mathematical-derivations-appendix.md

@author: edmun
"""
from Parameters import return_parameters
from OtherFunctions import load_pickle, get_simulation_diff, save_as_pickle_under_var_name
# Candidate-routing (QE-baseline freeze): rendered tables are written as
# `_candidate` siblings unless HAFISCAL_PROMOTE=1. See generated_output.py.
from generated_output import open_generated
import numpy as np
import pandas as pd

def Welfare_Results(saved_results_dir,table_dir,Parametrization='Baseline'):
    """Compute welfare results for the policy experiments and write LaTeX tables.

    Loads the pickled scenario results (base, Check/UI/TaxCut x recession/AD
    variants) from `saved_results_dir` via load_pickle, evaluates the welfare
    measures (felicity-based social-welfare aggregates and the consumption-
    equivalent welfare cells; see math-derive-appendix), and writes
    welfare1.tex ... welfare6.tex (plus welfare6-SplurgeComp.tex for the
    Splurge0 parametrization) to `table_dir`.

    Parametrization is forwarded to Parameters.return_parameters; *_PVSame
    variants read their non-PVSame comparison results from figs_dir_FullRun.
    Side effects only (files read/written); no return value.
    """
    [max_recession_duration, Rspell, Rfree_base, figs_dir_FullRun, CRRA]  = return_parameters(Parametrization=Parametrization,OutputFor='_Output_Results.py')
    
    
    folder_AD           = saved_results_dir
    if Parametrization.find('PVSame')>0:
        folder_nonPVSame         = figs_dir_FullRun
    else:
        folder_nonPVSame         = saved_results_dir
    
    base_results                        = load_pickle('base_results',saved_results_dir,locals())
    check_results                       = load_pickle('Check_results',saved_results_dir,locals())
    UI_results                          = load_pickle('UI_results',folder_nonPVSame,locals())
    TaxCut_results                      = load_pickle('TaxCut_results',saved_results_dir,locals())
    
    recession_results                   = load_pickle('recession_results',folder_nonPVSame,locals())
    recession_results_AD                = load_pickle('recession_results_AD',folder_nonPVSame,locals())
    recession_UI_results                = load_pickle('recessionUI_results',folder_nonPVSame,locals())       
    recession_UI_results_AD             = load_pickle('recessionUI_results_AD',folder_nonPVSame,locals())  
    recession_Check_results             = load_pickle('recessionCheck_results',saved_results_dir,locals())       
    recession_Check_results_AD          = load_pickle('recessionCheck_results_AD',saved_results_dir,locals())
    recession_TaxCut_results            = load_pickle('recessionTaxCut_results',saved_results_dir,locals())
    recession_TaxCut_results_AD         = load_pickle('recessionTaxCut_results_AD',saved_results_dir,locals())

    recession_all_results                   = load_pickle('recession_all_results',folder_nonPVSame,locals())
    recession_all_results_AD                = load_pickle('recession_all_results_AD',folder_nonPVSame,locals())
    recession_UI_all_results                = load_pickle('recessionUI_all_results',folder_nonPVSame,locals())       
    recession_UI_all_results_AD             = load_pickle('recessionUI_all_results_AD',folder_nonPVSame,locals())  
    recession_Check_all_results             = load_pickle('recessionCheck_all_results',saved_results_dir,locals())       
    recession_Check_all_results_AD          = load_pickle('recessionCheck_all_results_AD',saved_results_dir,locals())
    recession_TaxCut_all_results            = load_pickle('recessionTaxCut_all_results',saved_results_dir,locals())
    recession_TaxCut_all_results_AD         = load_pickle('recessionTaxCut_all_results_AD',saved_results_dir,locals())

    NPV_AddInc_Rec_Check                = get_simulation_diff(recession_results,recession_Check_results,'NPV_AggIncome') 
    NPV_AddInc_UI_Rec                   = get_simulation_diff(recession_results,recession_UI_results,'NPV_AggIncome') # Policy expenditure
    NPV_AddInc_Rec_TaxCut               = get_simulation_diff(recession_results,recession_TaxCut_results,'NPV_AggIncome')
    
    NPV_AddInc_Check                = get_simulation_diff(base_results,check_results,'NPV_AggIncome') 
    NPV_AddInc_UI                   = get_simulation_diff(base_results,UI_results,'NPV_AggIncome') # Policy expenditure
    NPV_AddInc_TaxCut               = get_simulation_diff(base_results,TaxCut_results,'NPV_AggIncome')
    
    # See math-derive-appendix (CRRA-utility): u(c) = c^(1-rho)/(1-rho)
    # implements (eq:utility-fn) of BUGS_private/HAFiscal_splurge_budget_inconsistency/models_CDC_and_ESC.md
    def felicity(cons):
        if CRRA==1:
            out = np.log(cons)
        else:
            out = (cons**(1-CRRA))/(1-CRRA)
        return out

    # The block below applies `felicity()` to `cLvl_all_splurge` and combines
    # the resulting per-agent utility series into the welfare bang-for-buck
    # measure W(policy, Rec, AD) — the (welfare6) of the paper. The composition
    # `felicity(cLvl_all_splurge)` is what makes this aggregator A (the shared
    # public-good form) rather than the strict-additive aggregator B; see
    # BUGS_private/HAFiscal_splurge_budget_inconsistency/welfare_code_and_paper_text_on_interpretation.md.
    # implements (welfare6) of BUGS_private/HAFiscal_splurge_budget_inconsistency/models_CDC_and_ESC.md
    base_welfare   = felicity(base_results['cLvl_all_splurge'])
    check_welfare  = felicity(check_results['cLvl_all_splurge'])
    UI_welfare     = felicity(UI_results['cLvl_all_splurge'])
    TaxCut_welfare = felicity(TaxCut_results['cLvl_all_splurge'])
    
    
    R_persist = 1.-1./Rspell
    recession_prob_array = np.array([R_persist**t*(1-R_persist) for t in range(max_recession_duration)])
    
    recession_welfare = np.sum(np.array([felicity(recession_all_results[t]['cLvl_all_splurge'])*recession_prob_array[t]  for t in range(max_recession_duration)]), axis=0)
    recession_welfare_AD = np.sum(np.array([felicity(recession_all_results_AD[t]['cLvl_all_splurge'])*recession_prob_array[t]  for t in range(max_recession_duration)]), axis=0)  
    recession_UI_welfare = np.sum(np.array([felicity(recession_UI_all_results[t]['cLvl_all_splurge'])*recession_prob_array[t]  for t in range(max_recession_duration)]), axis=0)  
    recession_UI_welfare_AD = np.sum(np.array([felicity(recession_UI_all_results_AD[t]['cLvl_all_splurge'])*recession_prob_array[t]  for t in range(max_recession_duration)]), axis=0)  
    recession_TaxCut_welfare = np.sum(np.array([felicity(recession_TaxCut_all_results[t]['cLvl_all_splurge'])*recession_prob_array[t]  for t in range(max_recession_duration)]), axis=0)
    recession_TaxCut_welfare_AD = np.sum(np.array([felicity(recession_TaxCut_all_results_AD[t]['cLvl_all_splurge'])*recession_prob_array[t]  for t in range(max_recession_duration)]), axis=0) 
    recession_Check_welfare = np.sum(np.array([felicity(recession_Check_all_results[t]['cLvl_all_splurge'])*recession_prob_array[t]  for t in range(max_recession_duration)]), axis=0)  
    recession_Check_welfare_AD = np.sum(np.array([felicity(recession_Check_all_results_AD[t]['cLvl_all_splurge'])*recession_prob_array[t]  for t in range(max_recession_duration)]), axis=0) 
    
    # See math-derive-appendix (SP-welfare): W = sum_t beta^t sum_i u(c_it)
    def SP_welfare(individual_welfare, SP_discount_rate):
        welfare = np.sum(np.sum(individual_welfare, axis=1)*np.array([SP_discount_rate**t for t in range(individual_welfare.shape[0])]))
        return welfare
    
    SP_discount_rate = 1/Rfree_base[0]
    Check_welfare_impact = SP_welfare(check_welfare, SP_discount_rate)-SP_welfare(base_welfare, SP_discount_rate)
    Check_welfare_impact_recession = SP_welfare(recession_Check_welfare, SP_discount_rate)-SP_welfare(recession_welfare, SP_discount_rate)
    Check_welfare_impact_recession_AD = SP_welfare(recession_Check_welfare_AD, SP_discount_rate)-SP_welfare(recession_welfare_AD, SP_discount_rate)
    
    UI_welfare_impact = SP_welfare(UI_welfare, SP_discount_rate)-SP_welfare(base_welfare, SP_discount_rate)
    UI_welfare_impact_recession = SP_welfare(recession_UI_welfare, SP_discount_rate)-SP_welfare(recession_welfare, SP_discount_rate)
    UI_welfare_impact_recession_AD = SP_welfare(recession_UI_welfare_AD, SP_discount_rate)-SP_welfare(recession_welfare_AD, SP_discount_rate)
    
    TaxCut_welfare_impact = SP_welfare(TaxCut_welfare, SP_discount_rate)-SP_welfare(base_welfare, SP_discount_rate)
    TaxCut_welfare_impact_recession = SP_welfare(recession_TaxCut_welfare, SP_discount_rate)-SP_welfare(recession_welfare, SP_discount_rate)
    TaxCut_welfare_impact_recession_AD = SP_welfare(recession_TaxCut_welfare_AD, SP_discount_rate)-SP_welfare(recession_welfare_AD, SP_discount_rate)
    
    # See math-derive-appendix (welfare-per-dollar): Delta_W / NPV_Gov_Spending
    Check_welfare_per_dollar_AD  = (Check_welfare_impact_recession_AD  - Check_welfare_impact) /NPV_AddInc_Rec_Check[-1]
    UI_welfare_per_dollar_AD     = (UI_welfare_impact_recession_AD     - UI_welfare_impact)    /NPV_AddInc_UI_Rec[-1]
    TaxCut_welfare_per_dollar_AD = (TaxCut_welfare_impact_recession_AD - TaxCut_welfare_impact)/NPV_AddInc_Rec_TaxCut[-1]
    
    Check_welfare_per_dollar2_AD = Check_welfare_impact_recession_AD/NPV_AddInc_Rec_Check[-1] - Check_welfare_impact/NPV_AddInc_Check[-1]
    UI_welfare_per_dollar2_AD = UI_welfare_impact_recession_AD/NPV_AddInc_UI_Rec[-1] - UI_welfare_impact/NPV_AddInc_UI[-1]
    TaxCut_welfare_per_dollar2_AD = TaxCut_welfare_impact_recession_AD/NPV_AddInc_Rec_TaxCut[-1] - TaxCut_welfare_impact/NPV_AddInc_TaxCut[-1]
     
    Check_welfare_per_dollar  = (Check_welfare_impact_recession  - Check_welfare_impact) /NPV_AddInc_Rec_Check[-1]
    UI_welfare_per_dollar     = (UI_welfare_impact_recession     - UI_welfare_impact)    /NPV_AddInc_UI_Rec[-1]
    TaxCut_welfare_per_dollar = (TaxCut_welfare_impact_recession - TaxCut_welfare_impact)/NPV_AddInc_Rec_TaxCut[-1]
    
    Check_welfare_per_dollar2 = Check_welfare_impact_recession/NPV_AddInc_Rec_Check[-1] - Check_welfare_impact/NPV_AddInc_Check[-1]
    UI_welfare_per_dollar2 = UI_welfare_impact_recession/NPV_AddInc_UI_Rec[-1] - UI_welfare_impact/NPV_AddInc_UI[-1]
    TaxCut_welfare_per_dollar2 = TaxCut_welfare_impact_recession/NPV_AddInc_Rec_TaxCut[-1] - TaxCut_welfare_impact/NPV_AddInc_TaxCut[-1]
     
    all_welfare_results = pd.DataFrame([[Check_welfare_per_dollar_AD,UI_welfare_per_dollar_AD,TaxCut_welfare_per_dollar_AD],
    [Check_welfare_per_dollar2_AD,UI_welfare_per_dollar2_AD,TaxCut_welfare_per_dollar2_AD],
    [Check_welfare_per_dollar,UI_welfare_per_dollar,TaxCut_welfare_per_dollar],
    [Check_welfare_per_dollar2,UI_welfare_per_dollar2,TaxCut_welfare_per_dollar2]])
    
    
    def mystr3(number):
        if not np.isnan(number):
            out = "{:.3f}".format(number)
        else:
            out = ''
        return out
    output  ="\\begin{tabular}{@{}lccc@{}} \n"
    output +="\\toprule \n"
    output +="                          & Check      & UI    & Tax Cut    \\\\  \\midrule \n"
    output +="$\\mathcal{G}(\\text{policy})$ & "  + mystr3(Check_welfare_per_dollar) + "  & "+ mystr3(UI_welfare_per_dollar) +  "  & "+  mystr3(TaxCut_welfare_per_dollar)  + "     \\\\ \n"
    output +="$\\mathcal{G}(AD,\\text{policy})$ & "  + mystr3(Check_welfare_per_dollar_AD) + "  & "+ mystr3(UI_welfare_per_dollar_AD) +  "  & "+  mystr3(TaxCut_welfare_per_dollar_AD)  + "     \\\\ \n"
    output +="\\end{tabular}  \n"
    with open_generated(table_dir+'welfare1.tex') as f:
        f.write(output)
        f.close()
    output  ="\\begin{tabular}{@{}lccc@{}} \n"
    output +="\\toprule \n"
    output +="                          & Check      & UI    & Tax Cut    \\\\  \\midrule \n"
    output +="$\\mathcal{G}(\\text{policy})$ & "  + mystr3(Check_welfare_per_dollar2) + "  & "+ mystr3(UI_welfare_per_dollar2) +  "  & "+  mystr3(TaxCut_welfare_per_dollar2)  + "     \\\\ \n"
    output +="$\\mathcal{G}(AD,\\text{policy})$ & "  + mystr3(Check_welfare_per_dollar2_AD) + "  & "+ mystr3(UI_welfare_per_dollar2_AD) +  "  & "+  mystr3(TaxCut_welfare_per_dollar2_AD)  + "     \\\\ \n"
    output +="\\end{tabular}  \n"
    with open_generated(table_dir+'welfare2.tex') as f:
        f.write(output)
        f.close()
    
    
    
    periods = base_results['cLvl_all_splurge'].shape[0]
    num_agents = base_results['cLvl_all_splurge'].shape[1]
    discount_array = np.transpose(np.array([[Rfree_base[0]**(-i) for i in range(periods)]]*num_agents))
    base_weights   = base_results['cLvl_all_splurge']*discount_array
    base_welfare   = felicity(base_results['cLvl_all_splurge'])
    check_welfare  = felicity(check_results['cLvl_all_splurge'])
    UI_welfare     = felicity(UI_results['cLvl_all_splurge'])
    TaxCut_welfare = felicity(TaxCut_results['cLvl_all_splurge'])
    
    # See math-derive-appendix (MRS-welfare): consumption-weighted welfare per dollar
    check_extra_welfare_ltd = np.sum((check_welfare - base_welfare)*base_weights)/np.sum((check_results['cLvl_all_splurge']-base_results['cLvl_all_splurge'])*discount_array)
    UI_extra_welfare_ltd    = np.sum((UI_welfare    - base_welfare)*base_weights)/np.sum((UI_results['cLvl_all_splurge']-base_results['cLvl_all_splurge'])*discount_array)
    TaxCut_extra_welfare_ltd = np.sum((TaxCut_welfare - base_welfare)*base_weights)/np.sum((TaxCut_results['cLvl_all_splurge']-base_results['cLvl_all_splurge'])*discount_array)
    
    smallUI = base_results['cLvl_all_splurge'] + (UI_results['cLvl_all_splurge'] - base_results['cLvl_all_splurge'])/10000
    smallUI_welfare     = np.log(smallUI)
    smallUI_extra_welfare    = np.sum((smallUI_welfare    - base_welfare)*base_weights)/np.sum((smallUI-base_results['cLvl_all_splurge'])*discount_array)
    
    check_extra_welfare = np.sum((check_welfare - base_welfare)*base_weights)/NPV_AddInc_Check[-1]
    UI_extra_welfare    = np.sum((UI_welfare    - base_welfare)*base_weights)/NPV_AddInc_UI[-1]
    TaxCut_extra_welfare = np.sum((TaxCut_welfare - base_welfare)*base_weights)/NPV_AddInc_TaxCut[-1]
    
    
    check_extra_welfare_AD = np.sum((recession_Check_welfare_AD - recession_welfare_AD)*base_weights)/NPV_AddInc_Rec_Check[-1]
    UI_extra_welfare_AD    = np.sum((recession_UI_welfare_AD    - recession_welfare_AD)*base_weights)/NPV_AddInc_UI_Rec[-1]
    TaxCut_extra_welfare_AD = np.sum((recession_TaxCut_welfare_AD - recession_welfare_AD)*base_weights)/NPV_AddInc_Rec_TaxCut[-1]
    
    check_extra_welfare_rec = np.sum((recession_Check_welfare - recession_welfare)*base_weights)/NPV_AddInc_Rec_Check[-1]
    UI_extra_welfare_rec    = np.sum((recession_UI_welfare    - recession_welfare)*base_weights)/NPV_AddInc_UI_Rec[-1]
    TaxCut_extra_welfare_rec = np.sum((recession_TaxCut_welfare - recession_welfare)*base_weights)/NPV_AddInc_Rec_TaxCut[-1]
    
    output  ="\\begin{tabular}{@{}lccc@{}} \n"
    output +="\\toprule \n"
    output +="                          & Check      & UI    & Tax Cut    \\\\  \\midrule \n"
    output +="$\\mathcal{G}3(\\text{policy})$ & "          + mystr3(check_extra_welfare)     + "  & "+ mystr3(UI_extra_welfare)     +  "  & "+  mystr3(TaxCut_extra_welfare)  + "     \\\\ \n"
    output +="$\\mathcal{G}3(Rec,\\text{policy})$ & "      + mystr3(check_extra_welfare_rec) + "  & "+ mystr3(UI_extra_welfare_rec) +  "  & "+  mystr3(TaxCut_extra_welfare_rec)  + "     \\\\ \n"
    output +="$\\mathcal{G}3(Rec, AD,\\text{policy})$ & "  + mystr3(check_extra_welfare_AD)  + "  & "+ mystr3(UI_extra_welfare_AD)  +  "  & "+  mystr3(TaxCut_extra_welfare_AD)  + "     \\\\ \n"
    output +="\\end{tabular}  \n"
    with open_generated(table_dir+'welfare3.tex') as f:
        f.write(output)
        f.close()
        
    #### METHOD 3
    W_c = 1/(1-SP_discount_rate)*base_welfare.shape[1]  #***************This assumes log utility. Need to fix this if we are going to use it
    P_c = 1/(1-SP_discount_rate)*base_results['AggCons'][0]
    
    Check_consumption_welfare   = (Check_welfare_impact_recession/W_c  - NPV_AddInc_Rec_Check[-1]/P_c)   - (Check_welfare_impact/W_c  - NPV_AddInc_Check[-1]/P_c) 
    UI_consumption_welfare      = (UI_welfare_impact_recession/W_c     - NPV_AddInc_UI_Rec[-1]/P_c)      - (UI_welfare_impact/W_c     - NPV_AddInc_UI[-1]/P_c) 
    TaxCut_consumption_welfare  = (TaxCut_welfare_impact_recession/W_c - NPV_AddInc_Rec_TaxCut[-1]/P_c)  - (TaxCut_welfare_impact/W_c - NPV_AddInc_TaxCut[-1]/P_c) 
    
    Check_consumption_welfare_AD   = (Check_welfare_impact_recession_AD/W_c  - NPV_AddInc_Rec_Check[-1]/P_c)   - (Check_welfare_impact/W_c  - NPV_AddInc_Check[-1]/P_c) 
    UI_consumption_welfare_AD      = (UI_welfare_impact_recession_AD/W_c     - NPV_AddInc_UI_Rec[-1]/P_c)      - (UI_welfare_impact/W_c     - NPV_AddInc_UI[-1]/P_c) 
    TaxCut_consumption_welfare_AD  = (TaxCut_welfare_impact_recession_AD/W_c - NPV_AddInc_Rec_TaxCut[-1]/P_c)  - (TaxCut_welfare_impact/W_c - NPV_AddInc_TaxCut[-1]/P_c) 
    
    #format as basis points
    def mystr3bp(number):
        if not np.isnan(number):
            out = "{:.3f}".format(number*10000)
        else:
            out = ''
        return out
    output  ="\\begin{tabular}{@{}lccc@{}} \n"
    output +="\\toprule \n"
    output +="                          & Stimulus check      & UI extension    & Tax cut    \\\\  \\midrule \n"
    output +="$\\mathcal{C}(Rec,\\text{policy})$ & "      + mystr3bp(Check_consumption_welfare)     + "  & "+ mystr3bp(UI_consumption_welfare)     +  "  & "+  mystr3bp(TaxCut_consumption_welfare)  + "     \\\\ \n"
    output +="$\\mathcal{C}(Rec, AD,\\text{policy})$ & "  + mystr3bp(Check_consumption_welfare_AD)  + "  & "+ mystr3bp(UI_consumption_welfare_AD)  +  "  & "+  mystr3bp(TaxCut_consumption_welfare_AD)  + "     \\\\ \n"
    output +="\\end{tabular}  \n"
    with open_generated(table_dir+'welfare4.tex') as f:
        f.write(output)
        f.close()
    
    print(NPV_AddInc_Check[-1])
    print(NPV_AddInc_UI[-1])
    print(NPV_AddInc_TaxCut[-1])
    
    #### METHOD 5 - suggested by referee 2 for QE
    W_c = 1/(1-SP_discount_rate)*base_welfare.shape[1] #*************************This assumes log utility. Need to fix this if we are going to use it
    P_c = 1/(1-SP_discount_rate)*base_results['AggCons'][0]
    
    Check_consumption_welfare5   = (Check_welfare_impact_recession/W_c) / (NPV_AddInc_Rec_Check[-1]/P_c)   - (Check_welfare_impact/W_c) / (NPV_AddInc_Check[-1]/P_c) 
    UI_consumption_welfare5      = (UI_welfare_impact_recession/W_c) / (NPV_AddInc_UI_Rec[-1]/P_c)      - (UI_welfare_impact/W_c) / (NPV_AddInc_UI[-1]/P_c) 
    TaxCut_consumption_welfare5  = (TaxCut_welfare_impact_recession/W_c) / (NPV_AddInc_Rec_TaxCut[-1]/P_c)  - (TaxCut_welfare_impact/W_c) / (NPV_AddInc_TaxCut[-1]/P_c) 
    
    Check_consumption_welfare_AD5   = (Check_welfare_impact_recession_AD/W_c) / (NPV_AddInc_Rec_Check[-1]/P_c)   - (Check_welfare_impact/W_c) / (NPV_AddInc_Check[-1]/P_c) 
    UI_consumption_welfare_AD5      = (UI_welfare_impact_recession_AD/W_c) / (NPV_AddInc_UI_Rec[-1]/P_c)      - (UI_welfare_impact/W_c) / (NPV_AddInc_UI[-1]/P_c) 
    TaxCut_consumption_welfare_AD5  = (TaxCut_welfare_impact_recession_AD/W_c) / (NPV_AddInc_Rec_TaxCut[-1]/P_c)  - (TaxCut_welfare_impact/W_c) / (NPV_AddInc_TaxCut[-1]/P_c) 
    
    #format as basis points
    def mystr3bp(number):
        if not np.isnan(number):
            out = "{:.3f}".format(number*10000)
        else:
            out = ''
        return out
    output  ="\\begin{tabular}{@{}lccc@{}} \n"
    output +="\\toprule \n"
    output +="                          & Stimulus check      & UI extension    & Tax cut    \\\\  \\midrule \n"
    output +="$\\mathcal{C}(Rec,\\text{policy})$ & "      + mystr3bp(Check_consumption_welfare5)     + "  & "+ mystr3bp(UI_consumption_welfare5)     +  "  & "+  mystr3bp(TaxCut_consumption_welfare5)  + "     \\\\ \n"
    output +="$\\mathcal{C}(Rec, AD,\\text{policy})$ & "  + mystr3bp(Check_consumption_welfare_AD5)  + "  & "+ mystr3bp(UI_consumption_welfare_AD5)  +  "  & "+  mystr3bp(TaxCut_consumption_welfare_AD5)  + "     \\\\ \n"
    output +="\\end{tabular}  \n"
    with open_generated(table_dir+'welfare5.tex') as f:
        f.write(output)
        f.close()
        
        
    #### METHOD 6 
    # See math-derive-appendix (MRS-welfare): MU-weighted welfare per dollar
    base_MU = (base_results['cLvl_all_splurge'] )**(-CRRA)
    NPV_AddCons_Rec_Check                = get_simulation_diff(recession_results,recession_Check_results,'NPV_AggCons') 
    NPV_AddCons_UI_Rec                   = get_simulation_diff(recession_results,recession_UI_results,'NPV_AggCons') 
    NPV_AddCons_Rec_TaxCut               = get_simulation_diff(recession_results,recession_TaxCut_results,'NPV_AggCons')
    
    NPV_AddCons_Check                = get_simulation_diff(base_results,check_results,'NPV_AggCons') 
    NPV_AddCons_UI                   = get_simulation_diff(base_results,UI_results,'NPV_AggCons')
    NPV_AddCons_TaxCut               = get_simulation_diff(base_results,TaxCut_results,'NPV_AggCons')
    
    # In the AD model, the cost of the tax cut is increased by 2% of the increase in income relative to the 
    NPV_AddInc_Rec_TaxCut_AD               = NPV_AddInc_Rec_TaxCut + 0.02*get_simulation_diff(recession_results_AD,recession_TaxCut_results_AD,'NPV_AggIncome')


    recession_Check_consumption_welfare6   = (np.sum(np.sum((recession_Check_welfare-recession_welfare)/base_MU,1)/NPV_AddInc_Rec_Check[-1]/Rfree_base[0]**np.arange(periods))) + (NPV_AddInc_Rec_Check[-1]-NPV_AddCons_Rec_Check[-1])/NPV_AddInc_Rec_Check[-1]
    Check_consumption_welfare6   = (np.sum(np.sum((check_welfare-base_welfare)/base_MU,1)/NPV_AddInc_Check[-1]/Rfree_base[0]**np.arange(periods))) + (NPV_AddInc_Check[-1]-NPV_AddCons_Check[-1])/NPV_AddInc_Check[-1]

    recession_UI_consumption_welfare6   = (np.sum(np.sum((recession_UI_welfare-recession_welfare)/base_MU,1)/NPV_AddInc_UI_Rec[-1]/Rfree_base[0]**np.arange(periods))) + (NPV_AddInc_UI_Rec[-1]-NPV_AddCons_UI_Rec[-1])/NPV_AddInc_UI_Rec[-1]
    UI_consumption_welfare6   = (np.sum(np.sum((UI_welfare-base_welfare)/base_MU,1)/NPV_AddInc_UI[-1]/Rfree_base[0]**np.arange(periods))) + (NPV_AddInc_UI[-1]-NPV_AddCons_UI[-1])/NPV_AddInc_UI[-1]

    recession_TaxCut_consumption_welfare6   = (np.sum(np.sum((recession_TaxCut_welfare-recession_welfare)/base_MU,1)/NPV_AddInc_Rec_TaxCut[-1]/Rfree_base[0]**np.arange(periods))) + (NPV_AddInc_Rec_TaxCut[-1]-NPV_AddCons_Rec_TaxCut[-1])/NPV_AddInc_Rec_TaxCut[-1]
    TaxCut_consumption_welfare6   = (np.sum(np.sum((TaxCut_welfare-base_welfare)/base_MU,1)/NPV_AddInc_TaxCut[-1]/Rfree_base[0]**np.arange(periods))) + (NPV_AddInc_TaxCut[-1]-NPV_AddCons_TaxCut[-1])/NPV_AddInc_TaxCut[-1]

    recession_Check_consumption_welfareAD6   = (np.sum(np.sum((recession_Check_welfare_AD -recession_welfare_AD)/base_MU,1)/NPV_AddInc_Rec_Check[-1] /Rfree_base[0]**np.arange(periods))) + (NPV_AddInc_Rec_Check[-1] -NPV_AddCons_Rec_Check[-1]) /NPV_AddInc_Rec_Check[-1]
    recession_UI_consumption_welfareAD6      = (np.sum(np.sum((recession_UI_welfare_AD    -recession_welfare_AD)/base_MU,1)/NPV_AddInc_UI_Rec[-1]    /Rfree_base[0]**np.arange(periods))) + (NPV_AddInc_UI_Rec[-1]    -NPV_AddCons_UI_Rec[-1])    /NPV_AddInc_UI_Rec[-1]
    recession_TaxCut_consumption_welfareAD6  = (np.sum(np.sum((recession_TaxCut_welfare_AD-recession_welfare_AD)/base_MU,1)/NPV_AddInc_Rec_TaxCut_AD[-1]/Rfree_base[0]**np.arange(periods))) + (NPV_AddInc_Rec_TaxCut_AD[-1]-NPV_AddCons_Rec_TaxCut[-1])/NPV_AddInc_Rec_TaxCut[-1]

    #format as 2 decimal places
    def mystr2dp(number):
        if not np.isnan(number):
            out = "{:.2f}".format(number)
        else:
            out = ''
        return out
    output  ="\\begin{tabular}{@{}lccc@{}} \n"
    output +="\\toprule \n"
    output +="                          & Stimulus check      & UI extension    & Tax cut    \\\\  \\midrule \n"
    # ui_norec is 0/0 BY CONSTRUCTION (the UI extension never activates in non-recession), so its
    # computed welfare is meaningless under EVERY method -> NEVER report it. Blank the Rec=0 UI cell
    # regardless of the value in UI_consumption_welfare6. (ui_rec / ui_rec_AD below ARE reported.)
    output +="$\\mathcal{W}(\\text{policy}, Rec=0, AD=0)$ & "    + mystr2dp(Check_consumption_welfare6)               + "  & "+ ""               +  "  & "+  mystr2dp(TaxCut_consumption_welfare6)  + "     \\\\ \n"
    output +="$\\mathcal{W}(\\text{policy}, Rec=1, AD=0)$ & "      + mystr2dp(recession_Check_consumption_welfare6)     + "  & "+ mystr2dp(recession_UI_consumption_welfare6)     +  "  & "+  mystr2dp(recession_TaxCut_consumption_welfare6)  + "     \\\\ \n"
    output +="$\\mathcal{W}(\\text{policy}, Rec=1, AD=1)$ & "  + mystr2dp(recession_Check_consumption_welfareAD6)  + "  & "+ mystr2dp(recession_UI_consumption_welfareAD6)  +  "  & "+  mystr2dp(recession_TaxCut_consumption_welfareAD6)  + "     \\\\ \\bottomrule \n"
    output +="\\end{tabular}  \n"
    with open_generated(table_dir+'welfare6.tex') as f:
        f.write(output)
        f.close()  
        
    # Save multiplier values for comparison
    if Parametrization=='Baseline':
        Welfare_Baseline_Results = {  
        'Check_consumption_welfare6':     mystr2dp(Check_consumption_welfare6),  
        'UI_consumption_welfare6':        mystr2dp(UI_consumption_welfare6),  
        'TaxCut_consumption_welfare6':    mystr2dp(TaxCut_consumption_welfare6),
        'recession_Check_consumption_welfare6':     mystr2dp(recession_Check_consumption_welfare6),  
        'recession_UI_consumption_welfare6':        mystr2dp(recession_UI_consumption_welfare6),  
        'recession_TaxCut_consumption_welfare6':    mystr2dp(recession_TaxCut_consumption_welfare6),
        'recession_Check_consumption_welfareAD6':  mystr2dp(recession_Check_consumption_welfareAD6),  
        'recession_UI_consumption_welfareAD6':     mystr2dp(recession_UI_consumption_welfareAD6),  
        'recession_TaxCut_consumption_welfareAD6': mystr2dp(recession_TaxCut_consumption_welfareAD6),
        }
        save_as_pickle_under_var_name(Welfare_Baseline_Results,table_dir,locals())

    # Comparison chart with baseline for Splurge = 0
    if Parametrization == 'Splurge0':
        import os
        Abs_Path              = os.getcwd()   
        Welfare_Baseline_Results = load_pickle('Welfare_Baseline_Results',Abs_Path+'/Tables/CRRA2/',locals())

        output  ="\\begin{tabular}{@{}lccc@{}} \n"
        output +="\\toprule \n"
        output +="                          & Stimulus check      & UI extension    & Tax cut    \\\\  \\midrule \n"
        output +="$\\mathcal{W}(\\text{policy}, Rec=0, AD=0)$ & "    + mystr2dp(Check_consumption_welfare6)             + "(" + Welfare_Baseline_Results['Check_consumption_welfare6']  + ")"  + "  & "+ mystr2dp(UI_consumption_welfare6)     + "(" + Welfare_Baseline_Results['UI_consumption_welfare6']  + ")"          +  "  & "+  mystr2dp(TaxCut_consumption_welfare6) + "(" + Welfare_Baseline_Results['TaxCut_consumption_welfare6'] + ")" + "     \\\\ \n"
        output +="$\\mathcal{W}(\\text{policy}, Rec=1, AD=0)$ & "      + mystr2dp(recession_Check_consumption_welfare6) + "(" + Welfare_Baseline_Results['recession_Check_consumption_welfare6']  + ")"    + "  & "+ mystr2dp(recession_UI_consumption_welfare6)   + "(" + Welfare_Baseline_Results['recession_UI_consumption_welfare6'] + ")"   +  "  & "+  mystr2dp(recession_TaxCut_consumption_welfare6) + "(" + Welfare_Baseline_Results['recession_TaxCut_consumption_welfare6'] + ")"  + "     \\\\ \n"
        output +="$\\mathcal{W}(\\text{policy}, Rec=1, AD=1)$ & "  + mystr2dp(recession_Check_consumption_welfareAD6)   + "(" + Welfare_Baseline_Results['recession_Check_consumption_welfareAD6'] + ")"   + "  & "+ mystr2dp(recession_UI_consumption_welfareAD6) + "(" + Welfare_Baseline_Results['recession_UI_consumption_welfareAD6'] + ")" +  "  & "+  mystr2dp(recession_TaxCut_consumption_welfareAD6) +  "(" + Welfare_Baseline_Results['recession_TaxCut_consumption_welfareAD6']  + ")"  + "     \\\\ \\bottomrule \n"
        output +="\\end{tabular}  \n"
        
        with open_generated(table_dir+'welfare6-SplurgeComp.tex') as f:
            f.write(output)
            f.close()  
             
        
        
        

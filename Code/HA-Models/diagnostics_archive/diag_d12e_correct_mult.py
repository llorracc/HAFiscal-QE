"""D-12e: Correct multiplier definition - normalize by gov spending (no-AD ΔY)."""
import pickle
import numpy as np

DIR = '/home/shared/github/llorracc/HAFiscal-Latest/Code/HA-Models/FromPandemicCode/Figures/Reduced_Run_diag_bug040_off'

def load(name):
    return pickle.load(open(f'{DIR}/{name}', 'rb'))

# Load all
rec_chk_mc_AD = load('recessionCheck_results_AD_MC.csv')
rec_chk_tm_AD = load('recessionCheck_results_AD_TM.csv')
rec_mc_AD = load('recession_results_AD_MC.csv')
rec_tm_AD = load('recession_results_AD_TM.csv')

# No-AD versions to compute "gov spending"
rec_chk_mc_noAD = load('recessionCheck_results_MC.csv')
rec_chk_tm_noAD = load('recessionCheck_results_TM.csv')
rec_mc_noAD = load('recession_results_MC.csv')
rec_tm_noAD = load('recession_results_TM.csv')

# 1st-round AD
rec_chk_mc_1AD = load('recessionCheck_results_firstRoundAD_MC.csv')
rec_chk_tm_1AD = load('recessionCheck_results_firstRoundAD_TM.csv')

print("MC vs TM-a CHECK multiplier (paper definition: ΔC(AD) / gov, where gov = ΔY(noAD))")
print("="*100)
print(f"{'horizon':<8} {'MC ΔC(AD)':<12} {'gov_MC':<10} {'MC mult':<10} {'TM ΔC(AD)':<12} {'gov_TM':<10} {'TM mult':<10} {'rel diff %':<12}")
for idx in [0, 1, 2, 3, 4, 5, 8, 11, 15, 19, 30, 39]:
    # MC: gov = Y(check noAD) - Y(rec noAD)
    gov_mc = rec_chk_mc_noAD['NPV_AggIncome'][idx] - rec_mc_noAD['NPV_AggIncome'][idx]
    gov_tm = rec_chk_tm_noAD['NPV_AggIncome'][idx] - rec_tm_noAD['NPV_AggIncome'][idx]

    dC_mc_AD = rec_chk_mc_AD['NPV_AggCons'][idx] - rec_mc_AD['NPV_AggCons'][idx]
    dC_tm_AD = rec_chk_tm_AD['NPV_AggCons'][idx] - rec_tm_AD['NPV_AggCons'][idx]

    mult_mc = dC_mc_AD / gov_mc if gov_mc != 0 else float('nan')
    mult_tm = dC_tm_AD / gov_tm if gov_tm != 0 else float('nan')
    rel = (mult_mc - mult_tm) / mult_tm * 100 if mult_tm != 0 else float('nan')

    print(f"{idx:<8} {dC_mc_AD:<12.2f} {gov_mc:<10.2f} {mult_mc:<10.4f} {dC_tm_AD:<12.2f} {gov_tm:<10.2f} {mult_tm:<10.4f} {rel:<+12.3f}")

print()
print("MC vs TM-a CHECK multiplier (1st-round AD: ΔC(1AD) / gov)")
print("="*100)
print(f"{'horizon':<8} {'MC ΔC(1AD)':<12} {'gov_MC':<10} {'MC mult':<10} {'TM ΔC(1AD)':<12} {'gov_TM':<10} {'TM mult':<10} {'rel diff %':<12}")
for idx in [0, 1, 2, 3, 4, 5, 8, 11, 15, 19, 30, 39]:
    gov_mc = rec_chk_mc_noAD['NPV_AggIncome'][idx] - rec_mc_noAD['NPV_AggIncome'][idx]
    gov_tm = rec_chk_tm_noAD['NPV_AggIncome'][idx] - rec_tm_noAD['NPV_AggIncome'][idx]

    rec_mc_1AD = load('recession_results_firstRoundAD_MC.csv')
    rec_tm_1AD = load('recession_results_firstRoundAD_TM.csv')

    dC_mc_1AD = rec_chk_mc_1AD['NPV_AggCons'][idx] - rec_mc_1AD['NPV_AggCons'][idx]
    dC_tm_1AD = rec_chk_tm_1AD['NPV_AggCons'][idx] - rec_tm_1AD['NPV_AggCons'][idx]

    mult_mc = dC_mc_1AD / gov_mc if gov_mc != 0 else float('nan')
    mult_tm = dC_tm_1AD / gov_tm if gov_tm != 0 else float('nan')
    rel = (mult_mc - mult_tm) / mult_tm * 100 if mult_tm != 0 else float('nan')

    print(f"{idx:<8} {dC_mc_1AD:<12.2f} {gov_mc:<10.2f} {mult_mc:<10.4f} {dC_tm_1AD:<12.2f} {gov_tm:<10.2f} {mult_tm:<10.4f} {rel:<+12.3f}")

print()
print("MC vs TM-a CHECK multiplier (NO AD: ΔC(noAD) / gov)")
print("="*100)
print(f"{'horizon':<8} {'MC ΔC(noAD)':<12} {'gov_MC':<10} {'MC mult':<10} {'TM ΔC(noAD)':<12} {'gov_TM':<10} {'TM mult':<10} {'rel diff %':<12}")
for idx in [0, 1, 2, 3, 4, 5, 8, 11, 15, 19, 30, 39]:
    gov_mc = rec_chk_mc_noAD['NPV_AggIncome'][idx] - rec_mc_noAD['NPV_AggIncome'][idx]
    gov_tm = rec_chk_tm_noAD['NPV_AggIncome'][idx] - rec_tm_noAD['NPV_AggIncome'][idx]

    dC_mc_noAD = rec_chk_mc_noAD['NPV_AggCons'][idx] - rec_mc_noAD['NPV_AggCons'][idx]
    dC_tm_noAD = rec_chk_tm_noAD['NPV_AggCons'][idx] - rec_tm_noAD['NPV_AggCons'][idx]

    mult_mc = dC_mc_noAD / gov_mc if gov_mc != 0 else float('nan')
    mult_tm = dC_tm_noAD / gov_tm if gov_tm != 0 else float('nan')
    rel = (mult_mc - mult_tm) / mult_tm * 100 if mult_tm != 0 else float('nan')

    print(f"{idx:<8} {dC_mc_noAD:<12.2f} {gov_mc:<10.2f} {mult_mc:<10.4f} {dC_tm_noAD:<12.2f} {gov_tm:<10.2f} {mult_tm:<10.4f} {rel:<+12.3f}")

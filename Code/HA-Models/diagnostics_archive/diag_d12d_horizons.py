"""D-12d: Compute MC vs TM-a multipliers at various NPV horizons."""
import pickle
import numpy as np

DIR = '/home/shared/github/llorracc/HAFiscal-Latest/Code/HA-Models/FromPandemicCode/Figures/Reduced_Run_diag_bug040_off'

def load(name):
    return pickle.load(open(f'{DIR}/{name}', 'rb'))

rec_chk_mc = load('recessionCheck_results_AD_MC.csv')
rec_chk_tm = load('recessionCheck_results_AD_TM.csv')
rec_mc = load('recession_results_AD_MC.csv')
rec_tm = load('recession_results_AD_TM.csv')

# Also no-AD
rec_chk_mc_noad = load('recessionCheck_results_MC.csv')
rec_chk_tm_noad = load('recessionCheck_results_TM.csv')
rec_mc_noad = load('recession_results_MC.csv')
rec_tm_noad = load('recession_results_TM.csv')

# 1st-round
rec_chk_mc_1ad = load('recessionCheck_results_firstRoundAD_MC.csv')
rec_chk_tm_1ad = load('recessionCheck_results_firstRoundAD_TM.csv')
rec_mc_1ad = load('recession_results_firstRoundAD_MC.csv')
rec_tm_1ad = load('recession_results_firstRoundAD_TM.csv')

print("MC vs TM-a CHECK multiplier at various NPV horizons (D-10 BUG-040 fix)")
print("="*100)

def show_horizons(label, rec_chk_mc, rec_chk_tm, rec_mc, rec_tm):
    print(f"\n--- {label} ---")
    print(f"{'horizon':<8} {'MC ΔC':<11} {'MC ΔY':<11} {'MC mult':<9} {'TM ΔC':<11} {'TM ΔY':<11} {'TM mult':<9} {'rel diff %':<10}")
    for idx in [0, 1, 2, 3, 4, 5, 8, 11, 15, 19, 30, 39]:
        npc_mc = rec_chk_mc['NPV_AggCons'][idx]
        npc_tm = rec_chk_tm['NPV_AggCons'][idx]
        nrc_mc = rec_mc['NPV_AggCons'][idx]
        nrc_tm = rec_tm['NPV_AggCons'][idx]
        npy_mc = rec_chk_mc['NPV_AggIncome'][idx]
        npy_tm = rec_chk_tm['NPV_AggIncome'][idx]
        nry_mc = rec_mc['NPV_AggIncome'][idx]
        nry_tm = rec_tm['NPV_AggIncome'][idx]

        dC_mc = npc_mc - nrc_mc
        dY_mc = npy_mc - nry_mc
        dC_tm = npc_tm - nrc_tm
        dY_tm = npy_tm - nry_tm

        mult_mc = dC_mc / dY_mc if dY_mc != 0 else float('nan')
        mult_tm = dC_tm / dY_tm if dY_tm != 0 else float('nan')
        rel = (mult_mc - mult_tm) / mult_tm * 100 if mult_tm != 0 else float('nan')

        print(f"{idx:<8} {dC_mc:<11.2f} {dY_mc:<11.2f} {mult_mc:<9.4f} {dC_tm:<11.2f} {dY_tm:<11.2f} {mult_tm:<9.4f} {rel:<+10.2f}")

show_horizons('NO AD', rec_chk_mc_noad, rec_chk_tm_noad, rec_mc_noad, rec_tm_noad)
show_horizons('1st ROUND AD', rec_chk_mc_1ad, rec_chk_tm_1ad, rec_mc_1ad, rec_tm_1ad)
show_horizons('FULL AD', rec_chk_mc, rec_chk_tm, rec_mc, rec_tm)

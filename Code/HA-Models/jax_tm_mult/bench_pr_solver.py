"""GPU speedup benchmark: PR #1779 AggShockMarkovConsumerTypeJAX vs HARK-numpy.
Step 1: default StateCount baseline + introspect per-state params for scaling.
Run with PYTHONPATH=<HARK-pr3 worktree>."""
import time, numpy as np, jax
print("jax backend:", jax.default_backend())

from HARK.ConsumptionSaving.ConsAggShockModel import (
    AggShockMarkovConsumerType, CobbDouglasMarkovEconomy)
from HARK.ConsumptionSaving.ConsAggShockModelJAX import AggShockMarkovConsumerTypeJAX

def build(AgentCls, seed=0):
    a = AgentCls(cycles=0, AgentCount=1000, seed=seed)
    e = CobbDouglasMarkovEconomy(agents=[a], seed=seed)
    e.give_agent_params()
    return a, e

def med_solve(agent, reps=5):
    agent.solve()  # warmup (JIT for JAX)
    ts = []
    for _ in range(reps):
        t0 = time.perf_counter(); agent.solve(); ts.append(time.perf_counter()-t0)
    return float(np.median(ts)), float(np.min(ts))

# HARK (numpy/numba)
a_np, e_np = build(AggShockMarkovConsumerType)
sc = a_np.MrkvArray.shape[0] if hasattr(a_np,'MrkvArray') else len(a_np.solution[0].cFunc)
hark_med, hark_min = med_solve(a_np)

# JAX (GPU)
a_jx, e_jx = build(AggShockMarkovConsumerTypeJAX)
jax_med, jax_min = med_solve(a_jx)

print(f"\n=== AggShockMarkov solve, StateCount={sc}, grid≈default ===")
print(f"  HARK (numba) : median {hark_med*1e3:8.2f} ms   min {hark_min*1e3:8.2f} ms")
print(f"  JAX  (GPU)   : median {jax_med*1e3:8.2f} ms   min {jax_min*1e3:8.2f} ms")
print(f"  speedup (HARK/JAX): {hark_med/jax_med:5.2f}x  (>1 = JAX faster)")

# introspect for scaling to StateCount~132
print("\n=== introspection for StateCount scaling ===")
for attr in ("MrkvArray","PermShkAggStd","TranShkAggStd","PermGroFacAgg","MrkvNow_init"):
    v = getattr(e_np, attr, getattr(a_np, attr, None))
    if v is not None:
        shp = getattr(v,'shape',None) or (len(v) if hasattr(v,'__len__') else '-')
        print(f"  economy.{attr}: shape/len = {shp}")
print("  aLvlGrid/aXtraGrid size:", len(getattr(a_np,'aXtraGrid',[])) or '-')

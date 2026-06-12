"""Step 2: sweep StateCount and time HARK vs JAX-GPU AggShockMarkov solve.
Enlarge the economy's Markov chain + tile per-state agg params; if give_agent_params
can't build N-state dynamics, record the failure and move on."""
import time, numpy as np, jax
print("jax backend:", jax.default_backend())
from HARK.ConsumptionSaving.ConsAggShockModel import (
    AggShockMarkovConsumerType, CobbDouglasMarkovEconomy)
from HARK.ConsumptionSaving.ConsAggShockModelJAX import AggShockMarkovConsumerTypeJAX

def enlarge(e, N):
    M = np.full((N, N), 0.1/(N-1)); np.fill_diagonal(M, 0.9); M /= M.sum(1, keepdims=True)
    e.MrkvArray = M
    for attr in ("PermShkAggStd", "TranShkAggStd", "PermGroFacAgg"):
        v = np.asarray(getattr(e, attr), dtype=float)
        setattr(e, attr, list(np.resize(v, N)))
    for attr in ("MrkvNow", "MrkvNow_init"):
        if hasattr(e, attr): setattr(e, attr, 0)

def build(AgentCls, N):
    a = AgentCls(cycles=0, AgentCount=1000, seed=0)
    e = CobbDouglasMarkovEconomy(agents=[a], seed=0)
    if N != 2: enlarge(e, N)
    e.give_agent_params()
    return a

def med(agent, reps=3):
    agent.solve()
    ts = [ (lambda t0: (agent.solve(), time.perf_counter()-t0)[1])(time.perf_counter()) for _ in range(reps) ]
    return float(np.median(ts))

print(f"\n{'N':>4} {'HARK_ms':>10} {'JAXgpu_ms':>10} {'speedup':>8}")
for N in (2, 4, 8, 16, 33, 66, 132):
    try:
        h = med(build(AggShockMarkovConsumerType, N))
        j = med(build(AggShockMarkovConsumerTypeJAX, N))
        print(f"{N:>4} {h*1e3:>10.1f} {j*1e3:>10.1f} {h/j:>7.2f}x")
    except Exception as ex:
        print(f"{N:>4}  FAILED: {type(ex).__name__}: {str(ex)[:60]}")

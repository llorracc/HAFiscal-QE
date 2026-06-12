#!/usr/bin/env python3
"""
Ask matsya whether recent upstream code changes affect its earlier rigor
critique of the HAFiscal household Bellman specification.

Submits a pre-digested summary of the changes (not raw diffs) into the
existing HAFiscal session, where matsya already has the Bellman spec.

Usage:
    python reproduce/matsya_submit_upstream_review.py

Requires:
    - matsya installed (pip install git+https://github.com/econ-ark/matsya.git)
    - MATSYA_TOKEN configured
"""

from matsya import ask

SESSION = "HAFiscal-Latest"

PROMPT = """\
Since you last examined the HAFiscal household Bellman specification,
significant upstream bug fixes and features have been merged into the
codebase. I want you to assess whether any of these changes affect the
critique items (A.1–A.8, B.1–B.4) you identified earlier.

Below is a summary of the changes. Most are about Monte Carlo vs
Transition Matrix alignment or aggregate-demand feedback — simulation
machinery that is downstream of the single-household Bellman. But some
touch the household problem definition itself. For each change, I note
what was modified.

## Changes that may touch the household problem definition

### 1. PermShk during unemployment (perm_shocks_during_unemployment flag)
Previously, unemployed agents always had PermShk=1.0 (no permanent shock).
A new opt-in flag `perm_shocks_during_unemployment=True` gives unemployed
agents the same PermShk distribution as employed agents, so that permanent
income is independent of the Markov employment state. This is needed for
the Harmenberg permanent-income normalization to be exact.

**Relevance to critique**: This changes the state-conditional shock
distribution ψ|z described in A.3 (joint law of shocks). When the flag
is True, ψ is independent of z. When False (paper default), ψ=1 for
unemployed states.

### 2. PermGroFac during unemployment (unemp_pLvl_grows_like_employed flag)
Similarly, a flag `unemp_pLvl_grows_like_employed=True` gives unemployed
agents the same permanent growth factor G as employed agents (instead of
PermGroFac=1.0). Combined with (1), this makes p fully independent of z.
Paper default is False (unemployed have G=1).

**Relevance to critique**: Strengthens A.3. The paper's implicit
specification (PermGroFac=1 for unemployed) is now the explicit default,
but can be toggled.

### 3. AggDemandFac in budget constraint (ad_in_budget flag)
New opt-in flag `ad_in_budget=True` scales the transitory shock by
AggDemandFac in get_states: mNrm += TranShk * (ADF - 1). Previously,
ADF was applied only in the aggregate consumption reporting layer, not
in the individual agent's perceived budget constraint during MC simulation.

**Relevance to critique**: This is about the aggregate-demand feedback
loop, which is out of scope for the household Bellman per se (the
household takes ADF as exogenous). But it changes what the agent
"sees" as its market resources. May be relevant to B.3 (aggregate
demand feedback specification).

### 4. mill_rule RecState timing fix (BUG-030)
The mill_rule that sows AggDemandFac to agents was using the current
period's recession state to compute next period's ADF. At
recession→recovery transitions, agents received the wrong ADF.

**Relevance to critique**: Pure simulation timing bug, unlikely to
affect the household Bellman specification.

### 5. Unemployment spike blending into half-step CondMrkv (BUG-029)
The initial unemployment spike at recession onset was not properly
blended into the conditional Markov transition matrix for the
half-step TM method.

**Relevance to critique**: TM implementation detail, not household
Bellman.

### 6. MC-shuffle (deterministic state counts)
New experimental feature using MarkovProcess.draw(shuffle=True) for
exact state-count matching between MC and TM. Eliminates sampling
noise on Markov state fractions.

**Relevance to critique**: MC implementation detail.

### 7. Single-source-of-truth income process (income_process_sst.py)
New module `income_process_sst.py` with `tile_PermGroFac_composite`
that builds PermGroFac arrays respecting all flags in one place,
imported by AggFiscalModel.py.

**Relevance to critique**: Improves code clarity for A.3 (shock
specification) but does not change the mathematical specification.

---

## My question

Given these changes, please re-examine your critique items A.1–A.8 and
B.1–B.4. For each item, state whether the upstream changes:
(a) resolve or partially resolve the issue,
(b) make the issue more complex (e.g., new flags create new degrees of
    freedom that the spec must document), or
(c) have no bearing on the issue.

Be concise — one or two sentences per item is sufficient.
"""


def main() -> None:
    print(f"Submitting upstream change summary to matsya session '{SESSION}'...")
    response = ask(PROMPT, session=SESSION)
    print("\n" + "=" * 72 + "\nMATSYA RESPONSE\n" + "=" * 72 + "\n")
    print(response)


if __name__ == "__main__":
    main()

# Phase 3 — 5D parallel equivalence check

Generated: 2026-05-16 15:21:27

## Pass criterion

`np.array_equal(seq, par) == True` for every per-duration series AND
every final reduced array. Zero floating-point tolerance.

## Results

## A=20 workers=1

```
=== Equivalence check A=20 workers=1 ===
  seq: reproduce/logs/5D_parallel/baseline_A20_seq.pkl (workers=1, A=20)
  par: reproduce/logs/5D_parallel/par_A20_w1.pkl (workers=1, A=20)

  [PASS] reduced/welfare_num_total: max|diff|=0.000e+00
  [PASS] reduced/AddInc_total_5D: max|diff|=0.000e+00
  [PASS] reduced/AddCons_total_5D: max|diff|=0.000e+00
  [PASS] rec_probs: max|diff|=0.000e+00
  [PASS] all per_duration series (11 durations × 5 arrays = 55 arrays bit-identical)

=== EQUIVALENCE PASS ===
```

## A=20 workers=4

```
=== Equivalence check A=20 workers=4 ===
  seq: reproduce/logs/5D_parallel/baseline_A20_seq.pkl (workers=1, A=20)
  par: reproduce/logs/5D_parallel/par_A20_w4.pkl (workers=4, A=20)

  [PASS] reduced/welfare_num_total: max|diff|=0.000e+00
  [PASS] reduced/AddInc_total_5D: max|diff|=0.000e+00
  [PASS] reduced/AddCons_total_5D: max|diff|=0.000e+00
  [PASS] rec_probs: max|diff|=0.000e+00
  [PASS] all per_duration series (11 durations × 5 arrays = 55 arrays bit-identical)

=== EQUIVALENCE PASS ===
```

## A=20 workers=11

```
=== Equivalence check A=20 workers=11 ===
  seq: reproduce/logs/5D_parallel/baseline_A20_seq.pkl (workers=1, A=20)
  par: reproduce/logs/5D_parallel/par_A20_w11.pkl (workers=11, A=20)

  [PASS] reduced/welfare_num_total: max|diff|=0.000e+00
  [PASS] reduced/AddInc_total_5D: max|diff|=0.000e+00
  [PASS] reduced/AddCons_total_5D: max|diff|=0.000e+00
  [PASS] rec_probs: max|diff|=0.000e+00
  [PASS] all per_duration series (11 durations × 5 arrays = 55 arrays bit-identical)

=== EQUIVALENCE PASS ===
```

## A=50 workers=1

```
=== Equivalence check A=50 workers=1 ===
  seq: reproduce/logs/5D_parallel/baseline_A50_seq.pkl (workers=1, A=50)
  par: reproduce/logs/5D_parallel/par_A50_w1.pkl (workers=1, A=50)

  [PASS] reduced/welfare_num_total: max|diff|=0.000e+00
  [PASS] reduced/AddInc_total_5D: max|diff|=0.000e+00
  [PASS] reduced/AddCons_total_5D: max|diff|=0.000e+00
  [PASS] rec_probs: max|diff|=0.000e+00
  [PASS] all per_duration series (11 durations × 5 arrays = 55 arrays bit-identical)

=== EQUIVALENCE PASS ===
```

## A=50 workers=11

```
=== Equivalence check A=50 workers=11 ===
  seq: reproduce/logs/5D_parallel/baseline_A50_seq.pkl (workers=1, A=50)
  par: reproduce/logs/5D_parallel/par_A50_w11.pkl (workers=11, A=50)

  [PASS] reduced/welfare_num_total: max|diff|=0.000e+00
  [PASS] reduced/AddInc_total_5D: max|diff|=0.000e+00
  [PASS] reduced/AddCons_total_5D: max|diff|=0.000e+00
  [PASS] rec_probs: max|diff|=0.000e+00
  [PASS] all per_duration series (11 durations × 5 arrays = 55 arrays bit-identical)

=== EQUIVALENCE PASS ===
```


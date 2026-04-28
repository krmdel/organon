#!/usr/bin/env python3 -u
"""Experiment 2: Wider range N=3500, select best 2000 from 2131 squarefree keys."""
import numpy as np, json, time, gc
from scipy.optimize import linprog
from evaluator import evaluate

def get_sqfree(n):
    s = np.ones(n+1, dtype=bool)
    for p in range(2, int(n**0.5)+1):
        for m in range(p*p, n+1, p*p): s[m] = False
    return np.array([k for k in range(2, n+1) if s[k]])

N = 3500
BUDGET = 2000

all_keys = get_sqfree(N)
print(f'N={N}: {len(all_keys)} sqfree keys', flush=True)

keys_f = all_keys.astype(np.float64)
max_x = int(10 * keys_f[-1])
c = np.log(keys_f) / keys_f

# Phase 1: overcomplete LP
print(f'Phase 1: {len(all_keys)} vars x {max_x} constraints...', flush=True)
t0 = time.time()
chunks = []
for s in range(1, max_x+1, 5000):
    e = min(s+5000, max_x+1)
    ns = np.arange(s, e, dtype=np.float64)
    chunks.append(np.floor(ns[:,None]/keys_f[None,:]) - ns[:,None]/keys_f[None,:])
A = np.vstack(chunks); b = np.full(A.shape[0], 1.0)
del chunks; gc.collect()
print(f'  Matrix: {A.nbytes//1e6:.0f}MB, {time.time()-t0:.1f}s', flush=True)

t0 = time.time()
r1 = linprog(c, A_ub=A, b_ub=b, bounds=[(-10,10)]*len(all_keys),
             method='highs-ipm', options={'maxiter':1000000, 'presolve':True, 'time_limit':7200})
print(f'  Phase 1 done: {time.time()-t0:.1f}s, score={-r1.fun:.15f}', flush=True)
del A, b; gc.collect()

# Select top BUDGET keys
imp = np.abs(r1.x)
top = np.argsort(-imp)[:BUDGET]
sel = all_keys[sorted(top)]
print(f'  Selected {len(sel)} keys, max_k={sel[-1]}', flush=True)

# Phase 2: re-solve with selected
sel_f = sel.astype(np.float64)
max_x2 = int(10 * sel_f[-1])
c2 = np.log(sel_f) / sel_f

print(f'Phase 2: {len(sel)} vars x {max_x2} constraints...', flush=True)
t0 = time.time()
chunks = []
for s in range(1, max_x2+1, 5000):
    e = min(s+5000, max_x2+1)
    ns = np.arange(s, e, dtype=np.float64)
    chunks.append(np.floor(ns[:,None]/sel_f[None,:]) - ns[:,None]/sel_f[None,:])
A2 = np.vstack(chunks); b2 = np.full(A2.shape[0], 1.0)
del chunks; gc.collect()

r2 = linprog(c2, A_ub=A2, b_ub=b2, bounds=[(-10,10)]*len(sel),
             method='highs-ipm', options={'maxiter':1000000, 'presolve':True, 'time_limit':7200})
print(f'  Phase 2 done: {time.time()-t0:.1f}s, score={-r2.fun:.15f}', flush=True)
del A2, b2; gc.collect()

# Build, verify, scale
f_dict = {int(sel[i]): float(r2.x[i]) for i in range(len(sel))}
verified = evaluate({'partial_function': {str(k):v for k,v in f_dict.items()}})
print(f'Verified: {verified:.15f}', flush=True)

lo, hi = 1.0, 1.001; best_s, best_sc = 1.0, verified
for _ in range(25):
    mid = (lo+hi)/2
    sc = evaluate({'partial_function': {str(k):v*mid for k,v in f_dict.items()}})
    if sc > float('-inf'):
        if sc > best_sc: best_sc, best_s = sc, mid
        lo = mid
    else: hi = mid

print(f'Scale={best_s:.15f}, Score={best_sc:.15f}', flush=True)
if best_s > 1.0:
    f_dict = {k: v*best_s for k,v in f_dict.items()}

json.dump({'partial_function': {str(k):v for k,v in f_dict.items()}}, open('solution.json','w'))
print(f'SAVED solution.json', flush=True)
print(f'JSAgent #1: 0.994847489977900', flush=True)
print(f'Our score:  {best_sc:.15f}', flush=True)
print(f'Diff: {best_sc - 0.994847489977900:+.2e}', flush=True)
print(f'{"BEATS #1!" if best_sc > 0.994847489977900 + 1e-5 else "Does not beat #1"}', flush=True)

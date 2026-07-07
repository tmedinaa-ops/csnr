#!/usr/bin/env python3
"""
horizon_from_bare.py -- extract the reactivity horizon from an existing bare
(fixed-drum) depletion, done properly.

Why this is meaningful even without a critical search: in the bare run the drums
stay at their BOL operating position and the core only sags to k ~ 0.97 over the
mission, a small subcriticality driven by composition, not by drum absorption. So
the spectrum stays close to the operating condition and the reactivity slope is
close to what a controlled run would give. What the bare run got wrong was the
bookkeeping, not the physics: it compared a hot trajectory (with ~600-800 pcm of
one-time Xe/Sm baked in) against a clean 767 pcm budget, which is apples to oranges
and produced a sub-1-year "EOL".

This script fixes that. It separates the one-time Xe/Sm equilibrium from the slow
burnup slope, then computes horizon = 767 pcm / (burnup slope), which is what the
project's 7.2 yr (79 kWt) and 5.1 yr (120 kWt) numbers assumed at 106 and 153
pcm/yr. It reports the measured slope with its Monte-Carlo uncertainty so you can
see whether noise explains any gap (it does not: the slope is ~337 +/- 20).

Usage:  python horizon_from_bare.py depletion_results.h5 79.1
        python horizon_from_bare.py depletion_results-2.h5 120
"""
import sys
import h5py
import numpy as np

EXCESS_PCM = 767.0          # project cold/burnup reactivity budget
EQ_START_YR = 0.33          # fit the slope past the xenon/samarium transient

fn = sys.argv[1] if len(sys.argv) > 1 else "depletion_results.h5"
P = float(sys.argv[2]) if len(sys.argv) > 2 else float("nan")

f = h5py.File(fn, "r")
number = np.array(f["number"])
eig = np.array(f["eigenvalues"])
time_s = np.array(f["time"])[:, 0]
idx = {n: int(f["nuclides"][n].attrs["atom number index"][()]) for n in f["nuclides"].keys()}

t = time_s / (365.25 * 86400)
kk = eig[:, 0]
rho = (kk - 1.0) / kk * 1e5

# the one material that actually fissioned is the whole core (shared-material lattice)
m0 = int(np.argmax(number[-1, :, idx["Cs137"]]))
u235 = number[:, m0, idx["U235"]]
burnup = (1.0 - u235 / u235[0]) * 100.0

# linear fit of reactivity past the Xe/Sm transient -> burnup slope + noise
sel = t >= EQ_START_YR
A = np.vstack([t[sel], np.ones(sel.sum())]).T
coef, *_ = np.linalg.lstsq(A, rho[sel], rcond=None)
slope, intercept = coef
dof = max(sel.sum() - 2, 1)
resid = rho[sel] - A @ coef
sigma_slope = np.sqrt((resid @ resid / dof) / np.sum((t[sel] - t[sel].mean()) ** 2))
xe_sm = rho[0] - intercept

hz = EXCESS_PCM / (-slope)
hz_lo = EXCESS_PCM / (-slope - sigma_slope)
hz_hi = EXCESS_PCM / (-slope + sigma_slope)
anchor = 106.0 if P < 100 else 153.0

print(f"\nfile {fn}   power {P} kWt   (core material {m0})")
print(f"burnup reactivity slope (t>{EQ_START_YR} yr): {slope:.0f} +/- {sigma_slope:.0f} pcm/yr")
print(f"one-time Xe/Sm + early equilibrium offset:   {xe_sm:.0f} pcm")
print(f"U-235 burnup rate:                           {burnup[-1]/t[-1]:.3f} %/yr")
print(f"\nreactivity horizon = {EXCESS_PCM:.0f} pcm / slope")
print(f"  measured: {hz:.1f} yr   (range {hz_hi:.1f}-{hz_lo:.1f} on slope 1-sigma)")
print(f"  project analytic: {EXCESS_PCM/anchor:.1f} yr at the {anchor:.0f} pcm/yr anchor")
print(f"\nreading: noise is +/-{sigma_slope:.0f} pcm/yr, far too small to close the gap to")
print(f"the anchor, so if this model is right the horizon is ~{hz:.0f}x shorter than assumed.")
print("Confirm at the operating spectrum with controlled_depletion.py before revising the")
print("mission numbers; the reconciliation is more likely a power/definition difference in")
print("the Service Life anchor than Monte-Carlo scatter.")

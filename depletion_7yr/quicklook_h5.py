#!/usr/bin/env python3
"""
quicklook_h5.py -- read a depletion_results.h5 with h5py alone (no OpenMC install
needed, so it runs on the Mac), print k(t), reactivity, and burnup against the
analytic targets, and detect the volume over-count bug from the pre-fix run script.

The bug and what survives it: the original run_depletion_7yr.py assigned the whole-
core fuel volume (8550.8 cm3) to EVERY depletable material (75 in fig12_test), so
the stored fissile inventory is 75x reality (~355 kg U235 instead of ~4.75 kg).
Absolute atoms burned are still correct (set by the power normalization), so the
burnup RATE is recoverable by rescaling with the volume factor. The reactivity
trajectory is NOT recoverable: the transport saw compositions evolving ~75x too
slowly, so k(t) from a bugged run must not be quoted. The fixed script splits the
volume across the materials; on a fixed run this quicklook applies no rescale and
all three legs are valid.

Usage: python3 quicklook_h5.py <path/to/depletion_results.h5> [POWER_KWT]
"""
import sys
import h5py
import numpy as np

TRUE_CORE_FUEL_CM3 = 8550.8
path = sys.argv[1] if len(sys.argv) > 1 else "depletion_results.h5"
p_kwt = float(sys.argv[2]) if len(sys.argv) > 2 else 79.1

f = h5py.File(path, "r")
ev, tt = f["eigenvalues"][:], f["time"][:]
t_yr = tt[:, 0] / (365.25 * 86400.0)
k, ks = ev[:, 0], ev[:, 1]
rho = (k - 1.0) / k * 1e5

mats = f["materials"]
tot_vol = float(sum(mats[m].attrs["volume"] for m in mats.keys()))
scale = tot_vol / TRUE_CORE_FUEL_CM3
bugged = scale > 1.5

idx = {n: f["nuclides"][n].attrs["atom number index"]
       for n in ("U234", "U235", "U236", "U238") if n in f["nuclides"]}
num = f["number"]
u = np.zeros(len(t_yr))
for i in idx.values():
    u += num[:, :, i].sum(axis=1)
bu = (1.0 - u / u[0]) * 100.0 * (scale if bugged else 1.0)

print(f"{path}: {len(t_yr)-1} steps to {t_yr[-1]:.2f} yr, "
      f"{len(mats.keys())} depletable materials, stored volume {tot_vol:.0f} cm3")
if bugged:
    print(f"*** PRE-FIX RUN DETECTED: inventory inflated x{scale:.0f}. Burnup below is "
          f"RESCALED and valid; k(t)/reactivity are corrupted, DO NOT QUOTE. Rerun "
          f"with the fixed run_depletion_7yr.py for the reactivity legs. ***")
print(f"\n{'t yr':>7}{'k':>10}{'sig pcm':>8}{'rho pcm':>9}{'burnup %':>9}")
for i in range(len(t_yr)):
    print(f"{t_yr[i]:7.3f}{k[i]:10.5f}{ks[i]*1e5:8.0f}{rho[i]:9.0f}{bu[i]:9.3f}")

sel = t_yr >= 1.0
bs = np.polyfit(t_yr[sel], bu[sel], 1)[0]
print(f"\nburnup rate (t>1yr): {bs:.3f} %/yr"
      f"{' (rescaled)' if bugged else ''}   analytic: 0.75 with 0.60 scaling spread; "
      f"first-principles check {13.1*(p_kwt/34.0)*1000/4750*0.1:.2f}"
      )
if not bugged:
    rs = np.polyfit(t_yr[sel], rho[sel], 1)[0]
    cum = rho[0] - rho
    eol = float(np.interp(767.0, cum, t_yr, right=np.nan))
    print(f"reactivity slope (t>1yr): {rs:.1f} pcm/yr   (analytic -106 at 79 kWt, -153 at 120)")
    print(f"767 pcm spent at t = {eol:.2f} yr           (analytic ~7.2 at 79 kWt, ~5.1 at 120)")
else:
    print("reactivity legs skipped (bugged inventory); rerun required")

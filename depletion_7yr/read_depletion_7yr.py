#!/usr/bin/env python3
"""
read_depletion_7yr.py -- read a 7-year depletion run and compare it against the
analytic mission simulation's fitted legs (SNAP-10A_7yr_Mission_Simulation.md).

Prints k(t) with Monte Carlo sigma, reactivity vs time and its slope in pcm/yr,
uranium burnup in percent of initial inventory and its rate, and the estimated
reactivity end-of-life (cumulative reactivity loss reaching the 767 pcm cold excess,
the Service Life Report's OpenMC-confirmed budget anchor).

Comparison targets (analytic model, to be confirmed or corrected by this run):
  79.1 kWt:  burnup 0.75 %/yr (spread 0.60-0.75), rho slope ~106 pcm/yr, EOL ~7.2 yr
  120 kWt:   burnup 1.14 %/yr,                    rho slope ~153 pcm/yr, EOL ~5.1 yr

Usage:  RUN_DIR=run_79kWt_7yr python read_depletion_7yr.py
Writes <RUN_DIR>/depletion_summary.csv for plotting on the Mac.
"""
import csv
import os
import sys
from pathlib import Path

import numpy as np
import openmc.deplete

RUN_DIR = Path(os.environ.get("RUN_DIR") or (sys.argv[1] if len(sys.argv) > 1 else "."))
res_path = RUN_DIR / "depletion_results.h5"
if not res_path.exists():
    sys.exit(f"no depletion_results.h5 in {RUN_DIR}")

COLD_EXCESS_PCM = 767.0

res = openmc.deplete.Results(str(res_path))
time_d, k = res.get_keff(time_units="d")
time_yr = time_d / 365.25
kk, ks = k[:, 0], k[:, 1]
rho_pcm = (kk - 1.0) / kk * 1e5

# Burnup must be computed only over the fuel that ACTUALLY fissions. The fig12 lattice
# shares one fuel material across the core, so in the 0-D (lumped) run exactly one
# depletable material carries the whole core's flux and the rest are unplaced orphans
# that stay frozen; summing over all of them divides the burnup by the orphan count
# (the 75x error that made the first read say 0.008 %/yr). Selecting the materials that
# built fission products (Cs137) gives the right denominator in both the lumped case
# (one whole-core material) and the DIFF case (every pin fissions). See the July 2026
# depletion audit.
mats = res.export_to_materials(0)
fuel_ids = [str(m.id) for m in mats if m.depletable]
u_nucs = ["U234", "U235", "U236", "U238"]


def series(mid, nuc):
    try:
        return res.get_atoms(mid, nuc)[1]
    except (KeyError, ValueError):
        return None


# keep only materials that fissioned (final-step Cs137 above a floor)
active = []
for mid in fuel_ids:
    cs = series(mid, "Cs137")
    if cs is not None and cs[-1] > 1e10:
        active.append(mid)
if not active:                    # fallback: use all, warn
    active = fuel_ids
    print("WARNING: no material shows fission products; using all depletable materials")
print(f"burnup over {len(active)} fissioning material(s) of {len(fuel_ids)} depletable "
      f"({'0-D lumped core' if len(active) == 1 else 'per-pin / differentiated'})")

u_atoms = np.zeros_like(time_yr)
u235_atoms = np.zeros_like(time_yr)
for mid in active:
    for nuc in u_nucs:
        a = series(mid, nuc)
        if a is not None:
            u_atoms += a
    a5 = series(mid, "U235")
    if a5 is not None:
        u235_atoms += a5
burnup_pct = (1.0 - u_atoms / u_atoms[0]) * 100.0
burnup_u235_pct = (1.0 - u235_atoms / u235_atoms[0]) * 100.0

print(f"{'t [yr]':>8}{'k-eff':>10}{'+/-':>8}{'rho [pcm]':>11}{'burnup %':>10}")
for t, kv, s, r, b in zip(time_yr, kk, ks, rho_pcm, burnup_pct):
    print(f"{t:>8.3f}{kv:>10.5f}{s:>8.5f}{r:>11.1f}{b:>10.3f}")

# slopes from year 1 onward (past the xenon/samarium transient)
sel = time_yr >= 1.0
if sel.sum() >= 2:
    rho_slope = np.polyfit(time_yr[sel], rho_pcm[sel], 1)[0]
    bu_slope = np.polyfit(time_yr[sel], burnup_pct[sel], 1)[0]
    drho_total = rho_pcm[0] - rho_pcm  # cumulative reactivity spent
    eol = np.interp(COLD_EXCESS_PCM, drho_total, time_yr,
                    right=float("nan"))
    bu5_slope = np.polyfit(time_yr[sel], burnup_u235_pct[sel], 1)[0]
    print(f"\nreactivity slope (t>1yr): {rho_slope:.1f} pcm/yr "
          f"(analytic fit: -106 at 79 kWt, -153 at 120 kWt)")
    print(f"burnup rate total-U (t>1yr): {bu_slope:.3f} %/yr "
          f"(analytic: 0.75 at 79 kWt, 1.14 at 120 kWt)")
    print(f"burnup rate U-235   (t>1yr): {bu5_slope:.3f} %/yr")
    print(f"reactivity EOL (767 pcm spent): {eol:.2f} yr "
          f"(analytic: ~7.2 at 79 kWt, ~5.1 at 120 kWt)")
    print("NOTE: the bare depletion holds the drums fixed, so this slope is the "
          "uncompensated loss; the Service Life anchor is the drum-controlled net.")

out = RUN_DIR / "depletion_summary.csv"
with open(out, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["time_yr", "keff", "keff_sigma", "rho_pcm", "burnup_pct"])
    for row in zip(time_yr, kk, ks, rho_pcm, burnup_pct):
        w.writerow([f"{v:.6g}" for v in row])
print(f"\nwrote {out}")

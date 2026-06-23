#!/usr/bin/env python3
"""
notify_results.py -- collapse the Layer 2 Cardinal validation outputs into one summary
line for a phone notification. Reads the CSVs in the run directory (default: current dir,
or pass the path). Safe if files are missing (prints what it can).

  python3 notify_results.py [run_dir]
"""
import csv
import glob
import os
import sys

run = sys.argv[1] if len(sys.argv) > 1 else "."


def last_row(path):
    try:
        with open(os.path.join(run, path)) as f:
            rows = list(csv.DictReader(f))
        return rows[-1] if rows else None
    except Exception:
        return None


def g(row, col):
    try:
        return float(row[col])
    except Exception:
        return None


parts = []

# k-eff and heat source
o = last_row("openmc_out.csv")
k = g(o, "k") if o else None
if k is not None:
    parts.append(f"k={k:.5f}")

# solid: peak fuel + power in
s = last_row("solid_core.csv")
fuel = g(s, "max_fuel_T") if s else None
pin = g(s, "power_in") if s else None

# THM channels: total heat the fluid actually received, and outlet temps
tot, outlets = 0.0, []
for fpath in sorted(glob.glob(os.path.join(run, "openmc_out_solid0_thm*_csv.csv"))):
    try:
        with open(fpath) as f:
            r = list(csv.DictReader(f))[-1]
        tot += float(r["heat_added"])
        outlets.append(float(r["T_fluid_out"]))
    except Exception:
        pass

if outlets:
    parts.append(f"NaK out mean={sum(outlets)/len(outlets):.1f}K max={max(outlets):.1f}K")
if fuel is not None:
    parts.append(f"peak fuel={fuel:.1f}K")
if outlets and pin:
    closure = 100.0 * tot / pin
    parts.append(f"THM heat={tot:.0f}W ({closure:.0f}% of {pin:.0f})")
    parts.append("CONVERGED" if closure > 90 else "STALLED-heat-not-closing")

head = "SNAP Cardinal done"
print(head + ": " + (" | ".join(parts) if parts else "no result CSVs found, check run.log"))

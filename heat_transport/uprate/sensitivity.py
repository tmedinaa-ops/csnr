#!/usr/bin/env python3
"""
sensitivity.py -- how firm is the ~65 kWt fuel-limited uprate ceiling?

The headline number from sweep.py (peak fuel reaches the 970 K hydride wall near 64-65
kWt at design flow) rests on a handful of assumed inputs. Before spending effort pinning
any one of them with an OpenMC run or a literature pull, this script asks which input
the ceiling is actually sensitive to, by recomputing the fuel-limited ceiling as each
input is varied one at a time around the base case. The largest mover is where the next
effort should go.

Base case: design flow, radial peaking 1.56, axial peaking 1.40, hydride wall 970 K,
clad k(T) on.
"""
import numpy as np
import sweep

BASE = dict(mdot_tot=sweep.MDOT_TOT_DESIGN, f_radial=sweep.F_RADIAL, f_axial=sweep.F_AXIAL,
            wall=970.0, clad_kT=True)


def ceiling(**kw):
    p = dict(BASE, **kw)
    return sweep.find_fuel_ceiling(**p) / 1e3


def band(name, values, key, fmt="{:.3g}"):
    base_c = ceiling()
    print(f"\n{name} (base ceiling {base_c:.1f} kWt):")
    print(f"  {'value':>10} {'ceiling kWt':>12} {'delta':>8}")
    for v in values:
        c = ceiling(**{key: v})
        tag = "  <-- base" if np.isclose(v, BASE[key]) else ""
        print(f"  {fmt.format(v):>10} {c:>12.1f} {c-base_c:>+8.1f}{tag}")


def main():
    print("Uprate ceiling sensitivity -- one input varied at a time\n")
    print(f"base case: design flow, f_radial 1.56, f_axial 1.40, wall 970 K, clad k(T) on")
    print(f"base fuel-limited ceiling: {ceiling():.1f} kWt")

    # 1) radial peaking -- now MEASURED at 1.317 (extract_pin_power.py); a residual band
    band("radial peaking f_radial", [1.20, sweep.F_RADIAL, 1.45, 1.56], "f_radial",
         "{:.3f}")

    # 2) flow -- what a stronger or TE-scaled pump could buy
    band("total NaK flow (x design)", [m * sweep.MDOT_TOT_DESIGN
         for m in (1.0, 1.25, 1.5, 2.0)], "mdot_tot", "{:.3f}")

    # 3) inlet temperature -- a colder cold leg (T_IN is a module global in sweep)
    base_c = ceiling()
    print(f"\ncore inlet temperature [K] (base ceiling {base_c:.1f} kWt):")
    print(f"  {'value':>10} {'ceiling kWt':>12} {'delta':>8}")
    saved = sweep.T_IN
    for Tin in (745.0, 755.37, 765.0):
        sweep.T_IN = Tin
        c = ceiling()
        tag = "  <-- base" if np.isclose(Tin, 755.37) else ""
        print(f"  {Tin:>10.2f} {c:>12.1f} {c-base_c:>+8.1f}{tag}")
    sweep.T_IN = saved

    # 4) hydride wall -- the limit value itself
    band("hydride wall limit [K]", [950.0, 970.0, 990.0], "wall", "{:.0f}")

    # 5) clad k(T) on vs off -- confirm it is a small refinement
    print(f"\nclad k(T) on vs constant 18.86:")
    print(f"  clad k(T) on : {ceiling(clad_kT=True):.1f} kWt")
    print(f"  clad const   : {ceiling(clad_kT=False):.1f} kWt")

    print("\n--- reading ---")
    c_lo, c_hi = ceiling(f_radial=1.70), ceiling(f_radial=1.40)
    print(f"Radial peaking alone moves the ceiling from {c_lo:.0f} to {c_hi:.0f} kWt across")
    print("a plausible 1.40-1.70 band, by far the widest swing. Flow is the other big")
    print("lever. Inlet T, the wall value, and clad k(T) are all secondary. So the next")
    print("effort that most sharpens the number is the REAL per-pin peaking from the")
    print("OpenMC snap model (replacing the assumed 1.56), then the true pump flow limit.")


if __name__ == "__main__":
    main()

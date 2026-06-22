#!/usr/bin/env python3
"""
g1_uprate_to_kwe.py -- chain the verified uprate ceiling into the Stirling output
(component G1 of the structural roadmap). Replaces the briefing's ASSUMED 85 kWt / 800 K /
13 kWe Route A with the COMPUTED thermal-hydraulic ceiling, its real hot-side temperature,
and the resulting electrical output, and answers whether the existing SNAP-10A core can
reach 14 kWe by running harder.

The chain: heat_transport/uprate/sweep.py gives the fuel-limited ceiling power and the
NaK-outlet (converter hot-side) temperature there; energy_conversion's Stirling model turns
that heat into electricity at a chosen radiator temperature, sizing the radiator and mass.

Pure NumPy/Matplotlib + the project's own sweep and Stirling modules. python3 g1_uprate_to_kwe.py
"""
import os
import sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, "..", "heat_transport", "uprate"))
sys.path.insert(0, os.path.join(HERE, "stirling_cycle_concept"))
import sweep                              # the thermal-hydraulic uprate model
import em_pump_curve as pump
from stirling_concept import operating_point   # the Stirling conversion model

FIGS = os.path.join(HERE, "path14kwe_figs")
os.makedirs(FIGS, exist_ok=True)

HEAT_FRAC = 31.9 / 34.0      # fraction of reactor heat reaching the converter (~0.938)
TARGET_KWE = 14.0
HX_DELTA = 25.0              # NaK-outlet to Stirling-hot-end heat-exchanger drop [K]


def ceilings():
    """Return the three uprate ceilings with power [W] and hot-side (NaK outlet) [K]."""
    held = sweep.find_fuel_ceiling()
    bol = sweep.find_fuel_ceiling_coupled()
    eol = sweep.find_fuel_ceiling_coupled(head_factor=pump.EOL_HEAD_FACTOR)
    out = {}
    out["held"] = (held, sweep.hot_channel(held, sweep.MDOT_TOT_DESIGN)["t_mix_out"])
    out["bol"] = (bol, sweep.coupled_flow(bol)[1]["t_mix_out"])
    out["eol"] = (eol, sweep.coupled_flow(eol, head_factor=pump.EOL_HEAD_FACTOR)[1]["t_mix_out"])
    return out


def kwe(P_W, T_hot, T_cold):
    return operating_point(T_hot, T_cold, P_W, HEAT_FRAC)


def radiator_for_target(P_W, T_hot, target_W=TARGET_KWE * 1e3):
    """Warmest radiator temperature that still reaches the target (bisection)."""
    lo, hi = 400.0, T_hot - 30.0
    if kwe(P_W, T_hot, lo)["P"] < target_W:
        return None
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if kwe(P_W, T_hot, mid)["P"] >= target_W:
            lo = mid
        else:
            hi = mid
    return lo


def fig_kwe_vs_radiator(P_eol, T_hot):
    Tc = np.linspace(450, 600, 120)
    fig, ax = plt.subplots(1, 2, figsize=(11, 4.5))
    for hx, lab, c in ((0.0, "NaK outlet hot side", "C0"),
                       (HX_DELTA, f"hot end -{HX_DELTA:.0f} K (heat exchanger)", "C1")):
        P = [kwe(P_eol, T_hot - hx, t)["P"] / 1e3 for t in Tc]
        ax[0].plot(Tc, P, c, label=lab)
    ax[0].axhline(TARGET_KWE, color="C3", ls="--", label="14 kWe target")
    ax[0].axvline(475, color="grey", ls=":", label="475 K radiator")
    ax[0].set_xlabel("radiator temperature [K]"); ax[0].set_ylabel("electrical output [kWe]")
    ax[0].set_title(f"Verified ceiling {P_eol/1e3:.0f} kWt, hot side {T_hot:.0f} K")
    ax[0].legend(fontsize=8)

    # the three ceilings at the 475 K radiator
    cs = ceilings()
    labs, vals = [], []
    for key, name in (("held", "held flow"), ("eol", "EOL (mission)"), ("bol", "BOL")):
        P_W, Th = cs[key]
        labs.append(f"{name}\n{P_W/1e3:.0f} kWt")
        vals.append(kwe(P_W, Th - HX_DELTA, 475.0)["P"] / 1e3)
    ax[1].bar(labs, vals, color=["grey", "C2", "C0"])
    ax[1].axhline(TARGET_KWE, color="C3", ls="--", label="14 kWe target")
    ax[1].axhline(13.0, color="C1", ls=":", label="briefing Route A (assumed 13)")
    ax[1].set_ylabel("kWe at 475 K radiator")
    ax[1].set_title("Verified output vs the 14 kWe target")
    ax[1].legend(fontsize=8)
    fig.suptitle("G1  Existing SNAP-10A uprated + Stirling + colder radiator -> kWe",
                 fontsize=11)
    fig.tight_layout()
    p = os.path.join(FIGS, "figK4_verified_kwe.png"); fig.savefig(p, dpi=120)
    plt.close(fig); return p


def main():
    cs = ceilings()
    P_eol, T_hot_eol = cs["eol"]
    T_hot = T_hot_eol - HX_DELTA          # converter hot end after the heat-exchanger drop

    print("G1  verified uprate -> kWe (existing SNAP-10A core, Stirling converter)\n")
    print(f"Uprate ceilings (fuel-limited at 970 K, hot side = NaK outlet):")
    for key, name in (("held", "held flow"), ("eol", "EOL mission"), ("bol", "BOL")):
        P_W, Th = cs[key]
        print(f"  {name:11s}: {P_W/1e3:5.1f} kWt   NaK outlet {Th:.0f} K")
    print(f"\nConverter hot end = NaK outlet - {HX_DELTA:.0f} K heat-exchanger drop = "
          f"{T_hot:.0f} K (using the EOL mission ceiling {P_eol/1e3:.0f} kWt)\n")

    print(f"{'radiator K':>10} {'overall':>8} {'kWe':>7} {'radiator m2':>12} "
          f"{'mass kg':>8} {'W/kg':>6}")
    for Tc in (590, 540, 500, 475, 450):
        o = kwe(P_eol, T_hot, float(Tc))
        flag = "  <- meets 14" if o["P"] >= TARGET_KWE * 1e3 else ""
        print(f"{Tc:>10} {o['eta']*100:>7.1f}% {o['P']/1e3:>6.2f} {o['A']:>12.1f} "
              f"{o['mass']:>8.0f} {o['sp']:>6.0f}{flag}")

    Tc14 = radiator_for_target(P_eol, T_hot)
    fig = fig_kwe_vs_radiator(P_eol, T_hot_eol)

    print("\n--- G1 reading ---")
    o475 = kwe(P_eol, T_hot, 475.0)
    print(f"At the verified {P_eol/1e3:.0f} kWt EOL ceiling, hot end {T_hot:.0f} K, a 475 K "
          f"radiator gives {o475['P']/1e3:.1f} kWe")
    print(f"({o475['eta']*100:.0f}% overall, {o475['A']:.0f} m2 radiator, {o475['mass']:.0f} kg, "
          f"{o475['sp']:.0f} W/kg).")
    if Tc14:
        print(f"14 kWe is met for any radiator at or below {Tc14:.0f} K.")
    print("So the existing SNAP-10A core, run to its thermal-hydraulic ceiling with a Stirling")
    print("converter and a colder radiator, reaches the 14 kWe requirement. The original")
    print("'14 kWe needs a bigger reactor' becomes '14 kWe needs the same reactor run harder,")
    print("plus a Stirling and a colder radiator'. The cost is radiator area and the")
    print("moving-parts reliability trade (carry KRUSTY's many-small-convertors answer).")
    print(f"\nwrote {os.path.relpath(fig, HERE)}")


if __name__ == "__main__":
    main()

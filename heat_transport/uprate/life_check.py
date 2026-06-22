#!/usr/bin/env python3
"""
life_check.py -- material and fluence life at the uprated power (component F1).

Answers the three questions the uprate ceiling rests on:
  1. Is the 970 K fuel wall real? (U-ZrH hydrogen dissociation, Simnad)
  2. Is the 977 K clad limit real, and does fast fluence threaten the clad or the Be
     reflector over the mission, at the uprated power?
  3. What does running the fuel hotter cost in hydrogen-redistribution life?

FINDINGS THIS ENCODES (sources in F1 section of the dossier):
- Fuel: SNAP used U-ZrH, ~10 wt% U (93 wt% HEU), H/Zr ~ 1.65 (delta phase). The 970 K
  (700 C) limit is the documented SNAP sustained-service ceiling (Simnad: glass-enamel /
  Sm2O3 coated clad "used successfully at temperatures up to 700 C"). It is a creep +
  hydrogen-permeation + redistribution service limit, NOT acute clad burst: at 970 K the
  equilibrium dissociation pressure is only ~0.1-0.3 atm (delta fuel). TRIGA's ~1150 C
  limit is for robust-clad transient-peak fuel, where the pressure is ~100-230 atm.
- Clad: Hastelloy-N (INOR-8) long-term ceiling 704 C = 977 K (creep-rupture rolloff,
  Haynes/ASME), essentially coincident with the fuel wall. Fast-fluence embrittlement
  threshold ~1e21 n/cm2 (E>0.1 MeV, ~0.5-1 dpa, McCoy ORNL-TM-3063), helium-driven.
- Flux/fluence: SNAP core fast flux ~1e11-1e12 n/cm2-s at 34 kWt (low power density);
  1-year design fast fluence ~order 1e19 n/cm2. Be reflector limit ~1e22 n/cm2 (E>1 MeV).
- So fast fluence is NOT life-limiting even at the uprate (orders of margin on clad and
  Be); the real mission-life cost of the uprate is accelerated hydrogen redistribution at
  the higher fuel temperature.

Pure NumPy/Matplotlib; runs on the Mac. python3 life_check.py
"""
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

FIGS = os.path.join(os.path.dirname(__file__), "figs")
os.makedirs(FIGS, exist_ok=True)

# --- fuel / hydride ----------------------------------------------------------------
X_HZR = 1.65                 # H/Zr atom ratio, SNAP SCA-4 delta-phase fuel
T_FUEL_WALL = 970.0          # K, SNAP service limit (Simnad, 700 C)
T_TRIGA = 1150.0 + 273.15    # K, TRIGA delta-phase peak-fuel limit, for contrast

# --- clad --------------------------------------------------------------------------
T_CLAD_LIMIT = 977.0         # K, Hastelloy-N 704 C creep ceiling (Haynes/ASME)
CLAD_FLUENCE_LIMIT = 1.0e21  # n/cm2, E>0.1 MeV embrittlement (McCoy ORNL-TM-3063)
BE_FLUENCE_LIMIT = 1.0e22    # n/cm2, E>1 MeV, conservative end of 1-6e22 band

# --- flux / mission (ESTIMATE; pin with an OpenMC energy-filtered tally) ------------
P_DESIGN = 34.0              # kWt
FAST_FLUX_DESIGN = 5.0e11    # n/cm2-s core fast flux at 34 kWt (mid of 1e11-1e12)
SEC_PER_YR = 3.1536e7
FLUENCE_1YR_DESIGN = FAST_FLUX_DESIGN * SEC_PER_YR   # ~1.6e19 n/cm2

# --- H migration (Simnad): D = 1.3e-2 exp(-12690/RT) cm2/s; permeation Q ~ 17800 -----
R_CAL = 1.987                # cal/mol-K
Q_MIGRATION = 12690.0
Q_PERMEATION = 17800.0


def simnad_pressure(T_K, X=X_HZR):
    """Equilibrium hydrogen dissociation pressure over delta ZrH_x [atm], Simnad 1981.
    log10(P) = K1 + K2*1e3/T. Reproduces Simnad's isochores in shape and order of
    magnitude (the published coefficients run ~3x low against his 1-atm-at-760C anchor for
    X=1.6, so treat absolute P as order-of-magnitude; the T and X trends are firm)."""
    K1 = -3.8415 + 38.6433 * X - 34.2639 * X**2 + 9.2821 * X**3
    K2 = -31.2982 + 23.5741 * X - 6.0280 * X**2
    return 10.0 ** (K1 + K2 * 1.0e3 / np.asarray(T_K, float))


def fast_fluence(p_kwt, years):
    """Core fast fluence [n/cm2] at power p_kwt over `years`, scaled from the design
    estimate (flux ~ power)."""
    return FLUENCE_1YR_DESIGN * (p_kwt / P_DESIGN) * years


def h_rate_ratio(T_hot, T_ref=805.0, Q=Q_MIGRATION):
    """Relative hydrogen migration/permeation rate vs a reference fuel temperature
    (Arrhenius). T_ref ~ 805 K is the arXiv design average fuel temperature."""
    return np.exp(-Q / R_CAL * (1.0 / np.asarray(T_hot, float) - 1.0 / T_ref))


# ---------------------------------------------------------------------------------
def fig_dissociation():
    T = np.linspace(700, 1500, 300)
    fig, ax = plt.subplots(figsize=(7.5, 5))
    for X, ls in ((1.6, "--"), (1.65, "-"), (1.7, ":")):
        ax.semilogy(T, simnad_pressure(T, X), ls, label=f"H/Zr = {X}")
    ax.axvline(T_FUEL_WALL, color="C3", lw=1.3)
    ax.text(T_FUEL_WALL - 6, 50, "SNAP service\nlimit 970 K", color="C3", ha="right",
            fontsize=8)
    ax.axvline(T_TRIGA, color="C2", lw=1.3)
    ax.text(T_TRIGA - 6, 0.02, "TRIGA peak\n1150 C", color="C2", ha="right", fontsize=8)
    ax.axhline(1.0, color="grey", ls="--", lw=0.8, label="1 atm")
    ax.set_xlabel("fuel temperature [K]"); ax.set_ylabel("H$_2$ dissociation pressure [atm]")
    ax.set_title("F1  U-ZrH dissociation pressure (Simnad): 970 K is a service limit, "
                 "not burst")
    ax.legend(fontsize=8)
    fig.tight_layout()
    p = os.path.join(FIGS, "fig_f1_dissociation.png"); fig.savefig(p, dpi=120)
    plt.close(fig); return p


def fig_fluence():
    P = np.linspace(34, 100, 100)
    fig, ax = plt.subplots(figsize=(7.5, 5))
    for yrs, c in ((1.0, "C0"), (3.0, "C1")):
        ax.semilogy(P, fast_fluence(P, yrs), c, label=f"{yrs:.0f}-year mission")
    ax.axhline(CLAD_FLUENCE_LIMIT, color="C3", ls="--",
               label="clad embrittlement ~1e21 (E>0.1 MeV)")
    ax.axhline(BE_FLUENCE_LIMIT, color="C2", ls="--",
               label="Be reflector ~1e22 (E>1 MeV)")
    ax.axvline(79, color="grey", ls=":", label="uprate ceiling ~79 kWt")
    ax.set_xlabel("core thermal power [kWt]"); ax.set_ylabel("core fast fluence [n/cm$^2$]")
    ax.set_title("F1  Fast fluence vs power and mission (estimate): far below the limits")
    ax.legend(fontsize=8)
    fig.tight_layout()
    p = os.path.join(FIGS, "fig_f1_fluence.png"); fig.savefig(p, dpi=120)
    plt.close(fig); return p


def fig_hloss():
    T = np.linspace(805, 970, 100)
    fig, ax = plt.subplots(figsize=(7.5, 5))
    ax.plot(T, h_rate_ratio(T, Q=Q_MIGRATION), label="migration (Q=12.7 kcal/mol)")
    ax.plot(T, h_rate_ratio(T, Q=Q_PERMEATION), label="permeation (Q=17.8 kcal/mol)")
    ax.axvline(970, color="C3", ls="--", label="fuel wall 970 K")
    ax.set_xlabel("fuel temperature [K]")
    ax.set_ylabel("H-redistribution rate / design (805 K)")
    ax.set_title("F1  Hydrogen-redistribution rate rises with uprate temperature")
    ax.legend(fontsize=8)
    fig.tight_layout()
    p = os.path.join(FIGS, "fig_f1_hloss.png"); fig.savefig(p, dpi=120)
    plt.close(fig); return p


def main():
    print("F1 material & fluence life -- SNAP-10A uprate\n")
    print("1) U-ZrH dissociation pressure (Simnad, H/Zr=1.65):")
    for T in (805, 850, 890, 970, T_TRIGA):
        print(f"   T = {T:>6.1f} K : P = {float(simnad_pressure(T)):.3g} atm")
    print(f"   -> at the 970 K wall P ~ {float(simnad_pressure(970)):.2g} atm (well under 1 "
          f"atm): 970 K is a creep/permeation/redistribution SERVICE limit, not burst.\n")

    print("2) Fast fluence vs limits (estimate, flux ~ power):")
    for P, yrs in ((34, 1), (79, 1), (79, 3)):
        flu = fast_fluence(P, yrs)
        print(f"   {P:>3.0f} kWt x {yrs} yr : {flu:.2g} n/cm2  -> "
              f"clad margin x{CLAD_FLUENCE_LIMIT/flu:.0f}, Be margin x{BE_FLUENCE_LIMIT/flu:.0f}")
    print("   -> fast fluence is NOT life-limiting even at the uprate.\n")

    print("3) Hydrogen-redistribution rate at the uprate (vs 805 K design average):")
    for T in (850, 890, 970):
        lo, hi = float(h_rate_ratio(T, Q=Q_MIGRATION)), float(h_rate_ratio(T, Q=Q_PERMEATION))
        print(f"   fuel avg {T} K : {lo:.1f}x - {hi:.1f}x faster")
    print("   -> the real mission-life cost of the uprate: running the fuel hotter speeds\n"
          "      hydrogen redistribution ~2-3x, shortening the H-limited life accordingly.\n")

    figs = [fig_dissociation(), fig_fluence(), fig_hloss()]
    for f in figs:
        print("wrote", os.path.relpath(f, os.path.dirname(__file__)))

    print("\n--- F1 reading ---")
    print("The 970 K fuel wall and 977 K clad limit are confirmed and sourced (Simnad;")
    print("Hastelloy-N 704 C), so the ~79 kWt ceiling stands on real limits, not placeholders.")
    print("Fast fluence clears clad and Be by orders of magnitude. The binding life cost of")
    print("the uprate is hydrogen redistribution accelerating ~2-3x at the hotter fuel, which")
    print("is exactly what limited SNAP's life and is the reason to hold fuel under the wall.")


if __name__ == "__main__":
    main()

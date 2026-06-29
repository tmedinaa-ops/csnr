#!/usr/bin/env python3
"""
verify_loop.py -- independent steady-state hand check of the system-loop MOOSE deck.

This reproduces the reactor -> NaK -> Stirling -> radiator -> space energy balance
analytically, with no MOOSE, so the loop_open.i / loop_closed.i results have targets
to hit. It is the same operating point as energy_conversion/nak_system_chain.py and
rejection_loop.py (the verified 14 kWe uprate), recomputed here standalone so this
folder is self-contained.

The efficiency law is the project's validated one
(energy_conversion/stirling_cycle_concept/stirling_converter.py): the Stirling
captures eta = carnot * rel, with rel a temperature-ratio model anchored to SNAP
and Kilopower. Run: python3 verify_loop.py
"""

SIGMA = 5.670e-8        # Stefan-Boltzmann [W/m^2/K^4]

# ---- operating point (must match loop_open.i header) ------------------------
Q_REACTOR = 79_000.0    # W   fuel-limited EOL core power
HEAT_FRAC = 0.938       # -   fraction reaching the converter
T_IN_HOT  = 755.37      # K   primary inlet
MDOT_HOT  = 0.64        # kg/s primary NaK flow
CP_NAK    = 879.903     # J/kg-K (arXiv Table II, 783 K)

PINCH_HOT = 25.0        # K   reactor outlet -> engine hot side
T_RAD     = 475.0       # K   radiator panel / engine cold side
EMISS     = 0.89
FIN_EFF   = 0.90

# rel(tau) anchors (stirling_converter.py, concept branch)
TAU_SNAP, REL_SNAP = 590.37 / 774.82, 0.30
TAU_KILO, REL_KILO = 475.0 / 950.0, 0.46
REL_FLOOR, REL_CEIL = 0.20, 0.50


def rel_efficiency(t_hot, t_cold):
    tau = t_cold / t_hot
    slope = (REL_KILO - REL_SNAP) / (TAU_KILO - TAU_SNAP)
    return max(REL_FLOOR, min(REL_CEIL, REL_SNAP + slope * (tau - TAU_SNAP)))


def carnot(t_hot, t_cold):
    return 1.0 - t_cold / t_hot


def main():
    # --- primary loop: reactor heats the NaK ---
    dT_primary = Q_REACTOR / (MDOT_HOT * CP_NAK)
    T_out = T_IN_HOT + dT_primary               # reactor NaK outlet

    # --- heat split at the engine ---
    Q_engine = Q_REACTOR * HEAT_FRAC            # to the hot end
    Q_parasitic = Q_REACTOR - Q_engine          # shield/transport loss

    # --- Stirling on the live temperatures ---
    T_hot_eng = T_out - PINCH_HOT
    eta_c = carnot(T_hot_eng, T_RAD)
    eta_r = rel_efficiency(T_hot_eng, T_RAD)
    eta = eta_c * eta_r
    electricity = eta * Q_engine
    Q_waste = Q_engine - electricity

    # --- radiator: area to reject Q_waste at T_RAD to 4 K space ---
    q_flux = EMISS * FIN_EFF * SIGMA * (T_RAD**4 - 4.0**4)
    A_rad = Q_waste / q_flux

    print("=" * 70)
    print("System loop steady-state targets  (reactor -> NaK -> Stirling -> space)")
    print("=" * 70)
    print(f"  reactor power               {Q_REACTOR/1e3:7.1f} kWt")
    print(f"  primary NaK rise            {dT_primary:7.1f} K   ({MDOT_HOT} kg/s, cp {CP_NAK:.1f})")
    print(f"  reactor NaK outlet  T_hot   {T_out:7.1f} K   <- loop_open T_core_out target")
    print(f"  heat to engine (Q_in)       {Q_engine/1e3:7.1f} kW  (heat_frac {HEAT_FRAC})")
    print(f"  parasitic loss              {Q_parasitic/1e3:7.1f} kW")
    print("-" * 70)
    print(f"  engine hot side             {T_hot_eng:7.1f} K   (outlet - {PINCH_HOT:.0f} K pinch)")
    print(f"  engine cold side (radiator) {T_RAD:7.1f} K")
    print(f"  Carnot ceiling              {eta_c*100:7.1f} %")
    print(f"  relative efficiency         {eta_r*100:7.0f} % of Carnot")
    print(f"  overall efficiency  eta     {eta*100:7.1f} %   <- loop_open eta target")
    print(f"  ELECTRICAL OUTPUT           {electricity/1e3:7.2f} kWe <- loop_open electricity target")
    print(f"  waste heat  Q_waste         {Q_waste/1e3:7.1f} kW  <- loop_open Q_waste / radiated target")
    print("-" * 70)
    print(f"  radiator area at {T_RAD:.0f} K     {A_rad:7.1f} m^2  (panel area folded into rad scale)")
    print("-" * 70)
    bal = Q_REACTOR - electricity - Q_waste - Q_parasitic
    print(f"  energy balance residual     {bal:7.2f} W   (reactor - elec - waste - parasitic; ~0)")
    print(f"  cross-check vs G1 reference : 14.6 kWe at 19.7% (Path_to_14kWe_Verified.md)")
    print("=" * 70)
    print("These are the numbers the MOOSE deck should converge to. T_core_out,")
    print("eta, electricity, Q_waste, and rad_to_space_integral are printed each step.")


if __name__ == "__main__":
    main()

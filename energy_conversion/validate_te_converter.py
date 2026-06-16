"""
Validate the SNAP-10A thermoelectric converter model against the NAA-SR-11955
Table 2 design point (the energy-conversion rows of
SNAP-10A_Validation_Targets.csv).

Run:  python validate_te_converter.py
"""

from snap10a_te_converter import (
    Converter, fit_design_point, carnot_efficiency, f_to_k,
)

# --- NAA-SR-11955 Table 2 design point -----------------------------------
N, n = 1440, 2
T_hj = f_to_k(902.0)    # average hot junction
T_cj = f_to_k(604.0)    # average cold junction
T_nak = f_to_k(935.0)   # average NaK  (Carnot hot reference)
T_rad = f_to_k(603.0)   # average radiator (Carnot cold reference)

targets = {
    "P (We)":           581.0,
    "E_terminal (V)":   28.5,
    "I (A)":            20.4,
    "R_internal (ohm)": 1.40,
    "Q_hot (kWt)":      31.90,
    "Q_cold (kWt)":     31.32,
    "eta_overall (%)":  1.82,
    "eta_device (%)":   7.65,
    "Carnot (%)":       23.8,
}

# --- fit per-couple constants from the loaded operating point ------------
conv = fit_design_point(
    N=N, n=n, T_hj=T_hj, T_cj=T_cj,
    V_terminal=28.5, I=20.4, R_internal=1.40, Q_hot=31_900.0,
)

# operating point: matched-ish load set by the stated terminal V and current
op = conv.operate(T_hj, T_cj, R_load=28.5 / 20.4)
carnot = carnot_efficiency(T_nak, T_rad)
eta_device = op["eta_overall"] / carnot
Z, ZT = conv.figure_of_merit(T_hj, T_cj)

computed = {
    "P (We)":           op["P"],
    "E_terminal (V)":   op["E_terminal"],
    "I (A)":            op["I"],
    "R_internal (ohm)": op["R_internal"],
    "Q_hot (kWt)":      op["Q_hot"] / 1000.0,
    "Q_cold (kWt)":     op["Q_cold"] / 1000.0,
    "eta_overall (%)":  op["eta_overall"] * 100.0,
    "eta_device (%)":   eta_device * 100.0,
    "Carnot (%)":       carnot * 100.0,
}

print("SNAP-10A thermoelectric converter, NAA-SR-11955 Table 2 reproduction")
print("=" * 68)
print("Fitted per-couple constants (from the loaded operating point):")
print(f"  S  = {conv.S * 1e6:7.1f} uV/K    sum Seebeck per couple")
print(f"  R0 = {conv.R0 * 1e3:7.3f} mohm    resistance per couple")
print(f"  K  = {conv.K:7.4f} W/K     thermal conductance per couple")
print(f"  Z  = {Z:.3e} /K    ZTbar = {ZT:.3f}  (Tbar = {0.5 * (T_hj + T_cj):.0f} K)")
print(f"  junction dT = {op['dT']:.1f} K   ({T_hj:.1f} K hot, {T_cj:.1f} K cold)")
print()

hdr = f"{'quantity':18s} {'target':>10s} {'model':>10s} {'rel err %':>10s}"
print(hdr)
print("-" * len(hdr))
worst = 0.0
for k in targets:
    t, c = targets[k], computed[k]
    err = 100.0 * (c - t) / t if t else 0.0
    worst = max(worst, abs(err))
    print(f"{k:18s} {t:10.3f} {c:10.3f} {err:+10.2f}")
print("-" * len(hdr))
print(f"worst-case error among reproduced Table 2 quantities: {worst:.2f}%")
print()

# --- internal consistency: heat-balance power vs circuit power -----------
P_heat = conv.N * op["i"] * conv.S * op["dT"] - conv.N * op["i"] ** 2 * conv.R0
print("Internal consistency:")
print(f"  circuit power  P = E I            = {op['P']:.1f} W")
print(f"  heat-balance   P = Q_hot - Q_cold = {op['Q_hot'] - op['Q_cold']:.1f} W")
print(f"  couple power   P = N i S dT - N i^2 R0 = {P_heat:.1f} W")
print()

# --- open-circuit voltage reconciliation ---------------------------------
E_oc_model = op["E_oc"]
E_oc_stated = 61.7
dT_oc = E_oc_stated * n / (N * conv.S)
print("Open-circuit voltage:")
print(f"  model, at the loaded dT = {op['dT']:.1f} K : {E_oc_model:.1f} V")
print(f"  Table 2 stated open-circuit          : {E_oc_stated:.1f} V")
print(f"  dT implied by 61.7 V at this S        : {dT_oc:.1f} K "
      f"(+{dT_oc - op['dT']:.1f} K vs loaded)")
print("  The 61.7 V is the open-circuit state, where zero current means no")
print("  Peltier cooling at the hot junction, so the junctions spread to a")
print("  wider dT. It is not in conflict with R and I at the loaded point.")

"""
SNAP-10A thermoelectric vs a Stirling converter on the SAME reactor heat source.

Comparison basis (agreed): hold SNAP-10A's heat source fixed, its reactor heat
input and its NaK hot / radiator cold temperatures, and ask what each converter
delivers at those temperatures. This isolates the converter choice. The Stirling
is NOT given KRUSTY's hotter temperatures; it is derated to SNAP's.

Reports overall efficiency, electrical output, radiator area, and specific power.

Run:  python compare_te_stirling.py
"""

from snap10a_te_converter import f_to_k
from stirling_converter import (
    carnot_efficiency, stirling_overall_efficiency, radiator_area,
    stirling_convertor_mass, REL_EFF_OPTIMISTIC, REL_EFF_CONSERVATIVE,
)

# --- fixed SNAP-10A heat source (NAA-SR-11955 Table 2) -------------------
Q_IN = 31_900.0                 # W thermal into the converter
T_HOT = f_to_k(935.0)           # 775 K, average NaK
T_COLD = f_to_k(603.0)          # 590 K, average radiator
CARNOT = carnot_efficiency(T_HOT, T_COLD)

# --- thermoelectric design point (the recreated SNAP converter) ----------
P_TE = 581.0
ETA_TE = P_TE / Q_IN
MASS_TE_PCS = 70.0              # kg, 154 lb wet, converter + radiator + balance
A_TE_ACTUAL = 5.8              # m^2, 62.5 ft^2 stated

# SNAP radiator areal density, used for the Stirling radiator estimate
RAD_AREAL_KG_M2 = (32.7 * 0.4536) / A_TE_ACTUAL   # 32.7 lb radiator / 5.8 m^2
BALANCE_KG = 25.0              # heat transport + structure + controller allowance

# --- radiator-model self-check against SNAP's stated 5.8 m^2 -------------
A_TE_model = radiator_area(Q_IN - P_TE, T_COLD)


def stirling_case(rel_eff: float) -> dict:
    eta = stirling_overall_efficiency(T_HOT, T_COLD, rel_eff)
    P = Q_IN * eta
    A = radiator_area(Q_IN - P, T_COLD)
    m_conv = stirling_convertor_mass(P)
    m_rad = A * RAD_AREAL_KG_M2
    m_pcs = m_conv + m_rad + BALANCE_KG
    return {"rel_eff": rel_eff, "eta": eta, "P": P, "A": A,
            "m_pcs": m_pcs, "sp": P / m_pcs}


cons = stirling_case(REL_EFF_CONSERVATIVE)
opt = stirling_case(REL_EFF_OPTIMISTIC)

print("SNAP-10A converter vs Stirling, SAME reactor heat source")
print("=" * 66)
print(f"Fixed heat source: {Q_IN/1000:.1f} kWt in, hot {T_HOT:.0f} K, "
      f"cold {T_COLD:.0f} K")
print(f"Carnot ceiling (same for both): {CARNOT*100:.1f} %")
print(f"Radiator model check: {A_TE_model:.2f} m^2 vs SNAP's stated "
      f"{A_TE_ACTUAL} m^2 ({100*(A_TE_model-A_TE_ACTUAL)/A_TE_ACTUAL:+.1f}%)")
print()

row = "{:24s} {:>12s} {:>14s} {:>14s}"
print(row.format("", "thermoelectric", "Stirling low", "Stirling high"))
print(row.format("relative eff (of Carnot)",
                 f"{ETA_TE/CARNOT*100:.1f}%",
                 f"{cons['rel_eff']*100:.0f}%", f"{opt['rel_eff']*100:.0f}%"))
print(row.format("overall efficiency",
                 f"{ETA_TE*100:.2f}%", f"{cons['eta']*100:.1f}%",
                 f"{opt['eta']*100:.1f}%"))
print(row.format("electrical output",
                 f"{P_TE:.0f} We", f"{cons['P']:.0f} We", f"{opt['P']:.0f} We"))
print(row.format("radiator area",
                 f"{A_TE_ACTUAL:.1f} m^2", f"{cons['A']:.1f} m^2",
                 f"{opt['A']:.1f} m^2"))
print(row.format("PCS mass (est.)",
                 f"{MASS_TE_PCS:.0f} kg", f"{cons['m_pcs']:.0f} kg",
                 f"{opt['m_pcs']:.0f} kg"))
print(row.format("specific power",
                 f"{P_TE/MASS_TE_PCS:.1f} W/kg", f"{cons['sp']:.0f} W/kg",
                 f"{opt['sp']:.0f} W/kg"))
print()

print("Headline ratios (Stirling vs thermoelectric, same reactor):")
print(f"  electrical output : {cons['P']/P_TE:.1f}x to {opt['P']/P_TE:.1f}x")
print(f"  specific power    : {cons['sp']/(P_TE/MASS_TE_PCS):.1f}x to "
      f"{opt['sp']/(P_TE/MASS_TE_PCS):.1f}x")
print(f"  radiator area     : {cons['A']/A_TE_ACTUAL:.2f}x to "
      f"{opt['A']/A_TE_ACTUAL:.2f}x  (barely shrinks)")
print()
print("Robustness: even if the Stirling PCS weighed the full 70 kg of the TE")
print(f"system, its specific power would still be "
      f"{cons['P']/MASS_TE_PCS:.0f} to {opt['P']/MASS_TE_PCS:.0f} W/kg, "
      f"{cons['P']/MASS_TE_PCS/(P_TE/MASS_TE_PCS):.0f} to "
      f"{opt['P']/MASS_TE_PCS/(P_TE/MASS_TE_PCS):.0f}x the TE value. The power")
print("gain drives the result, so the soft mass estimate does not change it.")

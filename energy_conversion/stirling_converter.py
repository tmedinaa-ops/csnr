"""
Stirling converter model for the SNAP-10A vs KRUSTY power-conversion comparison.

Agreed grain: overall efficiency = Carnot(T_hot, T_cold) * relative efficiency,
where the relative efficiency (the fraction of Carnot a real convertor captures)
is anchored to NASA's Kilopower/KRUSTY Stirling and derated for SNAP-10A's lower
temperature ratio. This is deliberately not a cycle-resolved Stirling model.

Anchors (sources in TE_vs_Stirling_Comparison.md):
- Kilopower design point: 23% system efficiency at 950 K hot / 475 K cold.
  Carnot(950, 475) = 0.500, so the system-level relative efficiency is 0.46.
- KRUSTY ground test: ~35% convertor-component efficiency, ~25% system.
- Convertor specific mass ~167 W/kg (about 6 kg/kWe, 5 kWe reference convertor).
- KRUSTY/Kilopower hot end ~950 to 1073 K; SNAP NaK is ~775 K, much cooler.

SNAP-10A runs at a far smaller temperature ratio (775 K hot, 590 K cold, Carnot
0.238) than Kilopower (0.500). A Stirling's relative efficiency falls at small
temperature ratio, because fixed parasitic losses (regenerator imperfection,
conduction, flow) take a larger share of the smaller ideal work. So the relative
efficiency is carried as a band, not a point:
  optimistic    : hold Kilopower's 0.46 (treat relative efficiency as ratio-free)
  conservative  : derate to 0.30 for SNAP's ratio
The band, not a single number, is the honest output at this fidelity.
"""

STEFAN_BOLTZMANN = 5.670e-8  # W m^-2 K^-4

REL_EFF_OPTIMISTIC = 0.46     # Kilopower system-level fraction of Carnot, held
REL_EFF_CONSERVATIVE = 0.30   # derated for SNAP's small temperature ratio

STIRLING_CONVERTOR_W_PER_KG = 167.0   # convertor-only specific mass (Kilopower)


def carnot_efficiency(T_hot: float, T_cold: float) -> float:
    return 1.0 - T_cold / T_hot


def stirling_overall_efficiency(T_hot: float, T_cold: float, rel_eff: float) -> float:
    """Overall conversion efficiency = Carnot * relative efficiency."""
    return carnot_efficiency(T_hot, T_cold) * rel_eff


def radiator_area(Q_reject_W: float, T_rad_K: float,
                  emissivity: float = 0.89, fin_eff: float = 0.90,
                  T_sink_K: float = 0.0) -> float:
    """Flat-radiator area (m^2) to reject Q_reject at T_rad. Uses SNAP-10A's
    emissivity 0.89 and fin effectiveness 0.90. Validated against SNAP's 5.8 m^2
    in the comparison harness."""
    q_flux = emissivity * fin_eff * STEFAN_BOLTZMANN * (T_rad_K ** 4 - T_sink_K ** 4)
    return Q_reject_W / q_flux


def stirling_convertor_mass(P_elec_W: float,
                            w_per_kg: float = STIRLING_CONVERTOR_W_PER_KG) -> float:
    """Convertor-only mass (kg) from Kilopower specific mass."""
    return P_elec_W / w_per_kg

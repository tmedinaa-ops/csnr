"""
Stirling converter, CONCEPT BRANCH.

This is the energy_conversion/stirling_converter.py model with one substantive
change: the relative efficiency now DEPENDS ON THE TEMPERATURE RATIO. In the
parent file the relative efficiency was a fixed band (0.30 to 0.46), which is
fine for a single operating point but wrong the moment you start raising the
reactor temperature, because a regenerative engine captures more of Carnot as
the hot-to-cold span widens. Here you can turn the reactor temperature up and
the converter improves the way a real one would, not just through Carnot.

The relative efficiency (fraction of Carnot captured) is a two-point anchored
model in the temperature ratio tau = T_cold / T_hot:
    SNAP-10A      tau = 590/775 = 0.761  ->  0.30
    Kilopower     tau = 475/950 = 0.500  ->  0.46
linearly interpolated in tau and clamped to [0.20, 0.50]. It is not a Schmidt
cycle solve. It captures the trend and reproduces both real anchors; treat about
+/- 0.05 as its uncertainty. If you build the idealized-Stirling tier later, this
is the function it replaces.

Units: temperatures in kelvin, power in watts, area in m^2, mass in kg.
"""

from snap10a_te_converter import f_to_k   # local copy in this folder

STEFAN_BOLTZMANN = 5.670e-8               # W m^-2 K^-4
STIRLING_CONVERTOR_W_PER_KG = 167.0       # convertor-only specific mass (Kilopower)

# relative-efficiency anchors (temperature ratio -> fraction of Carnot)
_TAU_SNAP, _REL_SNAP = f_to_k(603.0) / f_to_k(935.0), 0.30        # ~0.762 -> 0.30
_TAU_KILO, _REL_KILO = 475.0 / 950.0, 0.46                        # 0.500  -> 0.46
_REL_FLOOR, _REL_CEIL = 0.20, 0.50


def carnot_efficiency(T_hot: float, T_cold: float) -> float:
    return 1.0 - T_cold / T_hot


def relative_efficiency(T_hot: float, T_cold: float) -> float:
    """Fraction of Carnot the Stirling captures, as a function of the temperature
    ratio. Anchored to SNAP and Kilopower, clamped to a sane range."""
    tau = T_cold / T_hot
    slope = (_REL_KILO - _REL_SNAP) / (_TAU_KILO - _TAU_SNAP)
    rel = _REL_SNAP + slope * (tau - _TAU_SNAP)
    return max(_REL_FLOOR, min(_REL_CEIL, rel))


def stirling_overall_efficiency(T_hot: float, T_cold: float,
                                rel_override: float = None) -> float:
    """Overall efficiency = Carnot * relative efficiency. If rel_override is
    given it is used directly, otherwise the temperature-dependent model sets it."""
    rel = rel_override if rel_override is not None else relative_efficiency(T_hot, T_cold)
    return carnot_efficiency(T_hot, T_cold) * rel


def radiator_area(Q_reject_W: float, T_rad_K: float,
                  emissivity: float = 0.89, fin_eff: float = 0.90,
                  T_sink_K: float = 0.0) -> float:
    """Flat-radiator area (m^2). Reproduces SNAP's 5.8 m^2 at its design point."""
    q_flux = emissivity * fin_eff * STEFAN_BOLTZMANN * (T_rad_K ** 4 - T_sink_K ** 4)
    return Q_reject_W / q_flux


def stirling_convertor_mass(P_elec_W: float,
                            w_per_kg: float = STIRLING_CONVERTOR_W_PER_KG) -> float:
    """Convertor-only mass (kg) from Kilopower specific mass."""
    return P_elec_W / w_per_kg

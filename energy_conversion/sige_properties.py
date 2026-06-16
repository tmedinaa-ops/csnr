"""
SiGe thermoelectric property proxy for the SNAP-10A converter model.

READ THIS BEFORE USING.
SNAP-10A used 67 at% Si / 33 at% Ge, arsenic-doped N legs, fabricated by RCA.
Those exact temperature-dependent property curves are a classified or unretrieved
gap (the RCA "Development of Thermoelectric Modules for SNAP 10A" series and AI
memos NAA-SR-MEMO-10126 and NAA-SR-11205). What is public is RTG-grade Si80Ge20
(20 at% Ge), so the functions below are fits to published Si80Ge20 anchor points,
used as a PROXY. They are good for temperature trends, order of magnitude, and the
Seebeck cross-check. They are NOT SNAP's absolute properties. SNAP's richer Ge
(33 vs 20 percent) and cooler design point shift the real values, raising the
Seebeck and lowering the thermal conductivity relative to this proxy.

Confidence by property:
- Seebeck: best anchored, two-point fits to measured RTG-grade data.
- Resistivity: moderate, degenerate ~T form anchored at one high-T point.
- Thermal conductivity: weakest, a mild linear trend around the known ~4.5 W/m/K.

Anchor sources:
- Seebeck, n-type: ~120 uV/K at 300 K to ~284 uV/K at 1073 K (Basu et al.,
  J. Mater. Chem. A 2, 6922, 2014; consistent with Vining, J. Appl. Phys. 69,
  331, 1991, n-Si80Ge20 model).
- Seebeck, p-type: ~115 uV/K at 300 K to ~250 uV/K near 1100 K (Dismukes et al.,
  J. Appl. Phys. 35, 2899, 1964, B-doped Ge-Si; standard RTG p-SiGe).
- Resistivity, n-type: ~45 uOhm-m at 1073 K, degenerate ~T dependence (Basu 2014).
- Thermal conductivity, Si80Ge20: ~4.5 W/m/K, weak T dependence over 300-1100 K
  (Dismukes 1964; below Si95Ge5 because of alloy phonon scattering).

Units: temperature in kelvin, Seebeck in V/K returned as a positive magnitude,
resistivity in ohm-metre, thermal conductivity in W/(m K).
"""


def _lerp(T: float, T1: float, v1: float, T2: float, v2: float) -> float:
    """Linear interpolation/extrapolation between two anchor points."""
    return v1 + (v2 - v1) * (T - T1) / (T2 - T1)


def seebeck_n(T: float) -> float:
    """|Seebeck| of heavily P-doped n-type SiGe, V/K. Anchors 120 uV/K @ 300 K,
    284 uV/K @ 1073 K."""
    return _lerp(T, 300.0, 120e-6, 1073.0, 284e-6)


def seebeck_p(T: float) -> float:
    """Seebeck of heavily B-doped p-type SiGe, V/K. Anchors 115 uV/K @ 300 K,
    250 uV/K @ 1100 K."""
    return _lerp(T, 300.0, 115e-6, 1100.0, 250e-6)


def couple_seebeck(T: float) -> float:
    """Sum Seebeck of an N-P couple, |alpha_n| + |alpha_p|, V/K. Geometry-free,
    so this is the quantity directly comparable to the back-solved S."""
    return seebeck_n(T) + seebeck_p(T)


def resistivity_n(T: float) -> float:
    """n-type SiGe electrical resistivity, ohm-m. Degenerate ~T form anchored at
    45 uOhm-m @ 1073 K, floored near room-temperature value."""
    return max(8e-6, 45e-6 * T / 1073.0)


def resistivity_p(T: float) -> float:
    """p-type SiGe resistivity, ohm-m. Taken ~10 percent above n-type as a rough
    proxy for B-doped p-SiGe; uncertain."""
    return 1.1 * resistivity_n(T)


def thermal_conductivity(T: float) -> float:
    """Si80Ge20 total thermal conductivity, W/(m K). Mild linear decrease around
    the known ~4.5 W/m/K; weakest-anchored of the three properties."""
    return max(3.8, 4.7 - 7.0e-4 * (T - 300.0))


def material_zt_leg(alpha: float, rho: float, kappa: float, T: float) -> float:
    """Single-leg material figure of merit z*T = alpha^2 / (rho kappa) * T.
    Geometry-free, so comparable to the back-solved couple ZT for matched legs."""
    return alpha ** 2 / (rho * kappa) * T


def band_average(func, T_lo: float, T_hi: float, n: int = 101) -> float:
    """Average of func(T) over [T_lo, T_hi] by the trapezoid rule."""
    step = (T_hi - T_lo) / (n - 1)
    vals = [func(T_lo + i * step) for i in range(n)]
    return (sum(vals) - 0.5 * (vals[0] + vals[-1])) * step / (T_hi - T_lo)

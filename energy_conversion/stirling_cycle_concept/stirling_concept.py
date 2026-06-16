"""
Stirling concept explorer. Turn the reactor knobs and see what the Stirling
converter delivers, against a 14 kWe requirement.

Knobs (environment variables, all default to the SNAP-10A baseline):
    T_HOT_K        hot-side temperature delivered to the converter   [default 775]
    T_COLD_K       radiator / cold-side temperature                  [default 590]
    Q_THERMAL_KWT  reactor thermal power                             [default 34]
    HEAT_FRACTION  fraction of reactor heat reaching the converter   [default 0.938]
    TARGET_KWE     power requirement to test against                 [default 14]

Examples:
    python stirling_concept.py                          # SNAP baseline
    T_HOT_K=1050 Q_THERMAL_KWT=56 python stirling_concept.py    # KRUSTY-like
    T_HOT_K=1050 python stirling_concept.py             # hotter, same reactor power
"""

import os
from stirling_converter import (
    carnot_efficiency, relative_efficiency, radiator_area, stirling_convertor_mass,
)

RAD_AREAL_KG_M2 = (32.7 * 0.4536) / 5.8   # SNAP radiator areal density
BALANCE_KG = 25.0                          # heat transport + structure allowance


def _f(name, default):
    v = os.environ.get(name)
    return float(v) if v not in (None, "") else default


def operating_point(T_hot, T_cold, Q_thermal_W, heat_frac):
    carnot = carnot_efficiency(T_hot, T_cold)
    rel = relative_efficiency(T_hot, T_cold)
    eta = carnot * rel
    Q_conv = Q_thermal_W * heat_frac
    P = Q_conv * eta
    A = radiator_area(Q_conv - P, T_cold)
    m = stirling_convertor_mass(P) + A * RAD_AREAL_KG_M2 + BALANCE_KG
    return dict(carnot=carnot, rel=rel, eta=eta, Q_conv=Q_conv, P=P, A=A,
               mass=m, sp=P / m if m else 0.0)


def power_needed_kwt(target_W, eta, heat_frac):
    """Reactor thermal power to hit the target at this efficiency."""
    return target_W / (heat_frac * eta) / 1000.0


def hot_temp_for_target(target_W, T_cold, Q_thermal_W, heat_frac):
    """Lowest hot-side temperature that reaches the target at fixed reactor power.
    Returns (T_hot or None, max_P_W)."""
    best = 0.0
    for T in range(int(T_cold) + 20, 1601, 2):
        P = operating_point(T, T_cold, Q_thermal_W, heat_frac)["P"]
        best = max(best, P)
        if P >= target_W:
            return float(T), P
    return None, best


if __name__ == "__main__":
    T_hot = _f("T_HOT_K", 775.0)
    T_cold = _f("T_COLD_K", 590.0)
    Q_kwt = _f("Q_THERMAL_KWT", 34.0)
    heat_frac = _f("HEAT_FRACTION", 31.9 / 34.0)
    target = _f("TARGET_KWE", 14.0)
    Q_W = Q_kwt * 1000.0
    target_W = target * 1000.0

    op = operating_point(T_hot, T_cold, Q_W, heat_frac)

    print("Stirling concept point")
    print("=" * 56)
    print(f"  reactor thermal power : {Q_kwt:.1f} kWt   (heat to converter "
          f"{op['Q_conv']/1000:.1f} kWt)")
    print(f"  hot / cold side       : {T_hot:.0f} K / {T_cold:.0f} K")
    print(f"  Carnot ceiling        : {op['carnot']*100:.1f} %")
    print(f"  relative efficiency   : {op['rel']*100:.0f} % of Carnot "
          f"(temperature-dependent)")
    print(f"  overall efficiency    : {op['eta']*100:.1f} %")
    print(f"  ELECTRICAL OUTPUT     : {op['P']/1000:.2f} kWe")
    print(f"  radiator area         : {op['A']:.1f} m^2")
    print(f"  specific power        : {op['sp']:.0f} W/kg")
    print()

    gap = target_W - op["P"]
    print(f"Against the {target:.0f} kWe requirement:")
    if gap <= 0:
        print(f"  MET, with {-gap/1000:.2f} kWe to spare.")
    else:
        print(f"  short by {gap/1000:.2f} kWe.")
        q_need = power_needed_kwt(target_W, op["eta"], heat_frac)
        print(f"  at these temperatures, reaching {target:.0f} kWe needs "
              f"{q_need:.0f} kWt of reactor ({q_need/Q_kwt:.1f}x the current power).")
        T_need, max_P = hot_temp_for_target(target_W, T_cold, Q_W, heat_frac)
        if T_need:
            print(f"  at the current {Q_kwt:.0f} kWt, it needs the hot side raised "
                  f"to ~{T_need:.0f} K.")
        else:
            print(f"  at the current {Q_kwt:.0f} kWt, NO temperature reaches it "
                  f"(max ~{max_P/1000:.2f} kWe even at 1600 K). You need more "
                  f"thermal power, not just heat.")
    print()

    print("Temperature path at the current reactor power:")
    print(f"  {'T_hot (K)':>9} {'Carnot':>7} {'rel':>5} {'overall':>8} {'kWe':>7}")
    for T in (775, 850, 950, 1050, 1150):
        o = operating_point(float(T), T_cold, Q_W, heat_frac)
        flag = "  <- meets target" if o["P"] >= target_W else ""
        print(f"  {T:>9} {o['carnot']*100:>6.1f}% {o['rel']*100:>4.0f}% "
              f"{o['eta']*100:>7.1f}% {o['P']/1000:>6.2f}{flag}")

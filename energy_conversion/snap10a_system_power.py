"""
snap10a_system_power.py

Turn the SNAP-10A reactor's THERMAL power into ELECTRICAL power, and show the
correct way to read absolute heating out of an OpenMC kappa-fission tally.

The point this script makes concrete: OpenMC does not produce a power number. In
a criticality (k-eigenvalue) run the total power is an input you choose, and the
kappa-fission tally only tells you the FRACTION of that power deposited in each
region. So electrical output is (thermal power you set) x (converter efficiency
from a separate model), and the OpenMC tally gives the spatial distribution once
it is normalized to that power.

Two parts:
  system_electrical_power(...)   pure arithmetic, runs anywhere.
  normalize_kappa_fission(...)   reads an OpenMC statepoint, needs the openmc
                                 package and a statepoint file. Run it on the Mac
                                 in openmc-env, pointed at Documents/snap, e.g.:
                                   python snap10a_system_power.py ~/Documents/snap/statepoint.100.h5
"""

import sys
from snap10a_te_converter import f_to_k, fit_design_point
from stirling_converter import carnot_efficiency, REL_EFF_CONSERVATIVE, REL_EFF_OPTIMISTIC

# Design operating point. The reactor thermal power is a DESIGN INPUT, not an
# OpenMC output. SNAP ran 30 to 40 kWt across vintages; 34 kWt is the modeled
# value, of which about 31.9 kWt reaches the converter (NAA-SR-11955 Table 2).
REACTOR_THERMAL_KWT = 34.0
CONVERTER_HEAT_FRACTION = 31.9 / 34.0    # heat reaching the converter


def te_overall_efficiency() -> float:
    """Thermoelectric converter overall efficiency (electrical / converter heat),
    taken from the validated design-point model rather than hard-coded."""
    T_hj, T_cj = f_to_k(902.0), f_to_k(604.0)
    conv = fit_design_point(N=1440, n=2, T_hj=T_hj, T_cj=T_cj,
                            V_terminal=28.5, I=20.4, R_internal=1.40, Q_hot=31_900.0)
    return conv.operate(T_hj, T_cj, R_load=28.5 / 20.4)["eta_overall"]


def system_electrical_power(reactor_thermal_W: float, converter_efficiency: float,
                            heat_fraction: float = CONVERTER_HEAT_FRACTION) -> float:
    """Electrical power (W) = reactor thermal power x fraction reaching the
    converter x converter efficiency. converter_efficiency is electrical output
    divided by converter heat input."""
    return reactor_thermal_W * heat_fraction * converter_efficiency


def normalize_kappa_fission(statepoint_path: str, total_power_W: float):
    """Read an OpenMC kappa-fission tally and scale it to absolute watts.

    OpenMC reports the tally per source particle. The total recoverable energy
    per source particle is the tally summed over all bins, so the absolute power
    in each bin is simply total_power_W * (bin / sum). The 1.602e-19 J/eV factor
    and the source rate cancel out of the ratio. Caveat: the mesh must enclose
    essentially all fissions, or the sum understates the true total; a companion
    unfiltered kappa-fission tally gives the exact normalization base.
    """
    import openmc
    sp = openmc.StatePoint(statepoint_path)
    tally = sp.get_tally(scores=["kappa-fission"])
    kf = tally.mean.ravel()
    total = float(kf.sum())
    if total <= 0.0:
        raise ValueError("kappa-fission tally summed to zero; wrong tally or no fission scored")
    bin_power_W = total_power_W * kf / total
    return bin_power_W, total, float(sp.keff.nominal_value if sp.keff else float("nan"))


def _print_system_power():
    eta_te = te_overall_efficiency()
    Q = REACTOR_THERMAL_KWT * 1000.0
    P_te = system_electrical_power(Q, eta_te)

    print("SNAP-10A system electrical power")
    print("=" * 52)
    print(f"Reactor thermal power (design INPUT): {REACTOR_THERMAL_KWT:.1f} kWt")
    print(f"Heat reaching converter             : {Q*CONVERTER_HEAT_FRACTION/1000:.1f} kWt")
    print()
    print(f"Thermoelectric converter (what SNAP flew):")
    print(f"  converter efficiency  : {eta_te*100:.2f} %  (from the design-point model)")
    print(f"  electrical output     : {P_te:.0f} We  =  {P_te/1000:.2f} kWe")
    print(f"  reactor-to-electric   : {P_te/Q*100:.2f} %")
    print(f"  -> SNAP-10A currently produces about {P_te/1000:.2f} kWe")
    print()

    T_hot, T_cold = f_to_k(935.0), f_to_k(603.0)
    carnot = carnot_efficiency(T_hot, T_cold)
    print("For comparison, a Stirling on the same reactor and temperatures:")
    for rel, tag in [(REL_EFF_CONSERVATIVE, "low"), (REL_EFF_OPTIMISTIC, "high")]:
        eta = carnot * rel
        P = system_electrical_power(Q, eta)
        print(f"  {tag:4s} ({rel*100:.0f}% of Carnot): {eta*100:4.1f} % -> {P/1000:.2f} kWe")
    print()


if __name__ == "__main__":
    _print_system_power()

    if len(sys.argv) > 1:
        sp_path = sys.argv[1]
        power_W = REACTOR_THERMAL_KWT * 1000.0 * CONVERTER_HEAT_FRACTION
        print(f"Normalizing kappa-fission tally in {sp_path} to {power_W/1000:.1f} kWt ...")
        try:
            bins, total, keff = normalize_kappa_fission(sp_path, power_W)
            print(f"  k-eff in statepoint        : {keff:.5f}  "
                  f"({'critical, power is sustainable' if abs(keff-1) < 0.02 else 'NOT near critical'})")
            print(f"  mesh bins                  : {bins.size}")
            print(f"  total kappa-fission        : {total:.4e} eV per source particle")
            print(f"  sum of normalized bins     : {bins.sum()/1000:.2f} kWt  (should equal the power set)")
            print(f"  peak bin                   : {bins.max():.2f} W")
            print("  Note: OpenMC supplied only the SHAPE; the kWt total is the value you set.")
        except ImportError:
            print("  openmc not importable here. Run this on the Mac in openmc-env.")
        except FileNotFoundError:
            print(f"  no statepoint at {sp_path}")
    else:
        print("Pass an OpenMC statepoint path to also normalize its kappa-fission")
        print("tally to absolute watts, e.g.:")
        print("  python snap10a_system_power.py ~/Documents/snap/statepoint.100.h5")

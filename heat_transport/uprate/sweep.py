#!/usr/bin/env python3
"""
sweep.py -- the uprate driver: march reactor power up and read the three limits
(components B1 + B2 of the uprate roadmap, first cut).

This is the spine the roadmap calls the binding study. It ties A1 (NaK properties),
A2 (channel friction), and A3 (EM pump curve) to the analytic hot-channel conduction
stack and answers: how far can the EXISTING SNAP-10A core be uprated before a limit
bites? Three limits are read at each power:
  - peak fuel centerline vs the ~970 K U-ZrH hydride wall
  - peak clad vs the Hastelloy-N limit (placeholder, shared with component F1)
  - required NaK flow vs what the EM pump can deliver (A3)

ARCHITECTURE NOTE (per the structural roadmap recommendation): this runs in the cheap
analytic model, not the stiff coupled Cardinal solve. The friction and pump physics
that bound the uprate are 1-D channel closures, so the answer does not need the 3-D
conjugate. Use Cardinal only to spot-validate the ceiling for feedback-shifted peaking.

KEY PHYSICS the sweep exposes: at FIXED geometry and a FIXED EM pump, the hydraulic
operating point (pump curve intersect loop curve) pins the flow near design REGARDLESS
of power -- power does not enter the momentum balance. So you cannot simply add flow to
hold the fuel temperature down; the fuel wall caps the uprate at the design flow, and
relieving it needs more flow than the pump supplies. Both numbers are reported.

SCOPE / caveats (honest, first cut):
- Only the COOLANT properties are temperature-dependent (A1). Solid conductivities are
  the project constants (fuel 22.484, coat 1.729, clad 18.86); a clad k(T) is a small
  later refinement.
- Peaking is the analytic 1.56 radial x 1.40 axial; a Cardinal feedback run could shift
  it at high power.
- The EM pump curve uses the half-stall placeholder (A3) until NAA-SR-11879 is scanned.
- The clad temperature limit is a placeholder pending component F1 (material life).
"""
import argparse
import numpy as np
import nak78_properties as nak
import channel_hydraulics as hyd
import em_pump_curve as pump

# --- operating point / geometry (SI), consistent with hot_channel_analytic.py ------
N_PINS  = 37
T_IN    = 755.37
MDOT_TOT_DESIGN = 0.6199
R_FUEL, R_COAT, R_CLAD = 0.0153924, 0.0156210, 0.0158750
L       = 0.310515
HTC     = 5.01e4
K_FUEL, K_COAT, K_CLAD = 22.484, 1.729, 18.86

# --- limits ------------------------------------------------------------------------
T_FUEL_LIMIT = 970.0     # U-ZrH service limit (Simnad, SNAP 700 C); F1-confirmed, Material_Life_F1.md
T_CLAD_LIMIT = 977.0     # Hastelloy-N 704 C creep ceiling (Haynes/ASME); F1-confirmed

# --- radial peaking ----------------------------------------------------------------
# MEASURED from the snap OpenMC model by extract_pin_power.py (1M particles x 100
# batches, fig12_test operating case): hot pin / average pin = 1.317. This supersedes
# the 1.56 the sweep first borrowed from the Layer 2 report. The 1.56 was a local
# power-DENSITY peak that folded in axial peaking; this sweep applies the axial factor
# (1.40) separately, so the correct radial factor is the pin-integrated 1.317. Using
# 1.56 double-counted axial peaking and was over-conservative.
F_RADIAL = 1.317
F_AXIAL = 1.40


def k_clad_of_T(T):
    """Hastelloy-N clad conductivity [W/m-K], ORNL/MSDR correlation from the project's
    k_of_T_sources.md (reproduces arXiv Table II's 18.852 at ~800 K). Rises with T, so
    it slightly relieves the clad drop at uprated temperatures."""
    return 9.77 - 3.2e-4 * T + 1.46e-5 * T * T


def hot_channel(p_core, mdot_tot, f_radial=F_RADIAL, f_axial=F_AXIAL, nz=400, clad_kT=True):
    """March the hot channel with temperature-dependent NaK cp. Returns mixed-mean and
    hot-channel outlet, peak fuel centerline, peak clad inner-surface temperature."""
    mdot_ch = mdot_tot / N_PINS
    p_hot   = (p_core / N_PINS) * f_radial
    qp_mean = p_hot / L
    dz = L / nz

    def fz(z):
        return 1.0 + (f_axial - 1.0) * np.cos(2.0 * np.pi * (z - L / 2.0) / L)

    t_f = T_IN
    peak_fuel = peak_clad = -1e9
    t_out = T_IN
    for i in range(nz):
        z = (i + 0.5) * dz
        qp = qp_mean * fz(z)
        cp_loc = float(nak.cp(t_f))
        t_f += qp * dz / (mdot_ch * cp_loc)
        dt_film = qp / (2 * np.pi * R_CLAD) / HTC
        k_clad = k_clad_of_T(t_f + dt_film) if clad_kT else K_CLAD
        dt_clad = qp / (2 * np.pi * k_clad) * np.log(R_CLAD / R_COAT)
        dt_coat = qp / (2 * np.pi * K_COAT) * np.log(R_COAT / R_FUEL)
        dt_fuel = qp / (4 * np.pi * K_FUEL)
        t_clad_in = t_f + dt_film + dt_clad                       # clad/coat interface
        t_fuel_cl = t_clad_in + dt_coat + dt_fuel                 # fuel centerline
        peak_fuel = max(peak_fuel, t_fuel_cl)
        peak_clad = max(peak_clad, t_clad_in)
        t_out = t_f

    # mixed-mean outlet uses the band-mean cp
    cp_mean = float(nak.cp(0.5 * (T_IN + t_out)))
    t_mix_out = T_IN + p_core / (N_PINS * mdot_ch * cp_mean)
    return dict(t_mix_out=t_mix_out, t_hot_out=t_out,
                peak_fuel=peak_fuel, peak_clad=peak_clad)


def hydraulics(mdot_tot, t_mean, t_pump):
    """Per-channel friction, loop demand, and pump headroom at this flow. t_pump is the
    NaK temperature the EM pump sees (core outlet), which sets the Figure 14 curve."""
    mdot_ch = mdot_tot / N_PINS
    rho_m, mu_m = float(nak.rho(t_mean)), float(nak.mu(t_mean))
    fr = hyd.dp_friction(mdot_ch, rho_m, mu_m)
    Q = mdot_tot / rho_m
    hr = pump.headroom(Q, t_pump, pump.K_LOOP_DESIGN)
    return dict(Q=Q, dP_core=fr["dP"], Re=fr["Re"], V=fr["V"], **hr)


def coupled_flow(p_core, head_factor=1.0, itmax=200, tol=1e-5):
    """The flow the EM pump actually delivers at this power, by iterating the pump
    operating point (Figure 14) against the resulting NaK outlet temperature. This is
    the thermoelectric coupling: more power -> hotter NaK -> higher pump curve -> more
    flow, a self-limiting feedback. head_factor < 1 is end-of-life pump degradation.
    Returns (mdot_tot, hot_channel state)."""
    mdot = MDOT_TOT_DESIGN
    for _ in range(itmax):
        hc = hot_channel(p_core, mdot)
        T_pump = hc["t_mix_out"]
        op = pump.operating_point(T_pump, pump.K_LOOP_DESIGN, head_factor)
        mdot_new = op["Q"] * float(nak.rho(T_pump))
        if abs(mdot_new - mdot) < tol * mdot:
            mdot = mdot_new
            break
        mdot = 0.5 * (mdot + mdot_new)        # under-relax for stability
    return mdot, hot_channel(p_core, mdot)


def find_fuel_ceiling_coupled(wall=T_FUEL_LIMIT, head_factor=1.0):
    """Fuel-limited ceiling when the flow is set by the pump (Figure 14), not held."""
    lo, hi = 20000.0, 300000.0
    for _ in range(55):
        mid = 0.5 * (lo + hi)
        _, hc = coupled_flow(mid, head_factor)
        if hc["peak_fuel"] < wall:
            lo = mid
        else:
            hi = mid
    return lo


def row(p_core, mdot_tot):
    hc = hot_channel(p_core, mdot_tot)
    t_mean = 0.5 * (T_IN + hc["t_hot_out"])
    hy = hydraulics(mdot_tot, t_mean, hc["t_mix_out"])
    fuel_margin = T_FUEL_LIMIT - hc["peak_fuel"]
    clad_margin = T_CLAD_LIMIT - hc["peak_clad"]
    # flow is held at design, so the pump sits at its operating point by construction;
    # the pump constraint is read in the dedicated flow-needed analysis below, not here.
    limits = []
    if fuel_margin < 0: limits.append("FUEL")
    if clad_margin < 0: limits.append("CLAD")
    return dict(p=p_core, **hc, **hy, fuel_margin=fuel_margin,
                clad_margin=clad_margin, limit=",".join(limits) or "ok")


def find_fuel_ceiling(mdot_tot=MDOT_TOT_DESIGN, f_radial=F_RADIAL, f_axial=F_AXIAL,
                      wall=T_FUEL_LIMIT, clad_kT=True):
    """Bisection: the core power [W] at which the hot-pin peak fuel reaches the hydride
    wall, at the given flow and peaking. This is the fuel-limited uprate ceiling."""
    lo, hi = 20000.0, 300000.0
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        pf = hot_channel(mid, mdot_tot, f_radial, f_axial, clad_kT=clad_kT)["peak_fuel"]
        if pf < wall:
            lo = mid
        else:
            hi = mid
    return lo


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--p-min", type=float, default=34.0, help="min core power [kWt]")
    ap.add_argument("--p-max", type=float, default=110.0, help="max core power [kWt]")
    ap.add_argument("--step", type=float, default=4.0, help="power step [kWt]")
    args = ap.parse_args()

    print("SNAP-10A uprate sweep -- design flow held (the EM pump cannot add flow)\n")
    print(f"limits: fuel {T_FUEL_LIMIT:.0f} K, clad {T_CLAD_LIMIT:.0f} K (placeholder), "
          f"pump from A3 (half-stall placeholder)\n")
    hdr = (f"{'kWt':>5} {'mix out':>8} {'hot out':>8} {'pk fuel':>8} {'fuel mgn':>9} "
           f"{'pk clad':>8} {'Re':>6} {'limit':>10}")
    print(hdr); print("-" * len(hdr))

    ceiling = None
    powers = np.arange(args.p_min, args.p_max + 1e-9, args.step) * 1000.0
    for P in powers:
        r = row(P, MDOT_TOT_DESIGN)
        print(f"{P/1e3:>5.0f} {r['t_mix_out']:>8.1f} {r['t_hot_out']:>8.1f} "
              f"{r['peak_fuel']:>8.1f} {r['fuel_margin']:>9.1f} {r['peak_clad']:>8.1f} "
              f"{r['Re']:>6.0f} {r['limit']:>10}")
        if r["limit"] == "ok":
            ceiling = P

    fuel_ceiling = find_fuel_ceiling()
    coupled_ceiling = find_fuel_ceiling_coupled()
    coupled_ceiling_eol = find_fuel_ceiling_coupled(head_factor=pump.EOL_HEAD_FACTOR)

    print("\n--- reading ---")
    hc34 = hot_channel(34000.0, MDOT_TOT_DESIGN)
    print(f"Design point check (34 kWt): mix outlet {hc34['t_mix_out']:.1f} K "
          f"(target 817.7), peak fuel {hc34['peak_fuel']:.1f} K with the measured 1.317 "
          f"radial peaking (Layer 2 reported 867 K using the over-conservative 1.56).")
    print(f"Fuel-limited ceiling, DESIGN FLOW held         : {fuel_ceiling/1e3:.1f} kWt")
    print(f"Fuel-limited ceiling, PUMP-COUPLED, begin-of-life: {coupled_ceiling/1e3:.1f} kWt "
          f"(Figure 14, flow rises with NaK temperature)")
    print(f"Fuel-limited ceiling, PUMP-COUPLED, end-of-life  : {coupled_ceiling_eol/1e3:.1f} "
          f"kWt (pump degraded ~13% flow over 1 yr, Figure 33)")

    print("\nHow the pump-delivered flow grows with power (the TE coupling):")
    print(f"{'kWt':>5} {'flow kg/s':>10} {'x design':>9} {'mix out K':>10} "
          f"{'pk fuel K':>10}")
    for P in sorted((34e3, coupled_ceiling, 80e3, 100e3)):
        mdot, hc = coupled_flow(P)
        print(f"{P/1e3:>5.0f} {mdot:>10.3f} {mdot/MDOT_TOT_DESIGN:>9.2f} "
              f"{hc['t_mix_out']:>10.1f} {hc['peak_fuel']:>10.1f}")

    print("\nReading: the real Figure 14 pump curve raises performance with NaK temperature,")
    print("so as the core is uprated the pump delivers more flow on its own, lifting the")
    print(f"fuel-limited ceiling from ~{fuel_ceiling/1e3:.0f} kWt (flow held) to "
          f"~{coupled_ceiling/1e3:.0f} kWt begin-of-life. Pump degradation over the mission")
    print(f"pulls the SUSTAINED ceiling down to ~{coupled_ceiling_eol/1e3:.0f} kWt end-of-life, "
          f"which is the number a")
    print("design must actually meet for a year. Both beat the held-flow case, so the reading")
    print("leans toward 'same reactor run harder' being viable, with end-of-life pump margin")
    print("as the real constraint rather than the pump's beginning-of-life capacity.")
    print("Caveats still open: clad/fuel temperature limits (component F1), feedback-shifted")
    print("peaking (a Cardinal spot-check), and that the pump curve above 1000 F NaK is")
    print("extrapolated (validated against the 1056 F flight point to within ~6%).")


if __name__ == "__main__":
    main()

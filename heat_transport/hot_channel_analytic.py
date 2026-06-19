#!/usr/bin/env python3
"""
hot_channel_analytic.py  --  SNAP-10A hot-channel temperatures from the validated
OpenMC per-pin power, by per-channel energy balance + analytic conduction.

WHY THIS EXISTS: the full Cardinal conjugate (37 THM channels) is correct in
geometry and neutronics (peaked per-pin power confirmed), but the wall<->fluid
coupling is brutally stiff (htc 5e4) and was not converging in a reasonable run.
The quantities that matter -- the NaK outlet that feeds the converter, and the peak
fuel temperature -- do not need the coupled solve: they follow from the per-pin
power, the per-channel flow, and 1-D radial conduction. This is the standard
hot-channel analysis and it is what the conjugate model would reproduce at
convergence.

INPUTS are the confirmed operating point. Radial peaking (1.56) is from the OpenMC
solid 'power' field (center ~6.2e6 vs core-average ~3.98e6 W/m3, ParaView). Axial
peaking (1.40) is from extract_heat_source.py's kappa-fission axial tally. Swap in
exact per-pin powers with --pin-powers if you extract them.
"""
import argparse, math

# ---- operating point / geometry (SI) -----------------------------------------
N_PINS   = 37
T_IN     = 755.37          # NaK core inlet [K]
MDOT_CH  = 0.0167541       # per-channel NaK mass flow [kg/s]
CP       = 879.903         # NaK cp [J/kg-K]
R_FUEL   = 0.0153924       # fuel radius [m]
R_COAT   = 0.0156210       # coating outer radius [m]
R_CLAD   = 0.0158750       # clad outer radius [m]
L        = 0.310515        # active length [m]
HTC      = 5.01e4          # clad-NaK heat-transfer coeff [W/m2-K]
K_FUEL   = 22.484          # U-ZrH fuel k [W/m-K]   (arXiv Table II)
K_COAT   = 1.729           # coating/gap k [W/m-K]
K_CLAD   = 18.86           # Hastelloy-N clad k at ~800 K [W/m-K]


def hot_channel(p_core, f_radial, f_axial, nz=400):
    wch = MDOT_CH * CP                      # per-channel heat capacity rate [W/K]
    p_avg = p_core / N_PINS                 # core-average pin power [W]
    p_hot = p_avg * f_radial                # hot-pin power [W]

    # mixed-mean core outlet = the temperature the converter hot side actually sees
    t_mix_out = T_IN + p_core / (N_PINS * wch)

    # --- march the HOT channel along z (0 = inlet, L = outlet) -----------------
    # axial linear-power shape, mean 1, peak f_axial at mid-core
    def f(z):
        return 1.0 + (f_axial - 1.0) * math.cos(2.0 * math.pi * (z - L / 2.0) / L)
    dz = L / nz
    qp_mean = p_hot / L                     # mean linear power of the hot pin [W/m]
    t_f = T_IN
    peak_fuel_cl = -1e9
    peak_z = 0.0
    t_out = T_IN
    for i in range(nz):
        z = (i + 0.5) * dz
        qp = qp_mean * f(z)                 # local linear power [W/m]
        t_f += qp * dz / wch               # fluid temperature at this node
        # radial conduction drops (cylindrical), all driven by local linear power qp
        dt_film = qp / (2 * math.pi * R_CLAD) / HTC                       # film
        dt_clad = qp / (2 * math.pi * K_CLAD) * math.log(R_CLAD / R_COAT)  # clad
        dt_coat = qp / (2 * math.pi * K_COAT) * math.log(R_COAT / R_FUEL)  # coat/gap
        dt_fuel = qp / (4 * math.pi * K_FUEL)                              # fuel CL
        t_fuel_cl = t_f + dt_film + dt_clad + dt_coat + dt_fuel
        if t_fuel_cl > peak_fuel_cl:
            peak_fuel_cl = t_fuel_cl
            peak_z = z
            peak_break = (dt_film, dt_clad, dt_coat, dt_fuel)
        t_out = t_f
    return dict(p_avg=p_avg, p_hot=p_hot, t_mix_out=t_mix_out, t_hot_out=t_out,
                peak_fuel_cl=peak_fuel_cl, peak_z=peak_z, peak_break=peak_break,
                hot_rise=t_out - T_IN)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--power", type=float, default=34000.0, help="core thermal power [W]")
    ap.add_argument("--f-radial", type=float, default=1.56, help="hot-pin/avg radial peaking")
    ap.add_argument("--f-axial", type=float, default=1.40, help="peak/avg axial peaking")
    args = ap.parse_args()

    print(f"SNAP-10A hot-channel analytic estimate")
    print(f"  core power {args.power/1000:.0f} kWt, radial peak {args.f_radial:.2f}, "
          f"axial peak {args.f_axial:.2f}\n")
    for P in sorted({args.power, 34000.0, 40000.0, 46000.0}):
        r = hot_channel(P, args.f_radial, args.f_axial)
        df, dc, dk, dfu = r['peak_break']
        print(f"P_core = {P/1000:>4.0f} kWt")
        print(f"  avg pin {r['p_avg']:6.0f} W   hot pin {r['p_hot']:6.0f} W")
        print(f"  mixed-mean NaK outlet (-> converter hot side) : {r['t_mix_out']:6.1f} K")
        print(f"  HOT-channel NaK outlet                        : {r['t_hot_out']:6.1f} K "
              f"(rise {r['hot_rise']:.0f} K)")
        print(f"  HOT-channel peak fuel centerline              : {r['peak_fuel_cl']:6.1f} K "
              f"(at z={r['peak_z']*100:.0f}/{L*100:.0f} cm)")
        print(f"     film {df:.1f} + clad {dc:.1f} + coat {dk:.1f} + fuel {dfu:.1f} K "
              f"above the local NaK\n")


if __name__ == "__main__":
    main()

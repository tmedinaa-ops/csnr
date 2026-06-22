#!/usr/bin/env python3
"""
channel_hydraulics.py -- tight-lattice subchannel friction and pressure drop for the
SNAP-10A NaK core (component A2 of the uprate roadmap).

WHY THIS EXISTS:
The uprate is bounded by the coolant, not the fuel. To find the ceiling we have to
charge the flow a pumping head, which means a friction model. Nothing in the project
did this; flow was free. This module gives the per-channel friction pressure drop as a
function of mass flow and temperature, using the Cheng-Todreas rod-bundle correlation,
the same correlation MOOSE's ADWallFrictionChengMaterial implements, so the analytic
sweep and any later coupled run agree.

GEOMETRY: hexagonal (triangular-pitch) bare-rod bundle. The rod diameter for the
coolant subchannel is the CLAD outer diameter, D = 2*R_CLAD = 0.031750 m, and the hex
pitch P = 0.0320040 m, giving P/D = 1.008 (very tight). This resolves the apparent
"1.0396" reading, which used the fuel-meat radius rather than the wetted clad surface.

CHENG-TODREAS (verified against MOOSE source ADWallFrictionChengMaterial.C):
  f_Fanning = Cf / Re^n ,   Cf = a + b*(P/D - 1) + c*(P/D - 1)^2 ,   f_Darcy = 4*f_F
  n = 1 (laminar), n = 0.18 (turbulent).
  HEX INTERIOR subchannel, 1.0 <= P/D <= 1.1 coefficients:
    laminar   a=26,      b=888.2,  c=-3334
    turbulent a=0.09378, b=1.398,  c=-8.664
  Transition is blended between ReL and ReT (the physical CTD form). MOOSE's THM
  material instead hard-splits at Re=2100 and skips the blend; both modes are provided
  (mode='three_regime' default for accuracy, mode='moose' to match THM exactly).

VALIDITY: P/D = 1.008 sits at the extreme tight edge of CTD (stated ~1.0-1.5) and the
bundle has 37 >= 19 pins, so it is inside range, but the near-touching laminar geometry
factor carries extra uncertainty. Reference: Todreas & Kazimi, Nuclear Systems I (3rd
ed.), Eqs. 9.105/9.109, Tables 9.5; Cheng & Todreas, Nucl. Eng. Des. 92 (1986) 227.
"""
import numpy as np

# --- geometry (SI), clad-OD based --------------------------------------------------
R_CLAD = 0.0158750
D_ROD  = 2.0 * R_CLAD          # 0.031750 m, the wetted rod diameter
PITCH  = 0.0320040             # hex pitch
POD    = PITCH / D_ROD         # 1.008
L_ACT  = 0.310515             # active length

# Cheng-Todreas hex-interior coefficients, 1.0 <= P/D <= 1.1
_LAM  = (26.0,    888.2, -3334.0); _N_LAM  = 1.0
_TURB = (0.09378, 1.398, -8.664);  _N_TURB = 0.18


def cf(pod, coeffs):
    a, b, c = coeffs
    x = pod - 1.0
    return a + b * x + c * x * x


def hex_subchannel(D=D_ROD, P=PITCH):
    """Interior subchannel of a triangular-pitch bundle: flow area, wetted perimeter,
    hydraulic diameter [m]."""
    A_flow = (np.sqrt(3.0) / 4.0) * P * P - (np.pi / 8.0) * D * D
    P_wet  = 0.5 * np.pi * D
    Dh     = 4.0 * A_flow / P_wet
    return dict(A_flow=A_flow, P_wet=P_wet, Dh=Dh, PoD=P / D)


def _re_bounds(pod):
    ReL = 300.0 * 10.0 ** (1.7 * (pod - 1.0))
    ReT = 1.0e4 * 10.0 ** (0.7 * (pod - 1.0))
    return ReL, ReT


def friction_factor(Re, pod=POD, mode="three_regime"):
    """Darcy friction factor for the hex interior subchannel."""
    Re = max(float(Re), 1.0)
    fF_lam  = cf(pod, _LAM)  / Re ** _N_LAM
    fF_turb = cf(pod, _TURB) / Re ** _N_TURB
    if mode == "moose":                       # THM ADWallFrictionChengMaterial behaviour
        fF = fF_lam if Re <= 2100.0 else fF_turb
    else:                                     # physical three-regime CTD
        ReL, ReT = _re_bounds(pod)
        if Re <= ReL:
            fF = fF_lam
        elif Re >= ReT:
            fF = fF_turb
        else:
            psi = (np.log10(Re) - np.log10(ReL)) / (np.log10(ReT) - np.log10(ReL))
            fF = fF_lam * (1.0 - psi) ** (1.0 / 3.0) + fF_turb * psi ** (1.0 / 3.0)
    return 4.0 * fF                           # Fanning -> Darcy


def dp_friction(mdot_ch, rho, mu, L=L_ACT, D=D_ROD, P=PITCH, mode="three_regime"):
    """Per-channel friction pressure drop [Pa] for mass flow mdot_ch [kg/s]."""
    g = hex_subchannel(D, P)
    V  = mdot_ch / (rho * g["A_flow"])
    Re = rho * V * g["Dh"] / mu
    f  = friction_factor(Re, g["PoD"], mode)
    dP = f * (L / g["Dh"]) * (rho * V * V / 2.0)
    return dict(V=V, Re=Re, f_darcy=f, dP=dP, **g)


def validate():
    print("Cheng-Todreas hex-interior friction -- validation\n")
    # 1) Cf polynomial at P/D = 1.05 (the MOOSE-source-verified check point)
    print("Cf at P/D = 1.05 (vs MOOSE ADWallFrictionChengMaterial.C):")
    print(f"  laminar  Cf = {cf(1.05, _LAM):.4f}   (expected 62.075)")
    print(f"  turbulent Cf = {cf(1.05, _TURB):.5f}  (polynomial value 0.14202)\n")

    # 2) geometry at the SNAP P/D = 1.008
    g = hex_subchannel()
    print(f"SNAP subchannel geometry (D={D_ROD*1e3:.3f} mm, P={PITCH*1e3:.3f} mm, "
          f"P/D={g['PoD']:.4f}):")
    print(f"  A_flow = {g['A_flow']*1e6:.3f} mm^2   Dh = {g['Dh']*1e3:.3f} mm   "
          f"P_wet = {g['P_wet']*1e3:.3f} mm")
    ReL, ReT = _re_bounds(POD)
    print(f"  transition Reynolds bounds: ReL = {ReL:.0f}, ReT = {ReT:.0f}\n")

    # 3) design-point pressure drop (anchored NaK at ~786 K mean, design per-channel flow)
    import nak78_properties as nak
    Tm = 0.5 * (755.37 + 817.7)
    rho_m, mu_m = float(nak.rho(Tm)), float(nak.mu(Tm))
    r = dp_friction(0.0167541, rho_m, mu_m)
    print(f"Design point (mdot_ch=0.016754 kg/s, NaK at {Tm:.0f} K, "
          f"rho={rho_m:.1f}, mu={mu_m:.3e}):")
    print(f"  V = {r['V']:.3f} m/s   Re = {r['Re']:.0f}   f_Darcy = {r['f_darcy']:.4f}")
    print(f"  core friction dP = {r['dP']:.1f} Pa ({r['dP']/1e3:.3f} kPa)")
    print("  -> small vs the 7.58 kPa pump head, so the loop dP is dominated by the")
    print("     converter, piping and form losses, not bare core friction (expected).")


if __name__ == "__main__":
    validate()

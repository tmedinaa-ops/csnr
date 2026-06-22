#!/usr/bin/env python3
"""
make_figures.py -- analytical figures for the uprate study, regenerated from the live
models so the plots always match the numbers. Writes PNGs to figs/, which the
Implementation_Research_Dossier.md embeds.

Run: python3 make_figures.py    (pure NumPy + Matplotlib; no OpenMC/Cardinal needed)
"""
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import nak78_properties as nak
import channel_hydraulics as hyd
import em_pump_curve as pump
import sweep

FIGS = os.path.join(os.path.dirname(__file__), "figs")
os.makedirs(FIGS, exist_ok=True)
plt.rcParams.update({"figure.dpi": 120, "font.size": 10, "axes.grid": True,
                     "grid.alpha": 0.3, "axes.axisbelow": True})


def fig_a1_nak_properties():
    T = np.linspace(700, 1100, 200)
    fig, ax = plt.subplots(2, 2, figsize=(9, 6.5))
    specs = [("rho", nak.rho, "density [kg/m$^3$]", "rho"),
             ("cp", nak.cp, "specific heat [J/kg-K]", "cp"),
             ("k", nak.k, "thermal conductivity [W/m-K]", "k"),
             ("mu", nak.mu, "viscosity [Pa-s]", "mu")]
    for a, (name, fn, ylab, key) in zip(ax.flat, specs):
        a.plot(T, fn(T, anchored=True), label="anchored (Table II)")
        a.plot(T, fn(T, anchored=False), "--", label="raw correlation", alpha=0.7)
        a.plot(nak.ANCHOR_T, nak.ANCHOR[key], "ko", ms=6,
               label="arXiv Table II (783 K)")
        a.axvspan(755.37, 855, color="C1", alpha=0.08)
        a.set_xlabel("NaK temperature [K]"); a.set_ylabel(ylab)
        a.set_title(name)
    ax.flat[0].legend(fontsize=7, loc="upper right")
    fig.suptitle("A1  NaK-78 properties vs temperature (shaded = SNAP operating band)",
                 fontsize=11)
    fig.tight_layout()
    p = os.path.join(FIGS, "fig_a1_nak_properties.png")
    fig.savefig(p); plt.close(fig); return p


def fig_a2_friction():
    Re = np.logspace(2, 5.5, 300)
    f_three = [hyd.friction_factor(r, hyd.POD, "three_regime") for r in Re]
    f_moose = [hyd.friction_factor(r, hyd.POD, "moose") for r in Re]
    ReL, ReT = hyd._re_bounds(hyd.POD)

    fig, ax = plt.subplots(1, 2, figsize=(10, 4.2))
    ax[0].loglog(Re, f_three, label="three-regime (physical)")
    ax[0].loglog(Re, f_moose, "--", label="MOOSE 2100 split", alpha=0.8)
    for x, lab in ((ReL, "Re$_L$"), (ReT, "Re$_T$")):
        ax[0].axvline(x, color="grey", ls=":", lw=1)
        ax[0].text(x, 0.012, lab, rotation=90, va="bottom", fontsize=8)
    ax[0].axvline(7300, color="C3", lw=1.2)
    ax[0].text(7300, 0.5, "SNAP design Re", rotation=90, va="top", color="C3", fontsize=8)
    ax[0].set_xlabel("Reynolds number"); ax[0].set_ylabel("Darcy friction factor")
    ax[0].set_title("Cheng-Todreas, hex interior, P/D=1.008"); ax[0].legend(fontsize=8)

    Tm = 0.5 * (755.37 + 817.7)
    rho_m, mu_m = float(nak.rho(Tm)), float(nak.mu(Tm))
    mdot = np.linspace(0.005, 0.06, 200)
    dP = [hyd.dp_friction(m, rho_m, mu_m)["dP"] / 1e3 for m in mdot]
    ax[1].plot(mdot, dP)
    ax[1].plot(0.0167541, hyd.dp_friction(0.0167541, rho_m, mu_m)["dP"] / 1e3, "ko",
               label="design per-channel flow")
    ax[1].set_xlabel("per-channel mass flow [kg/s]")
    ax[1].set_ylabel("core friction $\\Delta P$ [kPa]")
    ax[1].set_title("Per-channel friction pressure drop"); ax[1].legend(fontsize=8)
    fig.tight_layout()
    p = os.path.join(FIGS, "fig_a2_friction.png")
    fig.savefig(p); plt.close(fig); return p


def fig_a3_pump_curves():
    Q_gpm = np.linspace(0, 30, 200)
    Q = Q_gpm * pump.GPM
    fig, ax = plt.subplots(figsize=(7.5, 5))
    for T_F, col in zip(pump.FIG14_T_F, ("C0", "C1", "C2")):
        T_K = (T_F - 32) * 5 / 9 + 273.15
        head = pump.pump_head(Q, T_K) / pump.PSI
        ax.plot(Q_gpm, head, col, label=f"pump {T_F:.0f} F")
        op = pump.operating_point(T_K)
        ax.plot(op["Q_gpm"], op["dP"] / pump.PSI, col + "o", ms=7)
    # end-of-life curve at 1000 F
    T1000 = 810.9
    ax.plot(Q_gpm, pump.pump_head(Q, T1000, pump.EOL_HEAD_FACTOR) / pump.PSI, "C2:",
            label="1000 F end-of-life", alpha=0.8)
    # loop curve
    ax.plot(Q_gpm, pump.loop_head(Q) / pump.PSI, "k--", label="SNAP loop K Q$^2$")
    # design + flight points
    ax.plot(13.0, 1.10, "k*", ms=14, label="design point (1010 F)")
    ax.plot(pump.FLIGHT_GPM, pump.loop_head(pump.FLIGHT_GPM * pump.GPM) / pump.PSI,
            "kD", ms=7, label="flight point 1056 F (14.4 gpm)")
    ax.set_xlabel("flow [gpm]"); ax.set_ylabel("pressure [psi]")
    ax.set_ylim(0, 3.2); ax.set_xlim(0, 30)
    ax.set_title("A3  EM pump H-Q from NAA-SR-11879 Fig 14 (dots = operating points)")
    ax.legend(fontsize=8, loc="upper right")
    fig.tight_layout()
    p = os.path.join(FIGS, "fig_a3_pump_curves.png")
    fig.savefig(p); plt.close(fig); return p


def fig_b_uprate_sweep():
    P = np.linspace(34, 110, 120) * 1e3
    pf_held = [sweep.hot_channel(p, sweep.MDOT_TOT_DESIGN)["peak_fuel"] for p in P]
    pf_bol, pf_eol, flow_bol, flow_eol = [], [], [], []
    for p in P:
        m_b, hc_b = sweep.coupled_flow(p)
        m_e, hc_e = sweep.coupled_flow(p, head_factor=pump.EOL_HEAD_FACTOR)
        pf_bol.append(hc_b["peak_fuel"]); pf_eol.append(hc_e["peak_fuel"])
        flow_bol.append(m_b); flow_eol.append(m_e)

    c_held = sweep.find_fuel_ceiling() / 1e3
    c_bol = sweep.find_fuel_ceiling_coupled() / 1e3
    c_eol = sweep.find_fuel_ceiling_coupled(head_factor=pump.EOL_HEAD_FACTOR) / 1e3

    fig, ax = plt.subplots(1, 2, figsize=(11, 4.5))
    ax[0].plot(P / 1e3, pf_held, label="flow held at design")
    ax[0].plot(P / 1e3, pf_bol, label="pump-coupled, begin-of-life")
    ax[0].plot(P / 1e3, pf_eol, label="pump-coupled, end-of-life")
    ax[0].axhline(sweep.T_FUEL_LIMIT, color="C3", ls="--", label="hydride wall 970 K")
    for c, lab, col in ((c_held, f"{c_held:.0f}", "C0"), (c_bol, f"{c_bol:.0f}", "C1"),
                        (c_eol, f"{c_eol:.0f}", "C2")):
        ax[0].axvline(c, color=col, ls=":", lw=1)
    ax[0].set_xlabel("core thermal power [kWt]"); ax[0].set_ylabel("peak fuel centerline [K]")
    ax[0].set_title("Fuel temperature vs power, and the three ceilings")
    ax[0].legend(fontsize=8)

    ax[1].plot(P / 1e3, np.array(flow_bol) / sweep.MDOT_TOT_DESIGN,
               label="pump-coupled, begin-of-life")
    ax[1].plot(P / 1e3, np.array(flow_eol) / sweep.MDOT_TOT_DESIGN,
               label="pump-coupled, end-of-life")
    ax[1].axhline(1.0, color="grey", ls="--", label="design flow")
    ax[1].set_xlabel("core thermal power [kWt]")
    ax[1].set_ylabel("NaK flow / design flow")
    ax[1].set_title("Pump-delivered flow rises with power (TE coupling)")
    ax[1].legend(fontsize=8)
    fig.suptitle(f"B1/B2  Uprate sweep (radial peaking {sweep.F_RADIAL:.3f}): "
                 f"held-flow {c_held:.0f} / begin-of-life {c_bol:.0f} / "
                 f"end-of-life {c_eol:.0f} kWt", fontsize=11)
    fig.tight_layout()
    p = os.path.join(FIGS, "fig_b_uprate_sweep.png")
    fig.savefig(p); plt.close(fig); return p


def _ceiling_fr(fr):
    """Pump-coupled fuel-limited ceiling [kWt] at a given radial peaking. The coupled
    flow is independent of f_radial (it follows the core-average outlet temperature), so
    take the coupled flow and evaluate the hot pin at the chosen peaking."""
    lo, hi = 20000.0, 300000.0
    for _ in range(45):
        mid = 0.5 * (lo + hi)
        m, _ = sweep.coupled_flow(mid)
        pf = sweep.hot_channel(mid, m, f_radial=fr)["peak_fuel"]
        if pf < sweep.T_FUEL_LIMIT:
            lo = mid
        else:
            hi = mid
    return lo / 1e3


def fig_b_sensitivity():
    base = sweep.find_fuel_ceiling_coupled() / 1e3
    rows = [("f_radial 1.25", _ceiling_fr(1.25) - base),
            ("f_radial 1.45", _ceiling_fr(1.45) - base),
            ("pump end-of-life",
             sweep.find_fuel_ceiling_coupled(head_factor=pump.EOL_HEAD_FACTOR) / 1e3 - base),
            ("wall 950 K", sweep.find_fuel_ceiling_coupled(wall=950) / 1e3 - base),
            ("wall 990 K", sweep.find_fuel_ceiling_coupled(wall=990) / 1e3 - base)]
    rows.sort(key=lambda r: r[1])
    labels = [r[0] for r in rows]
    deltas = [r[1] for r in rows]
    colors = ["C3" if d < 0 else "C2" for d in deltas]
    fig, ax = plt.subplots(figsize=(7.5, 4))
    ax.barh(labels, deltas, color=colors)
    ax.axvline(0, color="k", lw=0.8)
    ax.set_xlabel(f"change in pump-coupled ceiling [kWt]  (base {base:.0f} kWt)")
    ax.set_title("B2  Ceiling sensitivity (one input varied at a time)")
    fig.tight_layout()
    p = os.path.join(FIGS, "fig_b_sensitivity.png")
    fig.savefig(p); plt.close(fig); return p


if __name__ == "__main__":
    made = [fig_a1_nak_properties(), fig_a2_friction(), fig_a3_pump_curves(),
            fig_b_uprate_sweep(), fig_b_sensitivity()]
    for m in made:
        print("wrote", os.path.relpath(m, os.path.dirname(__file__)))

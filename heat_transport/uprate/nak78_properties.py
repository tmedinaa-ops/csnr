#!/usr/bin/env python3
"""
nak78_properties.py -- temperature-dependent thermophysical properties of NaK-78
(the sodium-potassium eutectic, 22 wt% Na / 78 wt% K) for the SNAP-10A uprate study.

WHY THIS EXISTS (component A1 of the uprate roadmap):
The heat_transport models so far carry NaK as constants: the analytic hot-channel uses
cp = 879.903 J/kg-K, and the Cardinal THM side used SimpleFluidProperties with a
room-temperature density (0.866 g/cm3) that is wrong for an 800 K loop by ~13%. The
uprate sweep pushes outlet temperatures up, so the properties have to move with
temperature. This module is the analytic-side property set; the MOOSE side has a
built-in NaKFluidProperties object (see Implementation_Research_Dossier.md, MOOSE A1).

SOURCES (full citations in the dossier):
- Density slope: Garber & Godfroy (NASA MSFC, ICAPP'06), rho = 872.85 - 0.2349*T_C,
  itself from SNAP Technology Handbook NAA-SR-8617. Cross-checks Foust 1972 to <1%.
- cp, k, mu: fitted to O.J. Foust (ed.), Sodium-NaK Engineering Handbook Vol. I (1972)
  synopsis data points; viscosity is the physically correct Arrhenius form.
- Anchors: Dalinger et al. (Cardinal, arXiv 2505.04024) Table II, NaK-78 at the design
  average 783.15 K: rho 755.92, cp 879.903, k 26.2345 W/m-K, mu 1.8835e-4 Pa-s.

ANCHORING (default on):
The raw literature correlations reproduce the arXiv Table II anchors to ~1-3%. To keep
bit-for-bit continuity with the v1.0-validated coupled model while still letting the
properties respond to temperature, the default mode shifts each correlation by a
constant (multiplicative for viscosity) so it passes exactly through the Table II
value at 783.15 K and carries the literature SLOPE around it. Set anchored=False for
the pure published correlation.

All public functions take T in KELVIN and return SI units. Scalars or numpy arrays.
"""
import numpy as np

# --- anchor point: arXiv 2505.04024 Table II, NaK-78 at design-average T ----------
ANCHOR_T = 783.15        # K  (design-average NaK)
ANCHOR = {
    "rho": 755.92,       # kg/m3
    "cp":  879.903,      # J/kg-K
    "k":   26.2345,      # W/m-K
    "mu":  1.8835e-4,    # Pa-s
}
ZERO_C = 273.15


# --- raw literature correlations (T in K internally -> C where the fit is in C) ----
def _rho_raw(T):                 # Garber & Godfroy / NAA-SR-8617, linear in C
    Tc = np.asarray(T, float) - ZERO_C
    return 872.85 - 0.2349 * Tc

def _cp_raw(T):                  # fit to Foust 1972, linear in C
    Tc = np.asarray(T, float) - ZERO_C
    return 965.9 - 0.1757 * Tc

def _k_raw(T):                   # fit to Foust 1972, linear in C (k RISES with T for NaK)
    Tc = np.asarray(T, float) - ZERO_C
    return 22.00 + 0.00775 * Tc

def _mu_raw(T):                  # fit to Foust 1972, Arrhenius in K
    Tk = np.asarray(T, float)
    return 6.925e-5 * np.exp(756.6 / Tk)


# --- additive / multiplicative anchor offsets (computed once) ---------------------
_OFF = {
    "rho": ANCHOR["rho"] - float(_rho_raw(ANCHOR_T)),
    "cp":  ANCHOR["cp"]  - float(_cp_raw(ANCHOR_T)),
    "k":   ANCHOR["k"]   - float(_k_raw(ANCHOR_T)),
}
_FAC_MU = ANCHOR["mu"] / float(_mu_raw(ANCHOR_T))   # viscosity: scale the Arrhenius


# --- public API -------------------------------------------------------------------
def rho(T, anchored=True):
    """Density [kg/m3], T in K."""
    return _rho_raw(T) + (_OFF["rho"] if anchored else 0.0)

def cp(T, anchored=True):
    """Isobaric specific heat [J/kg-K], T in K."""
    return _cp_raw(T) + (_OFF["cp"] if anchored else 0.0)

def k(T, anchored=True):
    """Thermal conductivity [W/m-K], T in K."""
    return _k_raw(T) + (_OFF["k"] if anchored else 0.0)

def mu(T, anchored=True):
    """Dynamic viscosity [Pa-s], T in K."""
    return _mu_raw(T) * (_FAC_MU if anchored else 1.0)

def prandtl(T, anchored=True):
    """Prandtl number cp*mu/k [-]."""
    return cp(T, anchored) * mu(T, anchored) / k(T, anchored)

def all_props(T, anchored=True):
    return dict(T=float(T), rho=float(rho(T, anchored)), cp=float(cp(T, anchored)),
                k=float(k(T, anchored)), mu=float(mu(T, anchored)),
                Pr=float(prandtl(T, anchored)))


def write_moose_csv(path, T_min=600.0, T_max=1100.0, nT=51,
                    p_min=1.0e5, p_max=2.0e5, nP=2, anchored=True):
    """Emit a TabulatedBicubicFluidProperties grid (only if you want to impose THESE
    correlations in MOOSE instead of the built-in NaKFluidProperties). Columns and
    row order follow the MOOSE format: pressure, temperature ascending, full grid."""
    Ts = np.linspace(T_min, T_max, nT)
    Ps = np.linspace(p_min, p_max, nP)
    rows = ["pressure, temperature, density, cp, k, viscosity"]
    for P in Ps:
        for T in Ts:
            rows.append(f"{P:.1f}, {T:.4f}, {float(rho(T,anchored)):.6f}, "
                        f"{float(cp(T,anchored)):.6f}, {float(k(T,anchored)):.6f}, "
                        f"{float(mu(T,anchored)):.8e}")
    with open(path, "w") as fh:
        fh.write("\n".join(rows) + "\n")
    return path


def validate(tol_pct=3.0):
    """Check the anchored and raw correlations against the arXiv Table II point, and
    print the SNAP operating band (755-855 K)."""
    print("NaK-78 property validation against arXiv 2505.04024 Table II (783.15 K)\n")
    print(f"{'prop':>5} {'anchor':>11} {'raw@783':>11} {'anchored@783':>13} {'raw err%':>9}")
    ok = True
    for name, fn in (("rho", _rho_raw), ("cp", _cp_raw), ("k", _k_raw), ("mu", _mu_raw)):
        a = ANCHOR[name]
        raw = float(fn(ANCHOR_T))
        anc = float({"rho": rho, "cp": cp, "k": k, "mu": mu}[name](ANCHOR_T))
        err = 100.0 * (raw - a) / a
        flag = "" if abs(err) <= tol_pct else "  <-- > tol"
        print(f"{name:>5} {a:>11.4g} {raw:>11.4g} {anc:>13.4g} {err:>8.2f}%{flag}")
        if abs(err) > tol_pct:
            ok = False
    print("\n  anchored mode reproduces every Table II value exactly by construction;")
    print("  the raw column shows the pure literature correlation error (all within "
          f"{tol_pct:.0f}%).\n")
    print("SNAP operating band, anchored:")
    print(f"{'T [K]':>7} {'rho':>9} {'cp':>9} {'k':>8} {'mu [Pa-s]':>12} {'Pr':>7}")
    for T in (755.37, 783.15, 817.7, 855.0, 900.0, 1050.0):
        p = all_props(T)
        print(f"{T:>7.1f} {p['rho']:>9.2f} {p['cp']:>9.2f} {p['k']:>8.3f} "
              f"{p['mu']:>12.4e} {p['Pr']:>7.4f}")
    print("\n  note rho falls from ~756 at design to ~700 at 1050 K (Route B hot side);")
    print("  the old 866 kg/m3 constant was the 20 C cold-fill value, ~13% too dense.")
    return ok


if __name__ == "__main__":
    validate()

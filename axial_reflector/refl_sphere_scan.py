#!/usr/bin/env python3
"""
refl_sphere_scan.py -- find the minimum-beryllium critical near-sphere reflector on the
m4 Li-7 + Nb-1Zr HALEU core.

Why: the radial-only sweep (hybrid_reflector_sweep.py MATSWAP=li_nb on m4) reached critical
at ~17.5 cm / 182 kg of beryllium, but a radial cylinder cannot reflect the axial ends, so it
overpays in mass to catch the 70% that leaks radially. snap.py's REFL_R knob builds a
spherical Be blanket that works both faces. This scans REFL_R, applies the same
NaK->Li-7 and Ni-steel->Nb-1Zr swap, runs k, and weighs the blanket, to find the smallest
sphere (and least beryllium) that reaches critical.

Per REFL_R it: (1) builds the U_MULT=4 model via snap.py with REFL_SHAPE=sphere, (2) weighs
the be_blanket_reflector cell by MC point sampling (blanket_mass.py's method), (3) applies the
Li-7 + Nb-1Zr swap, (4) runs k-eff. Reports k and Be mass vs REFL_R and interpolates the
critical radius, then compares its beryllium mass to the 182 kg radial-cylinder result.

Run on the PC (openmc-env, OPENMC_CROSS_SECTIONS set):
  SNAP_DIR=~/snap/haleu_test U_MULT=4 REFL_LIST=18,20,22,24,26 \
      OMP_NUM_THREADS=20 PARTICLES=200000 BATCHES=150 python refl_sphere_scan.py

Same caveat as the sweep: k=1 here is the eigenvalue only. The Nb hydrogen-getter cost, the
ZrH losing its hydrogen over the mission, is not in it and is the gate on whether this config
stays critical.
"""
import math
import os
import random
import subprocess
import sys
import warnings
from pathlib import Path

import numpy as np
import openmc
import openmc.data

warnings.filterwarnings("ignore", message="Another")
warnings.filterwarnings("ignore", category=openmc.IDWarning)


def _env(n, d):
    v = os.environ.get(n)
    return v if v not in (None, "") else d


SNAP_DIR     = Path(_env("SNAP_DIR", str(Path.home() / "snap" / "haleu_test"))).expanduser()
U_MULT       = _env("U_MULT", "4")
REFL_LIST    = [float(x) for x in _env("REFL_LIST", "18,20,22,24,26").split(",")]
LI7_ENRICH   = float(_env("LI7_ENRICH", "99.99"))
LI_DENSITY   = float(_env("LI_DENSITY", "0.49"))
NB_DENSITY   = float(_env("NB_DENSITY", "8.57"))
PARTICLES    = int(_env("PARTICLES", "200000"))
BATCHES      = int(_env("BATCHES", "150"))
INACTIVE     = int(_env("INACTIVE", "30"))
MASS_SAMPLES = int(_env("MASS_SAMPLES", "200000"))
RADIAL_KG    = float(_env("RADIAL_KG", "182"))   # the radial-cylinder critical mass to beat
OUTROOT      = Path(_env("OUTROOT", str(SNAP_DIR / "runs_sphere_m4")))

if not (SNAP_DIR / "snap.py").exists():
    raise SystemExit(f"no snap.py in {SNAP_DIR}; set SNAP_DIR to the haleu_test folder")


# --- material swap: same targeting as hybrid_reflector_sweep.py MATSWAP=li_nb -----------
def _li7():
    m = openmc.Material(name="Li-7 coolant")
    a7 = LI7_ENRICH / 100.0
    m.add_nuclide("Li7", a7)
    if a7 < 1.0:
        m.add_nuclide("Li6", 1.0 - a7)
    m.set_density("g/cm3", LI_DENSITY)
    return m


def _nb1zr():
    m = openmc.Material(name="Nb-1Zr")
    m.add_element("Nb", 0.99, "wo")
    m.add_element("Zr", 0.01, "wo")
    m.set_density("g/cm3", NB_DENSITY)
    return m


def _apply_li_nb(model):
    repl = {}
    for mat in model.geometry.get_all_materials().values():
        nucs = mat.get_nuclides()
        if "Na23" in nucs:
            repl[mat.id] = _li7()
        elif "Ni58" in nucs:
            repl[mat.id] = _nb1zr()
    if not repl:
        raise SystemExit("no Na/Ni materials found to swap")
    for cell in model.geometry.get_all_cells().values():
        f = cell.fill
        if isinstance(f, openmc.Material) and f.id in repl:
            cell.fill = repl[f.id]
        elif isinstance(f, (list, tuple)) and any(isinstance(x, openmc.Material) and x.id in repl for x in f):
            cell.fill = [repl[x.id] if isinstance(x, openmc.Material) and x.id in repl else x for x in f]
    model.materials = openmc.Materials(model.geometry.get_all_materials().values())


def build(refl_r):
    outdir = OUTROOT / f"r{refl_r:g}"
    outdir.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, U_MULT=str(U_MULT), REFL_SHAPE="sphere", REFL_R=str(refl_r))
    subprocess.run([sys.executable, "snap.py", "haleu_test", str(outdir)],
                   cwd=str(SNAP_DIR), env=env, check=True, stdout=subprocess.DEVNULL)
    return outdir / "model.xml"


def blanket_mass_kg(model):
    """Be mass of the be_blanket_reflector cell, by MC point sampling (blanket_mass.py method)."""
    geom = model.geometry
    blanket = next((c for c in geom.get_all_cells().values() if c.name == "be_blanket_reflector"), None)
    if blanket is None:
        return float("nan")
    mat = blanket.fill
    NA = 0.60221408
    density = sum(d * openmc.data.atomic_mass(n) for n, d, _ in mat.nuclides) / NA
    R = max((s.r for s in geom.get_all_surfaces().values() if isinstance(s, openmc.Sphere)), default=40.0)
    random.seed(1)
    hits = 0
    for _ in range(MASS_SAMPLES):
        p = (random.uniform(-R, R), random.uniform(-R, R), random.uniform(-R, R))
        found = geom.find(p)
        c = found[-1] if (found and isinstance(found[-1], openmc.Cell)) else None
        if c is not None and c.name == "be_blanket_reflector":
            hits += 1
    vol = (2 * R) ** 3 * hits / MASS_SAMPLES
    return vol * density / 1000.0


def run_k(model):
    model.tallies = openmc.Tallies()
    model.settings.particles = PARTICLES
    model.settings.batches = BATCHES
    model.settings.inactive = INACTIVE
    model.settings.run_mode = "eigenvalue"
    sp = model.run(output=False)
    with openmc.StatePoint(sp) as s:
        return s.keff.nominal_value, s.keff.std_dev


def main():
    print(f"snap: {SNAP_DIR}   U_MULT={U_MULT}   sphere REFL_R={REFL_LIST}")
    print("swap: NaK -> Li-7, Ni-steel -> Nb-1Zr\n")
    rows = []
    for r in REFL_LIST:
        mx = build(r)
        model = openmc.Model.from_model_xml(str(mx))
        mass = blanket_mass_kg(model)
        if math.isnan(mass):
            print(f"REFL_R {r:5.1f} cm   no be_blanket_reflector cell (radius below the vessel?) -- skipped")
            continue
        _apply_li_nb(model)
        k, s = run_k(model)
        rows.append((r, k, s, mass))
        flag = "  <-- critical" if k >= 1.0 else ""
        print(f"REFL_R {r:5.1f} cm   k {k:.5f} +/- {s:.5f}   Be {mass:6.1f} kg{flag}")

    crit = None
    for i in range(1, len(rows)):
        r0, k0, _, m0 = rows[i - 1]
        r1, k1, _, m1 = rows[i]
        if (k0 - 1.0) * (k1 - 1.0) <= 0 and k1 != k0:
            f = (1.0 - k0) / (k1 - k0)
            crit = (r0 + f * (r1 - r0), m0 + f * (m1 - m0))
            break

    print()
    if crit:
        print(f"critical near-sphere: REFL_R ~ {crit[0]:.1f} cm, ~ {crit[1]:.0f} kg Be")
        print(f"radial-cylinder critical was {RADIAL_KG:.0f} kg Be -> sphere saves ~ {RADIAL_KG - crit[1]:.0f} kg")
    else:
        print("no critical crossing in REFL_LIST; extend the range (up if all subcritical, down if all super)")

    if rows:
        np.savetxt("refl_sphere_scan.csv", np.array([r for r in rows]),
                   delimiter=",", header="refl_r_cm,keff,sigma,be_kg", comments="")
        print("wrote refl_sphere_scan.csv")


if __name__ == "__main__":
    main()

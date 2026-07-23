#!/usr/bin/env python3
"""
li_nb_base_reactivity.py -- one-shot reactivity of the U-ZrH HALEU core with the NaK
coolant swapped for enriched Li-7 and the Hastelloy-N clad swapped for Nb-1Zr.

This is the static-eigenvalue measurement of the coolant+clad material change, NOT the
reflector sweep. It runs the base model twice, as-built and with the two materials
replaced, and reports the reactivity worth of the swap. Vary LI7_ENRICH (e.g. 92.41 for
natural lithium) to price the Li-6 poison directly.

IMPORTANT, read before believing the number: a k-eff run only sees the lower parasitic
absorption of Li-7 and Nb versus NaK and Hastelloy-N. It does NOT see why this swap is a
trap on a hydride core. Niobium is a hydrogen getter and U-ZrH depends on holding its
hydrogen, so the real cost is hydrogen loss over time, which lives in the life/depletion
analysis, not the eigenvalue. Treat a positive delta here as the absorption gain only.

Run in openmc-env with OPENMC_CROSS_SECTIONS set:
  MODEL_XML=~/snap/haleu_test/m3/model.xml OMP_NUM_THREADS=20 python li_nb_base_reactivity.py

Knobs: LI7_ENRICH (atom % Li-7, default 99.99), LI_DENSITY (g/cc, 0.49 for liquid Li),
       NB_DENSITY (g/cc, 8.57 for Nb-1Zr), EXPECT_KBASE (self-check anchor, 0.869 at
       U_MULT=3), KBASE_TOL, RUN_BASELINE (1 default; 0 runs only the swapped case),
       PARTICLES/BATCHES/INACTIVE.
"""
import os
import warnings
from pathlib import Path

import openmc

warnings.filterwarnings("ignore", message="Another")  # benign cross-load ID reuse in one process


def _env(n, d):
    v = os.environ.get(n)
    return v if v not in (None, "") else d


MODEL_XML    = Path(_env("MODEL_XML", str(Path.home() / "snap" / "haleu_test" / "m3" / "model.xml"))).expanduser()
LI7_ENRICH   = float(_env("LI7_ENRICH", "99.99"))   # atom % Li-7
LI_DENSITY   = float(_env("LI_DENSITY", "0.49"))    # g/cc, liquid Li ~800 K
NB_DENSITY   = float(_env("NB_DENSITY", "8.57"))    # g/cc, Nb-1Zr
EXPECT_KBASE = float(_env("EXPECT_KBASE", "0.869"))
KBASE_TOL    = float(_env("KBASE_TOL", "0.010"))
RUN_BASELINE = _env("RUN_BASELINE", "1") == "1"
PARTICLES    = int(_env("PARTICLES", "200000"))
BATCHES      = int(_env("BATCHES", "150"))
INACTIVE     = int(_env("INACTIVE", "30"))

if not MODEL_XML.exists():
    raise SystemExit(f"missing {MODEL_XML}; build it first, e.g. in ~/snap/haleu_test:\n"
                     f"  U_MULT=3 python snap.py haleu_test m3")


def li7():
    m = openmc.Material(name="Li-7 coolant")
    a7 = LI7_ENRICH / 100.0
    m.add_nuclide("Li7", a7)
    if a7 < 1.0:
        m.add_nuclide("Li6", 1.0 - a7)
    m.set_density("g/cm3", LI_DENSITY)
    return m


def nb1zr():
    m = openmc.Material(name="Nb-1Zr clad")
    m.add_element("Nb", 0.99, "wo")
    m.add_element("Zr", 0.01, "wo")
    m.set_density("g/cm3", NB_DENSITY)
    return m


def _is_coolant(mat):
    return "Na23" in mat.get_nuclides()   # NaK is the only Na-bearing material in this model
def _is_clad(mat):
    return "Ni58" in mat.get_nuclides()   # Hastelloy-N is the only Ni-bearing material


def load(swap):
    model = openmc.Model.from_model_xml(str(MODEL_XML))
    model.tallies = openmc.Tallies()      # k-eff only; drop the heat mesh
    model.settings.particles = PARTICLES
    model.settings.batches = BATCHES
    model.settings.inactive = INACTIVE
    model.settings.run_mode = "eigenvalue"
    if not swap:
        return model, 0, 0

    repl, n_cool, n_clad = {}, 0, 0
    for mat in model.geometry.get_all_materials().values():
        if _is_coolant(mat):
            repl[mat.id] = li7(); n_cool += 1
        elif _is_clad(mat):
            repl[mat.id] = nb1zr(); n_clad += 1
    if n_cool == 0 or n_clad == 0:
        names = [f"{m.id}:{m.name}" for m in model.geometry.get_all_materials().values()]
        raise SystemExit(f"swap target not found (coolant={n_cool}, clad={n_clad}). "
                         f"materials in model: {names}")

    for cell in model.geometry.get_all_cells().values():
        f = cell.fill
        if isinstance(f, openmc.Material) and f.id in repl:
            cell.fill = repl[f.id]
        elif isinstance(f, (list, tuple)) and any(isinstance(x, openmc.Material) and x.id in repl for x in f):
            cell.fill = [repl[x.id] if isinstance(x, openmc.Material) and x.id in repl else x for x in f]
    model.materials = openmc.Materials(model.geometry.get_all_materials().values())
    return model, n_cool, n_clad


def run(model):
    sp = model.run(output=False)
    with openmc.StatePoint(sp) as s:
        return s.keff.nominal_value, s.keff.std_dev


def main():
    print(f"model: {MODEL_XML}")
    print(f"swap: NaK -> Li-7 ({LI7_ENRICH} at%, {LI_DENSITY} g/cc);  "
          f"Hastelloy-N -> Nb-1Zr ({NB_DENSITY} g/cc)\n")

    k_base = s_base = None
    if RUN_BASELINE:
        mb, _, _ = load(swap=False)
        k_base, s_base = run(mb)
        print(f"baseline (NaK + Hastelloy-N)  k = {k_base:.5f} +/- {s_base:.5f}")
        if abs(k_base - EXPECT_KBASE) > KBASE_TOL:
            raise SystemExit(f"SELF-CHECK FAIL: baseline k {k_base:.5f} off expected "
                             f"{EXPECT_KBASE:.3f} +/- {KBASE_TOL:.3f}. Wrong model/loading, "
                             f"or set EXPECT_KBASE for this build.")
        print("self-check: baseline matches the U_MULT=3 base. OK")

    ms, n_cool, n_clad = load(swap=True)
    print(f"\nswapped {n_cool} coolant + {n_clad} clad material(s)")
    k_sw, s_sw = run(ms)
    print(f"swapped  (Li-7 + Nb-1Zr)      k = {k_sw:.5f} +/- {s_sw:.5f}")

    if k_base is not None:
        worth = (k_sw - k_base) / (k_sw * k_base) * 1e5
        sig = ((s_sw ** 2 + s_base ** 2) ** 0.5) / (k_sw * k_base) * 1e5
        print(f"\nreactivity worth of the swap: {worth:+.0f} +/- {sig:.0f} pcm")
        print("NOTE: eigenvalue only. Excludes hydrogen loss from the Nb getter, which is the")
        print("real cost on a U-ZrH core and lives in the life analysis, not here.")


if __name__ == "__main__":
    main()

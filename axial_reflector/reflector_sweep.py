#!/usr/bin/env python3
"""
reflector_sweep.py -- the real worth-vs-thickness curve for added beryllium.

Runs k-eff for the baseline fig12 model and for a set of reflector variants (extra
radial beryllium, and/or axial end caps), and reports for each:
  - reflector worth  Delta-rho = (k - k_base)/(k*k_base) * 1e5   [pcm]
  - beryllium mass added  [kg]
  - reactivity horizon  (EXC0 + worth) / loss_rate   [yr]
so you can see where the worth saturates and what it costs in mass. This turns the
schematic worth-vs-thickness plot into measured numbers.

Two ways to build the variants, in order of reliability:

  OPTION A (preferred): wire build_variant() to snap.py, which builds the reflector
    parametrically. Cleanest, because it thickens the actual reflector rather than
    wrapping a shell outside the drums.

  OPTION B (generic, no snap.py): _generic_wrap() adds a beryllium shell and caps
    OUTSIDE the model's existing outer vacuum boundary, assuming that boundary is one
    ZCylinder plus two ZPlanes. This reflects neutrons that got past the drums back
    in, which is still a valid leakage reduction, but verify with a plots.xml
    (color_by material) that the beryllium landed where you expect before trusting k.

Run in openmc-env with OPENMC_CROSS_SECTIONS set:
  MODEL_XML=~/snap/model.xml python reflector_sweep.py
Knobs: RADIAL_CM (comma list), AXIAL_CM (comma list), EXC0_PCM, LOSS_PCM_YR,
       PARTICLES, BATCHES, INACTIVE.
"""
import os
from pathlib import Path

import numpy as np
import openmc


def _env(name, default):
    v = os.environ.get(name)
    return v if v not in (None, "") else default


MODEL_XML = Path(_env("MODEL_XML", str(Path.home() / "snap" / "model.xml"))).expanduser()
BE_DENSITY = 1.85  # g/cc
EXC0_PCM = float(_env("EXC0_PCM", "767"))       # as-built excess reactivity budget
LOSS_PCM_YR = float(_env("LOSS_PCM_YR", "337"))  # measured burnup loss rate (79 kWt)
RADIAL_CM = [float(x) for x in _env("RADIAL_CM", "0,3,5,8,10,15").split(",")]
AXIAL_CM = [float(x) for x in _env("AXIAL_CM", "0,5").split(",")]
PARTICLES = int(_env("PARTICLES", "40000"))
BATCHES = int(_env("BATCHES", "100"))
INACTIVE = int(_env("INACTIVE", "30"))

if not MODEL_XML.exists():
    raise SystemExit(f"missing {MODEL_XML}; set MODEL_XML to the snap fig12 model.xml")


def beryllium():
    be = openmc.Material(name="reflector_be_added")
    be.add_element("Be", 1.0)
    be.set_density("g/cm3", BE_DENSITY)
    be.add_s_alpha_beta("c_Be")
    return be


def _find_outer(model):
    """Return (radial ZCylinder, z-min ZPlane, z-max ZPlane) among the vacuum surfaces,
    or raise if the outer boundary is not a simple cylinder + two planes."""
    surfs = model.geometry.get_all_surfaces().values()
    vac = [s for s in surfs if getattr(s, "boundary_type", "") == "vacuum"]
    cyls = [s for s in vac if isinstance(s, openmc.ZCylinder)]
    planes = [s for s in vac if isinstance(s, openmc.ZPlane)]
    if len(cyls) != 1 or len(planes) != 2:
        raise SystemExit(
            "outer vacuum boundary is not one ZCylinder + two ZPlanes "
            f"(found {len(cyls)} cyl, {len(planes)} planes). Wire build_variant() to "
            "snap.py (OPTION A) for this geometry.")
    planes = sorted(planes, key=lambda p: p.z0)
    return cyls[0], planes[0], planes[1]


def _generic_wrap(radial_cm, axial_cm):
    model = openmc.Model.from_model_xml(str(MODEL_XML))
    if radial_cm == 0 and axial_cm == 0:
        return model  # baseline, unmodified

    cyl, zlo, zhi = _find_outer(model)
    R = cyl.r
    be = beryllium()
    model.materials.append(be)

    # open the old boundary, place the new one further out
    cyl.boundary_type = "transmissive"
    zlo.boundary_type = "transmissive"
    zhi.boundary_type = "transmissive"
    new_cyl = openmc.ZCylinder(r=R + radial_cm, boundary_type="vacuum")
    new_zhi = openmc.ZPlane(z0=zhi.z0 + axial_cm, boundary_type="vacuum")
    new_zlo = openmc.ZPlane(z0=zlo.z0 - axial_cm, boundary_type="vacuum")

    root = model.geometry.root_universe
    if radial_cm > 0:  # radial shell over the original axial span
        root.add_cell(openmc.Cell(fill=be, region=+cyl & -new_cyl & +zlo & -zhi))
    if axial_cm > 0:   # end caps out to the new radius
        root.add_cell(openmc.Cell(fill=be, region=-new_cyl & +zhi & -new_zhi))
        root.add_cell(openmc.Cell(fill=be, region=-new_cyl & +new_zlo & -zlo))
    if radial_cm > 0 and axial_cm > 0:  # fill the corner voids left by the shell
        root.add_cell(openmc.Cell(fill=be, region=+cyl & -new_cyl & +zhi & -new_zhi))
        root.add_cell(openmc.Cell(fill=be, region=+cyl & -new_cyl & +new_zlo & -zlo))
    return model


def build_variant(radial_cm, axial_cm):
    # OPTION A: replace the body with a snap.py call, e.g.
    #   import sys; sys.path.insert(0, str(Path.home()/"snap")); import snap
    #   return snap.build_model(case="fig12_test",
    #                            extra_radial_be_cm=radial_cm, axial_be_cm=axial_cm)
    return _generic_wrap(radial_cm, axial_cm)


def run_k(model):
    model.settings.particles = PARTICLES
    model.settings.batches = BATCHES
    model.settings.inactive = INACTIVE
    model.settings.run_mode = "eigenvalue"
    sp = model.run(output=False)
    with openmc.StatePoint(sp) as s:
        k = s.keff
    return k.nominal_value, k.std_dev


def be_mass_kg(radial_cm, axial_cm):
    """Approximate added beryllium mass from the outer radius and axial span."""
    model = openmc.Model.from_model_xml(str(MODEL_XML))
    cyl, zlo, zhi = _find_outer(model)
    R, H = cyl.r, (zhi.z0 - zlo.z0)
    Rn = R + radial_cm
    v_shell = np.pi * (Rn**2 - R**2) * H if radial_cm > 0 else 0.0
    v_caps = 2 * np.pi * Rn**2 * axial_cm if axial_cm > 0 else 0.0
    return (v_shell + v_caps) * BE_DENSITY / 1000.0


def main():
    print(f"baseline k from {MODEL_XML}")
    k_base, s_base = run_k(build_variant(0, 0))
    print(f"  k_base = {k_base:.5f} +/- {s_base:.5f}\n")

    rows = []
    for ax_cm in AXIAL_CM:
        for r_cm in RADIAL_CM:
            if r_cm == 0 and ax_cm == 0:
                k, s = k_base, s_base
            else:
                k, s = run_k(build_variant(r_cm, ax_cm))
            worth = (k - k_base) / (k * k_base) * 1e5
            mass = be_mass_kg(r_cm, ax_cm)
            horizon = (EXC0_PCM + worth) / LOSS_PCM_YR
            rows.append((r_cm, ax_cm, k, s, worth, mass, horizon))
            print(f"radial {r_cm:4.0f} cm  axial {ax_cm:3.0f} cm  k {k:.5f}  "
                  f"worth {worth:+7.0f} pcm  mass {mass:5.1f} kg  horizon {horizon:4.1f} yr")

    arr = np.array([r[:1] + r[1:] for r in rows], dtype=float)
    np.savetxt("reflector_sweep.csv", arr, delimiter=",",
               header="radial_cm,axial_cm,keff,sigma,worth_pcm,be_mass_kg,horizon_yr",
               comments="")
    print("\nwrote reflector_sweep.csv")

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(1, 2, figsize=(12, 4.6))
        for ax_cm in AXIAL_CM:
            m = arr[arr[:, 1] == ax_cm]
            m = m[np.argsort(m[:, 0])]
            lab = f"axial caps {ax_cm:.0f} cm" if ax_cm else "no caps"
            ax[0].plot(m[:, 0], m[:, 4], "o-", label=lab)
            ax[1].plot(m[:, 0], m[:, 6], "o-", label=lab)
        ax[0].set_xlabel("added radial Be [cm]"); ax[0].set_ylabel("worth [pcm]")
        ax[0].set_title("measured reflector worth"); ax[0].legend(fontsize=8); ax[0].grid(alpha=0.25)
        ax[1].axhline(7, ls=":", color="grey"); ax[1].axhline(EXC0_PCM / LOSS_PCM_YR, ls="--", color="#b03030")
        ax[1].set_xlabel("added radial Be [cm]"); ax[1].set_ylabel("horizon [yr]")
        ax[1].set_title(f"horizon at {LOSS_PCM_YR:.0f} pcm/yr"); ax[1].legend(fontsize=8); ax[1].grid(alpha=0.25)
        plt.tight_layout(); plt.savefig("reflector_sweep.png", dpi=140)
        print("wrote reflector_sweep.png")
    except Exception as e:
        print("plot skipped:", e)


if __name__ == "__main__":
    main()

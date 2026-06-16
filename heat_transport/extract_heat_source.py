"""
extract_heat_source.py
======================================================================
Pull the SNAP-10A heat source (the power shape) out of the snap OpenMC
model and write it in the form the MOOSE/Cardinal thermal deck consumes.

This is the bridge for "model the heat of the system from the OpenMC
model." OpenMC gives the SHAPE of the heat (where fission energy is
deposited); the MAGNITUDE is the assumed core thermal power (34 kWt).
The script combines them and writes absolute volumetric power q'''(z)
per fuel pin, so mvp/solid.i reads it directly (scale_factor = 1) and
the power_in postprocessor lands on 918.9 W with no further tuning.

The snap model is a single combined model.xml (built by snap.py with
model.export_to_model_xml). OpenMC ignores a separate tallies.xml when
model.xml is present, so the tally has to go INTO the model. This script
loads model.xml, injects a kappa-fission mesh tally, runs in a scratch
subdirectory so it never clobbers the validated model.xml, then reads the
statepoint.

WHERE TO RUN: on the Mac, in the snap directory, openmc-env active:
    conda activate openmc-env
    cd ~/Documents/snap
    python ~/Documents/Claude/Projects/CSNR/heat_transport/extract_heat_source.py
    cp axial_power.csv ~/Documents/Claude/Projects/CSNR/heat_transport/mvp/

Defaults target the fig12_test operating-condition model.xml already in
that folder (783 K), which is the case that matches the thermal model.
Use --particles to run a faster, lower-statistics shape if you just want
to see it work.
======================================================================
"""

import argparse
import math
import os
import sys

import numpy as np

try:
    import openmc
except ImportError:
    sys.exit("OpenMC not importable. Activate the openmc-env conda environment first.")

# ---- SNAP-10A constants for the magnitude + per-pin reduction ----------------
P_CORE = 34.0e3          # W thermal (base set: 34 kWt to match arXiv + shield)
N_PINS = 37              # fuel elements
R_FUEL = 1.53924         # cm fuel radius (arXiv Table I)
ACTIVE_L = 31.0515       # cm active fuel length (core centered at z=0 in snap.py)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", default="model.xml",
                    help="combined OpenMC model file (default model.xml in cwd)")
    ap.add_argument("--nz", type=int, default=30,
                    help="axial bins; match n_ax in the MOOSE deck (default 30)")
    ap.add_argument("--zmin", type=float, default=-ACTIVE_L / 2.0,
                    help="active region zmin [cm] (default -ACTIVE_L/2, snap is z-centered)")
    ap.add_argument("--zmax", type=float, default=ACTIVE_L / 2.0,
                    help="active region zmax [cm] (default +ACTIVE_L/2)")
    ap.add_argument("--particles", type=int, default=None,
                    help="override particles/batch (lower = faster, noisier shape)")
    ap.add_argument("--batches", type=int, default=None, help="override total batches")
    ap.add_argument("--radial", action="store_true",
                    help="also write radial peaking (radial_power.csv) for Layer 2")
    ap.add_argument("--nxy", type=int, default=21, help="radial mesh bins per side")
    ap.add_argument("--workdir", default="heat_extract",
                    help="scratch dir to run in (keeps your model.xml untouched)")
    ap.add_argument("--outdir", default=".", help="where to write the CSVs")
    args = ap.parse_args()

    if not os.path.exists(args.model):
        sys.exit(f"{args.model} not found. Run it from the snap directory, or run "
                 f"`python snap.py fig12_test` once to build model.xml first.")

    print(f"Loading {args.model} ...")
    model = openmc.Model.from_model_xml(args.model)

    # lateral mesh extent from the geometry bounding box (covers all 37 pins)
    try:
        bb = model.geometry.bounding_box
        halfwidth = float(min(abs(bb.lower_left[0]), abs(bb.upper_right[0]),
                              abs(bb.lower_left[1]), abs(bb.upper_right[1])))
        if not math.isfinite(halfwidth) or halfwidth <= 0:
            halfwidth = 12.0
    except Exception as e:
        print(f"[warn] bbox read failed ({e}); using 12 cm halfwidth")
        halfwidth = 12.0

    # axial kappa-fission tally (energy deposition rate vs z)
    amesh = openmc.RegularMesh()
    amesh.dimension = (1, 1, args.nz)
    amesh.lower_left = (-halfwidth, -halfwidth, args.zmin)
    amesh.upper_right = (halfwidth, halfwidth, args.zmax)
    axial = openmc.Tally(name="kappa_axial")
    axial.filters = [openmc.MeshFilter(amesh)]
    axial.scores = ["kappa-fission"]
    tallies = [axial]

    if args.radial:
        rmesh = openmc.RegularMesh()
        rmesh.dimension = (args.nxy, args.nxy, 1)
        rmesh.lower_left = (-halfwidth, -halfwidth, args.zmin)
        rmesh.upper_right = (halfwidth, halfwidth, args.zmax)
        radial = openmc.Tally(name="kappa_radial")
        radial.filters = [openmc.MeshFilter(rmesh)]
        radial.scores = ["kappa-fission"]
        tallies.append(radial)

    model.tallies = openmc.Tallies(tallies)
    if args.particles:
        model.settings.particles = args.particles
    if args.batches:
        model.settings.batches = args.batches
    # a fission-tally trigger from the criticality run would block forever here;
    # we just want the converged shape, so drop any active trigger
    model.settings.trigger_active = False

    os.makedirs(args.workdir, exist_ok=True)
    print(f"Running OpenMC in ./{args.workdir}/ (your model.xml is left untouched) ...")
    sp_path = model.run(cwd=args.workdir)
    if not os.path.exists(sp_path):
        sp_path = os.path.join(args.workdir, os.path.basename(str(sp_path)))
    print(f"Reading {sp_path}")

    with openmc.StatePoint(sp_path) as sp:
        t = sp.get_tally(name="kappa_axial")
        kf = t.mean.flatten()
        kf_err = t.std_dev.flatten()
        rad = None
        if args.radial:
            rad = sp.get_tally(name="kappa_radial").mean.reshape(args.nxy, args.nxy)

    nz = kf.size
    if kf.sum() <= 0:
        sys.exit("kappa-fission tally is all zero: the mesh window missed the fuel. "
                 "Check --zmin/--zmax against your model's core position.")

    shape = kf / kf.sum()
    dz_cm = (args.zmax - args.zmin) / nz
    z_centers_m = (np.array([args.zmin + (i + 0.5) * dz_cm for i in range(nz)])
                   - args.zmin) / 100.0
    r_fuel_m = R_FUEL / 100.0
    dz_m = dz_cm / 100.0

    # absolute per-pin volumetric source per bin:
    #   q'''_i = (P_CORE * shape_i / N_PINS) / (pi r_fuel^2 dz)
    v_bin = math.pi * r_fuel_m**2 * dz_m
    qppp = (P_CORE * shape / N_PINS) / v_bin
    peak_to_avg = qppp.max() / qppp.mean()
    rel_err = float(np.max(kf_err[kf > 0] / kf[kf > 0]))

    os.makedirs(args.outdir, exist_ok=True)
    out = os.path.join(args.outdir, "axial_power.csv")
    with open(out, "w") as f:
        f.write("# z_m,qppp_Wm3  -- per-pin volumetric heat source vs axial position\n")
        f.write(f"# P_core={P_CORE} W, N_pins={N_PINS}, per-pin={P_CORE/N_PINS:.1f} W\n")
        f.write(f"# peak/avg={peak_to_avg:.3f}, max tally rel err={rel_err:.3%}\n")
        for z, q in zip(z_centers_m, qppp):
            f.write(f"{z:.6f},{q:.6e}\n")

    integral = float((qppp * v_bin).sum())
    print("-" * 60)
    print(f"axial bins         : {nz}")
    print(f"peak / average     : {peak_to_avg:.3f}  (cosine ~1.57; real core flatter)")
    print(f"max tally rel err  : {rel_err:.3%}  (want < ~2%; raise --particles if high)")
    print(f"integral check     : {integral:.1f} W per pin  (target {P_CORE/N_PINS:.1f})")
    print(f"wrote              : {out}")
    print("-" * 60)
    print("In mvp/solid.i: switch set_power's function to a PiecewiseLinear that")
    print("reads axial_power.csv (axis = y, scale_factor = 1). power_in should then")
    print(f"report ~{P_CORE/N_PINS:.0f} W and the shape is your model's, not a cosine.")

    if rad is not None:
        rad_norm = rad / rad[rad > 0].mean() if (rad > 0).any() else rad
        rout = os.path.join(args.outdir, "radial_power.csv")
        np.savetxt(rout, rad_norm, delimiter=",",
                   header="per-pin radial peaking (normalized to mean), row-major x,y")
        print(f"wrote              : {rout}  (radial peaking map for Layer 2)")


if __name__ == "__main__":
    main()

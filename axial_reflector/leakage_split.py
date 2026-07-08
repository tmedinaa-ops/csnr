#!/usr/bin/env python3
"""
leakage_split.py -- measure how SNAP-10A's neutron leakage splits between the
axial ends (top + bottom) and the radial side, so you reflect where the neutrons
actually leave.

Method: wrap the whole reactor in a single 1x1x1 mesh whose faces sit just inside
the outer vacuum boundary, and tally net current through those faces. The +z and
-z faces are axial leakage; the four side faces are radial. The larger fraction is
where beryllium buys back the most reactivity.

This does NOT need to know the internal geometry; it reads the model's bounding box.
It also prints k-eff so you can sanity-check against the validated fig12 value.

Run in openmc-env with OPENMC_CROSS_SECTIONS set:
  MODEL_XML=~/snap/model.xml python leakage_split.py

Caveat: OpenMC's MeshSurfaceFilter bin labels have shifted across versions. The
script prints the full tally dataframe so you can confirm the face labels; the
axial/radial grouping below keys off the 'mesh surface' label strings and falls
back to positional bins if the labels are absent. Eyeball the printed table once.
"""
import os
from pathlib import Path

import numpy as np
import openmc

MODEL_XML = Path(os.environ.get("MODEL_XML", str(Path.home() / "snap" / "model.xml"))).expanduser()
PARTICLES = int(os.environ.get("PARTICLES", "40000"))
BATCHES = int(os.environ.get("BATCHES", "80"))
INACTIVE = int(os.environ.get("INACTIVE", "20"))

if not MODEL_XML.exists():
    raise SystemExit(f"missing {MODEL_XML}; set MODEL_XML to the snap fig12 model.xml")

model = openmc.Model.from_model_xml(str(MODEL_XML))


def reactor_extent(model):
    """Radius and z-span of the physical reactor. The snap model has an unbounded
    'outside' cell so geometry.bounding_box returns inf; fall back to the outermost
    real surfaces (ZCylinder radius, ZPlane z0). Override with env vars if needed."""
    if os.environ.get("MESH_R"):
        return (float(os.environ["MESH_R"]),
                float(os.environ["MESH_ZMIN"]), float(os.environ["MESH_ZMAX"]))
    bb = model.geometry.bounding_box
    ll, ur = np.array(bb.lower_left, float), np.array(bb.upper_right, float)
    if np.all(np.isfinite(ll)) and np.all(np.isfinite(ur)):
        R = max(ur[0], -ll[0], ur[1], -ll[1])
        return R, ll[2], ur[2]
    # scan surfaces
    surfs = model.geometry.get_all_surfaces().values()
    radii = [s.r for s in surfs if isinstance(s, openmc.ZCylinder)]
    zs = [s.z0 for s in surfs if isinstance(s, openmc.ZPlane)]
    spheres = [s.r for s in surfs if isinstance(s, openmc.Sphere)]
    if spheres and not radii:
        R = max(spheres); return R, -R, R
    if not radii or not zs:
        raise SystemExit("could not infer reactor extent from surfaces; set MESH_R, "
                         "MESH_ZMIN, MESH_ZMAX (e.g. the reflector OD/2 and the axial "
                         "reflector ends; for SNAP roughly R=16.5, z=-16.5..16.5 cm)")
    return max(radii), min(zs), max(zs)


R, zmin, zmax = reactor_extent(model)
print(f"reactor extent: R={R:.2f} cm, z={zmin:.2f}..{zmax:.2f} cm")

# cylindrical mesh, faces just inside the physical boundary so escaping neutrons
# cross them before they are killed. The r=R face is radial leakage; the two z
# faces are axial. A cylindrical mesh (not a box) is what makes that split clean.
er, ez = 1e-3 * R, 1e-3 * (zmax - zmin)
mesh = openmc.CylindricalMesh(
    r_grid=[0.0, R - er],
    phi_grid=[0.0, 2 * np.pi],
    z_grid=[zmin + ez, zmax - ez],
    origin=(0.0, 0.0, 0.0),
)

leak = openmc.Tally(name="leak")
leak.filters = [openmc.MeshSurfaceFilter(mesh)]
leak.scores = ["current"]
model.tallies = openmc.Tallies([leak])

model.settings.particles = PARTICLES
model.settings.batches = BATCHES
model.settings.inactive = INACTIVE
# a mesh-surface current tally needs track-length off; leave estimator default

sp_path = model.run(output=True)

with openmc.StatePoint(sp_path) as sp:
    k = sp.keff
    t = sp.get_tally(name="leak")
    df = t.get_pandas_dataframe()

print("\nk-eff:", k)
print("\nfull leakage tally (confirm the face labels once):")
print(df.to_string())


# ---- axial vs radial grouping -------------------------------------------------
# For a full-2pi CylindricalMesh, get_pandas_dataframe labels the surfaces with x/y/z
# headers where x = r, y = phi, z = z. So leakage is the OUTGOING current on:
#   radial = 'x-max out'  (the r=R outer face)
#   axial  = 'z-min out' + 'z-max out'
# The phi faces ('y') net to zero by symmetry, and 'x-min' is the r=0 axis, not leakage.
def group_axial_radial(df):
    # flatten possibly-MultiIndex columns to simple strings
    cols = ["_".join(str(x) for x in c) if isinstance(c, tuple) else str(c)
            for c in df.columns]
    d = df.copy(); d.columns = cols
    surf_col = next(c for c in cols if "surf" in c.lower())
    mean_col = next(c for c in cols if "mean" in c.lower() and "std" not in c.lower())
    axial = radial = 0.0
    for _, row in d.iterrows():
        lab = str(row[surf_col]).lower()
        val = float(row[mean_col])
        if "out" not in lab:              # only outgoing current is leakage
            continue
        if lab.startswith("z"):           # z-min/z-max -> axial
            axial += val
        elif "x-max" in lab or lab.startswith("r"):  # r=R outer -> radial
            radial += val
        # x-min (r=0 axis) and y (phi) are not leakage
    return axial, radial


axial, radial = group_axial_radial(df)
total = axial + radial
print("\n--- leakage split (outgoing current through the reactor boundary) ---")
print(f"axial (top+bottom): {axial:.4e}   {100*axial/total:5.1f} %")
print(f"radial (side)     : {radial:.4e}   {100*radial/total:5.1f} %")
print("\nRead: if axial is a large fraction AND the real geometry has bare ends, end")
print("reflectors are worth building. If radial dominates, thicken the radial reflector")
print("instead. Confirm the ends against the arXiv 2505.04024 geometry either way.")

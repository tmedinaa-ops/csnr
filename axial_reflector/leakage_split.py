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

# one mesh cell spanning the whole reactor. Shrink a hair off the bounding box so
# the faces sit just inside the vacuum boundary and catch neutrons as they exit.
bbox = model.geometry.bounding_box
ll = np.array(bbox.lower_left, dtype=float)
ur = np.array(bbox.upper_right, dtype=float)
if not (np.all(np.isfinite(ll)) and np.all(np.isfinite(ur))):
    raise SystemExit("geometry bounding box is unbounded; the outer boundary is not "
                     "vacuum-closed. Set the mesh extents by hand for this model.")
eps = 1e-3 * (ur - ll)
mesh = openmc.RegularMesh()
mesh.dimension = [1, 1, 1]
mesh.lower_left = (ll + eps).tolist()
mesh.upper_right = (ur - eps).tolist()

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
# Prefer the label column if present ('mesh surface' / 'surf'); else fall back to
# the documented positional order for a 1x1x1 mesh:
#   [x-min, x-max, y-min, y-max, z-min, z-max], each net-outward with 'current'.
def group_axial_radial(df, tally):
    label_col = next((c for c in df.columns if "surf" in c.lower()), None)
    vals = np.abs(tally.mean.ravel())
    if label_col is not None:
        labels = df[label_col].astype(str).str.lower().values
        axial = sum(v for lab, v in zip(labels, vals) if "z-" in lab or "zmin" in lab or "zmax" in lab)
        radial = sum(v for lab, v in zip(labels, vals) if ("x-" in lab or "y-" in lab
                                                           or "xmin" in lab or "xmax" in lab
                                                           or "ymin" in lab or "ymax" in lab))
        if axial + radial > 0:
            return axial, radial
    # positional fallback
    if vals.size == 6:
        xmin, xmax, ymin, ymax, zmin, zmax = vals
    elif vals.size == 12:  # in/out interleaved per face
        v = vals.reshape(6, 2).sum(axis=1)
        xmin, xmax, ymin, ymax, zmin, zmax = v
    else:
        raise SystemExit(f"unexpected {vals.size} surface bins; inspect the dataframe above")
    return zmin + zmax, xmin + xmax + ymin + ymax


axial, radial = group_axial_radial(df, t)
total = axial + radial
print("\n--- leakage split (net current through the enclosing box) ---")
print(f"axial (top+bottom): {axial:.4e}   {100*axial/total:5.1f} %")
print(f"radial (side)     : {radial:.4e}   {100*radial/total:5.1f} %")
print("\nRead: if axial is a large fraction AND the real geometry has bare ends, end")
print("reflectors are worth building. If radial dominates, thicken the radial reflector")
print("instead. Confirm the ends against the arXiv 2505.04024 geometry either way.")

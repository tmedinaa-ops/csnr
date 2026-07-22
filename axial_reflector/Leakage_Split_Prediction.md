# Leakage split: prediction before measurement

Written July 22 2026, before running `leakage_split.py`. The point is to commit to a
number first, then let the tally confirm or break it, per the project's predict-then-measure
rule. Read `README.md` for why this branch exists.

## The geometry, read off the model

Firm dimensions from `snap.py` (via `../fuel_tradeoff/SNAP-10A_Reactor_Dimensioned.py`,
which is drawn to the OpenMC geometry):

- active fuel column: R about 11.15 cm (37-pin hex bundle to the reflector inner edge), H about 31.05 cm
- aspect ratio H/D = 1.39
- lattice P/D = 1.008 (pins effectively touching)
- radial reflector: about 5.3 cm of beryllium from the bundle edge (111.5 mm) out to the flange (164.7 mm), with the four control drums in that annulus
- axial ends: grid plates (6.35 mm each) plus the NaK plena, no dedicated axial beryllium in the flight article

This corrects the `README.md` premise that the core is "roughly equant." It is not. It is
taller than it is wide (H/D 1.39), which sharpens, rather than softens, the expectation below.

## Two different splits, do not conflate them

**Intrinsic (bare-buckling) split.** Where the geometry wants to leak with no reflector.
Bare-cylinder buckling:

- radial term (2.405/R)^2 = 0.0465 cm^-2
- axial term (pi/H)^2  = 0.0102 cm^-2
- split 82% radial / 18% axial, a 4.5:1 bias to the sides

Reproduce:

```python
import math
R, H = 11.15, 31.05
br, bz = (2.405/R)**2, (math.pi/H)**2
print(br, bz, 100*br/(br+bz), 100*bz/(br+bz))   # 0.0465 0.0102 82 18
```

The core leaks radially because it is skinny (R only 11 cm against a 31 cm column). This is
also why the flight design put all of its reflection (5.3 cm Be plus four drums) on the radial
face and left the ends nearly bare.

**Measured (post-reflector) split.** What `leakage_split.py` actually tallies: net current
through the outer boundary, past the reflector. This is NOT the 82/18 number, because the
radial face is heavily reflected while the ends are not. The 5.3 cm radial reflector suppresses
radial escape far more than the bare ends suppress axial escape, so the measured radial fraction
must sit **below** the intrinsic 82%, and the axial fraction must rise above 18%.

## The prediction

The radial reflector pulls the measured split toward axial, but it starts from a 4.5:1 radial
bias, so it is unlikely to fully invert. Expectation:

- measured radial fraction roughly 55 to 70%, axial 30 to 45%
- radial still leads, but axial is a real, non-trivial fraction, not the 18% the bare geometry suggests

The number that flips the decision: if measured **axial exceeds about 40%** and the ends are
confirmed bare, end caps are the higher-yield move and this branch is live. If measured radial
still dominates (above ~65%), the lever is radial reflection instead, and under the no-beryllium
constraint that means a heavier or moderating radial reflector, not more Be.

Falsifiers, in order: if axial comes back near or below the intrinsic 18%, the ends are already
reflected and the branch is moot (check the arXiv 2505.04024 geometry for axial Be). If the split
comes back near 50/50, the reflector is doing more radial work than assumed and both faces are
worth pricing.

## What the B2 levers do to this (context, not part of the run)

From the same geometry, at the current 42% total leakage:

- reshape to the optimal H/D 0.924 at constant volume: B^2 down 6%, leakage 42 -> 40. Not worth it, and not buildable at P/D 1.008 with a fixed fuel length.
- add a fourth fuel ring (37 -> 61 pins): B^2 down 32%, leakage 42 -> 33, plus added fuel. The only geometric move with real magnitude, but it is a bigger core, not the flight article.
- ideal axial caps (kill ~85% of the axial term): B^2 down 15%, leakage 42 -> 38. This is what the measurement below is deciding whether to pursue.

## Run it

In `openmc-env` on the Mac (or the PC), with `OPENMC_CROSS_SECTIONS` set:

```bash
conda activate openmc-env
cd <CSNR repo>/axial_reflector

# primary: let the script infer the reactor extent from the model surfaces
MODEL_XML=~/snap/model.xml PARTICLES=200000 BATCHES=150 INACTIVE=30 \
    python leakage_split.py
```

If `~/snap/model.xml` does not exist yet, export it from the validated fig12 case in the snap
repo first (snap.py builds the `openmc.Model`; `model.export_to_model_xml("model.xml")`), then
point `MODEL_XML` at it.

If the auto-inferred extent looks wrong in the printout (it prints `reactor extent: R=.. z=..`),
override it with the firm outer dimensions, flange OD/2 and the vessel ends:

```bash
MODEL_XML=~/snap/model.xml MESH_R=16.47 MESH_ZMIN=-16.45 MESH_ZMAX=16.45 \
    PARTICLES=200000 BATCHES=150 INACTIVE=30 python leakage_split.py
```

Eyeball the printed tally dataframe once to confirm the face labels (the script warns that
`MeshSurfaceFilter` bin labels have shifted across OpenMC versions), then read the axial/radial
percentages at the bottom.

## Record back here

After the run, append the measured k-eff and the axial/radial percentages, and mark the
prediction hit or miss. If axial cleared 40%, move to `Axial_Reflector_Variant_Guide.md` and
build the caps. If not, the lever is radial, and given the no-Be constraint, the next note is a
moderating-radial-reflector option, not thicker beryllium.

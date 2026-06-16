# OpenMC Workshop, Day 2 (Part 2) — Spatial Tallies and Criticality Search

Afternoon of Day 2: the spatial filters (cell, mesh, distributed cell), 3D
visualization through ParaView, and the criticality (k-eff) search. The k-eff
search is the standout for your work — it is the tool for the SNAP-10A control-
drum and enrichment questions — so it gets the most detail and a tie-in at the
end. The Lego/lunch chatter in the recording is skipped. API signatures here were
checked against the OpenMC docs, since the audio garbled several of them.

---

## 1. The three spatial filters

Tallies so far used energy and material filters. There are also three ways to
bin a tally in space, and none of them change the physics — they only change how
the output is post-processed:

- Cell filter (a cell tally). Count events inside a named cell. Nest concentric
  cylinders and each becomes a radial bin; add more for a smoother profile.
- Mesh filter (a mesh tally). Overlay a grid and count per element. The grid can
  be structured (a regular x,y,z lattice) or unstructured (built in meshing
  software, conforming to the geometry).
- Functional expansion tally (FET). Expands the unknown (flux, heating) in
  orthogonal polynomials and tallies the expansion coefficients, giving a fully
  continuous, non-discretized result. Advanced and rarely needed; mentioned for
  completeness only.

## 2. Modifying a loaded model without hardcoding IDs

The session loaded a built-in PWR assembly (`openmc.examples`) and made it finite
in z so neutrons would leak and produce visible flux gradients. The lesson worth
keeping is how to edit a loaded model without typing fragile IDs.

OpenMC auto-assigns IDs, and they differ between notebook runs — the live session
hit a `KeyError` because the root cell was 7 on one machine, 12 or 14 on others.
So do not hardcode them. Find things by name or by walking the geometry:

```python
cells = model.geometry.get_all_cells()       # dict: {id: Cell}
# find a cell by its name instead of its id:
target = next(c for c in cells.values() if c.name == "root cell")
# or, if there is a single top-level cell, grab the root universe's cell:
root_cell = model.geometry.root_universe.cells  # dict of the top-level cells
```

To make the infinite assembly finite, intersect an existing cell's region with
two z-planes (vacuum boundaries so neutrons leak):

```python
zmin = openmc.ZPlane(0.0, boundary_type="vacuum")
zmax = openmc.ZPlane(100.0, boundary_type="vacuum")
target.region = target.region & +zmin & -zmax
```

## 3. Mesh tallies

```python
mesh = openmc.RegularMesh()
mesh.lower_left, mesh.upper_right = model.bounding_box   # reuse the model extent
mesh.dimension = (50, 50, 1)                             # 2D map: 50x50x1 = 2500 bins
mtally = openmc.Tally(name="mesh")
mtally.filters = [openmc.MeshFilter(mesh)]
mtally.scores = ["flux", "heating"]
```

Reading and plotting: `get_values` returns a flat array (2500 entries for a
50x50x1 mesh, in the order filters x nuclides x scores). Reshape to the mesh
dimensions before handing it to matplotlib:

```python
flux = mtally.get_values(scores=["flux"]).reshape(mesh.dimension)  # -> (50,50,1)
```

Statistics, the lesson April drove home: a noisy mesh tally breaks the symmetry
the geometry should have (reflective sides, symmetric lattice → the map should be
symmetric; if it is not, you under-ran). Relative error is highest where the flux
is lowest — the water corners with little fuel get few samples, like a many-sided
die never landing on its small faces. And finer mesh means worse per-bin
statistics: quadrupling the bins (50x50 → 100x100) at fixed particle count roughly
quadruples each bin's error, because each bin now collects a quarter of the
samples. Production runs use far more than the workshop's handful: order a million
particles per batch, ~500 inactive and ~1000 active batches.

Heating vs flux: a heating mesh tally shows essentially all the heat in the fuel
and almost none in the water (a few percent from scattering), so it traces the
geometry far more recognizably than the flux map.

Normalization — the volume subtlety that differs from a whole-problem tally.
A mesh tally's counts are per source particle, taken over a single mesh element,
so you divide by the volume of one element, not the whole problem:

```python
import numpy as np
total_vol = np.prod(np.array(mesh.upper_right) - np.array(mesh.lower_left))
elem_vol  = total_vol / np.prod(mesh.dimension)          # volume of ONE bin
# source rate S from imposed power: sum the heating tally over all bins = total power
R = mtally.get_values(scores=["heating"]).sum()          # eV/source particle, whole assembly
S = (17e6 / 1.602e-19) / R                                # 17 MW -> eV/s, then /R
flux_phys = flux * S / elem_vol                           # n/cm^2/s, ~1e15 here
```

## 4. 3D visualization through ParaView (VTK export)

`get_values` returns raw numbers; `get_slice` returns a Tally object you can write
to VTK and open in ParaView (the standard tool for mesh data):

```python
t = mtally.get_slice(scores=["heating"])                 # a Tally, not an array
mesh.write_data_to_vtk("tally.vtk", {"mean": t.mean})    # needs the `vtk` python module
```

Open `tally.vtk` in ParaView, choose Surface representation, and slice through it.
Axial flux peaks in the center because the top and bottom are vacuum (neutrons
born near the ends leak and do not return) while the four sides are reflective —
that is the axial power shape, not noise.

## 5. Unstructured mesh tallies

Same idea, but the mesh is built in external meshing software and conforms to the
geometry, so no bin straddles fuel and water:

```python
umesh = openmc.UnstructuredMesh("assembly.exo", library="libmesh")  # or 'moab'
tally.filters = [openmc.MeshFilter(umesh)]
```

This requires OpenMC compiled with the mesh library (libMesh or MOAB), so it does
not run in the stock Colab. Output is written as `tally_<id>.<batches>.e` (Exodus)
or VTK and opened in ParaView. The result hugs the geometry — heating only in the
fuel rings — instead of the pixelated look of a regular mesh.

## 6. Distributed cell tallies

A cell built once and repeated through a lattice (the fuel-pin universe stamped
264 times) is one cell ID but many instances. The pair (ID, instance) is a unique
entity, so you can tally each lattice position separately:

```python
fuel = next(c for c in model.geometry.get_all_cells().values() if c.name == "fuel")
model.geometry.determine_paths()        # walks the model to count instances
print(fuel.num_instances)               # 264 here

dtally = openmc.Tally(name="distribcell")
dtally.filters = [openmc.DistribcellFilter(fuel)]   # smarter than CellFilter: knows instances
dtally.scores = ["heating"]
```

`determine_paths()` is the required step — until you call it, the model does not
know how many instances exist. Read the 264-row result as a pandas dataframe, or
view it in openmc-plotter's tally overlay (which had a display bug in April's
build; normally it color-codes each instance and should show quarter or eighth
symmetry once enough particles are run).

## 7. Functional expansion tallies (brief)

For a continuous result, expand the flux or heating in orthogonal polynomials,
tally the coefficients, then reconstruct the shape by evaluating the polynomial
after the run. A research-grade capability, not common; noted so you recognize it.

---

## 8. Criticality (k-eff) search — the design tool

The recurring engineering task: find the value of one knob that makes the reactor
critical (k = 1) — control-drum or control-rod position, soluble boron
concentration, enrichment, a dimension. You can loop OpenMC by hand, but there is
a built-in search.

It is a module-level function, `openmc.search_for_keff`, NOT a model method (the
audio said "model.k-effective search," which is wrong). Its first argument is a
model builder: a function that takes the search parameter and RETURNS a fresh
`openmc.model.Model`. The search runs OpenMC repeatedly, using a generalized
secant method (or a bracketed method if you pass a bracket), and ramps the batch
count up as it closes in, to avoid wasting compute far from the answer.

```python
def build_model(enrichment):
    # ...build materials/geometry using `enrichment`, return a Model...
    return model

crit_enrichment, guesses, results = openmc.search_for_keff(
    build_model,
    bracket=[1.0, 5.0],     # two starting guesses in wt% (or use initial_guess=)
    target=1.0,             # k to search for; defaults to 1.0
    tol=1e-3,               # convergence tolerance on k
    print_iterations=True,
)
```

Signature (checked against docs):
`openmc.search_for_keff(model_builder, initial_guess=None, target=1.0,
bracket=None, model_args=None, tol=None, bracketed_method='bisect',
print_iterations=False, run_args=None, **kwargs)`. It returns the parameter value
at the target k, the list of guesses, and the list of (k, uncertainty) results.
Provide `initial_guess` or `bracket` (bracket wins if both given). `target` lets
you search for a value other than 1.0 (e.g. 1.1). Good starting guesses near the
answer make it converge faster.

What the builder can change is anything you can express in a function:
- Enrichment: remove the uranium and re-add it at the passed weight percent. The
  worked example converged to ~1.74 wt% for that pin cell.
- A dimension: set a surface's radius, keeping dependent surfaces consistent
  (e.g. `inner.r = r; outer.r = r + 10` to hold a 10 cm shell). Watch for geometry
  you might break — moving a surface past another creates overlaps.
- Soluble boron, via the helper `openmc.model.borated_water(boron_ppm,
  temperature, pressure)`, which returns a water material with the density solved
  from an equation of state. It also takes `density=` to set the density directly
  and override temperature/pressure (this answered a student's question — yes, you
  can give density instead of T and P).

One parameter at a time. For a trade study, loop one search inside the other —
e.g. for each radius, search for the critical density — to map the Pareto front of
critical (radius, density) pairs. There is no two-parameter search, because two
free parameters give an infinite set of critical states, not one answer.

Physics aside worth keeping: a lead reflector gave a smaller critical sphere than
aluminum, for two reasons — lead is far denser (more scattering centers to reflect
neutrons back) and has a sizable (n,2n) cross section (a neutron in, two out)
adding bonus neutrons. To minimize critical mass you want a good moderator/
reflector: high scattering, low absorption.

---

## 9. What this means for SNAP-10A

The k-eff search is the concrete tool for the reactor-section questions in your
build spec, and it is the most directly useful thing in this session:

- Control-drum critical search. Write a `build_model(drum_angle)` that rotates the
  four external beryllium control drums (a geometry/rotation change) and run
  `search_for_keff` with `target=1.0` to find the critical drum angle. The same
  machinery, integrated over a drum sweep, gives the coarse-drum worth (~$4.80 in
  the build spec) and per-drum worth that the reports leave unstated.
- Design searches. Swap the builder's parameter for enrichment (fixed at 93 wt% by
  design, but you can test sensitivity) or the H/Zr ratio (the main unsourced fuel
  knob) and search for the value giving k = 1. This is how you'd answer "what
  enrichment / hydrogen loading holds the core critical" quantitatively.
- Trade studies via the loop-one-search-inside-another pattern: drum angle vs k,
  or enrichment vs critical core size, mapping the design space the originals
  explored by hand.

Mesh tallies are your shield and power-shape tool:
- A mesh tally down the LiH shield axis gives the per-source-neutron flux profile —
  exactly the validation table in the build spec. Normalize by the single-element
  volume and the source rate S from the 34 kW core power (Section 3) to get
  absolute flux, then a flux-to-dose response for the dose at 284.3 cm.
- VTK/ParaView export turns those into shield flux maps and clean report figures.

Distributed cell tallies give the core power distribution:
- `DistribcellFilter` on the fuel element of the 37-position hex lattice, after
  `determine_paths()`, tallies heating per element — the radial power distribution
  and the peaking factor (1.98 in the build spec) to compare against the reports.

The axial-center flux peak from end leakage is the axial power shape you would
validate against the documented profile. `borated_water` itself does not apply
(SNAP-10A uses NaK, no soluble boron), but the model-builder pattern generalizes
to any SNAP-10A knob you want to drive to a target k.

No searched-answer section here: the substantive questions in this session
(optimal reflector material, lead vs aluminum, mesh resolution vs error, whether
you can search two parameters) were all answered in the room.

# OpenMC Workshop, Day 1 — Notes

April Novak (UIUC). Day 1 was Monte Carlo theory plus building a PWR pin cell
from scratch in the Python API. These notes strip out the live debugging and
keep the physics and the workflow. The companion script is `pincell.py`. The
last two sections connect all of it to the SNAP-10A shielding build.

---

## 1. What Monte Carlo transport actually is

OpenMC does not solve the neutron transport equation as a differential equation.
It simulates the random walk of individual neutral particles (neutrons and
photons), then averages a large population of them. The transport equation is
never coded anywhere; it is replaced by repeated random sampling from
probability distributions.

The loop, per particle:

1. Birth. Sample a starting position, energy, and direction. In a fission
   system the birth site is sampled from the fission source.
2. Distance to next collision. Sampled from a distribution that assumes the
   cross section is constant along the flight. So the particle is forced to stop
   at any material boundary it would cross, where it re-samples (more on this
   below).
3. Collision type. Roll against the ratio of cross sections — fission, capture,
   elastic scatter, (n,2n), and so on. It is a many-sided die weighted by the
   reaction probabilities.
4. Outcome. Scatter changes energy and direction (sampled from their own
   distributions, often anisotropic). Capture or fission ends the particle. A
   fission also banks new source sites and a sampled number of new neutrons.
5. Repeat until the particle is absorbed or leaks out, then move to the next.

Run a million histories, average them, and you recover the flux and every
reaction rate that follows from it. The number you usually want, k_eff, is just
a ratio of two reaction rates.

Why the boundary stop in step 2 matters: the flight-length distribution is only
valid where the cross section is uniform. Cross the boundary into a new material
and that assumption breaks, so OpenMC halts the particle on the surface and
draws a fresh distance. Almost every Monte Carlo code does this. (Delta tracking
is the technique that lets you skip it; it is being added to OpenMC but is not
the default.)

## 2. Stochastic vs deterministic — and when each wins

| | Monte Carlo (OpenMC) | Deterministic (S_N, diffusion) |
|---|---|---|
| Geometry | Exact, no mesh | Meshed, approximated |
| Energy | Continuous, exact lookup | Usually multigroup (histograms) |
| Output | Only what you tally | Full flux solution everywhere |
| Cost | Slow; 1/sqrt(N) convergence | Faster, especially transients |
| Parallelism | Trivially parallel | Harder |

The asymmetry that bites: Monte Carlo records only what you explicitly ask for.
Decide after the run that you wanted scatter rates too, and you re-run the whole
thing. A deterministic solve gives you the entire flux at once. Transients are
still deterministic territory because Monte Carlo is too slow per time step.

## 3. Fixed source vs eigenvalue — the distinction that matters for SNAP-10A

There are two problem types, and which one you have changes how you set up the run.

Fixed source: you know the source completely — its strength, energy, and angular
distribution. Radiation detection and fusion neutronics are fixed source. You
define the source, run once, no source iteration.

Eigenvalue (criticality): the source is fission, which is proportional to the
flux you are solving for. You cannot know it in advance, so the transport
equation becomes an eigenvalue problem. You guess an initial fission source and
iterate it to convergence before tallying anything. The pin cell in `pincell.py`
is this kind.

This is the single most important thing to carry into your work: the pin cell is
eigenvalue, but the SNAP-10A shield problem (NAA-SR-MEMO-8768 / FMC-N) is fixed
source. You have a known fission spectrum entering a shield. So the shield model
is set up differently from everything in Day 1 — see Section 9.

## 4. Source convergence (eigenvalue only)

Because the fission source starts as a guess, the first batches are wrong. You
run `inactive` batches to let the source settle into its real spatial shape, and
throw their tallies away. Only the `active` batches count. The guess can be
anything physical — a point source in the middle of the core works — but a bad
guess just means you need more inactive batches. OpenMC errors if more than ~95%
of your initial source sites land somewhere a neutron cannot be born (outside
the geometry, in a pure absorber). Fixed-source runs skip this entirely.

## 5. Constructive solid geometry (CSG)

Every surface is an equation written with everything moved to one side, so it
equals zero. A sphere of radius r is `x^2 + y^2 + z^2 - r^2 = 0`. A plane at
x = 3 is `x - 3 = 0`.

A surface splits all of space into two half-spaces:

- Negative half-space (`-surface`): points where plugging in gives f < 0. For a
  sphere, that is everything inside.
- Positive half-space (`+surface`): f > 0. Everything outside.

You build a region by combining half-spaces with boolean operators:

- `&` intersection (AND)
- `|` union (also/OR)
- `~` complement (NOT)

April's example: a finite cylinder ("trash can") is the intersection of three
half-spaces — inside an infinite cylinder, above a bottom plane, below a top
plane. Then a `Cell` is a region plus a fill (a material, or `None` for void).

This is the whole geometry language. Most reactor parts are well described by
cylinders and planes. Curved or odd shapes that are not second-order surfaces
(or fourth-order for tori) need a mesh-based geometry (DAGMC) instead, because
CSG surfaces have to stay low-order for the ray tracing to be efficient.

## 6. Boundary conditions

Set on surfaces. The default is transmission (the particle keeps going through).
The forgettable bug from the workshop: if your outermost surfaces are left as
transmission, neutrons leak into undefined space and the run fails. So always set
the outer surfaces.

- `vacuum`: particle crossing is killed. Models an open boundary.
- `reflective`: particle is mirrored back. A symmetry plane. Reflective on the
  four radial faces of the pin cell makes it behave like one cell of an infinite
  2D lattice.
- `periodic`: pairs two surfaces; a particle leaving one re-enters the paired one
  with the same direction. Used to tile a repeating structure.

In `pincell.py` the radial planes are reflective and the axial planes vacuum:
infinite in the radial array, finite (300 cm) in height.

## 7. Materials — three things to remember

Element expansion. `add_element('Zr', 1.0)` pulls natural isotopic abundances
from your cross-section library, not from a hardcoded table. If the library is
missing an isotope, OpenMC just renormalizes the ones it has.

The enrichment helper. `add_element('U', 1.0, enrichment=3.5)` does the
U-235/U-238 atom-fraction arithmetic for you (weight percent by default). This
is the function that removes the most tedious hand calculation in the field.

S(alpha,beta) thermal scattering — the one that silently corrupts results.
At normal energies a neutron scatters off an isolated free atom (free-gas model),
which is fine because the neutron is moving so fast the chemical bonds are
irrelevant. When the neutron slows to thermal, its wavelength grows and it
interacts with clumps of bonded atoms and lattice vibrational modes instead.
The S(alpha,beta) table is that correction. OpenMC does not add it automatically.
For any thermal system, stop and ask whether your moderators and reflectors need
one. Water does: `add_s_alpha_beta('c_H_in_H2O')`. The naming is `c_<scatterer>_
in_<compound>` because hydrogen in water behaves nothing like hydrogen in
zirconium hydride. Forget it and the code runs but the answer is wrong.

## 8. Tallies and statistics

A tally is a volume-integrated count of something. It has scores (what to
measure: `flux`, `fission`, `absorption`, `heating`, and ~50 others) and filters
(which part of phase space to count over: a cell, a surface, an energy range, a
mesh). No filter means integrate over everything. A bare `flux` score with no
multiplier gives you the neutron flux; multiply by a fission cross section and
you get the fission reaction rate.

Every result is a mean with a standard deviation. Always report the uncertainty;
it tells you how much to trust the run. Monte Carlo converges as 1/sqrt(N), so
cutting the statistical error in half costs 4x the particles. This is why deep
shielding problems are expensive and need variance reduction.

---

## 9. OpenMC Python API — quick reference

Build order is always: materials → surfaces → regions → cells → universe →
geometry → settings → (tallies) → model → run.

```python
import openmc

# --- Materials ---
m = openmc.Material(name="fuel")
m.add_element("U", 1.0, enrichment=3.5)   # enrichment in wt% U-235
m.add_element("O", 2.0)                    # prefer add_element over add_nuclide('O16',..)
m.add_nuclide("U235", 0.0009)              # explicit nuclide if you need one
m.set_density("g/cm3", 10.0)              # or 'atom/b-cm', or 'sum'
m.add_s_alpha_beta("c_H_in_H2O")          # thermal scattering, thermal systems only
m.remove_nuclide("O16")                    # materials are mutable
materials = openmc.Materials([m, ...])

# --- Surfaces (each splits space into +/- half-spaces) ---
cyl  = openmc.ZCylinder(r=0.46)
px   = openmc.XPlane(x0=-0.63, boundary_type="reflective")
pz   = openmc.ZPlane(z0=150, boundary_type="vacuum")
sph  = openmc.Sphere(r=1.0)
cone = openmc.ZCone(z0=0, r2=0.011)        # for the SNAP shield frustum

# --- Regions (boolean combos of half-spaces) ---
region = -cyl & +px & -pz                  # & and, | or/also, ~ not

# --- Cells (region + fill) ---
c = openmc.Cell(name="clad", region=region, fill=m)   # fill=None means void
root = openmc.Universe(cells=[c, ...])
geometry = openmc.Geometry(root)

# --- Settings ---
s = openmc.Settings()
s.particles = 1000
s.batches   = 100
s.inactive  = 10                           # eigenvalue only; drop for fixed source
s.run_mode  = "eigenvalue"                 # or "fixed source"
# explicit source:
# s.source = openmc.IndependentSource(
#     space=openmc.stats.Point((0,0,0)),
#     energy=openmc.stats.Watt(),           # fission spectrum
#     angle=openmc.stats.Isotropic())

# --- Tallies (Monte Carlo records only what you ask) ---
t = openmc.Tally(name="flux")
t.filters = [openmc.CellFilter(c), openmc.EnergyFilter([0, 1e6, 20e6])]
t.scores  = ["flux", "fission"]
tallies = openmc.Tallies([t])

# --- Build and run ---
model = openmc.Model(geometry=geometry, materials=materials, settings=s)
model.tallies = tallies
sp_path = model.run()
with openmc.StatePoint(sp_path) as sp:
    print(sp.keff)

# --- Plotting ---
root.plot(width=(1.26, 1.26), basis="xy", pixels=(400, 400))
```

Conventions: functions are `snake_case`, classes are `CamelCase`, modules are
lowercase (`import openmc`, `openmc.deplete`). In a notebook, `help(openmc.Cell)`
or shift-Tab shows the docstring; Tab shows available methods. Don't track IDs —
OpenMC assigns them; using them by hand only makes things harder.

---

## 10. How this maps to the SNAP-10A shielding build

The Day 1 toolkit transfers directly, but the shield problem is a different class
of run. What carries over and what changes:

Same as the pin cell:
- The build order and the whole CSG language. OpenMC has purpose-built composite
  surfaces for the shield: `openmc.model.ConicalFrustum` for the 6-degree
  truncated LiH body and `openmc.model.Vessel` (cylinder with semi-ellipsoid
  heads) for the 316 SS casing with its torispherical top and hemispherical lower
  head, plus planes for the axial cuts. Raw `openmc.ZCone` and `openmc.Sphere`
  are the fallback. (Composite-surface names verified against the openmc.model
  docs.)
- Materials by number density. The FMC-N homogenized atom densities in the base
  set are in atoms/(barn·cm), so add each nuclide with its `ao` value and call
  `set_density('sum')`, rather than the `g/cm3` route used for the pellet:
  `mat.add_nuclide('Li6'/'Li7'/'H1', density_in_atom_b_cm)`, etc. Same for the
  homogenized core, reflector, and plena.
- Continuous-energy transport with the same library mechanics, including the same
  element-expansion and library-mismatch pitfalls that caused the live O16 crash.

Different, and this is where the real work is:
- Fixed source, not eigenvalue. Set `run_mode="fixed source"`, drop the inactive
  batches, and define the source explicitly. The FMC-N spectrum (0.0919–18 MeV,
  fission fractions 0.8051 / 0.1647 / 0.0295 / 0.000685 over its four bands) goes
  into `settings.source` as a tabulated or Watt energy distribution, spatially
  sampled over the homogenized core region. This is Section 3's distinction made
  concrete: you know the source here, so you do not iterate it.
- It is all tallies. Day 1 ran none. The shield deliverables ARE tallies: a flux
  tally vs. axial position (a mesh or a stack of cell tallies down the shield
  axis) to reproduce the per-source-neutron flux table, the attenuation ratio
  (0.0359), and the factor-of-six mating-plane drop; plus a current/surface tally
  at the 284.3 cm dose plane. Nothing is recorded unless you score it.
- Variance reduction is mandatory, not optional. A LiH shield attenuates the fast
  flux by orders of magnitude, and analog Monte Carlo (what the pin cell uses)
  will never get statistics in the far field. FMC-N already did source biasing,
  splitting, and Russian roulette over 68,000 histories for exactly this reason.
  You will need weight windows or the same biasing tricks. This is the biggest
  practical jump from Day 1 and worth raising with April directly, since
  multiphysics and deep-penetration variance reduction are her area.
- Thermal scattering is less central here than in the pin cell. The shield job is
  fast-neutron removal, so the dominant physics is elastic down-scatter and
  absorption, not thermalization. Add S(alpha,beta) for LiH only if you tally
  thermal flux inside the shield; for the removal-cross-section validation it is
  secondary.

Validation stays per your policy: reproduce the reports' numbers (0.156 cm^-1
removal cross section, the ~6x mating-plane reduction, the 0.0359 ratio, the
per-source-neutron flux table) with their geometry and homogenized densities
first, then move to modern 3D geometry and ENDF/B-VIII.

The AIM-6 diffusion cross-check (Equations doc 1.2) is a separate small Python
job, not an OpenMC run — a slab diffusion solve with the (2.405/R)^2 buckling
term — useful as a fast independent check on the OpenMC flux.

## 11. Gotchas from the live session, worth keeping

- O16 not found: a cross-section library mismatch. The Colab ran ENDF/B-VII.1,
  which stores oxygen differently than `add_nuclide('O16')` expects. Fix:
  `add_element('O', ...)`. Same failure mode shows up with carbon, where some
  libraries carry `C0` (natural, lumped) and others split it into isotopes.
- Jupyter cells go stale. Re-running a material cell increments its auto-ID and
  can desync the model from what later cells reference. April's own habit is to
  write a single script and run it top to bottom instead of editing cells out of
  order. For real work, prefer the script (`pincell.py`) over the notebook.
- The geometry exists only in your head until you plot it. Plot as you build.
- A missing fill is void, not an error. The gap cell with `fill=None` lets
  neutrons stream straight through with no collision. Intended here; a silent bug
  if you meant to put something there.

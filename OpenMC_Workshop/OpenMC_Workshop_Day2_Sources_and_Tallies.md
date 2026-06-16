# OpenMC Workshop, Day 2 — Sources and Tallies

Two notebooks: defining the starting source, then tallies (the output). Tallies
are the reason you run OpenMC at all, and the normalization piece is the one that
turns the code's per-source-particle numbers into physical units. Both connect
hard to the SNAP-10A shield, so there is a dedicated tie-in at the end and flags
throughout. The post-lunch conversation in the recording is off-topic and skipped.

---

## A. Why OpenMC gives shape, not magnitude

Criticality is an eigenvalue problem: the equation is satisfied for any
multiple of the flux, so OpenMC returns the *shape* of the flux, not its
magnitude. The same reactor can be critical at a thousand neutrons (trivial
power) or a trillion-trillion (enormous power); k cannot tell them apart. So
OpenMC cannot give you power. You recover absolute magnitude only by imposing a
constraint you know from outside the transport solve — almost always the power.
This is the whole reason tallies come back in odd units and need normalizing
(Section C), and it is exactly the step that converts the SNAP-10A
per-source-neutron flux table into absolute dose rates.

## B. Sources

### The default

Specify nothing and you get a point source at the origin, isotropic in angle,
with a Watt fission spectrum in energy (Watt is the scientist, no relation to the
power unit). For a criticality run the starting source barely matters — a bad
guess just costs more inactive batches to converge away from. The physical
fission source is nu-Sigma_f times the flux, which you do not know until after
you have run and tallied it, so you guess and iterate. For a fixed-source run the
source is the whole problem and you must know it.

### The four source classes

- `IndependentSource` — the workhorse. Mix and match an independent probability
  distribution for each part of phase space (space, angle, energy).
- `FileSource` — sample starting particles from an HDF5 file you wrote.
- `MeshSource` / `MeshSpatial` — overlay a mesh and set a source strength per
  element.
- `CompiledSource` — the catch-all, written in C++ for distributions too complex
  to build from the others (joint energy-angle distributions, many fusion
  sources). Not covered.

### Spatial distributions (openmc.stats)

```python
openmc.stats.Point((1, 1, 0))
openmc.stats.Box(lower_left, upper_right)            # uniform in a cuboid
openmc.stats.CartesianIndependent(x_dist, y_dist, z_dist)
openmc.stats.CylindricalIndependent(r_dist, phi_dist, z_dist, origin=(0,0,0))
```

The component distributions: `Uniform(a, b)`, `Discrete(values, probabilities)`,
`PowerLaw(a, b, n)`.

A real trap with the cylindrical source: sampling r uniformly piles points near
the axis, because the volume element is r·dr·dphi·dz. To fill a cylinder
uniformly by volume, sample r with `PowerLaw(0, R, 1)` (the exponent-1 gives the
r·dr weighting), not `Uniform`. This same geometric reasoning matters if you ever
sample a source over the SNAP-10A core volume by hand.

### The recommended source — bounding box plus fissionable constraint

The simplest reliable source for a criticality problem: a uniform box over the
entire model, with a constraint that rejects any site not in fissile material.

```python
bbox = model.bounding_box          # auto axis-aligned box; has .lower_left/.upper_right
space = openmc.stats.Box(*bbox)
src = openmc.IndependentSource(space=space, constraints={'fissionable': True})
model.settings.source = src
```

OpenMC knows what is fissionable from the cross sections. This removes the need to
hand-place the source in the fuel. You still run enough inactive batches to wash
out the guess.

### Angular and energy distributions

Angle: `Isotropic()` (default and usually right), `Monodirectional(reference_uvw=
(0,1,0))` for a beam, `PolarAzimuthal` for a specified solid-angle distribution.
Energy: `Watt()` default; `Discrete([1.41e7], [1.0])` for a monoenergetic fusion
source, or discrete photon lines for a Cs-137 detector source.

### Visualizing source sites

`model.plot` will scatter the source sites as dots over the geometry. Use a
`plane_tolerance` so sites near the slice actually show (otherwise a thin slice
through a tall model catches almost none). Plotting 500 sites is enough to see the
distribution.

### File and surface sources — the shielding workflow

You can write your own source particles and load them back:

```python
particles = [openmc.SourceParticle(r=(x, y, 0)) for x, y in ring]
openmc.write_source_file(particles, "source.h5")
model.settings.source = openmc.FileSource("source.h5")
```

The important use, and April said this explicitly, is shielding. Run one
criticality calculation of the reactor, write every neutron that crosses the
reactor-shield boundary to a surface source, then run a fixed-source calculation
on the shield alone, loading that file. You never re-run the reactor while
iterating the shield. This is the SNAP-10A shield workflow — see the tie-in.

Two ways OpenMC writes a source during a run:

```python
# Write the fission-bank source at chosen batches (watch source convergence):
model.settings.sourcepoint = {'batches': [1, 55], 'separate': True, 'write': True}

# Write particles crossing a surface, with directional and count control:
model.settings.surf_source_write = {
    'surface_ids': [1],      # surfaces to bank crossings on
    'max_particles': 1000,   # cap so the file does not explode
    'cellfrom': fuel_cell.id # only crossings coming FROM this cell (directional)
}
# read it back into a fixed-source run:
model.settings.surf_source_read = {'path': 'surface_source.h5'}
```

Direction is controlled by the `cell`, `cellfrom`, and `cellto` keys (bank
particles associated with that cell, leaving it, or entering it). `max_particles`
caps the file size; `max_source_files` splits it across files if needed. (Keys
confirmed against the openmc.Settings docs.)

### Mesh source

Overlay a regular mesh and assign a per-element source strength:

```python
mesh = openmc.RegularMesh()
mesh.lower_left = (-10, -10, -1)
mesh.upper_right = (10, 10, 1)
mesh.dimension = (3, 3, 1)
space = openmc.stats.MeshSpatial(mesh, strengths)   # strengths: one weight per element
```

Note the API quirk April dwelt on: `lower_left`/`upper_right` are set as
attributes after construction, not passed to the constructor. The reason is that
the same information could instead come from a bounding box, so the constructor
keeps its required arguments minimal rather than forcing one input style.

### Combining sources, fixed-source mode, photons

Multiple sources: set `model.settings.source = [src1, src2]`. Each source has a
relative `.strength` (default 1); weight them (0.3 / 0.7) to control the mix.

Fixed source: `model.settings.run_mode = "fixed source"`. Inactive batches become
irrelevant (you know the source, so nothing needs discarding), and OpenMC prints
"simulating batch" instead of a k value.

Photons: `model.settings.photon_transport = True`, and set `particle='photon'` on
a source if it emits photons. OpenMC does pure neutron, pure photon, or coupled
(neutrons producing photons via (n,gamma)) — coupling matters more for fusion and
for accurate energy deposition.

---

## C. Tallies

A tally is a volume integral of the angular flux weighted by a score, optionally
restricted by filters. Score = what to measure; filter = which part of phase
space to count over.

### Scores and filters

Scores (the user guide "specifying tallies" page is the reference): `flux`
(weight 1), reaction rates like `fission`, `absorption`, `scatter`,
`kappa-fission`, `heating`, production rates like `(n,t)`, and current
(omega·n, surface crossings). About fifty exist. These are instantaneous rates;
isotope inventory like Sr-90 buildup needs depletion (Day 3), not a score.

Filters constrain the integral. No filter means whole phase space: all energy
(0 to infinity), all angle, the whole model volume. Common ones: `EnergyFilter`,
`CellFilter`, `MaterialFilter`, `MeshFilter`. Example intent: fission rate from
fast neutrons in cell 3 = a fission score with an energy filter (above ~1 MeV)
and a cell filter on cell 3.

### Units and normalization — the central idea

OpenMC reports everything per source particle, so running more particles only
shrinks the statistical error, it does not scale the means. Geometry is in cm,
energy in eV. A flux tally comes back as particle-cm per source particle; a
reaction-rate tally as reactions per source particle. To get physical units you
multiply by a source rate S (real-world source particles per second) and, for
flux, divide by the tally volume.

Where S comes from:

- Fixed source: you know it. A 1 Ci photon source is 3.7e10 decays/s; times the
  photon branching ratio gives photons/s.
- Eigenvalue: you don't know it, so impose a known reaction rate, usually power.
  Add a `kappa-fission` (recoverable heating) tally to get R in eV per source
  particle. Pick a power P in watts, convert to eV/s, and S = (P in eV/s) / R.
  So whenever you want absolute numbers from a criticality run, you also add a
  heating tally to back out S.

Ratios of two tallies need no normalization, because S and volume cancel — useful,
and directly relevant to the SNAP-10A validation ratios.

### Example 1 — average energy per fission (a ratio, no normalization)

```python
t = openmc.Tally(name="fission")
t.scores = ["fission", "kappa-fission"]      # denominator and numerator
model.tallies = openmc.Tallies([t])
model.run(apply_tally_results=True)          # populates the tally objects in memory

fission     = t.get_values(scores=["fission"]).squeeze()
kappa       = t.get_values(scores=["kappa-fission"]).squeeze()
mev_per_fis = kappa / fission / 1e6          # ~193-200 MeV
```

`kappa-fission` is the recoverable energy (it drops the neutrino energy, which
escapes), which is what you want for heating. Read means with `.mean`/`get_values`
and errors with `value="std_dev"`. The `tallies.out` text file holds the same
numbers for a sanity check, but parse the objects for real work. Propagate
uncertainty with the `uncertainties` package:

```python
from uncertainties import ufloat
r = ufloat(kappa_mean, kappa_sd) / ufloat(fis_mean, fis_sd)
```

Always report uncertainty. Relative error = std_dev / mean; under ~1% is good,
under 5% is usually trustworthy, and it only shrinks as 1/sqrt(N) so halving it
costs 4x the particles. This is statistical error only — it says nothing about
wrong dimensions, wrong nuclear data, or too few inactive batches.

### Example 2 — flux spectrum

Use an energy filter from a standard group structure rather than hand-listing
bins:

```python
ef = openmc.EnergyFilter.from_group_structure("CASMO-70")   # thermal-reactor structure
spec = openmc.Tally(name="spectrum")
spec.filters = [ef]
spec.scores = ["flux"]
```

Plot per unit lethargy (lethargy = ln(E_high/E_low), the log-space bin width);
OpenMC exposes the lethargy bin widths, so divide the flux by them. A thermal
reactor then shows the Watt fission peak at high energy and a thermal Maxwellian
peak at low energy; a fast or fusion spectrum has no thermal peak. Picking a
fusion structure like VITAMIN-J-175 for a thermal reactor hides the thermal peak
in one fat low-energy group, which is why the structure choice matters.

Flux is total track length per volume per time (equivalently, surface crossings
per area per time), units 1/cm^2/s after normalizing. The volume subtlety: with
no spatial filter the volume is the whole problem. For an axially-infinite pin
cell, normalize per unit height (volume = dx·dy·1). Typical reactor flux is
~1e13 to 1e14 n/cm^2/s once you apply S from an imposed power (e.g. 200 W for the
pin cell).

### Example 3 — reaction rates by material

```python
mf = openmc.MaterialFilter(list_of_materials)
rates = openmc.Tally()
rates.filters = [mf]
rates.scores = ["absorption", "fission", "scatter"]
df = rates.get_pandas_dataframe()            # tidy table; add rate/sec = mean * S
```

`get_pandas_dataframe` is the clean way to read material/score breakdowns. Water
dominates scatter (moderation), fuel dominates fission and absorption.

### Triggers — run until statistics are good enough

Instead of guessing the particle count, let OpenMC keep adding batches until a
statistical threshold is met.

```python
model.settings.keff_trigger = {"type": "std_dev", "threshold": 0.001}
model.settings.trigger_active = True
model.settings.trigger_batch_interval = 10     # how often to check
model.settings.batches = 50                     # with a trigger, this is the MINIMUM
model.settings.trigger_max_batches = 1000       # fail-safe maximum
```

With a trigger active, `batches` is interpreted as the minimum number of batches
and `trigger_max_batches` is the hard cap. (Confirmed against the openmc.Settings
docs — the cap is its own attribute, not `batches`.)

Tally triggers attach to a tally:

```python
trig = openmc.Trigger("rel_err", 0.01)         # 1% relative error
fission_tally.triggers = [trig]
```

The most-limiting active trigger drives the run length, and it will run to the max
batches if it cannot meet the threshold (a trigger on a reaction with no events
would otherwise run forever — hence the fail-safe). For k, uncertainty is quoted
in pcm (percent mille, 1 pcm = 1e-5); aim for tens of pcm, because k differences
that matter are the size of beta (~600-700 pcm), so a 1000 pcm uncertainty is
useless. Use triggers for production runs, not while building a model.

---

## D. What this means for SNAP-10A

The file/surface-source workflow is your shield calculation, almost verbatim:

1. Run the 37-element core as a criticality (eigenvalue) model.
2. Write a surface source of every neutron crossing the core-shield boundary,
   directional (leaving the core), capped at a sensible particle count.
3. Run the LiH shield as a fixed-source problem reading that file, with the
   ConicalFrustum/Vessel geometry from the Day 1 notes.

That is the concrete mechanism behind the "shield is fixed-source" decision in the
build spec. Two ways to feed it: extract the leakage source from your own core
model (above), or prescribe the FMC-N spectrum directly with an
`IndependentSource` (the 0.0919 to 18 MeV bands, fractions 0.8051 / 0.1647 /
0.0295 / 0.000685). For matching the report's published numbers, prescribe the
FMC-N spectrum so you are validating against their stated source; use the
extracted leakage source later when you move to the coupled modern model.

Normalization is how you close the NAA-SR-9647 gap (absolute dose rates). The
per-source-neutron flux table in the build spec is exactly the un-normalized
OpenMC flux tally. To get absolute neutron and gamma dose at the 284.3 cm plane:
add a heating tally, impose the 34 kW core power to solve for S, then multiply the
flux (and a flux-to-dose response) through. Until you do that, your OpenMC flux is
in per-source-particle units, which is fine for the validation ratios.

The validation ratios need no normalization, which makes them robust targets:
the factor-of-six mating-plane reduction, the 0.0359 attenuation ratio, and the
0.156 cm^-1 removal cross section are all ratios or slopes of flux tallies, so S
and volume cancel exactly like the energy-per-fission ratio in Example 1.

Two more concrete hooks: the fast-fluence cutoff conflict (>0.1 vs >1.0 MeV) is
just the lower bound of an `EnergyFilter` on the fluence tally, so you can compute
both and report the difference rather than picking one blind. And triggers will
help push the shield tally to acceptable statistics, but they do not substitute
for variance reduction — a trigger on the far-field flux could run to the batch
cap without converging if too few particles penetrate, which is the deep-
penetration problem flagged in the Day 1 notes. Triggers tighten a converging
answer; weight windows are what get particles to the dose plane in the first place.

A tally-by-material run (Example 3) on the core also hands you the per-material
absorption and fission rates for free, and a k-effective trigger is the tool for
the control-drum critical search (rotate a drum, run to tight k statistics, find
the angle giving k = 1).

---

## E. Questions left open in the room — searched answers

These were asked in the workshop and got "I don't know," a guess, or no answer.
The answers below were researched afterward and are not from the workshop.

### SNAP-10A startup neutron source (the room could not resolve this) [partially resolved]

A student asked how SNAP-10A was started in orbit and what neutron source it
used; April did not know, and the room half-remembered "ambient protons from
space" and debated whether omitting a dedicated source was a weight decision.

Operationally, startup was by reflector rotation, not by injecting neutrons. The
reactor flew subcritical with its beryllium reflector drums turned to let neutrons
leak out; on ground command in orbit the drums rotated to reflect neutrons back
into the core and drive it critical. On the Snapshot flight (3 April 1965) startup
began about 3 h 48 min after launch, criticality came at 10 h 13 min, and full
power about 2 h 15 min later. That matches the "slow, ~9-10 hour" startup the room
recalled; the pace was set by reactivity-insertion control and thermal limits, not
by source strength.

The actual source-neutron question — what kept a measurable neutron population in
the subcritical core so the approach to critical could be monitored — is not
settled by the accessible secondary sources. Any subcritical reactor needs source
neutrons for excore detectors to read subcritical multiplication, or the count
decays toward zero. A fresh HEU U-ZrH core has an inherent background ((alpha,n)
on light elements plus a little spontaneous fission), and in orbit cosmic-ray-
induced neutrons add to it, which is the grain of truth in the "protons from
space" remark. Whether SNAP-10A carried a dedicated installed startup source (an
Sb-Be or similar photoneutron source, standard in terrestrial reactors) or relied
on the inherent/background source, I could not confirm from a citable source. The
authoritative place to settle it is the primary startup report already in your
bibliography, NAA-SR-9720 (SNAP 10A prestartup and startup performance) — look for
its source-neutron / subcritical-monitoring section.

Sources: [Drew Ex Machina, "The First Nuclear Reactor in Orbit"](https://www.drewexmachina.com/2015/04/03/first-nuclear-reactor-in-orbit/); [nuclear-power.com, Source neutrons and external source of neutrons](https://www.nuclear-power.com/nuclear-power/reactor-physics/reactor-dynamics/subcritical-multiplication/source-neutrons-and-external-source-of-neutrons/).

### What the sourcepoint "separate" flag does (April: "I don't remember") [resolved]

Writing the fission-bank source at chosen batches, April set `separate` and said
she did not remember its effect, guessing it kept separate files. Confirmed from
the openmc.Settings docs: `separate` is a bool controlling whether the source is
written to its own file rather than embedded inside the statepoint file. Her guess
was right — it isolates the source bank into a standalone source HDF5 file instead
of bundling it into the statepoint.

Source: [openmc.Settings documentation](https://docs.openmc.org/en/stable/pythonapi/generated/openmc.Settings.html).

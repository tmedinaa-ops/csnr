# OpenMC Workshop, Day 3 — Depletion and Multiphysics

Two notebooks: depletion (how composition changes over reactor life) and a bare-
bones multiphysics coupling (neutronics talking to a thermal solver). This is the
session that maps most directly onto your SNAP-10A multiphysics validation work —
the Cardinal Picard loop, the temperature feedback coefficients, and the coupled
k_eff are all here in their simplest form. A dedicated tie-in is at the end. API
names were checked against the openmc.deplete and openmc.lib docs, since the audio
garbled several. The depletion-chain file-sharing struggle and the Lego/pistachio
chatter are skipped.

---

## A. Depletion (burnup)

### Why composition changes, and why it matters

Materials transmute (neutron-induced reactions change one nuclide into another)
and decay (radioactive nuclides change on their own). U-238 alpha-decays to
thorium; capture builds heavier actinides; fission splits into fission products.
Every such change alters the cross sections, so the reactor is a moving target.

All the released energy ends up as heat. It comes from the mass difference
between reactants and products (E = mc^2), carried off as kinetic energy of the
products, which scatter and deposit it as thermal vibration. The exceptions leave
the system — neutrinos from fission carry energy off and barely interact. Some
heat is prompt (at the reaction), some is delayed: a nuclide created radioactive
may not decay for years, releasing decay heat long after.

Reasons to predict this: deliberate transmutation (breeding plutonium, making
medical isotopes), waste radioactivity and handling, fuel chemistry and its
effect on structural materials, fuel burnup (you deplete fissile material and
eventually cannot stay critical — this sets reactor lifetime), and safety (the
changing composition shifts reactivity coefficients over life).

### The Bateman equations

The math is a large coupled system of linear ODEs, one per nuclide on the chart of
the nuclides (~3400). Each nuclide has source terms (transmutation in, decay in)
and sink terms (its own decay, transmutation away). The neutron-induced terms
carry the flux, so the system couples to transport. The solve is staggered: run
OpenMC for the flux and reaction rates, project the composition forward one time
step, then the changed composition changes the cross sections, so rerun OpenMC,
and repeat across the reactor's life. OpenMC has depletion built in
(`openmc.deplete`) — no external ORIGEN needed.

### Setup: volumes and the chain file

Depletion needs the volume of each depleted region, because reaction rates are
normalized to an imposed power under the hood. Set it directly (`mat.volume =
pi*r**2*h`) for simple shapes, or have OpenMC compute it with a stochastic volume
calculation. You only deplete materials you care about — here, just the fuel, so
only the fuel volume is set. For an axially-infinite model, everything is per unit
height, so the "volume" is pi*r^2 per cm.

The Bateman system also needs a depletion chain file: half-lives, decay modes and
branching, and fission product yields. Download it from openmc.org alongside the
cross sections, matched to your library, and to your spectrum — thermal vs fast
fission yields differ, so a thermal reactor uses the thermal chain. Point OpenMC
at it the same way as cross sections:

```python
import openmc.deplete
openmc.config['chain_file'] = 'chain_endfb80.xml'   # or pass to the operator below
```

The full chain has ~3400 nuclides; many have microsecond half-lives irrelevant to
most analyses. A reduced/simplified chain (the workshop's `chain_simple.xml` has
~9) collapses those for speed — drop a nuclide's negligible intermediate and route
straight to its product, or omit nuclides that could never be produced in your
material.

### The two classes: operator and integrator

Depletion needs a transport operator (runs OpenMC, gets reaction rates, hands them
to the Bateman solver) and a time integrator (advances composition over each step).

```python
operator = openmc.deplete.CoupledOperator(model, 'chain_simple.xml')

power = 174          # W (per unit height here); the irradiation power
timesteps = [30, 30, 47, 10, 5, 5]   # units of your choosing (days below)

integrator = openmc.deplete.PredictorIntegrator(
    operator, timesteps, power, timestep_units='d')
integrator.integrate()
```

`CoupledOperator` is the transport-coupled operator (an `IndependentOperator`
exists for multigroup, transport-free depletion). `PredictorIntegrator` is the
simplest, first-order forward Euler. Higher-order integrators (`CECMIntegrator`,
`CELIIntegrator`, `CF4Integrator`, and others) cost more per step but converge
faster as you shrink the step and tolerate bigger steps — the usual accuracy/cost
trade. `integrate()` runs OpenMC once per step (plus one at the end if asked).

Power and time steps can vary. To model shutdown, set power to 0 for a span and
keep stepping — composition still evolves (decay heat, waste radioactivity). Units
can be mixed per step (days, then hours).

### Reading results

```python
results = openmc.deplete.Results('depletion_results.h5')
time, keff = results.get_keff(time_units='d')        # returns (time, value+/-unc)
time, n5  = results.get_atoms(fuel, 'U235', nuc_units='atom/b-cm', time_units='d')
time, rr  = results.get_reaction_rate(fuel, 'U235', 'fission')
```

`get_keff`, `get_atoms`, `get_mass`, `get_reaction_rate`, `get_decay_heat` each
return time plus the quantity (k with its uncertainty — plot it with error bars).
Over life, k_eff trends down as fissile material burns. Xe-135 builds up fast and
has a huge thermal absorption cross section, which is the reason to use small time
steps early — it jumps in a single step otherwise. (`atom/b-cm` is atoms per
barn-cm, a barn being 1e-24 cm^2, just atoms per unit volume in nuclear units.)

Time-step size matters like mesh resolution: too big and the answer is wrong, too
small and you waste compute. A rule of thumb caps the step by energy released per
kg of heavy metal; `operator.heavy_metal` gives the heavy-metal mass to form that
ratio. Keep steps under ~1 month, and ~1 day for the first month while fast-
building products settle.

### Per-instance depletion

In a lattice, the repeated fuel cell is one object but many instances. To deplete
each position separately (different plutonium buildup per pin), pass
`diff_burnable_mats=True` when building the operator:

```python
operator = openmc.deplete.CoupledOperator(
    model, chain, diff_burnable_mats=True)
```

---

## B. Multiphysics coupling

### Why couple: temperature and density feedback

Cross sections depend on temperature, mainly through Doppler broadening. Atoms
vibrate more as temperature rises, so the relative neutron-nucleus energy smears
out, widening resonances. Wider resonances raise absorption in fertile nuclides
like U-238 (which mostly captures rather than fissions at low energy), which lowers
k_eff as temperature rises. That negative feedback is the self-regulating reactor:
get too hot and the chain reaction damps itself, like lifting off the gas pedal.
It depends on composition — very high enrichment with little fertile material can
flip the sign positive, which is why almost all reactors are designed for negative
feedback.

The second mechanism is density. The macroscopic cross section is microscopic
times number density, and density falls with temperature. Boiling or heating the
coolant thins it, so it moderates less, neutrons stay fast, and k_eff drops — again
negative feedback.

OpenMC computes neither temperature nor density; it needs them as inputs to pick
the right cross sections. So a real reactor analysis is a coupled solve with a
thermal-hydraulics (TH) solver.

### Picard iteration

OpenMC produces a heat tally (q‴, recoverable fission energy = the `kappa-fission`
score), which is the source term for the TH solver's conduction/energy equation.
The TH solver returns temperatures and densities, which update the cross sections,
which change the heat tally. Iterate until things stop changing:

1. Run OpenMC at current T, rho -> heat source q‴.
2. TH solver -> new T, rho.
3. Update cross sections; rerun OpenMC.
4. Stop when the relative change between iterations is below a tolerance.

This fixed-point loop is Picard iteration. Coupling can be external (file-based:
statepoint -> script -> new input -> rerun; simple but slow) or in-memory through
the C API (no file I/O). Cardinal does the in-memory coupling and hides the
plumbing; the workshop builds the bare version by hand.

### Setting temperature and density

Four ways to set temperature, with a precedence order. The workshop sets it per
cell (any cell with a unique ID+instance can have its own temperature). Setting it
per material would force a unique material per region (memory-heavy). A model-wide
default goes in a settings dictionary:

```python
model.settings.temperature = {
    'default': 573,             # K, applied where nothing else is set
    'method': 'interpolation',  # vs 'nearest'
    'range': (500, 1200),       # load libraries spanning this up front
}
```

Libraries exist only at discrete temperatures (ENDF/B has six). For a temperature
in between, `'nearest'` snaps to the closest library (crude when they are far
apart). `'interpolation'` is the recommendation, and OpenMC does it stochastically:
at a collision at 700 K between 600 K and 900 K libraries, it rolls a random number
and reads the 900 K data a third of the time, 600 K the rest, which averages to a
linear interpolation without storing a pre-averaged 700 K library (that would
multiply the already-large data by the number of temperatures). Cross sections load
once at the start, so `'range'` tells OpenMC which temperature libraries to load
before the run, covering every temperature the Picard loop will reach. Density is
set per cell similarly.

### The C API (openmc.lib)

Running OpenMC all at once (`model.run()`) reloads the model and cross sections and
writes a statepoint every time. For a Picard loop that is wasteful — you only want
to rerun transport after nudging temperatures. The C API breaks OpenMC into pieces
held in memory:

```python
import openmc.lib
# manual form:
openmc.lib.init(); openmc.lib.run(); openmc.lib.reset(); openmc.lib.finalize()
# or the context manager that handles init/finalize:
with openmc.lib.run_in_memory():
    for _ in range(5):                 # fixed iteration count to avoid infinite loop
        openmc.lib.reset()             # clear old tallies
        openmc.lib.run()               # one transport solve
        # ... read heat tally, call TH solver, set new T/rho ...
```

Mapping data between the codes is the hard part: OpenMC is CSG, the TH solver is
usually a mesh, and neither knows the other's indexing. `openmc.lib.find_cell((x,
y, z))` returns the cell and instance at a point, so you can map a temperature from
the TH mesh to the right OpenMC cell instead of hardcoding it. Set the result via
the in-memory cell objects (`openmc.lib.cells[id]`, with set-temperature/set-
density methods). To damp oscillations where the heat source and temperature chase
each other between two states, apply relaxation — blend the new tally with the
previous one before passing it on. You can also run one batch at a time
(`openmc.lib.next_batch`) for feedback at the finest granularity.

### Result

Layer the pin into a 3D lattice (e.g. 20 axial layers) so each layer carries its
own temperature and density, tally heat per layer with a `DistribcellFilter`, and
run the loop. The coolant enters cold and dense at the bottom and leaves hot and
thin at the top, so Doppler (hot top) and reduced moderation (thin top) both push
power toward the bottom — the power profile shifts down. Engineering payoff: the
power distribution drives the cooling-system design and the achievable power
rating, since OpenMC alone enforces no melting-point or critical-heat-flux limit.
Multiphysics matters most for space systems, which already run hot.

---

## C. What this means for SNAP-10A

This session is your multiphysics validation workstream in miniature. The build
spec's coupled target — k_eff = 1.00086, fuel and fluid temperatures within ~3 K
of NAA-SR-9903 — is exactly a converged Picard loop, and the arXiv 2505.04024 paper
does it with Cardinal. April's hand-built version is the same loop without Cardinal.

The temperature feedback is your reactivity-coefficient physics. Doppler broadening
plus the ZrH moderator hardening is where the U-ZrH prompt negative temperature
coefficient comes from — the build spec's prompt fuel coefficient and the FS-3
measured -0.29 +/- 0.02 cents/F. The self-regulating negative feedback is also the
core of the safety argument in the settled conclusions. Reproducing the sign and
rough magnitude of that coefficient from a coupled OpenMC run is a concrete,
checkable validation, and the temperature-interpolation settings (with `range`
covering the NaK loop 755-816 K and fuel ~805-853 K from the base set) are how you
feed the operating temperatures in.

Depletion is secondary for SNAP-10A but not irrelevant. The reactor ran ~43 days
before the payload fault against a one-year design life, so burnup reactivity loss
is modest; k_eff vs time still gives the reactivity-vs-life curve, and the isotopic
inventory feeds the disposal/radioactivity side of the argument (how active the
orbiting reactor is, relevant to the NaK-debris and 4000-year-orbit case). Use a
reduced chain matched to ENDF/B-VIII.0, and set the fuel volume from the 37-element
geometry. Note SNAP-10A is an epithermal U-ZrH system, so pick chain fission yields
accordingly rather than defaulting to the pure-thermal set.

The most actionable point: the C API path is the lightweight alternative to a full
Cardinal build, which the project notes flag as HPC-only. The conda OpenMC on your
Mac can drive a Picard loop through `openmc.lib` against a simple Python thermal
model right now, with no MOOSE. That makes a first coupled SNAP-10A temperature-
feedback test feasible locally before committing to the heavier Cardinal stack —
worth doing as a proof of concept, with the explicit caveat that the workshop's TH
back-end is a toy and any real coupling needs MOOSE or Cardinal for the thermal
side.

---

## D. Question left open in the room — searched answer

### Why didn't 10x more particles slow the in-memory multiphysics run? (April: "not sure, not super important") [resolved]

April raised `model.settings.particles` by 10x for the C-API multiphysics run and
it stayed suspiciously fast; she guessed the setting "doesn't respond in an active
OpenMC simulation." That guess is right. When you run through `openmc.lib`, the
particle count is fixed at `openmc.lib.init()` from the exported settings — the C++
side already holds its configuration, so reassigning `model.settings.particles` in
Python afterward does not propagate to the running simulation. To actually change
it, set the value before `init()` (so it is in the exported settings.xml), or
re-export and re-initialize. This is a real gotcha for the in-memory coupling you'd
use on SNAP-10A: change run parameters before initializing the library session,
not inside the loop. (Behavior confirmed against the openmc.lib API model, where
init reads the exported model and run/reset operate on that fixed in-memory state.)

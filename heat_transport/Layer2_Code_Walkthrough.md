# Layer 2 heat transport: code walkthrough

This explains every file that runs in the Layer 2 coupled model, block by block,
the same way `Layer1_Code_Walkthrough.md` does for the single pin, plus the bugs
we hit getting it to run and what each one taught. Layer 2 is the full SNAP-10A
core: 37 fuel pins, solved three ways at once. OpenMC computes where the fission
heat lands across the whole core, MOOSE conducts it through every pin, and 37 THM
channels carry it away in the NaK. The numbers that come out, the hot-channel
outlet temperature and the peak fuel temperature, are what feed the energy-
conversion models and the 14 kWe study.

Read this next to the files in `layer2_core/`. It assumes you have already read
the Layer 1 walkthrough, because Layer 2 is the same architecture scaled up, and
this document spends its time on what changed rather than repeating what stayed
the same.

## The big picture

Still a star. The solid conduction solve is the hub. OpenMC and THM hang off it as
sub-apps. The hub owns the clock and asks the sub-apps to solve each step.

```
        heat_source -->                       T_wall -->
  OpenMC  ------------------>  SOLID (hub)  ----------------->  THM bundle
 openmc_core.i  <-- temperature  solid_core.i  <-- T_fluid, htc   thm.i x37
   (the snap.py 37-pin core)   (owns the clock)    (one channel per pin)
```

Three things are different from Layer 1, and every change in the files traces back
to one of them:

1. The OpenMC model is the real 37-pin `snap.py` core, not a single reflected pin.
   So the power is the full 34 kWt, the heat shape has real radial peaking (center
   pins hotter than edge pins), and the geometry is a HexLattice that nests deeper,
   which is why `cell_level` changes.
2. The NaK side is a bundle: 37 THM channels instead of one. This is the part that
   broke and got fixed, and most of this document's debugging story is about it.
3. The mesh is centered on z to line up with `snap.py`, which runs its fuel from
   minus half-length to plus half-length rather than 0 to L. That one change ripples
   into the THM channel placement.

Same two unit conventions as Layer 1: MOOSE is SI (meters, kelvin), OpenMC is
centimeters, bridged by `scaling = 100`. Same two conda environments: `openmc-env`
builds the OpenMC model, `moose` runs Cardinal.

Execution order when you launch a run:

1. `python snap.py fig12_test` (in the snap repo, `openmc-env`, run once) writes
   the 37-pin OpenMC model to `model.xml`. Copy it into `layer2_core/`.
2. `cardinal-opt -i make_core_mesh.i --mesh-only core37.e` (run once) builds the
   37-pin mesh.
3. `mpiexec -np 4 cardinal-opt -i solid_core.i --n-threads=4` launches the hub.
4. `solid_core.i` starts and, as its sub-apps, launches `openmc_core.i` once and
   `thm.i` thirty-seven times (once per pin position).
5. They march together; results land in `solid_core.csv` and the 37
   `solid_core_out_thm*_csv.csv` files.

---

## File 1: make_core_mesh.i (builds the 37-pin mesh)

Run once with `--mesh-only` to produce `core37.e`. Layer 1 meshed one pin with a
`ConcentricCircleMeshGenerator`. Layer 2 reuses that exact validated cross section
and stamps 37 copies of it at the real pin coordinates, then extrudes and centers.
The reason it stamps copies instead of using the reactor module's hex generators
is risk: the copy approach reuses a cross section we know meshes, and the 37 exact
coordinates, so it is the lower-risk first build.

```
r_fuel = 0.0153924
r_coat = 0.0156210
r_clad = 0.0158750
L      = 0.310515
n_ax   = 30
```

The pin radii and active length in meters. These match `snap.py`'s `r1/r2/r3` and
twice its half-height, so the MOOSE solid and the OpenMC geometry describe the same
pin.

```
[pin_xs]
  type = ConcentricCircleMeshGenerator
  num_sectors = 8
  radii = '${r_fuel} ${r_coat} ${r_clad}'
  rings = '4 1 1'
  has_outer_square = false
  preserve_volumes = true
[]
```

One pin's 2-D cross section: fuel, coating, clad rings, no coolant ring. Identical
to Layer 1's, deliberately, so a known-good piece is the building block.

```
[core_xs]
  type = CombinerGenerator
  inputs = 'pin_xs'
  positions = '
     0.0000000  0.0000000  0
     0.0277162  0.0160020  0
     ... (37 lines) ...
     0.0000000 -0.0960120  0'
[]
```

`CombinerGenerator` copies `pin_xs` to each of the 37 positions, which are
`snap.py`'s fuel coordinates divided by 100 to get meters. The result is 37
separate pin cross sections, not connected to each other. That disconnection is
correct: the pins do not touch, and the only path from one pin to another is
through the NaK, which THM handles. Same-named sidesets merge, so all 37 clad
surfaces share one sideset called `outer`.

```
[names]   RenameBlockGenerator   old_block = '1 2 3'   new_block = 'fuel coating clad'
[core3d]  AdvancedExtruderGenerator   direction = '0 0 1'   heights = '${L}'   num_layers = '${n_ax}'
[bottom], [top]  ParsedGenerateSideset   (axial end faces)
```

Name the three rings, extrude the whole 37-pin cross section into a 3-D core over
the 0.31 m length with 30 axial layers, and tag the end faces. So far this matches
Layer 1, just with 37 pins instead of one.

```
[center]
  type = TransformGenerator
  input = top
  transform = TRANSLATE
  vector_value = '0 0 -0.1552575'
[]
```

This is new and it matters. The extrude above runs z from 0 to L. But `snap.py`'s
core is centered on z=0, its fuel spanning minus 0.1552575 to plus 0.1552575 m.
Cardinal maps OpenMC to MOOSE by absolute position, so if the mesh sat at 0 to L
the fuel elements would map to vacuum above the real core and the coupling would
garble. `TransformGenerator` shifts the whole mesh down by half a length so it
sits centered like `snap.py`. It is done last, after the `bottom`/`top` sidesets
are assigned, so those stay attached to the right faces. The single pin got away
without this because `snap_unit_pin.py` also ran 0 to L; the full core does not.

---

## File 2: pin_positions.txt (the 37 channel locations)

A plain text file, one line per pin, three numbers each: x, y, z in meters.

```
0.0000000 0.0000000 -0.1552575
0.0277162 0.0160020 -0.1552575
... (37 lines) ...
0.0000000 -0.0960120 -0.1552575
```

The x and y are the pin centers (the same coordinates as the mesh). The z is minus
half-length, which seats each NaK channel on the centered pin. Both `solid_core.i`
blocks that need the pin locations read this one file, so the channel placement and
the surface partition can never drift out of sync. Using the file instead of typing
the list twice is the single-source-of-truth move; it also made the energy-
conservation fix a one-file edit.

---

## File 3: the OpenMC model (snap.py -> model.xml)

Layer 1 built its OpenMC model from `snap_unit_pin.py`, a small self-contained
script. Layer 2 uses the real core model from the `snap` repository, which is a
large file with its own walkthrough there. What you need to know here:

- You build it with `python snap.py fig12_test`, which writes `model.xml`. The
  `fig12_test` case is the operating-condition configuration: 37 fresh fuels, NaK,
  control drums at 94 degrees, 783.15 K. It is the same case whose standalone
  k-effective (about 1.00086) the coupled run should reproduce.
- The geometry is an `openmc.HexLattice`, four rings of pins (1 + 6 + 12 + 18 =
  37). The pins nest one universe level below the lattice container, which is why
  `cell_level` is 1 here and was 0 for the flat single pin.
- For the first coupled run we use the default coarse model (334 cells). The finer
  axial discretization that gives a real axial heat shape is a flag in `snap.py`
  you turn on once the coarse coupling is working.
- `model.xml` is the only file Cardinal reads for the neutronics, so it has to sit
  in `layer2_core/` (copy it in after building). It is not tracked in git because
  it is generated.

---

## File 4: openmc_core.i (the OpenMC neutronics sub-app)

Wraps the 37-pin OpenMC model as a Cardinal sub-app. Same role as Layer 1's
`openmc.i`, with three changes for the full core.

```
[Mesh]
  [core]  type = FileMeshGenerator  file = core37.e  []
[]
```

Reuse the 37-pin mesh, so OpenMC's cells map onto the conduction elements.

```
[Problem]
  type = OpenMCCellAverageProblem
  particles = 20000
  power = 34000.0
  scaling = 100.0
  cell_level = 1
  temperature_blocks = 'fuel coating clad'
  check_equal_mapped_tally_volumes = true
  relaxation = robbins_monro
  [Tallies]
    [heat_source]  type = CellTally  block = 'fuel'  name = heat_source  []
  []
[]
```

Four lines carry the Layer 2 differences:

- `particles = 20000` overrides the particle count baked into `model.xml`. The snap
  model is built for standalone production criticality at a million particles per
  batch. That is a memory spike and ruinously slow when OpenMC re-solves every
  coupling step, so we cut it. The relaxed march averages the source over a couple
  hundred steps, so each solve needs only modest statistics. The final reported
  k and source come from one high-statistics standalone solve, not the march.
- `power = 34000.0` is the full core power, not the per-pin 918.9 W. All 37 pins
  are present, so the normalization is the whole core.
- `cell_level = 1` points Cardinal one universe level below the root, where the pin
  cells live inside the HexLattice. The single pin was a flat universe, level 0.
- `check_equal_mapped_tally_volumes = true` aborts the run if the mapped tally
  volumes come out uneven, which is the usual symptom of a wrong `cell_level` or a
  mesh-to-geometry misalignment. It is a tripwire so you find a mapping error in
  seconds instead of trusting a bad run.

The `CellTally` named `heat_source` measures the kappa-fission heat on every pin's
fuel, the same as Layer 1 but now summed over 37 pins to the full 34 kW.

```
[Executioner]
  type = Transient
  dt = 1e6
[]
```

The same huge-dt trick as Layer 1: OpenMC has no time physics, so a large dt stops
this sub-app from clamping the parent clock down to its own default.

---

## File 5: thm.i (one NaK channel, run 37 times)

The single-channel NaK model, identical in spirit to Layer 1's `thm.i`. The hub
launches one copy per pin. Two things are worth pointing out for the bundle.

```
T_in   = 755.37
mdot   = 0.0167541
P_hf   = 0.0997456
```

The per-channel flow conditions are unchanged from Layer 1, because each Layer 2
channel is still one pin's worth of flow. Thirty-seven of them at 0.0167541 kg/s
reproduce the full 0.6199 kg/s core flow exactly, which is what makes the bundle
energy-exact: each pin's heat goes into one pin's flow and produces the right
temperature rise.

```
[Postprocessors]
  [T_fluid_out]  SideAverageValue  boundary = 'pipe:out'
  [T_fluid_in]   SideAverageValue  boundary = 'pipe:in'
  [heat_removed] ParsedPostprocessor  expression = 'mdot * cp * (T_fluid_out - T_in)'
[]
```

`heat_removed` is the power this one channel carries away. In Layer 1 there was a
companion `power_imbalance` postprocessor that differenced this against the per-pin
918.9 W. That does not carry over to the core, because each channel's power differs
with the radial peaking, so there is no single per-channel reference to subtract.
The per-channel `power_imbalance` was removed; the convergence check moved up to
the core level in `solid_core.i`. `heat_removed` stays so you can read the hot-to-
cold spread across the 37 channels.

```
[Outputs]
  [out]  type = Exodus
  [csv]  type = CSV       # no file_base
[]
```

The CSV has no `file_base`. In Layer 1, one channel, it was fixed to `thm_nak`.
With 37 instances a fixed name would make all of them write the same file, which
MOOSE refuses. Leaving `file_base` off lets MOOSE auto-name each instance, so you
get `solid_core_out_thm0_csv.csv` through `solid_core_out_thm36_csv.csv`, with
`thm0` the center pin and the higher indices fanning outward.

---

## File 6: solid_core.i (the hub)

The center of the star, the file `cardinal-opt -i` points at. Mesh, variables,
kernels, and materials are the Layer 1 hub scaled to 37 pins, so this walkthrough
covers only what is different: the 37-channel coupling, the core-level convergence
check, and the longer march.

```
[Variables]   [T]  initial_condition = 783.15
[AuxVariables]   [power]   [T_fluid]   [htc]
[Kernels]   [conduction]   [time]   [source]  block = fuel
[Materials]   fuel 22.484, coating 1.729, clad k(T), clad rho-cp
```

All identical to Layer 1, just over a 37-pin mesh. `T` is the unknown,
`power`/`T_fluid`/`htc` are supplied by the transfers, the three kernels are the
heat equation with the OpenMC source, and the materials are the same sourced
conductivities.

```
[CoupledHeatTransfers]
  [interface]
    boundary = 'outer'
    T = T   T_fluid = 'T_fluid'   T_wall = T_wall   htc = 'htc'
    multi_app = thm
    T_fluid_user_objects = 'T_uo'   htc_user_objects = 'Hw_uo'
    position = '0 0 0'   orientation = '0 0 1'   length = ${L}   n_elems = ${n_ax}
    positions_file = 'pin_positions.txt'
    skip_coordinate_collapsing = true
  []
[]
```

This block is where Layer 2 lives or dies, so it is worth understanding exactly.
Per the MOOSE `CoupledHeatTransferAction` docs, this action builds a
`NearestPointLayeredSideAverage` over the `outer` sideset. That user object
partitions the surface by which sub-app position is nearest, so each pin's clad
surface is assigned to the channel sitting at that pin. Then it transfers each
channel's wall temperature in and its fluid temperature and heat-transfer
coefficient back, layer by layer.

The `positions_file` line is the one that makes it work, and its absence is what
broke the first attempts. The action only knows the channel positions if you hand
them to the action, not just to the MultiApp. Without `positions_file` here, the
`NearestPointLayeredSideAverage` had a single point, so it collapsed all 37 pins'
surfaces onto one channel and the rest of the heat went nowhere. `position = '0 0
0'` is the per-channel axial base copied from `thm.i`'s flow channel; the file
supplies the per-pin offsets, including the minus-half-length z that seats each
channel on the centered mesh.

```
[MultiApps]
  [openmc]  type = TransientMultiApp  input_files = 'openmc_core.i'  execute_on = timestep_end
  [thm]     type = TransientMultiApp  input_files = 'thm.i'  positions_file = 'pin_positions.txt'  sub_cycling = true
[]
```

One OpenMC sub-app and the THM bundle. The THM MultiApp reads the same
`pin_positions.txt`, so the 37 sub-app instances sit at exactly the points the
action partitions the surface by. That shared file is why the placement and the
partition cannot disagree.

```
[Transfers]
  [heat_from_openmc]  ... source_variable = heat_source  variable = power  (conserving)
  [temp_to_openmc]    ... source_variable = T  variable = temp
[]
```

Same as Layer 1: heat up from OpenMC into `power` with the total wattage preserved,
temperature down to OpenMC. The THM transfers are not listed because the
`CoupledHeatTransfers` action created them.

```
[Executioner]
  type = Transient   scheme = bdf2
  dt = 100.0   num_steps = 350
  fixed_point_max_its = 1
[]
```

A pseudo-transient march, one coupled exchange per step. The big difference from
Layer 1's original setup is `num_steps = 350` and the single fixed-point iteration.
Layer 1 taught us that the approach to steady is paced by the loose one-exchange-
per-step coupling, about 1.5 percent of the remaining error removed each step, not
by any physical thermal time constant. So it takes a couple hundred steps, and 350
is headroom. There is no `steady_state_detection` on purpose: the Monte-Carlo noise
in the OpenMC source trips a norm-based detector into a false stop.

```
[Postprocessors]
  [power_in]          ElementIntegralVariablePostprocessor  variable = power  block = fuel
  [max_fuel_T]        ElementExtremeValue  variable = T  block = fuel  value_type = max
  [surface_heat_out]  SideDiffusiveFluxIntegral  boundary = 'outer'  diffusivity = thermal_conductivity
  [power_imbalance]   ParsedPostprocessor  expression = 'power_in - surface_heat_out'
[]
```

`power_in` must integrate to 34000 W, the first check on any run. `max_fuel_T` is
the peak fuel temperature, the safety number, which should settle around 840 to
855 K and must stay above the NaK outlet and under 900. `surface_heat_out` and
`power_imbalance` were meant to be the convergence check, but they have a wrinkle
explained in the convergence section below: trust the channel sum instead.

---

## How one time step actually executes

A single 100 s parent step with 37 channels:

1. The parent begins the step. With `fixed_point_max_its = 1` it does one exchange,
   not a converged inner loop.
2. It runs the OpenMC sub-app once: OpenMC does an eigenvalue solve at the current
   temperatures and produces the heat shape across all 37 pins, normalized to
   34000 W.
3. That heat transfers up into `power`, total wattage preserved.
4. The solid solves the heat equation for `T` over the whole 37-pin mesh with that
   source and the current NaK boundary.
5. The new wall temperature goes to the THM bundle. The action's nearest-point
   partition sends each pin's wall temperature to its own channel; all 37 channels
   sub-cycle their 0.25 s steps across the 100 s and return their fluid temperatures
   and heat-transfer coefficients.
6. The clock advances 100 s. Because it is one exchange per step, the coupled fields
   are slightly lagged, and the lag washes out over the march.
7. The postprocessors write to `solid_core.csv`; each channel writes its own CSV.

Over successive steps the pins heat up, the channels warm, and the heat carried by
the NaK climbs toward 34000 W. When it gets there and `max_fuel_T` flattens, the
core is at steady state.

---

## The bugs we hit, and what each one taught

Most of "what is going on" with Layer 2 is the debugging path, because the coupled
core surfaced one failure at a time. In order:

1. **MPI launcher mismatch.** The first run aborted with a PMIx error. Cause: the
   run was launched from the `openmc-env` conda environment, whose `mpiexec` is a
   different MPI than the one `cardinal-opt` was built against. Lesson, the same
   discipline as everywhere: build the OpenMC model in `openmc-env`, run Cardinal
   in `moose`.

2. **Output filename collision.** The run got through instantiating the sub-apps,
   then errored because `thm.i` forced its CSV to a fixed `file_base` and 37
   instances cannot share one file. Fix: drop `file_base`, let MOOSE auto-name.
   This is the difference between one channel and a bundle.

3. **A million particles per batch.** The next run got into OpenMC and died around
   the second batch. The snap `model.xml` runs a million particles per batch, which
   is right for a standalone k but a memory spike and far too slow when repeated
   every coupling step. Fix: `particles = 20000` in `openmc_core.i`. The relaxed
   march does not need production statistics per step.

4. **Too many data copies.** Before the particle cut, running 18 MPI ranks meant 18
   private copies of the nuclear data, which overran the WSL memory. Lesson for the
   full core: prefer fewer ranks with more threads, because OpenMP threads share one
   copy of the cross sections while MPI ranks duplicate them. `-np 4 --n-threads=4`
   is 16-way at a quarter of the memory.

5. **The big one: 33 kW vanishing.** With the coupling finally running, the energy
   did not close. The solid showed about 34 kW leaving its surface, but the channels
   together absorbed under 1 kW. The peak fuel temperature sat at 782 K, below the
   817 K the NaK outlet has to reach, which is physically impossible if the coolant
   were really heating, so it proved the NaK was staying cold. Cause: the
   `CoupledHeatTransfers` action was given the channel positions only through the
   MultiApp, not through the action itself, so its nearest-point partition collapsed
   all 37 surfaces onto one channel. Fix: pass `positions_file` to the action, and
   give it all 37 pins instead of 3 so the energy closes pin by pin. This is the fix
   in `pin_positions.txt` and the `CoupledHeatTransfers` block.

The throughline: a coupled multiphysics deck fails one layer at a time, and each
error is narrower than the last. The energy balance is the check that caught the
real physics bug, because a deck can run cleanly and still be wrong, and the only
way to know is to make it conserve energy and reach a physically sane temperature.

---

## How to read the output and judge convergence

This is the one place the deck is currently misleading, so read carefully.

The intuitive convergence check is `power_imbalance` in `solid_core.csv`, which is
`power_in` minus `surface_heat_out`. It is a false signal here, and the reason is
worth understanding. Conduction inside each pin equilibrates in seconds, so the heat
reaches the clad surface almost immediately and `surface_heat_out` hits 34000 W
within a few steps. But the solid-to-NaK coupling converges slowly, at that 1.5
percent per step. So `surface_heat_out` says "done" while the NaK has absorbed only
a fraction. `power_imbalance` reads near zero long before the coolant has actually
heated.

The honest convergence signals are two:

- The total heat the channels carry, summed across all 37 CSVs, climbing to 34000 W.
  This is the real heat entering the NaK. You compute it by summing the last column
  of every channel file:

  ```
  for f in solid_core_out_thm*_csv.csv; do tail -1 "$f"; done \
    | awk -F, '{s+=$4} END{printf "%.0f W\n", s}'
  ```

  It tracks the coupling-paced curve. At step 13 it was about 6160 W, which is 18
  percent of 34000, and 1 minus 0.985 to the 13th is also 18 percent, so it is on
  the textbook trajectory. Converged means within about 340 W of 34000.

- `max_fuel_T` in `solid_core.csv` climbing past 782 K, where the broken run
  flatlined, and settling around 840 to 855 K, above the outlet and under 900.

The end state, once converged: `power_in` at 34000, the channel sum at about 34000,
`max_fuel_T` flat near 840 to 855, and the 37 channel outlets fanned out with the
center pin hottest (above the 817.7 K core average) and the edge pins coolest. That
fan is the radial peaking, the result you cannot get from a single pin and the
reason the full core exists. A follow-up cleanup is to replace `surface_heat_out`
in the deck with the channel-sum heat removal so `power_imbalance` means what it
says.

## Glossary (additions to the Layer 1 glossary)

- HexLattice: OpenMC's hexagonal array of pin universes, four rings making the 37
  positions. The pins nest below it, which sets `cell_level = 1`.
- cell_level: how many universe levels below the root the mapped pin cells sit. 0
  for the flat single pin, 1 for the lattice core.
- positions_file: a text file of sub-app locations read by both the THM MultiApp and
  the CoupledHeatTransfers action, so placement and surface partition stay in sync.
- NearestPointLayeredSideAverage: the user object the coupling action builds to
  split one shared surface among many channels by nearest position. The thing that
  needs the positions to be told to the action, not just the MultiApp.
- check_equal_mapped_tally_volumes: a Cardinal tripwire that aborts if the OpenMC-
  to-mesh mapping is distorted, the fast way to catch a wrong cell_level.
- radial peaking: the center-hot, edge-cool variation of pin power across the core,
  absent in the single pin and the new physics Layer 2 produces.

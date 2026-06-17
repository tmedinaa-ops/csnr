# Layer 2: full 37-pin core (scaffold)

These are starter decks for the production step in `../ROADMAP_full_core.md`,
which is deliberately documented-not-built because it needs iteration on your
machine. The architecture does not change from Layer 1: the solid conduction app
is the hub, OpenMC and THM are its sub-apps. What changes is scale (one pin to
37), the OpenMC model (the unit pin to the real `snap.py` core), and the NaK side
(one channel to a bundle).

Nothing here has been executed. Every file is grounded in the working Layer 1
decks, the roadmap, and the actual `snap.py` geometry (lattice center (0,0),
pitch 3.2004 cm, the 37 fuel coordinates, radii 1.53924/1.56210/1.58750), but the
reactor-side mechanics that Layer 1 never exercised (the multi-channel THM, the
`cell_level` into the HexLattice) will need shaking out. Each file lists its own
TODOs; the cross-cutting ones are below.

## Files

```
make_core_mesh.i   37-pin core mesh: validated single-pin cross-section x37 via
                   CombinerGenerator at the exact snap.py coordinates, extruded.
openmc_core.i      OpenMC sub-app pointing at snap.py's model.xml (full-core
                   power 34 kWt, cell_level into the lattice, volume check on).
solid_core.i       the hub: 37-pin conduction + OpenMC + a 3-channel THM bundle.
thm.i              per-channel NaK template (byte copy of Layer 1's thm.i; the
                   THM MultiApp in solid_core.i launches it at each channel).
```

## Build order (do not skip; this is why the model is layered)

1. Build and INSPECT the mesh: `cardinal-opt -i make_core_mesh.i --mesh-only core37.e`,
   then look at it in Peacock/ParaView. Confirm 37 pins, the `fuel/coating/clad`
   blocks, and the `outer` sideset.
2. Build `snap.py`'s `model.xml` with the feedback flags on
   (`FLAG_FINE_DISCRETIZATION=True`, `FLAG_DISTRIB_COOLANT=True`), case
   `fig12_test`, in the snap dir; confirm the 37/37 lattice mapping check. Put
   `model.xml` where Cardinal runs.
3. Run `solid_core.i` ONE-WAY with a frozen source first (OpenMC MultiApp and the
   two OpenMC transfers commented out, `power` driven from
   `extract_heat_source.py --radial`). Confirm `power_in = 34000 W`, hot-channel
   NaK rise ~62 K, peak fuel < 900 K.
4. Turn the live OpenMC coupling on. Confirm coupled k near 1.00086 and
   `power_in` still 34000 W.
5. Refine: THM 3 channels -> 37, cross-section `4 1 1` -> `16 2 2`.
6. Only then turn the 14 kWe knobs (core power, inlet T).

## The three things most likely to need iteration

- `cell_level` in `openmc_core.i`. The snap pins sit one universe level below the
  HexLattice container; the deck guesses `1`. `check_equal_mapped_tally_volumes`
  is on to catch a wrong level; bump to `2` if it trips or the mapped fuel count
  isn't 37.
- The multi-channel THM mapping in `solid_core.i`. Splitting one `outer` sideset
  across 3 position-keyed channels is the least-tested mechanic. The documented
  fallback (3 separate sidesets + 3 single-channel couplings, each the validated
  Layer 1 pattern) is lower risk; switch to it if the position mapping fights you.
- Mesh-to-geometry alignment. The mesh (m) x100 must land on snap.py (cm). A
  rotation mismatch (hex flat-side orientation) shows up as mapping errors; fix it
  at the mesh or with an OpenMC rotation, never by moving pins.

## Convergence (lesson carried from Layer 1)

The march to steady is paced by the loose one-exchange-per-step coupling, ~1.5%
error reduction per step, NOT a physical thermal time constant. Layer 1's single
pin took ~250-290 steps at dt=100 to close the energy balance to 1%. So `num_steps`
starts at 350 and you stop when `power_imbalance` (printed each step) drops under
~340 W, 1% of 34000. Do not expect a 60-90 step run to be converged; a high
imbalance at step 90 means more steps, not a bug, as long as the increments are
still shrinking. Whether cutting the solid `cp` accelerates this (it did or didn't
in Layer 1's `cp_accel` test) decides if you slash `num_steps` here too.

The convergence check is at the CORE level: `power_imbalance = power_in -
surface_heat_out`, where `surface_heat_out` is the total heat conducted through
every pin's clad surface (`SideDiffusiveFluxIntegral` on `outer`). Layer 1's
per-channel imbalance does not apply, because each channel's power differs by
radial peaking. The per-channel `thm.i` still reports `heat_removed` so you can
read the hot-to-cold spread across the representative channels.

## Validation targets (from ROADMAP_full_core.md and verify_energy_balance.py)

- Coupled k near the standalone fig12_test 1.00086; a large drift after coupling
  means temperature interpolation range or cell mapping, not geometry.
- Fuel and fluid temperatures within ~3 K of NAA-SR-9903 (the coupled target).
- NaK rise 62 K at 34 kWt; hot-channel outlet near 817.7 K.
- Per-pin powers track the radial peaking the tally produces.
- `power_in` integrates to 34000 W, and `power_imbalance` -> ~0 at steady.

## Seeing the NaK and the heat transfer

The NaK is a 1-D THM subchannel, not a 3-D fluid volume (no CFD; that was a
deliberate project choice). So you visualize it as line(s), not a coolant field.
When `solid_core.i` runs (the one-way frozen-source step already does it, before
live neutronics), the THM sub-app writes its own Exodus per channel, e.g.
`solid_core_out_thm0_out.e`. Open those alongside `solid_core_out.e` in ParaView:
the pins show the 3-D fuel/clad temperature, and each channel shows the NaK bulk
temperature rising inlet-to-outlet, with `T_wall` and the HTC `Hw` available as the
heat-transfer story. A true 3-D coolant temperature field or cross-flow between
channels would need the SUBCHANNEL module or NekRS CFD, which this model does not
use on purpose.

## Why this is the layer that wants the 20-core PC

Unlike the single pin, the 37-pin core is a big enough transport problem that one
OpenMC solve actually uses all 20 cores well, and the conduction mesh is ~37x the
DOFs. This is where the hardware scaling pays off, and where the cp-acceleration
and reduced-statistics march from `../layer1_cp_accel` matter most for turnaround.

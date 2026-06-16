# Layer 2: full 37-pin core, and the path to 14 kWe

This is the production step the MVP and the single-pin two-way model build toward.
It is documented rather than built because it needs iteration on your machine,
and because it should not start until Layer 1 converges. The architecture does
not change: the solid core conduction is still the hub, OpenMC and THM are still
its sub-apps. What changes is geometry (one pin becomes 37), the OpenMC model
(the unit pin becomes the real snap.py core), and the NaK side (one channel
becomes a bundle).

## The mesh

Use the MOOSE reactor module, which Cardinal compiles in. Build it in three
steps and check each with `--mesh-only` before moving on.

Build one hex pin cell with `PolygonConcentricCircleMeshGenerator`: the
concentric fuel, coating, and clad rings inside a hexagonal coolant background,
at the 3.2004 cm pitch. Assemble the 37-pin array with `PatternedHexMeshGenerator`
(37 is four hex rings, 1 plus 6 plus 12 plus 18). Extrude to 3-D with
`AdvancedExtruderGenerator` over the 31.05 cm active length.

The conduction solve only needs the solid, so either delete the coolant
background blocks or keep them as dummy blocks carrying a `NullKernel`, the way
the Cardinal gas-compact tutorial keeps a fluid block for data transfer without
solving on it. Keep the per-pin clad outer surfaces as a sideset for the NaK
coupling. The core vessel and reflector do not need meshing for conduction;
OpenMC carries them neutronically.

If `PolygonConcentricCircleMeshGenerator` parameters fight you, the simpler
fallback is to mesh one pin (as in `two_way/make_mesh.i`) and place 37 copies
with `CombinerGenerator` at the hex coordinates, then stitch. The reactor module
is cleaner if it cooperates.

## Coupling to the real snap.py model

Point OpenMC at snap.py instead of the unit pin. Two things matter. Set `power`
to the full 34 kWt, not the per-pin value, since all 37 pins are now present. Set
`cell_level` to the lattice depth where the individual pin cells live: the snap
model is a HexLattice, so the pin cells are at least one level below the root, and
Cardinal needs that level to map each pin's fuel cell to its mesh elements. Turn
on `check_equal_mapped_tally_volumes` to catch mapping distortion. Use the same
ENDF/B-VIII.0 data and the temperature interpolation range that already covers
the NaK and fuel band.

Run `extract_heat_source.py --run --radial` against snap.py first. That gives
both the axial shape and the per-pin radial peaking. Even before the live
coupling works, the frozen radial-plus-axial source lets the full-core conduction
and NaK bundle run one-way, which is the right way to debug the bundle before
adding neutronics feedback on top.

## The NaK bundle

Thirty-seven separate sub-apps would be unwieldy. The scalable pattern is one
`TransientMultiApp` with a `positions` list of the 37 pin centers, running thm.i
37 times, with the `CoupledHeatTransfers` action mapping each clad surface to its
channel. Start smaller: three representative channels grouped by radial ring
(center, middle, edge) driven by the radial peaking, which captures the
hot-channel-to-average spread without 37 of everything. Refine to per-pin once
that converges.

The other option is the SUBCHANNEL module, which Cardinal also compiles and which
is purpose-built for rod bundles with cross-flow between subchannels. It is the
more physical bundle model. Evaluate it against the multi-channel THM approach;
THM is the safer first move because the single-channel version is already
validated in the MVP, and SUBCHANNEL coupling into Cardinal is the less trodden
path.

## Validation

The coupled eigenvalue should land near the paper's 1.00086, the number the snap
fig12 case already reproduces standalone, so a drift after coupling points at the
temperature feedback, not the geometry. Fuel and fluid temperatures should sit
within about 3 K of NAA-SR-9903, the build-spec coupled target. The NaK rise
should stay at 62 K at 34 kWt. Per-pin powers should match the radial peaking the
tally produced. If the coupled k moves far from the standalone value, suspect the
temperature interpolation range or the cell-to-element mapping before anything
else.

## The 14 kWe tie-in

This model is the heat-transport half of the 14 kWe redesign. Its job is to turn
a reactor power and a core temperature into a NaK outlet temperature, which is
the hot-side input to the Stirling efficiency model in `../energy_conversion`.

Make core power and inlet temperature explicit knobs at the top of the input,
which they already are. SNAP's roughly 32 kWt core at SNAP temperatures caps near
7.6 kWe by Carnot, so 14 kWe is a bigger and hotter core, not a converter swap.
Push the model toward the 1050 K hot-side regime: raise core power, raise the
coolant temperature, and watch the fuel temperature, which is the constraint that
eventually bites. Feed the resulting NaK outlet into the Stirling model and read
the electric output.

The supplemental sodium loop from the project's next-steps list sits between a
hotter core and the converter. Model it as a second THM loop coupled to the first
through a heat-exchanger junction, then size its flow and temperature drop against
the conversion-efficiency gain. The MOOSE heat-conduction and THM energy balance
already in this folder are the right tools for that loop, which is why it lives
here and not in the Python converter models.

Carry one constraint through any 14 kWe design: the Stirling path trades SNAP's
no-moving-parts reliability for a dynamic machine, so the KRUSTY answer of many
small converters with redundancy belongs in the design even though it is not a
term in this thermal model.

## Order of work

Get Layer 1 converging first, because it shakes out the OpenMC-to-MOOSE transfer
and the THM conjugate coupling at a scale you can debug. Then build and inspect
the 37-pin mesh on its own. Then run the full-core conduction and a few
representative NaK channels with the frozen radial-plus-axial source. Then add the
live snap.py coupling. Only then turn the power and temperature knobs for the
14 kWe study. Each step is a working model, not a stepping stone you discard.

# SNAP-10A heat transport model (OpenMC heat into a MOOSE/THM NaK loop)

This folder models the reactor-to-converter thermal path: OpenMC supplies the
fission heat, MOOSE conducts it through the fuel pin, and the MOOSE Thermal
Hydraulics Module (THM) carries it away in the NaK-78 coolant. The output that
matters is the NaK outlet temperature, which is the hot-side input to the
separate Python thermoelectric and Stirling models in `../energy_conversion`.
The model stops at the NaK outlet on purpose. Cardinal does not model the
thermoelectrics, so the converter is a boundary condition, not part of this
solve.

The recurring SNAP rule holds here: OpenMC gives the heat shape, the assumed
core power (34 kWt) gives the magnitude. `extract_heat_source.py` is where those
two combine.

## How it is built: a minimum viable model you grow

The full target is the three-way coupling at full core: the 37-pin snap OpenMC
model feeding a 3-D core conduction solve feeding a THM NaK loop, all in a live
two-way Picard loop. That is the destination. To get there without debugging a
single giant untested deck, the model is built in layers that each run on their
own, on the same architecture so nothing is thrown away.

Layer 0, the MVP, in `mvp/`. One representative fuel pin, 2-D axisymmetric (RZ),
conduction coupled to one THM NaK subchannel. The heat source is frozen: either
an analytic cosine (so it runs with no other files) or the real axial shape that
`extract_heat_source.py` pulls from the snap model. This is the runnable first
result and the thing to validate. A pin is a cylinder, so RZ is exact and cheap.

Layer 1, two-way, in `two_way/`. The same conduction-and-THM coupling, now 3-D
and with OpenMC added as a live sub-app so the heat source updates with
temperature. Geometry is a single reflected pin (`snap_unit_pin.py`), small on
purpose, so the coupling mechanics are debugged before scale. The solid stays
the hub: OpenMC and THM are both its sub-apps. This is the `feedback/lattice`
Cardinal pattern with a THM channel attached.

Layer 2, full core. Swap the single-pin mesh for the 37-pin hex core and couple
to the real snap.py model. This is the production step. See
`ROADMAP_full_core.md`; it is documented, not built, because it needs iteration
on your machine.

The delta from Layer 0 to Layer 1 is small: the mesh goes from 2-D RZ to 3-D
(OpenMC mapping needs 3-D), OpenMC becomes a second sub-app, and the power comes
from a transfer instead of a function. Everything else, the THM channel, the
conjugate coupling, the materials, is identical.

## Architecture

```
            heat_source  ->            T_wall ->
  OpenMC  --------------->  SOLID  ----------------->  THM (NaK)
 (openmc.i)  <- temperature (solid_3d.i) <- T_fluid, htc   (thm.i)
                            the hub
```

The solid conduction app is the center. OpenMC hands it the kappa-fission heat
and reads back temperature. THM takes the clad wall temperature and returns the
NaK bulk temperature and heat-transfer coefficient through the
`CoupledHeatTransfers` action, which is the tested MOOSE way to couple a 1-D flow
channel to a conduction solid. In Layer 0 the OpenMC arm is replaced by a frozen
source, so the solid only talks to THM.

## Running it

Everything runs with the `cardinal-opt` you already built (it includes THM,
heat transfer, and the reactor module; confirmed in the Makefile). Activate the
moose conda env, not openmc-env, for Cardinal runs. The OpenMC model build in
`snap_unit_pin.py` and the extraction in `extract_heat_source.py` use the
standalone openmc-env.

Layer 0 (MVP), from `mvp/`:

```
cardinal-opt -i solid.i
```

`thm.i` launches automatically as the sub-app. Watch the console for `power_in`
(must be 918.9 W), `max_fuel_T`, and `wall_T_avg`. The NaK outlet is `T_fluid_out`
in the THM output. To use the real OpenMC axial shape instead of the cosine,
first run the extraction (below), then follow the comment in `mvp/solid.i` to
point the source at `axial_power.csv`.

The extraction, on the Mac in the snap directory:

```
conda activate openmc-env
cd ~/Documents/snap
python /path/to/heat_transport/extract_heat_source.py --run --nz 30
```

That writes `axial_power.csv` (per-pin volumetric heat versus axial position) and
prints the integral, which should land on 918.9 W per pin.

Layer 1 (two-way), from `two_way/`:

```
conda activate openmc-env && python snap_unit_pin.py   # writes the OpenMC XMLs
cardinal-opt -i make_mesh.i --mesh-only pin3d.e        # build + inspect the 3-D mesh
cardinal-opt -i solid_3d.i                             # the coupled run
```

Inspect `pin3d.e` in ParaView or Peacock before the coupled run. Mesh generation
is the one Layer 1 block whose generator boundary-naming can vary by MOOSE
version, so verify it in isolation first.

## Validation targets

These come from `verify_energy_balance.py`, an independent hand calculation from
the base-set inputs. Run it any time: `python verify_energy_balance.py`.

NaK temperature rise: 62 K, outlet near 817.7 K, at 34 kWt and 0.6199 kg/s. The
arXiv table lists 61.1 K; Q = m cp dT with their own numbers gives 62.3 K, and
the roughly 1 K gap is rounding inside their table. The 37-subchannel flow
reproduces the total core flow exactly, which is the check that the per-pin split
is consistent.

Peak fuel centerline: about 840 K, comfortably under 900 K. SNAP-10A ran cool,
and U-ZrH conducts well, so the film, clad, and coating drops are small and the
fuel-to-coolant difference is only a few tens of degrees. If the model returns a
peak fuel temperature far above 900 K, something is wrong with the source
normalization or the conductivities.

Source normalization: `power_in` integrates the volumetric source over the fuel
and must equal 918.9 W per pin. This is the first thing to check on any run.

## Decisions worth knowing

SI everywhere in MOOSE, with `scaling = 100` in the OpenMC problem to bridge to
OpenMC's centimeters. This avoids running the conduction and THM solves in CGS,
which is the usual Cardinal headache.

Temperature-and-HTC conjugate coupling, not a flux march. The solid sends its
wall temperature to THM and THM returns the fluid temperature and the
coefficient; the `CoupledHeatTransfers` action builds the convective boundary
condition and the transfers. The NaK rise then comes out as a result and
confirms energy conservation, rather than being imposed. The flux-based variant
that the NekRS tutorials use is the alternative if you ever swap THM for NekRS
CFD, which the project has decided you do not need.

NaK-78 as a constant-property liquid metal from the arXiv Table II values. Good
to within the table's own consistency at the design point. The upgrade is a
temperature-dependent liquid-metal property set, or the sodium and potassium
libraries that Cardinal compiles, once you want off-design behavior for the
14 kWe study.

## Caveats and open conflicts

I cannot run Cardinal, MOOSE, or your OpenMC here; my shell is a separate Linux
sandbox and your stack is native Apple Silicon. So every input file is grounded
in the current Cardinal and MOOSE documentation and verified test inputs, the
Python is syntax-checked, and the energy balance is checked numerically, but the
decks have not been executed. Expect to shake out a few version-specific names on
first run, most likely in the Layer 1 mesh generator. The MVP is the lowest-risk
piece because every block matches a tested example.

Power vintage. 34 kWt is used throughout to match the arXiv model and the shield
design point. The FS-3 endurance test ran at 39.5 to 40 kWt. If you switch power,
the NaK rise and fuel temperature scale with it, and `extract_heat_source.py` and
the validation targets need the same number.

Inlet temperature. The arXiv reactor model uses 755.37 K inlet, 816.48 K outlet.
NAA-SR-11955 lists the converter NaK inlet at 987 F (530.6 C, about 803.7 K),
which is the reactor outlet, about 13 K below the arXiv outlet. The reactor-side
model here uses the arXiv pair to stay consistent with the snap OpenMC model. The
converter side is the Python model's domain.

H/Zr ratio in the fuel is set to 1.6 in `snap_unit_pin.py`. The primary reports
do not state it (a base-set gap); 1.6 is the standard SNAP hydride value and is
flagged as an assumption.

Material conductivities. Updated June 16 2026 in `two_way/solid_3d.i` and sourced
in `k_of_T_sources.md`. Hastelloy N clad is now the ORNL/MSDR k(T) correlation
(9.77 - 3.2e-4 T + 1.46e-5 T^2), which reproduces the arXiv Table II clad value
of 18.852 at ~800 K and replaces the prior 23.6 (that was the same curve read at
700 C, far above the clad's real ~510-545 C). U-ZrH fuel (22.484) and Sm2O3
coating (1.729) match the arXiv Table II and stay constant on purpose: the
literature gives no defensible T-dependence for either in this band. The
fuel-conductivity magnitude carries an 18-to-22.484 spread (Simnad vs the paper),
a ~3 K sensitivity on peak fuel T documented in the sources file. The MVP
(`mvp/solid.i`) still carries the old 18/1.5/23.6 constants; update it to match
if you want the two layers strictly consistent.

## Files

```
verify_energy_balance.py   independent targets (NaK rise, fuel T, HTC, D_h)
k_of_T_sources.md          conductivity sourcing (fuel/coating/clad, why only clad is k(T))
extract_heat_source.py     pull the axial power shape from the snap model
mvp/solid.i                Layer 0 parent: 2-D RZ pin conduction + frozen source
mvp/thm.i                  Layer 0 NaK channel (THM)
two_way/snap_unit_pin.py   single reflected pin OpenMC model (coupling testbed)
two_way/make_mesh.i        3-D pin mesh generator (run with --mesh-only)
two_way/openmc.i           OpenMC neutronics sub-app
two_way/solid_3d.i         Layer 1 hub: 3-D conduction + OpenMC + THM
two_way/thm.i              Layer 1 NaK channel (axis = z)
ROADMAP_full_core.md       Layer 2: 37-pin core and the 14 kWe tie-in
```

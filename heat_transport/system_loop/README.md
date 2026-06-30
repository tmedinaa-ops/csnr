# SNAP-10A 14 kWe system loop (reactor heat all the way to space)

This is the deck the rest of `heat_transport/` stops short of. The `mvp/`,
`two_way/`, and `layer2_core/` models end at the NaK outlet on purpose, because
Cardinal does not model the converter. This folder carries the heat the rest of
the way: into the Stirling hot end, out the cold end as electricity plus waste
heat, and off the radiator to 4 K space, as one transient MOOSE/THM solve. It is
the system-loop counterpart of the analytic `energy_conversion/nak_system_chain.py`,
done as a spatially resolved, time-dependent thermal model instead of a steady
algebraic ladder.

## What MOOSE actually solves, and what it cannot

MOOSE/THM solves real physics for every leg of the path: heat conduction in the
core structure with a fission source, 1-D single-phase NaK energy and momentum
transport in each loop segment, conduction in the converter and radiator
structures, and radiative loss to space off the radiator panel.

It does not solve the Stirling thermodynamic cycle, and it should not pretend to.
A Stirling cycle is a closed periodic gas process, not a field equation. So the
engine is a heat-extraction component: the hot end is a heat sink that pulls
`Q_in` out of the primary NaK, the cold end is a heat source that dumps `Q_waste`
into the rejection NaK, and the split between electricity and waste is set by the
project's validated efficiency law

    eta = carnot(T_hot, T_cold) * rel(T_cold / T_hot)

from `energy_conversion/stirling_cycle_concept/stirling_converter.py`. The
`[ControlLogic]` block recomputes that split every timestep from the live NaK
temperatures, so the engine responds to the loop: hotter delivery gives more
electricity and less waste, which cools the radiator, all inside one transient.
This is the honest boundary of the tool, not a shortcut. You see heat move through
every pipe, the engine interfaces, and the radiator; the gas cycle stays external.

## Why two NaK circuits even though it is a "single loop"

"Single NaK loop" is the chosen architecture from the NaK-only branch: no
intermediate heat exchanger between the reactor and the converter. It does not
mean one stream. A Stirling needs a hot source and a cold sink at different
temperatures, so the model has two NaK circuits coupled only through the engine:

```
  PRIMARY (hot)     755 K --> [REACTOR +79 kW] --> 896 K --> [STIRLING HOT END -74 kW]
                       ^                                              |  (-4.9 kW parasitic)
                       |______________________________________________|  back to ~755 K

                                   STIRLING ENGINE
                          Q_in 74.1 kW = 14.6 kWe + 59.5 kW waste
                                          |
  REJECTION (cold)  475 K --> [COOLER +59.5 kW] --> 497 K --> [RADIATOR -59.5 kW to 4 K space]
                       ^                                              |
                       |______________________________________________|  back to ~475 K
```

You cannot make one stream be 896 K and 475 K at once. The primary runs hot
(755 to 896 K), the rejection loop runs cold (475 to 497 K), and the only thing
that crosses between them is the engine.

## The operating point and the validation targets

The numbers are the verified 14 kWe uprate (`energy_conversion/Path_to_14kWe_Verified.md`,
`nak_system_chain.py`, `rejection_loop.py`): a 79 kWt fuel-limited core, a Stirling
at a 475 K radiator. Run `python3 verify_loop.py` for the independent hand
calculation. The deck should converge to these:

| quantity | target | deck postprocessor |
|---|---|---|
| reactor NaK outlet (T_hot) | 895.7 K | `T_core_out` |
| heat to engine, Q_in | 74.1 kW | (header `Q_engine`) |
| overall efficiency | 19.6 % | `eta` |
| electrical output | 14.55 kWe | `electricity` |
| waste heat, Q_waste | 59.5 kW | `Q_waste` |
| heat radiated to space | 59.5 kW | `rad_to_space_integral` |
| radiator panel temperature | ~475 K | `T_cold` |
| energy balance residual | ~0 W | `energy_residual` |

`verify_loop.py` reproduces all of these at zero residual and cross-checks the
14.6 kWe / 19.7 % G1 reference, so the deck has a clean bar to clear.

## Running it

Plain THM is enough here (no OpenMC in this layer), and your `cardinal-opt`
includes THM, so either works. From the moose conda env, in this folder:

```
cardinal-opt -i system_loop.i
```

Watch the console: `T_core_out` should climb to ~896 K, `electricity` to
~14.6 kWe, `Q_waste` and `rad_to_space_integral` to ~59.5 kW, and
`energy_residual` to ~0. The full transient is in `system_loop.csv` and the
Exodus file for ParaView.

## How the MOOSE pieces map to the physics (all confirmed against current docs)

The approach was checked against the live MOOSE Thermal Hydraulics
documentation before building. The mapping:

- Reactor, engine hot end, engine cold end: each is a `TotalPower` feeding a
  `HeatSourceFromTotalPower` into a `HeatStructureCylindrical`, coupled to its
  flow channel by `HeatTransferFromHeatStructure1Phase` (convective
  `q = Hw*(T_surface - T_fluid)`). A positive `TotalPower` is a source (reactor,
  cooler); a negative `TotalPower` is a sink (the engine hot end, the parasitic
  loss). `TotalPower.power` is documented as controllable, which is what lets the
  cold-end source track the engine.
- The Stirling efficiency law is three `ParsedPostprocessor`s (`eta`,
  `electricity`, `Q_waste`) evaluated on the live `T_hot` and `T_cold`. The
  `[ControlLogic]` then forwards `Q_waste` into the cold-end `TotalPower.power`
  with `CopyPostprocessorValueControl` plus `SetComponentRealValueControl`. The
  coupling carries a one-step lag, which keeps it stable (no added stiffness).
- Radiator to space: `HSBoundaryRadiation` on the panel's outer surface applies
  `q = scale * sigma * emissivity * view_factor * (T^4 - T_ambient^4)` with
  `T_ambient = 4 K`. It auto-adds the `rad_to_space_integral` postprocessor for
  the radiated heat rate.
- Loop plumbing: `FlowChannel1Phase` segments joined by `JunctionOneToOne1Phase`
  (`connections = 'a:out b:in'`), with `InletMassFlowRateTemperature1Phase` and
  `Outlet1Phase` at the NaK boundaries. NaK is `SimpleFluidProperties` at the
  arXiv Table II design values, the same set the validated `mvp/thm.i` uses.

## Decisions and caveats worth knowing

The radiator's 26 m2 of flat-panel area is carried by the `scale` factor on
`HSBoundaryRadiation`, not by literal geometry, because a 1-D pipe wrap cannot
hold 26 m2 of surface and a thick cylinder would add false conduction resistance
and mass. The wall stays a realistic thin shell and `scale = A_panel / A_geom`
makes it radiate the true area, so the panel temperature is a real solved value
that lands near 475 K. A faithful flat-plate radiator with its own mesh, coupled
to the rejection channel, is the clean upgrade if you want the panel temperature
distribution rather than a lumped value.

The 6 percent that does not reach the converter (`1 - heat_frac`) is modeled as a
small fixed parasitic sink on the hot leg, so the radiator rejects exactly
59.5 kW and not 64.4 kW. Dropping it and folding the loss into efficiency would
mis-route that heat through the engine cold side. It is worth the extra component.

NaK properties are held constant at the 783 K design point. The loop spans 475 to
896 K, so this carries a known ~10 percent density error at the extremes. The swap
is MOOSE's built-in `NaKFluidProperties` (Foust 1972 eutectic), commented in the
`[FluidProperties]` block, and is the right move once you trust the absolute
temperatures off-design. Constant properties are kept here to match the validated
reactor-side deck and to keep the first run robust.

I could not execute MOOSE in this environment (separate sandbox, your stack is
native). Every block is grounded in the current THM docs and the project's own
validated `thm.i`, and the energy balance is checked numerically in
`verify_loop.py`, but the deck itself has not been run. The highest-risk spots on
first run, in rough order: the `regions` parameter name on `HeatSourceFromTotalPower`
(some versions name the region list differently) and the auto-added postprocessor
name `rad_to_space_integral`. If either trips, the fix is a one-line rename, and
the rest of the deck is independent of it.

Resolved on the first PC run, two issues:
1. The control logic originally used a `CopyPostprocessorValueControl` to forward
   `Q_waste` into control data, which errored with "Q_waste already declared"
   because THM already exposes every postprocessor as control data under its own
   name. Fix: drop that block, have `SetComponentRealValueControl` read the
   `Q_waste` postprocessor directly (`value = Q_waste`).
2. The `T_cold` postprocessor (radiator panel temperature, on `rad_hs:outer`)
   read `variable = T` and returned 0 K, because in THM the heat-structure solid
   temperature is `T_solid`, not `T` (which is the flow-channel fluid). With
   T_cold = 0 the efficiency law collapsed to its 50% ceiling and reported 37 kWe.
   Fix: `variable = T_solid`. Flow-channel postprocessors stay `T`; only the
   heat-structure-surface reads use `T_solid`.
3. After (2) the panel read 446 K (should be ~475) and electricity was 16.3 kWe
   (should be ~14.6). Cause: the radiator wall was 3 mm. Because `scale` radiates
   the full 26 m2 but conduction crosses the tube's real small wall area, a 3 mm
   wall throws a spurious `Q*t/(k*A)` drop of ~40 K from the NaK to the radiating
   surface, so the panel sat too cold, under-radiated, and the cold side looked
   colder than it is (which inflated efficiency). Fix: `rad_wall = 0.0005` and
   `sp_rad k = 50`, so the radiating surface tracks the coolant the way a finned
   radiator does. This is the seam of the area-folding lumped radiator; the clean
   alternative is the flat-plate radiator (Layer C) with matched convection and
   radiation area.

## The recirculating version: system_loop_closed.i

`system_loop.i` prescribes the NaK boundary temperatures (primary inlet 755 K,
rejection return 475 K). That is well-posed and is why it converges cleanly, and
the cold side is still closed to space. `system_loop_closed.i` goes one step
further: the NaK physically recirculates, each loop's return temperature feeds
back into its own inlet, so the NaK that leaves the reactor comes back to it.

Two things change from the open deck, and both come straight from the MOOSE
workshop notes (the "singular system" point: a domain with only sources and sinks
has its temperature defined only up to a constant, so once the fixed inlets are
gone the level must be re-anchored physically).

- Recirculation. Flow is the EM pump's known rate (imposed via
  `InletMassFlowRateTemperature1Phase`, whose `T` is controllable). Two extra
  `SetComponentRealValueControl`s feed `T_heater_out` into the reactor inlet and
  `T_rad_out` into the cooler inlet each step. This is the robust "thermal
  recirculation" choice. A full momentum ring (`Pump1Phase` plus ring junctions,
  with the loop pressure solved) is the higher-fidelity alternative; it is more
  realistic but closed compressible liquid-metal loops are finicky to converge.
- Hot-loop anchor. The Stirling hot end is no longer a fixed power draw. It is a
  temperature-following draw `Q_draw = UA*(T_hot - T_engine_set)`, set by control
  each step. `UA` and `T_engine_set` are chosen (`Q_engine/pinch_hot` and
  `T_hot_design - pinch_hot`) so the loop settles at the validated point: the NaK
  runs exactly hot enough to push 74.1 kW into the engine, which pins the reactor
  outlet at 895.6 K. The radiator still anchors the cold loop through its T^4 law.
  A floor `max(0, ...)` keeps the engine from acting as a heat source during the
  cold startup.

It should converge to the same numbers as the open deck (reactor outlet 895.6 K,
eta 19.6%, 14.6 kWe, 59.5 kW rejected), because the anchor is tuned to that point.
The differences to watch on the run: `T_core_in` is now a solved, fed-back value
that should settle near 755 K (not an imposed boundary), `Q_engine_draw` should
settle at ~74.1 kW, and `energy_residual` (= reactor - draw - parasitic) is now a
genuine convergence check rather than the identity it was in the open deck, so it
only reaches ~0 once the hot loop has anchored. Run `system_loop.i` first as the
reference, then `system_loop_closed.i`. It may take more steps to settle because
recirculation adds a slower coupled mode (hence `num_steps = 800`).

If convergence is marginal, the workshop notes point at two cheap knobs:
`automatic_scaling = true` for the coupled system, and switching `line_search`
from `basic` to `bt` (backtracking) for the stiffer coupling.

## Files

```
system_loop.i         open deck: prescribed NaK boundaries, validated to targets
system_loop_closed.i  recirculating deck: NaK loops back, temperature-anchored
verify_loop.py        independent steady-state hand check; prints the targets (both decks)
README.md             this file
```

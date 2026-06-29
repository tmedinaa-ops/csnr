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

Resolved on the first PC run: the control logic originally used a
`CopyPostprocessorValueControl` to forward `Q_waste` into control data, which
errored with "Q_waste already declared" because THM already exposes every
postprocessor as control data under its own name. The fix was to drop that block
and have `SetComponentRealValueControl` read the `Q_waste` postprocessor directly
(`value = Q_waste`).

## Closing the NaK recirculation (optional refinement)

This deck prescribes the NaK boundary temperatures: the primary cold-leg enters
at 755 K (the reactor inlet) and the rejection loop returns at 475 K (off the
radiator). That is a well-posed way to pose the heat path, and it is why the deck
converges cleanly to the targets. It is also where the chosen scope lands: the
cold side is closed to space, which was the point of carrying the model past the
NaK outlet.

Recirculating the NaK itself (returning each loop's outlet back to its own inlet,
driven by a pump) is a real next step, with two requirements. First, momentum
closure: replace the inlet/outlet pairs with a `Pump1Phase` and ring the segments
with junctions. Second, a temperature pin: with the reactor power fixed and the
engine removal fixed, the primary loop's absolute temperature level floats (any
uniform offset is also a steady state). The radiator already pins the cold loop
through its `T^4` law. To pin the hot loop, model the engine hot end as a
conductance `Q = UA*(T_NaK - T_gas_hot)` against a fixed engine gas temperature
instead of a fixed power, so the NaK level is set by how hot it must run to push
74 kW into the engine. That is the physically faithful closed loop, and it is the
natural follow-up once this open-boundary version is running and trusted.

## Files

```
system_loop.i    the transient THM deck: reactor -> NaK -> Stirling -> radiator -> space
verify_loop.py   independent steady-state hand check; prints the deck's targets
README.md        this file
```

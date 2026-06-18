# Layer 2 fixes (June 2026): make the run fast, the numbers conserve, and the radial self-diagnosing

Written after the first 37-pin run came back with three problems: a ~3-hour runtime, a
fluid energy balance that did not close (channels summed to 44 kW against 34 kW supplied),
and a near-flat radial power (all 37 outlets within 0.35 K). The fixes below are grounded
in the Cardinal and MOOSE-THM docs/tutorials, not guesses. One earlier guess (raise
cell_level) was wrong and is explicitly reversed here.

## What the first run actually showed

- power_in held at 34000 W (imposed by the OpenMC normalization), surface_heat_out
  ~34265 W, max_fuel_T flat at ~856 K. Solid side conserved to 0.78% (flux-integral
  discretization, not stored energy: fuel m*cp x dT/dt was ~0.5 W).
- OpenMC ran live (solid_core_out_openmc0.e exists; combined k ~1.0006, matching the
  standalone fig12_test 1.00086). The coupling milestone is real.
- The 37 THM channels each reported ~1198 W via mdot*cp*(T_out - 755.37), summing to
  44.3 kW. The channel's OWN reported in/out gave 26.6 kW. The solid delivered 34.3 kW.
  Three disagreeing numbers => the THM temperature readout, not the physics, is wrong.

## Root causes (researched, with sources)

1. Slow. The solid carried a real rho*cp `HeatConductionTimeDerivative`, so the march was
   a physical thermal transient paced by the ~7000 s time constant -> 350 steps. The
   Cardinal OpenMC+solid+THM tutorial (gas_assembly) does NOT do this: its solid is steady
   conduction (no time kernel) and it converges in ~6-10 fixed-point iterations with
   constant 0.5 relaxation. Refs: https://cardinal.cels.anl.gov/tutorials/openmc_fluid.html
   ; https://github.com/neams-th-coe/cardinal/blob/devel/tutorials/gas_assembly/solid.i

2. Non-conserving / wrong power readout. `SideAverageValue` of T on a THM flow-channel
   boundary returns the adjacent CELL-CENTROID value (THM is cell-centered FV), so on a hot
   short channel pipe:in reads tens of K above the real inlet; differencing temperatures to
   get power is the wrong tool. The right tool is `ADHeatRateConvection1Phase`, which
   integrates the actual wall flux Hw*P_hf*(T_wall - T). Refs: MOOSE discussion #28926
   (this exact coupled-MOOSE-THM external-app case), #21966 (use heat-rate / enthalpy, not
   rho*cp*dT), THM CHT tutorial step 2; ADHeatRateConvection1Phase source.

3. Flat radial: most likely NOT the neutronics. cell_level = 1 is correct for our nesting
   (root -> cell_core(fill=HexLattice) -> 37 distinct pin universes -> pin cells); the
   Cardinal lattice regression test uses cell_level=1 for exactly this pattern. So the flat
   OUTLETS are more likely the THM partition smearing wall heat across channels (the same
   defect as #2), not flat power. `check_equal_mapped_tally_volumes` cannot catch a collapse
   to one cell (one bin = trivially equal volumes), so it gave false confidence. Refs:
   https://cardinal.cels.anl.gov/source/tallies/CellTally.html ; .../tutorials/pincell1.html

## What changed in the decks

openmc_core.i
- relaxation robbins_monro -> constant, relaxation_factor = 0.5 (gas_assembly setting).
- Added cell_id (CellIDAux) and cell_instance (CellInstanceAux) AuxVariables. These are the
  radial diagnostic: color core37 by cell_id in ParaView -> 37 distinct values = pins
  resolved.
- cell_level kept at 1; comment updated to record it is verified correct (do not raise to 2).

solid_core.i
- Removed the `HeatConductionTimeDerivative` kernel (solid is now steady conduction each
  Picard step). density/specific_heat in [Materials] are now unused but harmless.
- num_steps 350 -> 25 (Picard iteration budget, not physical time).
- Kept power_in / surface_heat_out / power_imbalance / max_fuel_T as the trustworthy
  solid-side conservation check.

thm.i
- Replaced heat_removed (mdot*cp*(T_out - 755.37)) with `heat_added`
  (ADHeatRateConvection1Phase, block = pipe, P_hf), the conserving wall-flux power.
- Renamed the pipe:in side average to T_fluid_in_diag and documented it is NOT the inlet
  (the inlet is the BC, 755.37 K).
- Added steady_state_detection to stop each THM call once its channel is steady.

## How to run (PC, WSL, moose env, OPENMC_CROSS_SECTIONS set)

Prereq: build snap.py model.xml for fig12_test with FLAG_FINE_DISCRETIZATION=True and
FLAG_DISTRIB_COOLANT=True (confirm "Lattice mapping check OK (37/37)"), and place it where
Cardinal runs. Then from layer2_core/:

    cardinal-opt -i solid_core.i

Expect roughly 25 fixed-point iterations and ~10-20 min, not 3 hours.

## The ONE run is self-diagnosing. Check, in order:

1. Conservation: sum heat_added across the 37 solid_core_out_thmNN.csv files.
   - ~34 kW (= power_in) -> fixed. The 44 kW artifact is gone.
   - still far off -> the wall-heat partition is broken; apply the #28926 fixes (confirm the
     CoupledHeatTransfers action's num_layers == n_elems == 30, no ProjectionAux in the
     path, var_type = elemental on [ht] -- already set).
2. Radial power, two independent reads that must agree:
   - openmc side: color solid_core_out_openmc0.e by cell_id (expect 37 distinct values) and
     by heat_source (expect a center-to-edge gradient, ~1.2-1.3 peak/avg).
   - fluid side: the spread of heat_added across the 37 channels.
   - Both peaked -> radial is real, Layer 2 is delivering the hot-channel result.
   - cell_id distinct but heat_added flat -> power is fine, the THM partition is smearing
     (fix the coupling, not the neutronics).
   - cell_id uniform -> the source is collapsing in OpenMC (revisit model.xml build, not
     cell_level).
3. Convergence: power_imbalance and max_fuel_T flat over the last several iterations; coupled
   k near 1.0009.

Only after this is clean: drive the model at the operating power you actually want
(openmc_core.i `power =`), 34 vs 40 vs ~46 kWt FS-3 etc. NaK rise scales as P / 545 W/K.

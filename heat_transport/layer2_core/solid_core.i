# =============================================================================
# Layer 2: 37-pin core conduction + NaK -- SOLID sub-app  (restructured June 2026)
# =============================================================================
# RESTRUCTURED: this used to be the main app with OpenMC as a sub-app. It is now a
# SUB-APP of openmc.i (OpenMC is the main app). Run the coupled model with
#   cardinal-opt -i openmc.i        (NOT this file directly)
#
# This file owns the solid conduction and the 37-channel NaK conjugate coupling
# (CoupledHeatTransfers -> thm.i). The OpenMC parent fills the fuel 'power' AuxVar by
# transfer and reads the solid T back. Each time OpenMC calls this app, it converges
# the solid<->THM CONJUGATE loop (the fixed_point loop in [Executioner]) against the
# frozen heat source -- this is the cheap inner loop the restructure isolates so
# OpenMC only solves once per outer step.
#
#   openmc.i (main) --power--> THIS (solid) --T_wall--> thm.i (37 channels)
#        <-- temperature --            <-- T_fluid / htc --
#
# Prereqs: core37.e (make_core_mesh.i); snap.py model.xml (see openmc.i header). The
# solid + THM physics are the validated Layer 1 pattern; only the hierarchy moved.
# =============================================================================

L    = 0.310515
n_ax = 30
Hw   = 5.01e4

[Mesh]
  [core]
    type = FileMeshGenerator
    file = core37.e
  []
[]

[Variables]
  [T]
    initial_condition = 783.15
  []
[]

[AuxVariables]
  [power]                 # filled by the transfer from OpenMC (heat_source)
    family = MONOMIAL
    order = CONSTANT
    block = fuel
  []
  [T_fluid]               # filled by CoupledHeatTransfers from THM
    family = MONOMIAL
    order = CONSTANT
    initial_condition = 755.37
  []
  [htc]
    family = MONOMIAL
    order = CONSTANT
    initial_condition = ${Hw}
  []
[]

[Kernels]
  [conduction]
    type = HeatConduction
    variable = T
  []
  # NO time-derivative kernel (removed June 2026). The Cardinal OpenMC+solid+THM
  # tutorial (gas_assembly) solves the solid as STEADY conduction each Picard step
  # and converges in ~6-10 iterations. Carrying a real rho*cp HeatConductionTime-
  # Derivative instead turned this into a physical thermal transient paced by the
  # ~7000 s thermal time constant -> the 350-step, ~3-hour march. At steady the time
  # term is identically zero, so dropping it does NOT change the converged answer,
  # only the (now irrelevant) approach path. density/specific_heat in [Materials]
  # are now unused (harmless).
  [source]
    type = CoupledForce
    variable = T
    v = power
    block = fuel
  []
[]

# ---- NaK conjugate coupling: ALL 37 channels, energy-exact ------------------
# One THM channel per pin at the 37 pin centers (pin_positions.txt), so each pin's
# clad surface couples to its OWN co-located channel carrying one pin's flow. Energy
# -exact: each pin's power goes into its pin's NaK and makes the right ~62 K rise,
# and 37 channels reproduce the full 0.6199 kg/s core flow.
#
# THIS is what was wrong at 3 channels: per the MOOSE CoupledHeatTransferAction docs,
# the action builds a NearestPointLayeredSideAverage that partitions 'outer' by the
# nearest sub-app position, but it only knows those positions if you pass 'positions'
# to the ACTION, not just the MultiApp. Without it, the whole 37-pin surface collapsed
# onto a single channel -> the ~33 kW that "vanished" from the energy balance.
# Both the action and the MultiApp now read the SAME pin_positions.txt.
#
# Z: the mesh is centered on z (+-L/2) to match snap.py, but thm.i's flow channel
# runs 0..L in its own frame, so pin_positions.txt offsets each channel to z=-L/2
# (-0.1552575), seating it on the centered pin. 'position' below stays '0 0 0' (the
# per-channel axial base, copied from thm.i's FlowChannel1Phase, per the docs).
[CoupledHeatTransfers]
  [interface]
    boundary = 'outer'
    T = T
    T_fluid = 'T_fluid'
    T_wall = T_wall
    htc = 'htc'
    multi_app = thm
    T_fluid_user_objects = 'T_uo'
    htc_user_objects = 'Hw_uo'
    position = '0 0 0'
    orientation = '0 0 1'
    length = ${L}
    n_elems = ${n_ax}
    positions_file = 'pin_positions.txt'   # <-- 37 pin centers; the missing piece
    skip_coordinate_collapsing = true
  []
[]

[MultiApps]
  # OpenMC is no longer a sub-app here -- it is the MAIN app (openmc.i) and THIS file
  # is its sub-app. The fuel 'power' AuxVar is filled by a transfer from the OpenMC
  # parent; the solid T is read back up there. Only THM remains a sub-app of the
  # solid, via the CoupledHeatTransfers action above (the proven 37-channel coupling).
  [thm]
    type = TransientMultiApp
    input_files = 'thm.i'
    execute_on = timestep_end
    sub_cycling = true
    # all 37 channels, one per pin, at the pin centers shifted to the centered-mesh
    # z (-L/2). Same file the CoupledHeatTransfers action reads, so the sub-app
    # placement and the surface partition use identical points. 37 tiny 1-D apps.
    positions_file = 'pin_positions.txt'
  []
[]

# The OpenMC <-> solid power/temperature transfers now live in the parent openmc.i.
# (THIS app's only coupling is the CoupledHeatTransfers -> THM, above.)

# Same conductivities as Layer 1 (k_of_T_sources.md): fuel/coating constant,
# Hastelloy N clad k(T). Copied verbatim so the two layers stay consistent.
[Materials]
  [fuel_mat]
    type = GenericConstantMaterial
    block = fuel
    prop_names  = 'thermal_conductivity density specific_heat'
    prop_values = '22.484 6000.0 300.0'
  []
  [coating_mat]
    type = GenericConstantMaterial
    block = coating
    prop_names  = 'thermal_conductivity density specific_heat'
    prop_values = '1.729 7400.0 400.0'
  []
  [clad_k]
    type = PiecewiseLinearInterpolationMaterial
    block = clad
    property = thermal_conductivity
    variable = T
    extrapolation = true
    x = '300   400   500   600   700   800   900   1000  1100'
    y = '10.99 11.98 13.26 14.83 16.70 18.86 21.31 24.05 27.08'
  []
  [clad_rhocp]
    type = GenericConstantMaterial
    block = clad
    prop_names  = 'density specific_heat'
    prop_values = '8860.0 578.0'
  []
[]

[Preconditioning]
  [smp]
    type = SMP
    full = true
  []
[]

[Executioner]
  # CONJUGATE inner loop. OpenMC (the parent) calls this app once per outer step as a
  # FullSolveMultiApp; here we converge the solid<->THM coupling against the frozen
  # heat source. The fixed_point loop IS the conjugate iteration: each pass solves the
  # solid (steady conduction, no time derivative) and re-solves the 37 THM channels
  # (sub_cycling), exchanging wall/fluid temperature and HTC, until power_imbalance
  # closes. No OpenMC re-solve happens in here -- that is the whole point.
  #
  # num_steps = 1: one solid time step per OpenMC call; the work is the fixed_point
  # loop, not stepping. dt only drives THM sub_cycling. The conjugate is stiff (high
  # Hw), so give it a generous iteration budget; it stops early on the tol. If it
  # oscillates or won't close, relax the interface temperature:
  #   relaxation_factor = 0.7 ; transformed_variables = 'T_fluid'
  type = Transient
  scheme = bdf2
  start_time = 0
  dt = 100.0
  num_steps = 1
  fixed_point_max_its = 50
  fixed_point_rel_tol = 1e-4
  fixed_point_abs_tol = 1e-2
  accept_on_max_fixed_point_iteration = true
  solve_type = NEWTON
  petsc_options_iname = '-pc_type'
  petsc_options_value = ' lu'
  nl_rel_tol = 1e-7
  nl_abs_tol = 1e-6
  l_max_its = 100
[]

[Postprocessors]
  [power_in]
    type = ElementIntegralVariablePostprocessor
    variable = power
    block = fuel
    execute_on = 'transfer initial timestep_end'
    # FULL CORE target: 34000 W across all 37 pins (not 918.9). First check on any run.
  []
  [max_fuel_T]
    type = ElementExtremeValue
    variable = T
    block = fuel
    value_type = max
  []
  # CORE-LEVEL energy-closure convergence check. Layer 1's per-channel imbalance
  # trick does NOT carry over: each channel's power differs by radial peaking, so
  # there is no single per-channel reference like 918.92. Instead measure the total
  # heat CONDUCTED out through every pin's clad surface and compare to power_in. At
  # steady they are equal; the gap is energy still being stored. Computed entirely
  # in the solid, so no cross-channel aggregation, and it works for 3 or 37 channels.
  # (VERIFY the SideDiffusiveFluxIntegral signature on your MOOSE; 'diffusivity' takes
  # the material-property name. If it wants a functor form, adjust per the docs.)
  [surface_heat_out]
    type = SideDiffusiveFluxIntegral
    variable = T
    boundary = 'outer'
    diffusivity = thermal_conductivity
    execute_on = 'initial timestep_end'
  []
  [power_imbalance]      # -> 0 at steady; stop when |.| < ~340 W (1% of 34000)
    type = ParsedPostprocessor
    expression = 'power_in - surface_heat_out'
    pp_names = 'power_in surface_heat_out'
    execute_on = 'initial timestep_end'
  []
[]

[Outputs]
  exodus = true
  [csv]
    type = CSV
    file_base = solid_core
  []
  [console]
    type = Console
    show = 'power_in surface_heat_out power_imbalance max_fuel_T'
  []
[]

# TODO on the machine, in order (mirrors ROADMAP_full_core.md "Order of work"):
#  1. --mesh-only inspect core37.e.
#  2. Run THIS one-way, frozen source (openmc MultiApp + OpenMC transfers off,
#     'power' from extract_heat_source.py --radial). Confirm power_in = 34000 W,
#     NaK rise ~62 K on the hot channel, peak fuel < 900 K.
#  3. Turn the live OpenMC coupling on. Confirm coupled k near 1.00086 and
#     power_in still 34000 W.
#  4. Refine THM from 3 channels to 37; refine the cross-section to '16 2 2'.
#  5. THEN turn the 14 kWe knobs (core power, inlet T) per ROADMAP_full_core.md.

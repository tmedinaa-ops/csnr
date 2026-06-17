# =============================================================================
# Layer 2: full 37-pin core conduction  --  HUB app  (UNTESTED DRAFT)
# =============================================================================
# The Layer 1 hub (solid_3d.i) grown from one pin to the 37-pin core. Same star:
# the solid is the center, OpenMC (openmc_core.i) and THM (thm.i) are sub-apps.
# OpenMC hands the kappa-fission heat in and reads temperature back; THM exchanges
# wall/fluid temperature and HTC. The output that matters is the hot-channel NaK
# outlet, which feeds ../energy_conversion.
#
#   OpenMC (openmc_core.i) <-- heat/temperature --> THIS <-- T_wall/T_fluid/htc -->
#   THM bundle (thm.i at N positions)
#
# Prereqs: core37.e built (make_core_mesh.i), and snap.py's model.xml present for
# OpenMC (see openmc_core.i header). Run:
#   cardinal-opt -i solid_core.i
#
# BUILD ORDER (per ROADMAP_full_core.md, do not skip): get core37.e inspected,
# then run THIS one-way with a FROZEN source first (comment out the openmc MultiApp
# and the two OpenMC transfers, drive 'power' from extract_heat_source.py's radial+
# axial CSV), confirm the NaK bundle and conduction behave, THEN switch the live
# OpenMC coupling back on. Debugging the bundle and the neutronics at the same time
# is the thing this layering exists to avoid.
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
  [time]
    type = HeatConductionTimeDerivative
    variable = T
  []
  [source]
    type = CoupledForce
    variable = T
    v = power
    block = fuel
  []
[]

# ---- NaK conjugate coupling, multi-channel ----------------------------------
# Representative-channel start (ROADMAP): 3 channels by radial ring, center / mid /
# edge, which captures the hot-to-average spread without 37 of everything. The THM
# MultiApp below launches thm.i at these 3 positions; this action maps each clad
# surface to its nearest channel by position. Refine to all 37 positions once the
# 3-channel version converges.
#
# !! VERIFY: position-based mapping of ONE 'outer' sideset to multiple channels is
# the least-tested mechanic here. If the action will not split one sideset across
# channels, the fallback is 3 separate sidesets (outer_c/outer_m/outer_e from
# make_core_mesh.i TODO #2) and 3 CoupledHeatTransfers blocks, each the validated
# single-channel Layer 1 coupling. That fallback is lower risk; start there if this
# fights you.
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
    skip_coordinate_collapsing = true
  []
[]

[MultiApps]
  [openmc]
    type = TransientMultiApp
    input_files = 'openmc_core.i'
    execute_on = timestep_end
  []
  [thm]
    type = TransientMultiApp
    input_files = 'thm.i'
    execute_on = timestep_end
    sub_cycling = true
    # 3 representative channels: center pin 1, a ring-2 pin (11), a ring-3 pin (24)
    # positions in meters (snap.py fuel_positions/100). Grow to all 37 later.
    positions = '0 0 0
                 0 0.0640080 0
                 0 0.0960120 0'
  []
[]

[Transfers]
  [heat_from_openmc]
    type = MultiAppGeneralFieldShapeEvaluationTransfer
    from_multi_app = openmc
    source_variable = heat_source
    variable = power
    from_postprocessors_to_be_preserved = heat_source
    to_postprocessors_to_be_preserved = power_in
  []
  [temp_to_openmc]
    type = MultiAppGeneralFieldShapeEvaluationTransfer
    to_multi_app = openmc
    source_variable = T
    variable = temp
  []
[]

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
  # Pseudo-transient march to steady, single coupled exchange per step, same as the
  # final Layer 1 setup. LESSON FROM LAYER 1: the approach is paced by the loose
  # one-exchange-per-step OpenMC<->solid<->THM coupling (~1.5% error reduction per
  # step), NOT a physical thermal time constant, so it takes MANY steps. Layer 1's
  # single pin needed ~250-290 steps to reach the 1%-imbalance mark at dt=100; the
  # 37-pin core is unlikely to be faster, so num_steps starts at 350 and you STOP
  # when power_imbalance (below) drops under ~1% of 34000 = ~340 W. NO
  # steady_state_detection (MC noise trips a norm-based detector). Whether cutting
  # solid cp accelerates this is the open question Layer 1's cp_accel run is testing;
  # if it does, cut cp here too and num_steps drops hard.
  type = Transient
  scheme = bdf2
  start_time = 0
  dt = 100.0
  num_steps = 350
  fixed_point_max_its = 1
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

# =============================================================================
# SNAP-10A fuel pin conduction  --  HUB app  (cp-ACCELERATED steady cross-check)
# =============================================================================
# IDENTICAL physics to ../layer1_transfer/solid_3d.i EXCEPT the solid heat
# capacity is cut 4x to accelerate the march to steady, and dt/num_steps are
# retuned to the shortened time constant. This is the fast steady config and the
# cross-check that the heat-capacity acceleration is steady-EXACT: at dT/dt = 0
# the time term vanishes, so rho*cp cannot affect the converged temperatures, and
# the energy balance that sets the NaK outlet (P / (mdot*cp_NaK)) has no solid cp
# in it. PASS CRITERION: this run must land on the SAME steady values the long
# layer1_transfer march reaches, NaK outlet 817.7 K and max_fuel_T ~826-832 K, in
# far fewer OpenMC solves. If it does, the cp trick is validated and becomes the
# default fast iterate config; only the per-step transient path differs, which we
# never report. Runs self-contained in this folder (own XMLs/mesh/outputs), so it
# can run concurrently with layer1_transfer on spare cores.
#
#   OpenMC (openmc.i)  <-- heat_source / temperature -->  THIS  <-- T_wall /
#   T_fluid / htc -->  THM (thm.i)
#
# Prereqs: snap_unit_pin.py exported the OpenMC XMLs, and make_mesh.i produced
# pin3d.e. Run:
#   bash run_layer1.sh          # (or: cardinal-opt -i solid_3d.i)
# =============================================================================

L    = 0.310515
n_ax = 30
Hw   = 5.01e4

[Mesh]
  [pin]
    type = FileMeshGenerator
    file = pin3d.e
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

# ---- NaK conjugate coupling (same as the MVP) -------------------------------
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
    orientation = '0 0 1'        # pin axis is z in the 3-D mesh
    length = ${L}
    n_elems = ${n_ax}
    skip_coordinate_collapsing = true
  []
[]

[MultiApps]
  [openmc]
    type = TransientMultiApp
    input_files = 'openmc.i'
    execute_on = timestep_end
  []
  [thm]
    type = TransientMultiApp
    input_files = 'thm.i'
    execute_on = timestep_end
    sub_cycling = true
  []
[]

[Transfers]
  # heat source in (conserve total power across the projection)
  [heat_from_openmc]
    type = MultiAppGeneralFieldShapeEvaluationTransfer
    from_multi_app = openmc
    source_variable = heat_source
    variable = power
    from_postprocessors_to_be_preserved = heat_source
    to_postprocessors_to_be_preserved = power_in
  []
  # temperature back to OpenMC ('temp' is auto-created by OpenMCCellAverageProblem)
  [temp_to_openmc]
    type = MultiAppGeneralFieldShapeEvaluationTransfer
    to_multi_app = openmc
    source_variable = T
    variable = temp
  []
[]

# Thermal conductivities: see k_of_T_sources.md for the full sourcing.
# Only thermal_conductivity sets the steady temperature; density and
# specific_heat only set the march speed, so they are the acceleration knob here.
# CP-ACCELERATED: specific_heat is cut 4x vs layer1_transfer (fuel 300->75,
# coating 400->100, clad 578->144.5) to shrink the ~1200-1500 s time constant to
# ~300-375 s, so the march reaches steady in ~50 steps instead of ~360. This does
# NOT change the converged temperatures (cp drops out at dT/dt=0); it only coarsens
# the transient path we never report. thermal_conductivity is UNTOUCHED (it is what
# sets steady). U-ZrH and Sm2O3 k stay constant (no defensible T-dependence per the
# literature); Hastelloy N has a real, sourced k(T), so it is tabulated.
[Materials]
  [fuel_mat]      # U-ZrH (SCA-4). k = 22.484 = reference model (arXiv 2505.04024
                  # Table II). Simnad GA-A16029 gives ~18 W/m-K, ~flat in T; that
                  # is a ~+3 K sensitivity on peak fuel T, documented, one-number
                  # switch if you want literature-primary instead of paper-match.
    type = GenericConstantMaterial
    block = fuel
    prop_names  = 'thermal_conductivity density specific_heat'
    prop_values = '22.484 6000.0 75.0'   # cp 300->75 (cp/4 accel; steady-exact)
  []
  [coating_mat]   # Sm2O3 coating. k = 1.729 = reference model (arXiv Table II).
                  # Low confidence: no usable T-dependent data for the sesquioxide.
    type = GenericConstantMaterial
    block = coating
    prop_names  = 'thermal_conductivity density specific_heat'
    prop_values = '1.729 7400.0 100.0'   # cp 400->100 (cp/4 accel; steady-exact)
  []
  [clad_k]        # Hastelloy N k(T), ORNL/MSDR correlation
                  # k = 9.77 - 3.2e-4 T + 1.46e-5 T^2  (W/m-K, T in K).
                  # Reproduces the reference model's 18.852 at ~800 K and the
                  # Haynes datasheet ~11 at RT. The old constant 23.6 was this
                  # same curve read at 700 C (973 K), far above the ~510-545 C the
                  # clad actually runs, so it overstated clad k by ~25%.
    type = PiecewiseLinearInterpolationMaterial
    block = clad
    property = thermal_conductivity
    variable = T
    extrapolation = true
    x = '300   400   500   600   700   800   900   1000  1100'
    y = '10.99 11.98 13.26 14.83 16.70 18.86 21.31 24.05 27.08'
  []
  [clad_rhocp]    # density and specific_heat only affect the march to steady
    type = GenericConstantMaterial
    block = clad
    prop_names  = 'density specific_heat'
    prop_values = '8860.0 144.5'   # cp 578->144.5 (cp/4 accel; steady-exact)
  []
[]

[Preconditioning]
  [smp]
    type = SMP
    full = true
  []
[]

[Executioner]
  type = Transient
  scheme = bdf2
  start_time = 0
  # CONTROLLED COMPARISON vs layer1_transfer. Identical executioner (dt=100,
  # num_steps=90, max_its=1) so the ONLY difference from layer1_transfer is the
  # solid cp, cut 4x in [Materials] above. This isolates whether the slow approach
  # to steady is thermal-mass-paced or coupling-paced.
  #
  # Why this matters: the layer1_transfer dt=100 run reached only ~80% of the rise
  # in 90 steps (outlet 805.5 of 817.7, imbalance 180 W), and it does NOT lie on the
  # same physical-time curve as the earlier dt=25 run (55% at 1500 s). That points
  # at the loose one-exchange-per-step OpenMC<->solid<->THM coupling converging ~1.5%
  # per step, i.e. a slow fixed-point iteration, not a physical thermal lag.
  #   - If cp is the pace-setter, this cp/4 run reaches steady FAR sooner than step
  #     90 (outlet 817.7, imbalance < 9 W well before the end). cp acceleration wins.
  #   - If it tracks the same ~80%-at-step-90 curve, the pace is the COUPLING, not
  #     mass, so cp is a dead end; march ~300 steps or accelerate the coupling.
  # Either way, compare fraction-done step-for-step against layer1_transfer.
  #
  # NO steady_state_detection (MC noise trips a norm detector). Judge steady
  # PHYSICALLY: thm_nak.csv power_imbalance (918.92 W minus NaK heat removed) -> 0,
  # with the max_fuel_T increment flat. PASS target if it converges: outlet 817.7 K,
  # max_fuel_T ~826-832 K (must match layer1_transfer; cp cannot change steady).
  dt = 100.0
  num_steps = 90
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
  []
  [max_fuel_T]
    type = ElementExtremeValue
    variable = T
    block = fuel
    value_type = max
  []
  [wall_T_avg]
    type = SideAverageValue
    variable = T
    boundary = 'outer'
  []
[]

[Outputs]
  exodus = true
  [csv]                       # per-step power_in / max_fuel_T / wall_T_avg
    type = CSV
    file_base = solid_3d
  []
  [console]
    type = Console
    show = 'power_in max_fuel_T wall_T_avg'
  []
[]

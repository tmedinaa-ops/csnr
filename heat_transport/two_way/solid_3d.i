# =============================================================================
# SNAP-10A fuel pin conduction  --  HUB app (Layer 1 two-way + NaK loop)
# =============================================================================
# This is the center of the star: a 3-D single pin that (a) pulls the live
# kappa-fission heat source from OpenMC and pushes temperature back, and (b)
# exchanges wall/fluid temperature and HTC with the THM NaK channel. It is the
# MVP's solid.i grown to 3-D with OpenMC added as a second sub-app; the THM
# coupling is unchanged.
#
#   OpenMC (openmc.i)  <-- heat_source / temperature -->  THIS  <-- T_wall /
#   T_fluid / htc -->  THM (thm.i)
#
# Prereqs: snap_unit_pin.py exported the OpenMC XMLs, and make_mesh.i produced
# pin3d.e. Run:
#   cardinal-opt -i solid_3d.i
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
# specific_heat only set the march speed, so they are left as the prior
# constants. U-ZrH and Sm2O3 stay constant because the literature gives no
# defensible T-dependence in this band (U-ZrH is ~flat per Simnad; Sm2O3 is
# poorly characterized). Hastelloy N has a real, sourced k(T), so it is tabulated.
[Materials]
  [fuel_mat]      # U-ZrH (SCA-4). k = 22.484 = reference model (arXiv 2505.04024
                  # Table II). Simnad GA-A16029 gives ~18 W/m-K, ~flat in T; that
                  # is a ~+3 K sensitivity on peak fuel T, documented, one-number
                  # switch if you want literature-primary instead of paper-match.
    type = GenericConstantMaterial
    block = fuel
    prop_names  = 'thermal_conductivity density specific_heat'
    prop_values = '22.484 6000.0 300.0'
  []
  [coating_mat]   # Sm2O3 coating. k = 1.729 = reference model (arXiv Table II).
                  # Low confidence: no usable T-dependent data for the sesquioxide.
    type = GenericConstantMaterial
    block = coating
    prop_names  = 'thermal_conductivity density specific_heat'
    prop_values = '1.729 7400.0 400.0'
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
  type = Transient
  scheme = bdf2
  start_time = 0
  # Pseudo-transient march to steady. Pin thermal time constant is ~325 s, so
  # num_steps * dt must clear ~4-5 tau: 60 * 25 = 1500 s ~= 4.6 tau reaches ~99%
  # of the steady rise. (The old num_steps=40 = 1000 s = 3.1 tau left ~5%, ~3 K,
  # still moving.) FIXED steps, no steady_state_detection: the OpenMC source is
  # stochastic, and with a small dt the per-step solution change drops under any
  # tolerance before the pin has physically heated -- that false trip is what
  # stopped the prior run at t=4 s with the fuel still at its 783 K initial
  # condition. Read the plateau off the console / solid_3d.csv instead; the last
  # several steps should be flat to < 0.5 K.
  dt = 25.0
  num_steps = 60
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

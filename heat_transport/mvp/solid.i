# =============================================================================
# SNAP-10A fuel pin heat conduction  --  parent app (Layer 0 MVP)
# =============================================================================
# One representative SNAP-10A fuel pin (U-ZrH fuel + Sm2O3 coating + Hastelloy N
# clad), 2-D axisymmetric (RZ). A cylinder is axisymmetric, so RZ is exact for a
# single pin and far cheaper than 3-D; Layer 1 (OpenMC coupling) switches this
# mesh to 3-D, nothing else changes.
#
# This is the PARENT. It:
#   - generates the pin's heat from a frozen axial power shape (cosine default,
#     or swap in the OpenMC-extracted shape via the PiecewiseLinear option),
#   - solves conduction across fuel/coating/clad,
#   - exchanges wall temperature / fluid temperature / HTC with the THM NaK
#     channel (thm.i) through the [CoupledHeatTransfers] action.
#
# Validation targets (see verify_energy_balance.py):
#   power_in    -> 918.9 W   (normalization of the source is correct)
#   NaK outlet  -> ~817.7 K  (62 K rise; read T_fluid_out in thm.i output)
#   max_fuel_T  -> ~840 K    (SNAP ran cool, well under 900 K)
#
# Run (from this folder, after building Cardinal):
#   cardinal-opt -i solid.i
#   (thm.i is launched automatically as the sub-app)
# Plain MOOSE/THM with heat_transfer + thermal_hydraulics also works since there
# is no OpenMC in Layer 0; cardinal-opt is fine and is what Layer 1 needs.
# =============================================================================

# ---- pin geometry (SI; arXiv 2505.04024 Table I) ----------------------------
r_fuel = 0.0153924     # m  U-ZrH fuel radius
w_coat = 0.0002286     # m  Sm2O3 coating thickness (r_coat - r_fuel)
w_clad = 0.0002540     # m  Hastelloy N clad thickness (r_clad - r_coat)
L      = 0.310515      # m  active length
n_ax   = 30            # axial cells (MUST match thm.i and CoupledHeatTransfers)

# ---- power (34 kWt / 37 pins) and the frozen axial shape --------------------
# Default axial shape is a chopped cosine, q'''(y) = A*cos(pi*(y-L/2)/L), zero at
# both ends, peak at center, peak/avg = pi/2 ~ 1.57. A is set so the volume
# integral equals the per-pin power (the power_in postprocessor checks this).
#   A = P_pin / (2 * L * r_fuel^2) = 918.92 / (2*0.310515*0.0153924^2)
A_q = 6.2458e6         # W/m^3  cosine amplitude (peak volumetric source)
Hw  = 5.01e4           # W/m^2-K  NaK HTC initial value for the htc aux var

[Mesh]
  [pin]
    type = CartesianMeshGenerator
    dim = 2
    dx = '${r_fuel} ${w_coat} ${w_clad}'   # radial: fuel | coating | clad
    ix = '16 2 3'                           # radial cells per region
    dy = '${L}'
    iy = '${n_ax}'
    subdomain_id = '1 2 3'                  # one row, three radial columns
  []
  [names]
    type = RenameBlockGenerator
    input = pin
    old_block = '1 2 3'
    new_block = 'fuel coating clad'
  []
  coord_type = RZ          # x is radius, y is axial; outer surface = 'right'
  rz_coord_axis = Y
[]

[Variables]
  [T]
    initial_condition = 755.37
  []
[]

# aux fields filled by the CoupledHeatTransfers action from the THM sub-app,
# plus the volumetric power that drives conduction
[AuxVariables]
  [T_fluid]
    family = MONOMIAL
    order = CONSTANT
    initial_condition = 755.37
  []
  [htc]
    family = MONOMIAL
    order = CONSTANT
    initial_condition = ${Hw}
  []
  [power]
    family = MONOMIAL
    order = CONSTANT
    block = fuel
  []
[]

[Functions]
  # ---- reference: analytic chopped cosine (peak/avg = pi/2 = 1.57) ----
  [axial_q_cosine]
    type = ParsedFunction
    expression = '${A_q} * cos(pi * (y - ${fparse L/2}) / ${L})'
  []
  # ---- ACTIVE: real axial shape from the snap OpenMC model ------------
  # 30 points from extract_heat_source.py on fig12_test (783 K). q'''(y) is the
  # per-pin volumetric source in W/m^3; integral over the fuel = 918.9 W,
  # peak/avg = 1.40 (flatter than the cosine, as a reflected core should be).
  # axis = y maps each value to the RZ axial coordinate. To refresh, re-run the
  # extractor and paste the new x/y, or point a PiecewiseLinear at axial_power.csv.
  [axial_q]
    type = PiecewiseLinear
    axis = y
    x = '0.005175 0.015526 0.025876 0.036227 0.046577 0.056928 0.067278 0.077629 0.087979 0.098330 0.108680 0.119031 0.129381 0.139732 0.150082 0.160433 0.170783 0.181134 0.191484 0.201835 0.212185 0.222536 0.232886 0.243237 0.253587 0.263938 0.274288 0.284639 0.294989 0.305340'
    y = '1.161306e+06 1.777274e+06 2.292906e+06 2.775669e+06 3.223749e+06 3.632488e+06 4.008014e+06 4.324900e+06 4.639348e+06 4.881117e+06 5.125747e+06 5.304348e+06 5.436040e+06 5.546684e+06 5.555723e+06 5.545521e+06 5.508157e+06 5.423774e+06 5.292901e+06 5.129700e+06 4.885133e+06 4.626874e+06 4.331711e+06 4.005320e+06 3.623291e+06 3.218149e+06 2.761341e+06 2.292055e+06 1.782779e+06 1.164047e+06'
  []
[]

[AuxKernels]
  [set_power]
    type = FunctionAux
    variable = power
    function = axial_q          # real OpenMC shape; use axial_q_cosine for the analytic fallback
    block = fuel
    execute_on = 'INITIAL TIMESTEP_BEGIN'
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

# Clad outer surface ('right') loses heat to the NaK. The convective BC and the
# T_wall/T_fluid/htc transfers are all created by this action. Axial ends
# (top/bottom) are left natural = insulated, the MVP assumption.
[CoupledHeatTransfers]
  [interface]
    boundary = 'right'
    T = T
    T_fluid = 'T_fluid'
    T_wall = T_wall
    htc = 'htc'
    multi_app = thm
    T_fluid_user_objects = 'T_uo'
    htc_user_objects = 'Hw_uo'
    position = '0 0 0'
    orientation = '0 1 0'
    length = ${L}
    n_elems = ${n_ax}
    skip_coordinate_collapsing = true
  []
[]

[MultiApps]
  [thm]
    type = TransientMultiApp
    input_files = 'thm.i'
    execute_on = 'TIMESTEP_END'
    sub_cycling = true          # let THM take its own smaller steps
    # app_type omitted on purpose: the default CardinalApp registry includes THM
  []
[]

[Materials]
  # Constant properties for the MVP. Conductivity sets the steady answer;
  # density and specific_heat only set how fast we march to steady.
  [fuel_mat]      # U-ZrH (SCA-4), k ~ ZrH1.6 at operating T   (medium confidence)
    type = GenericConstantMaterial
    block = fuel
    prop_names  = 'thermal_conductivity density specific_heat'
    prop_values = '18.0 6000.0 300.0'
  []
  [coating_mat]   # Sm2O3, thin, low-k rare-earth oxide          (low confidence)
    type = GenericConstantMaterial
    block = coating
    prop_names  = 'thermal_conductivity density specific_heat'
    prop_values = '1.5 7400.0 400.0'
  []
  [clad_mat]      # Hastelloy N near 700 C                        (medium confidence)
    type = GenericConstantMaterial
    block = clad
    prop_names  = 'thermal_conductivity density specific_heat'
    prop_values = '23.6 8860.0 578.0'
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
  dt = 1.0
  num_steps = 500
  solve_type = NEWTON
  petsc_options_iname = '-pc_type'
  petsc_options_value = ' lu'
  nl_rel_tol = 1e-7
  nl_abs_tol = 1e-6
  l_max_its = 100

  # stop automatically once the pin reaches thermal steady state
  steady_state_detection = true
  steady_state_tolerance = 1e-7
[]

[Postprocessors]
  [power_in]            # MUST equal P_pin = 918.9 W (source normalization)
    type = ElementIntegralVariablePostprocessor
    variable = power
    block = fuel
    execute_on = 'INITIAL TIMESTEP_END'
  []
  [max_fuel_T]          # target ~840 K
    type = ElementExtremeValue
    variable = T
    block = fuel
    value_type = max
  []
  [wall_T_avg]          # clad outer surface average temperature
    type = SideAverageValue
    variable = T
    boundary = 'right'
  []
  [wall_T_max]
    type = NodalExtremeValue
    variable = T
    boundary = 'right'
    value_type = max
  []
[]

[Outputs]
  exodus = true
  [csv]
    type = CSV
    file_base = mvp_solid
  []
  [console]
    type = Console
    show = 'power_in max_fuel_T wall_T_avg wall_T_max'
  []
[]

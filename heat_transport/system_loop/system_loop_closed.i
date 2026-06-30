# =============================================================================
# SNAP-10A 14 kWe system loop  --  RECIRCULATING (closed) version
# reactor -> NaK -> Stirling -> radiator -> space, and the NaK loops BACK.
# The heat physically recirculates: each loop's return temperature is fed back to
# its own inlet, so the NaK that leaves the reactor comes back to it. Flow is the
# EM pump's known rate (imposed), the realistic and robust choice; a full momentum
# ring with Pump1Phase is the higher-fidelity alternative noted in README.md.
# The hot loop is anchored by a temperature-following engine draw (see the
# closed-loop anchor block below); the cold loop is anchored by the radiator.
# Companion to the open, validated system_loop.i. Run the open one first.
# =============================================================================
# This is the deck the project's heat_transport model stopped short of. The
# existing mvp/ and layer2_core/ decks end at the NaK outlet on purpose; this
# one carries the heat the rest of the way: into the Stirling hot end, out the
# cold end as electricity plus waste heat, and off the radiator to 4 K space.
#
# What MOOSE solves here (all real physics):
#   - conduction in the reactor "core" structure with a fission heat source
#   - 1-D single-phase NaK energy/momentum transport in every loop segment
#   - conduction in the converter and radiator structures
#   - radiative heat loss to space off the radiator panel (HSBoundaryRadiation)
#
# What MOOSE does NOT solve (it cannot, and should not pretend to): the Stirling
# thermodynamic gas cycle. The engine is a HEAT-EXTRACTION COMPONENT. The hot end
# is a heat sink that pulls Q_in out of the primary NaK; the cold end is a heat
# source that dumps Q_waste into the rejection NaK. The split between electricity
# and waste is set by the project's validated efficiency law
#   eta = carnot(T_hot,T_cold) * rel(T_cold/T_hot)
# (energy_conversion/stirling_cycle_concept/stirling_converter.py), recomputed
# every timestep from the live NaK temperatures by the [ControlLogic] block. So
# the engine RESPONDS to the loop: hotter delivery -> more electricity -> less
# waste -> cooler radiator, all in one transient.
#
# "Single NaK loop" (the chosen architecture) means NO intermediate heat
# exchanger on the hot side. It does NOT mean one stream: a Stirling needs a hot
# source and a cold sink at different temperatures, so there are two NaK circuits
# (hot primary ~755->897 K, cold rejection ~475->500 K) coupled only through the
# engine. You cannot make one stream be 897 K and 475 K at once.
#
# Operating point: the verified 14 kWe uprate (energy_conversion/Path_to_14kWe_
# Verified.md, nak_system_chain.py, rejection_loop.py). 79 kWt fuel-limited core.
# Validation targets are in README.md and verify_loop.py.
#
# Run (moose conda env, from this folder):
#   cardinal-opt -i system_loop.i      # or any MOOSE app built with THM
# Plain THM is enough here (no OpenMC in this layer); cardinal-opt also works.
#
# I could not execute this here (separate sandbox). Every block is grounded in
# current MOOSE THM docs and the project's own validated thm.i. Expect to shake
# out a version-specific name or two on first run; the likely spots are flagged.
# =============================================================================

# ---- operating point (verified uprate; see README) --------------------------
Q_reactor   = 79000.0     # W   fuel-limited EOL core power
heat_frac   = 0.938       # -   fraction of core heat that reaches the converter
Q_engine    = ${fparse Q_reactor * heat_frac}          # 74102 W to the hot end
Q_parasitic = ${fparse Q_reactor * (1.0 - heat_frac)}  #  4898 W shield/transport loss

T_in_hot    = 755.37      # K   primary cold-leg inlet (arXiv Table II)
mdot_hot    = 0.64        # kg/s primary NaK flow (uprate; design 0.6199)
T_in_cold   = 475.0       # K   rejection-loop inlet (returns from radiator)
mdot_cold   = 3.0         # kg/s rejection NaK flow (sized for ~22 K cooler rise)

# Stirling efficiency-law constants (stirling_converter.py, concept branch)
pinch_hot   = 25.0        # K   hot-side delivery drop (reactor outlet -> engine);
                          #     matches the G1 "hot side = outlet - 25 K" assumption
rel_slope   = -0.61084    # -   d(rel)/d(tau), anchored SNAP(0.762->0.30)/Kilo(0.50->0.46)
tau0        = 0.76195     # -   SNAP anchor tau = 590.37/774.82
rel_floor   = 0.20
rel_ceil    = 0.50

# ---- closed-loop anchor (recirculating version) -----------------------------
# Recirculating both loops removes the fixed inlet temperatures that anchored the
# open deck, so the hot loop's temperature level would float (a domain with only
# sources/sinks is defined up to a constant, the singular-system point from the
# MOOSE workshop). The radiator already anchors the cold loop through its T^4 law.
# The hot loop is anchored by making the Stirling hot end a TEMPERATURE-FOLLOWING
# heat draw instead of a fixed power: Q_draw = UA*(T_hot - T_engine_set). The NaK
# then runs exactly as hot as it must to push the reactor's heat into the engine.
# UA and T_engine_set are set so the loop settles at the validated design point
# (reactor outlet 895.6 K, draw 74.1 kW), reproducing the open deck's numbers.
T_hot_design = ${fparse T_in_hot + Q_reactor / (mdot_hot * 879.903)}   # 895.6 K
T_engine_set = ${fparse T_hot_design - pinch_hot}                      # 870.6 K engine hot gas
UA_engine    = ${fparse Q_engine / pinch_hot}                          # 2964 W/K, draw = Q_engine at design

# radiator (HSBoundaryRadiation to space)
T_space     = 4.0         # K   deep-space sink
emiss_rad   = 0.89        # -   GFRC emissivity (G1 merge)
fineff_rad  = 0.90        # -   fin efficiency, carried as the view factor
A_panel     = 26.0        # m^2 flat-panel radiating area at the 14 kWe point

Hw_nak      = 5.01e4      # W/m^2-K  clad/wall-to-NaK HTC (arXiv Table II)

# ---- pipe geometry (lumped transport channels; sets transit time, not the
#      steady energy balance) ---------------------------------------------------
D_hot   = 0.06
A_hot   = ${fparse pi * D_hot^2 / 4.0}
P_hot   = ${fparse pi * D_hot}
D_cold  = 0.12
A_cold  = ${fparse pi * D_cold^2 / 4.0}
P_cold  = ${fparse pi * D_cold}
L_seg   = 0.5             # m   length of each loop segment
n_ax    = 20             # axial cells per segment

# radiator structure: thin wall on the rejection pipe; the 26 m^2 of flat-panel
# area is carried by the HSBoundaryRadiation 'scale' (area amplification), so the
# wall stays a realistic thin shell while radiating the true area. A faithful
# flat-plate radiator with its own mesh is the documented Layer C upgrade.
# The wall MUST be thin and conductive: because 'scale' radiates the full 26 m^2
# but conduction crosses the tube's real (small) wall area, a thick wall throws a
# spurious Q*t/(k*A) drop (~40 K at 3 mm) that holds the radiating surface below
# the coolant. 0.5 mm keeps that drop to a few K, so the panel tracks the NaK as a
# real finned radiator does (the fin_eff = 0.90 already assumes near-isothermal).
rad_wall   = 0.0005
rad_ro     = ${fparse D_cold/2.0 + rad_wall}
A_rad_geom = ${fparse 2.0 * pi * rad_ro * L_seg}   # HS outer surface (small)
rad_scale  = ${fparse A_panel / A_rad_geom}        # amplify to the panel area

[GlobalParams]
  initial_p     = 1.0e5
  initial_vel   = 0.3
  initial_T     = 650.0
  closures      = simple_closures
  fp            = nak
[]

# ---- NaK-78 as a constant-property liquid metal (arXiv Table II, 783 K) ------
# Proven values from the project's validated thm.i. The loop spans 475-897 K, so
# constant properties carry a known ~10% density error at the extremes; the swap
# is MOOSE's built-in NaKFluidProperties (Foust 1972), commented below. Kept
# constant here for robustness and to match the validated reactor-side deck.
[FluidProperties]
  [nak]
    type = SimpleFluidProperties
    density0             = 755.92
    viscosity            = 1.8835e-4
    thermal_conductivity = 26.2345
    cp                   = 879.903
    cv                   = 879.903
    thermal_expansion    = 2.5e-4
    bulk_modulus         = 1.0e9
  []
  # [nak]
  #   type = NaKFluidProperties     # T-dependent eutectic; off-design upgrade
  # []
[]

[Closures]
  [simple_closures]
    type = Closures1PhaseSimple
  []
[]

# ---- solid materials for the heat structures --------------------------------
[SolidProperties]
  [sp_fuel]            # U-ZrH core stand-in
    type = ThermalFunctionSolidProperties
    rho = 6000.0
    cp  = 300.0
    k   = 18.0
  []
  [sp_steel]           # Hastelloy-N / structure
    type = ThermalFunctionSolidProperties
    rho = 8860.0
    cp  = 578.0
    k   = 23.0
  []
  [sp_rad]             # radiator panel (Ti/GFRC stand-in; high k so the thin wall
                       # does not throttle heat to the radiating surface)
    type = ThermalFunctionSolidProperties
    rho = 4500.0
    cp  = 600.0
    k   = 50.0
  []
[]

[Components]
  # ===========================================================================
  # PRIMARY (HOT) CIRCUIT:  inlet -> core (heat in) -> junction -> heater
  #                         (engine sink + parasitic loss) -> outlet
  # ===========================================================================
  [hot_inlet]
    type  = InletMassFlowRateTemperature1Phase
    input = 'core_pipe:in'
    m_dot = ${mdot_hot}
    T     = ${T_in_hot}
  []

  # --- reactor: fission heat conducted into the primary NaK ---
  [core_pipe]
    type        = FlowChannel1Phase
    position    = '0 0 0'
    orientation = '0 0 1'
    length      = ${L_seg}
    n_elems     = ${n_ax}
    A   = ${A_hot}
    D_h = ${D_hot}
    f   = 0.02
  []
  [reactor_power]
    type  = TotalPower
    power = ${Q_reactor}
  []
  [reactor_hs]
    type = HeatStructureCylindrical
    position    = '0 0 0'
    orientation = '0 0 1'
    length      = ${L_seg}
    n_elems     = ${n_ax}
    inner_radius = 0.0
    widths       = 0.03
    n_part_elems = 3
    names        = 'fuel'
    solid_properties       = 'sp_fuel'
    solid_properties_T_ref = '300'
    initial_T    = 800.0
  []
  [reactor_src]
    type  = HeatSourceFromTotalPower
    hs    = reactor_hs
    regions = 'fuel'
    power = reactor_power
  []
  [reactor_ht]
    type         = HeatTransferFromHeatStructure1Phase
    flow_channel = core_pipe
    hs           = reactor_hs
    hs_side      = OUTER
    Hw           = ${Hw_nak}
    P_hf         = ${P_hot}
  []

  [j_hot]
    type        = JunctionOneToOne1Phase
    connections = 'core_pipe:out heater_pipe:in'
  []

  # --- heater: the NaK gives heat to the Stirling hot end (sink) and loses a
  #     small parasitic to shield/transport. Two heat structures share this pipe.
  [heater_pipe]
    type        = FlowChannel1Phase
    position    = '0 0 ${L_seg}'
    orientation = '0 0 1'
    length      = ${L_seg}
    n_elems     = ${n_ax}
    A   = ${A_hot}
    D_h = ${D_hot}
    f   = 0.02
  []
  # Stirling hot end: NEGATIVE total power = heat sink. In the closed loop the
  # magnitude is NOT fixed; [ControlLogic] sets it every step to the temperature-
  # following draw -UA*(T_hot - T_engine_set), which anchors the hot loop. The
  # value here is just the design-point initial guess.
  [engine_hot_power]
    type  = TotalPower
    power = ${fparse -Q_engine}
  []
  [engine_hot_hs]
    type = HeatStructureCylindrical
    position    = '0 0 ${L_seg}'
    orientation = '0 0 1'
    length      = ${L_seg}
    n_elems     = ${n_ax}
    inner_radius = 0.0
    widths       = 0.02
    n_part_elems = 2
    names        = 'shoe'
    solid_properties       = 'sp_steel'
    solid_properties_T_ref = '300'
    initial_T    = 850.0
  []
  [engine_hot_src]
    type  = HeatSourceFromTotalPower
    hs    = engine_hot_hs
    regions = 'shoe'
    power = engine_hot_power
  []
  [engine_hot_ht]
    type         = HeatTransferFromHeatStructure1Phase
    flow_channel = heater_pipe
    hs           = engine_hot_hs
    hs_side      = OUTER
    Hw           = ${Hw_nak}
    P_hf         = ${P_hot}
  []
  # parasitic shield/transport loss off the hot leg (fixed small sink)
  [parasitic_power]
    type  = TotalPower
    power = ${fparse -Q_parasitic}
  []
  [parasitic_hs]
    type = HeatStructureCylindrical
    position    = '0 0 ${L_seg}'
    orientation = '0 0 1'
    length      = ${L_seg}
    n_elems     = ${n_ax}
    inner_radius = 0.031
    widths       = 0.004
    n_part_elems = 2
    names        = 'shield'
    solid_properties       = 'sp_steel'
    solid_properties_T_ref = '300'
    initial_T    = 800.0
  []
  [parasitic_src]
    type  = HeatSourceFromTotalPower
    hs    = parasitic_hs
    regions = 'shield'
    power = parasitic_power
  []
  [parasitic_ht]
    type         = HeatTransferFromHeatStructure1Phase
    flow_channel = heater_pipe
    hs           = parasitic_hs
    hs_side      = INNER
    Hw           = 2.0e3
    P_hf         = ${P_hot}
  []

  [hot_outlet]
    type  = Outlet1Phase
    input = 'heater_pipe:out'
    p     = 1.0e5
  []

  # ===========================================================================
  # REJECTION (COLD) CIRCUIT: inlet -> cooler (engine waste in) -> junction
  #                           -> radiator (heat out to space) -> outlet
  # ===========================================================================
  [cold_inlet]
    type  = InletMassFlowRateTemperature1Phase
    input = 'cooler_pipe:in'
    m_dot = ${mdot_cold}
    T     = ${T_in_cold}
  []

  # --- cooler: the Stirling cold end dumps its waste heat into the NaK. This is
  #     a POSITIVE source whose magnitude Q_waste is set live by [ControlLogic]. ---
  [cooler_pipe]
    type        = FlowChannel1Phase
    position    = '1 0 0'
    orientation = '0 0 1'
    length      = ${L_seg}
    n_elems     = ${n_ax}
    A   = ${A_cold}
    D_h = ${D_cold}
    f   = 0.02
  []
  [cold_power]
    type  = TotalPower
    power = 59500.0        # initial guess; overwritten every step by the control
  []
  [cold_hs]
    type = HeatStructureCylindrical
    position    = '1 0 0'
    orientation = '0 0 1'
    length      = ${L_seg}
    n_elems     = ${n_ax}
    inner_radius = 0.0
    widths       = 0.03
    n_part_elems = 2
    names        = 'cooler'
    solid_properties       = 'sp_steel'
    solid_properties_T_ref = '300'
    initial_T    = 500.0
  []
  [cold_src]
    type  = HeatSourceFromTotalPower
    hs    = cold_hs
    regions = 'cooler'
    power = cold_power
  []
  [cold_ht]
    type         = HeatTransferFromHeatStructure1Phase
    flow_channel = cooler_pipe
    hs           = cold_hs
    hs_side      = OUTER
    Hw           = ${Hw_nak}
    P_hf         = ${P_cold}
  []

  [j_cold]
    type        = JunctionOneToOne1Phase
    connections = 'cooler_pipe:out rad_pipe:in'
  []

  # --- radiator: NaK gives heat to the panel wall (inner), the wall radiates to
  #     4 K space (outer). 'scale' carries the 26 m^2 flat-panel area. ---
  [rad_pipe]
    type        = FlowChannel1Phase
    position    = '1 0 ${L_seg}'
    orientation = '0 0 1'
    length      = ${L_seg}
    n_elems     = ${n_ax}
    A   = ${A_cold}
    D_h = ${D_cold}
    f   = 0.02
  []
  [rad_hs]
    type = HeatStructureCylindrical
    position    = '1 0 ${L_seg}'
    orientation = '0 0 1'
    length      = ${L_seg}
    n_elems     = ${n_ax}
    inner_radius = ${fparse D_cold/2.0}
    widths       = ${rad_wall}
    n_part_elems = 2
    names        = 'panel'
    solid_properties       = 'sp_rad'
    solid_properties_T_ref = '300'
    initial_T    = 480.0
  []
  [rad_ht]
    type         = HeatTransferFromHeatStructure1Phase
    flow_channel = rad_pipe
    hs           = rad_hs
    hs_side      = INNER
    Hw           = ${Hw_nak}
    P_hf         = ${P_cold}
  []
  [rad_to_space]
    type        = HSBoundaryRadiation
    hs          = rad_hs
    boundary    = 'rad_hs:outer'
    T_ambient   = ${T_space}
    emissivity  = ${emiss_rad}
    view_factor = ${fineff_rad}
    scale       = ${rad_scale}
  []

  [cold_outlet]
    type  = Outlet1Phase
    input = 'rad_pipe:out'
    p     = 1.0e5
  []
[]

# =============================================================================
# THE STIRLING ENGINE, as a live control:
#   read T_hot (reactor outlet NaK) and T_cold (radiator panel)
#   -> eta(T_hot,T_cold) -> electricity = eta * Q_engine
#   -> Q_waste = Q_engine - electricity -> set the cold-end source power
# Computed in ParsedPostprocessors (visible in CSV), forwarded into the cold
# source by the control. One-step lag, which keeps the coupling stable.
# =============================================================================
[Postprocessors]
  # --- temperatures that drive the engine ---
  [T_hot]                          # NaK delivered to the hot end (reactor outlet)
    type     = SideAverageValue
    boundary = 'core_pipe:out'
    variable = T
    execute_on = 'INITIAL TIMESTEP_END'
  []
  [T_cold]                         # radiator panel temperature (engine cold side)
    type     = SideAverageValue
    boundary = 'rad_hs:outer'
    variable = T_solid             # heat-structure solid temp is T_solid, NOT T (that is the fluid)
    execute_on = 'INITIAL TIMESTEP_END'
  []

  # --- the temperature-following engine draw (the hot-loop anchor) ---
  # Q_draw = UA*(T_hot - T_engine_set). At steady state the loop forces this to
  # equal Q_reactor - Q_parasitic = 74.1 kW, which pins T_hot at 895.6 K.
  [Q_engine_draw]
    type        = ParsedPostprocessor
    pp_names    = 'T_hot'
    constant_names       = 'UA Tset'
    constant_expressions = '${UA_engine} ${T_engine_set}'
    # max(0, ...) so the engine only ever REMOVES heat. The loop starts at 650 K,
    # below T_engine_set, so without the floor the draw would go negative and turn
    # the hot end into a heat source during warmup. With the floor the engine stays
    # off until the reactor has heated the NaK past T_engine_set, then it anchors.
    expression  = 'max(0.0, UA * (T_hot - Tset))'
    execute_on  = 'INITIAL TIMESTEP_END'
  []
  [engine_power_set]               # negative -> heat sink; pushed into engine_hot_power
    type        = ParsedPostprocessor
    pp_names    = 'Q_engine_draw'
    expression  = '-Q_engine_draw'
    execute_on  = 'INITIAL TIMESTEP_END'
  []

  # --- the efficiency law, evaluated on the live temperatures ---
  [eta]
    type        = ParsedPostprocessor
    pp_names    = 'T_hot T_cold'
    constant_names        = 'pinch slope tau0 rfl rcl'
    constant_expressions  = '${pinch_hot} ${rel_slope} ${tau0} ${rel_floor} ${rel_ceil}'
    expression  = '(1 - T_cold/(T_hot - pinch)) * max(rfl, min(rcl, 0.30 + slope*(T_cold/(T_hot - pinch) - tau0)))'
    execute_on  = 'INITIAL TIMESTEP_END'
  []
  [electricity]                    # eta applied to the live engine draw
    type        = ParsedPostprocessor
    pp_names    = 'eta Q_engine_draw'
    expression  = 'eta * Q_engine_draw'
    execute_on  = 'INITIAL TIMESTEP_END'
  []
  [Q_waste]
    type        = ParsedPostprocessor
    pp_names    = 'Q_engine_draw electricity'
    expression  = 'Q_engine_draw - electricity'
    execute_on  = 'INITIAL TIMESTEP_END'
  []

  # --- loop temperatures (the heat moving through the system) ---
  [T_core_in]
    type = SideAverageValue
    boundary = 'core_pipe:in'
    variable = T
    execute_on = 'INITIAL TIMESTEP_END'
  []
  [T_core_out]
    type = SideAverageValue
    boundary = 'core_pipe:out'
    variable = T
    execute_on = 'INITIAL TIMESTEP_END'
  []
  [T_heater_out]
    type = SideAverageValue
    boundary = 'heater_pipe:out'
    variable = T
    execute_on = 'INITIAL TIMESTEP_END'
  []
  [T_cooler_in]
    type = SideAverageValue
    boundary = 'cooler_pipe:in'
    variable = T
    execute_on = 'INITIAL TIMESTEP_END'
  []
  [T_cooler_out]
    type = SideAverageValue
    boundary = 'cooler_pipe:out'
    variable = T
    execute_on = 'INITIAL TIMESTEP_END'
  []
  [T_rad_out]
    type = SideAverageValue
    boundary = 'rad_pipe:out'
    variable = T
    execute_on = 'INITIAL TIMESTEP_END'
  []

  # NOTE: the actual heat radiated to space is reported by the postprocessor
  # 'rad_to_space_integral', which HSBoundaryRadiation auto-creates on a
  # cylindrical heat structure. It is shown in the Outputs below. At steady state
  # it should match Q_waste (~59.5 kW), confirming the cold side closes to space.

  # --- anchor / convergence check: reactor = engine draw + parasitic ---
  # Now a REAL check (unlike the open deck where it was an identity): the engine
  # draw is set by temperature, so this only reaches ~0 once the hot loop has
  # anchored at the right level. = Qr - Q_engine_draw - Qpar.
  [energy_residual]
    type        = ParsedPostprocessor
    pp_names    = 'electricity Q_waste'
    constant_names       = 'Qr Qpar'
    constant_expressions = '${Q_reactor} ${Q_parasitic}'
    expression  = 'Qr - electricity - Q_waste - Qpar'
    execute_on  = 'INITIAL TIMESTEP_END'
  []
[]

[ControlLogic]
  # Postprocessors are exposed as control data under their own names, so each
  # setter reads one directly. Four controls run the closed loop:

  # 1. Stirling cold end dumps the waste heat into the rejection NaK.
  [set_cold_power]
    type      = SetComponentRealValueControl
    component = cold_power
    parameter = power
    value     = Q_waste
  []

  # 2. Stirling hot end draws the temperature-following heat (the hot-loop anchor).
  [set_engine_power]
    type      = SetComponentRealValueControl
    component = engine_hot_power
    parameter = power
    value     = engine_power_set
  []

  # 3. Recirculate the hot loop: the reactor inlet takes the heater's return temp,
  #    so the NaK that left the reactor comes back to it.
  [recirc_hot]
    type      = SetComponentRealValueControl
    component = hot_inlet
    parameter = T
    value     = T_heater_out
  []

  # 4. Recirculate the cold loop: the cooler inlet takes the radiator's return temp.
  [recirc_cold]
    type      = SetComponentRealValueControl
    component = cold_inlet
    parameter = T
    value     = T_rad_out
  []
[]

[Preconditioning]
  [pc]
    type = SMP
    full = true
  []
[]

[Executioner]
  type   = Transient
  scheme = bdf2
  start_time = 0
  dt     = 2.0
  dtmin  = 1e-4
  num_steps = 800        # recirculation adds a slower coupled mode than the open deck;
                         # steady_state_detection should still trip well before this

  solve_type = NEWTON
  line_search = basic
  nl_rel_tol = 1e-6
  nl_abs_tol = 1e-5
  nl_max_its = 25
  l_tol = 1e-3
  l_max_its = 100
  petsc_options_iname = '-pc_type'
  petsc_options_value = ' lu'

  steady_state_detection  = true
  steady_state_tolerance  = 1e-7
[]

[Outputs]
  [console]
    type = Console
    show = 'T_core_in T_core_out T_heater_out Q_engine_draw eta electricity Q_waste T_cold rad_to_space_integral energy_residual'
  []
  [csv]
    type = CSV
    file_base = system_loop_closed
  []
  exodus = true
[]

# =============================================================================
# SNAP-10A NaK coolant channel  --  THM sub-app (Layer 1, 3-D pin)
# =============================================================================
# Identical physics to mvp/thm.i, but the channel runs along z (the 3-D pin
# axis) instead of y, so orientation and the LayeredAverage direction are z.
# Launched automatically by solid_3d.i. SI units.
# =============================================================================

T_in   = 755.37
mdot   = 0.0167541
p_out  = 4.0e5
A_flow = 9.530e-5
D_h    = 3.822e-3
P_hf   = 0.0997456
L      = 0.310515
Hw     = 5.01e4
n_ax   = 30

[GlobalParams]
  initial_p   = ${p_out}
  initial_vel = 0.233
  initial_T   = ${T_in}
  closures    = simple_closures
  fp          = nak
[]

[FluidProperties]
  [nak]
    type = SimpleFluidProperties
    density0             = 755.92
    viscosity           = 1.8835e-4
    thermal_conductivity = 26.2345
    cp                  = 879.903
    cv                  = 879.903
    thermal_expansion   = 2.5e-4
    bulk_modulus        = 1.0e9
  []
[]

[Closures]
  [simple_closures]
    type = Closures1PhaseSimple
  []
[]

[AuxVariables]
  [Hw]
    family = MONOMIAL
    order  = CONSTANT
    block  = pipe
  []
[]
[AuxKernels]
  [Hw_ak]
    type = ADMaterialRealAux
    variable = Hw
    property = 'Hw'
    block = pipe
  []
[]

[UserObjects]
  [T_uo]
    type = LayeredAverage
    direction = z
    variable = T
    num_layers = ${n_ax}
    block = pipe
  []
  [Hw_uo]
    type = LayeredAverage
    direction = z
    variable = Hw
    num_layers = ${n_ax}
    block = pipe
  []
[]

[Components]
  [inlet]
    type = InletMassFlowRateTemperature1Phase
    input = 'pipe:in'
    m_dot = ${mdot}
    T = ${T_in}
  []
  [pipe]
    type = FlowChannel1Phase
    position    = '0 0 0'
    orientation = '0 0 1'        # along the 3-D pin axis (z)
    length      = ${L}
    n_elems     = ${n_ax}
    A   = ${A_flow}
    D_h = ${D_h}
    f   = 0.02
  []
  [outlet]
    type = Outlet1Phase
    input = 'pipe:out'
    p = ${p_out}
  []
  [ht]
    type = HeatTransferFromExternalAppTemperature1Phase
    flow_channel = pipe
    Hw = ${Hw}
    P_hf = ${P_hf}
    initial_T_wall = ${T_in}
    var_type = elemental
  []
[]

[Preconditioning]
  [pc]
    type = SMP
    full = true
  []
[]

[Executioner]
  type = Transient
  scheme = bdf2
  start_time = 0
  dt = 0.25
  dtmin = 1e-5
  num_steps = 100000        # high cap: with sub_cycling the parent (dt=25) drives total time
  abort_on_solve_fail = true
  solve_type = NEWTON
  line_search = basic
  nl_rel_tol = 1e-7
  nl_abs_tol = 1e-5
  nl_max_its = 25
  l_tol = 1e-3
  l_max_its = 100
  petsc_options_iname = '-pc_type'
  petsc_options_value = ' lu'
[]

[Postprocessors]
  [T_fluid_out]
    type = SideAverageValue
    variable = T
    boundary = 'pipe:out'
    execute_on = 'INITIAL TIMESTEP_END'
  []
  [T_fluid_in]
    type = SideAverageValue
    variable = T
    boundary = 'pipe:in'
    execute_on = 'INITIAL TIMESTEP_END'
  []
  # ---- PER-CHANNEL heat removal (NOT a per-channel convergence check) ---------
  # heat_removed is the power THIS channel carries away: mdot*cp*(T_out - T_in),
  # true inlet enthalpy = the inlet BC 755.37 K (not SideAverageValue T_fluid_in,
  # which has a ~3 K boundary-cell offset). mdot*cp = 0.0167541*879.903 = 14.742 W/K.
  # In the core this varies channel to channel with radial peaking, so there is NO
  # single per-channel reference to difference against (Layer 1's 918.92 trick does
  # not apply). The CONVERGENCE check lives at the core level in solid_core.i
  # (power_in vs total clad-surface heat flux). heat_removed here just reports each
  # channel's NaK rise so you can see the hot/cold spread across the 3 channels.
  # NOTE: 'expression' is modern-MOOSE ParsedPostprocessor syntax; if the build
  # errors on it, rename 'expression' -> 'function' (fails at setup, not mid-run).
  [heat_removed]
    type = ParsedPostprocessor
    expression = 'mdot * cp * (T_fluid_out - T_in)'
    pp_names = 'T_fluid_out'
    constant_names = 'mdot cp T_in'
    constant_expressions = '0.0167541 879.903 755.37'
    execute_on = 'INITIAL TIMESTEP_END'
  []
[]

[Outputs]
  [out]
    type = Exodus
    show = 'T T_wall Hw'
  []
  [csv]
    # per-channel CSV (T_fluid_out, heat_removed). NO file_base on purpose: the THM
    # MultiApp runs multiple instances (center/mid/edge), so MOOSE must auto-name
    # each one by sub-app index. Forcing a shared file_base makes all instances
    # write the same file, which is the error this Layer 2 first run hit.
    type = CSV
  []
[]

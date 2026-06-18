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
  num_steps = 100000        # high cap; steady_state_detection stops each call early
  # Stop each THM call once its channel reaches steady (residence ~1.3 s) instead of
  # grinding the whole sub_cycle window. THM is deterministic, so a norm detector is
  # safe here (unlike the OpenMC-coupled parent). Large sub-cycle saving.
  steady_state_detection = true
  steady_state_tolerance = 1e-8
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
  # Outlet bulk temperature. SideAverageValue on a THM flow-channel boundary returns
  # the adjacent CELL-CENTROID value (THM is cell-centered finite volume), so it
  # carries a half-cell offset. It is the tool the THM CHT tutorial uses for T_out;
  # read it as "near-outlet bulk T", not an exact face value.
  [T_fluid_out]
    type = SideAverageValue
    variable = T
    boundary = 'pipe:out'
    execute_on = 'INITIAL TIMESTEP_END'
  []
  # DO NOT read this as "the inlet temperature." SideAverageValue at pipe:in returns
  # the FIRST cell centroid, half a cell downstream of the physical inlet, and on a
  # hot short channel it sits tens of K above the real inlet -- exactly what made the
  # old heat_removed read ~30% high. The true inlet is the BC: T_in = 755.37 K. Kept
  # only as a diagnostic of the boundary offset.
  [T_fluid_in_diag]
    type = SideAverageValue
    variable = T
    boundary = 'pipe:in'
    execute_on = 'INITIAL TIMESTEP_END'
  []
  # ---- PER-CHANNEL heat actually delivered to the NaK (THE FIX, June 2026) -----
  # Integrate the real wall convective flux Hw*P_hf*(T_wall - T) the solver applied,
  # instead of differencing side-average temperatures. This is the CONSERVING
  # quantity: summed over the 37 channels it must equal the solid's surface_heat_out
  # (= power_in). The old mdot*cp*(T_out - T_in) gave three disagreeing numbers
  # (26.6 / 44.4 kW vs the solid's 34.3) because both side averages are biased; this
  # reads the heat the fluid genuinely received. ADHeatRateConvection1Phase pulls the
  # T_wall that HeatTransferFromExternalAppTemperature1Phase transferred in, so it
  # covers the external-app coupling directly. (If the build rejects the AD object,
  # switch to HeatRateConvection1Phase -- fails at setup, not mid-run.)
  # Ref: MOOSE THM ADHeatRateConvection1Phase; single_phase_flow CHT tutorial step 2.
  [heat_added]
    type = ADHeatRateConvection1Phase
    block = pipe
    P_hf = ${P_hf}
    execute_on = 'INITIAL TIMESTEP_END'
  []
[]

[Outputs]
  [out]
    type = Exodus
    show = 'T T_wall Hw'
  []
  [csv]
    # per-channel CSV (T_fluid_out, T_fluid_in_diag, heat_added). NO file_base on
    # purpose: the THM MultiApp runs 37 instances, so MOOSE auto-names each by sub-app
    # index (solid_core_out_thmNN). Forcing a shared file_base makes all instances
    # write the same file. CHECK THE RUN: sum heat_added over the 37 files -> must
    # equal ~power_in (NOT 44 kW); its spread across pins = the real radial peaking.
    type = CSV
  []
[]

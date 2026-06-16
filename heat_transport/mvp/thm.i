# =============================================================================
# SNAP-10A NaK coolant channel  --  THM sub-app (Layer 0 MVP)
# =============================================================================
# One representative NaK-78 subchannel, modeled with the MOOSE Thermal
# Hydraulics Module (1-D area-averaged single-phase flow). This is the CHILD
# app. The parent (solid.i) sends the clad wall temperature in via the
# [CoupledHeatTransfers] action; this app sends fluid temperature (T_uo) and
# heat-transfer coefficient (Hw_uo) back. All SI units.
#
# Pattern verified against:
#   moose/modules/thermal_hydraulics/test/tests/actions/coupled_heat_transfer_action/sub.i
#   MOOSE docs: HeatTransferFromExternalAppTemperature1Phase
#
# Run standalone (sanity check the loop alone, fixed wall temp):
#   cardinal-opt -i thm.i
# Normally launched automatically by solid.i as the sub-app.
# =============================================================================

# ---- shared parameters (keep in sync with solid.i) --------------------------
T_in   = 755.37        # K   core inlet (arXiv Table II)
mdot   = 0.0167541     # kg/s per subchannel = 0.6199 / 37
p_out  = 4.0e5         # Pa  nominal loop pressure (pumped liquid metal, low)
A_flow = 9.530e-5      # m^2 subchannel flow area (verify_energy_balance.py)
D_h    = 3.822e-3      # m   hydraulic diameter
P_hf   = 0.0997456     # m   heated perimeter = 2*pi*r_clad (pi*0.031750)
L      = 0.310515      # m   active length
Hw     = 5.01e4        # W/m^2-K liquid-metal HTC (Lyon corr., see verify script)
n_ax   = 30            # axial cells (MUST match solid.i CoupledHeatTransfers)

[GlobalParams]
  initial_p   = ${p_out}
  initial_vel = 0.233       # m/s, from the energy-balance check
  initial_T   = ${T_in}
  closures    = simple_closures
  fp          = nak
[]

# ---- NaK-78 as a constant-property liquid metal -----------------------------
# Numbers from arXiv 2505.04024 Table II at the 783 K average. SimpleFluidProperties
# gives a near-incompressible liquid (high bulk modulus, small expansion), which
# is what we want for a low-Mach pumped loop. Upgrade path: temperature-dependent
# liquid-metal correlation or the MOOSE sodium/potassium libraries.
[FluidProperties]
  [nak]
    type = SimpleFluidProperties
    density0             = 755.92      # kg/m^3
    viscosity           = 1.8835e-4   # Pa.s
    thermal_conductivity = 26.2345    # W/m-K
    cp                  = 879.903     # J/kg-K
    cv                  = 879.903     # liquid: cv ~ cp
    thermal_expansion   = 2.5e-4      # 1/K (NaK-78, approximate)
    bulk_modulus        = 1.0e9       # Pa (stiff -> near-incompressible)
  []
[]

[Closures]
  [simple_closures]
    type = Closures1PhaseSimple
  []
[]

# ---- expose the wall HTC as a field so it can be layer-averaged and sent up --
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

# ---- layer averages transferred back to the solid (T_fluid and HTC) ---------
[UserObjects]
  [T_uo]
    type = LayeredAverage
    direction = y
    variable = T
    num_layers = ${n_ax}
    block = pipe
  []
  [Hw_uo]
    type = LayeredAverage
    direction = y
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
    orientation = '0 1 0'      # flow bottom-to-top, axial = +y (matches solid RZ y)
    length      = ${L}
    n_elems     = ${n_ax}
    A   = ${A_flow}
    D_h = ${D_h}
    f   = 0.02                 # Darcy friction factor (tight bundle; refine later)
  []

  [outlet]
    type = Outlet1Phase
    input = 'pipe:out'
    p = ${p_out}
  []

  # receives the clad wall temperature from the solid (variable named T_wall);
  # imposes q'' = Hw * (T_wall - T_fluid) on the fluid energy equation
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
  num_steps = 400
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
  [T_wall_avg]
    type = ElementAverageValue
    variable = T_wall
    execute_on = 'INITIAL TIMESTEP_END'
  []
  [htc_avg]
    type = ElementAverageValue
    variable = Hw
    execute_on = 'INITIAL TIMESTEP_END'
  []
[]

[Outputs]
  [out]
    type = Exodus
    show = 'T T_wall Hw'
  []
  [csv]
    type = CSV
    file_base = mvp_nak
  []
[]

# =============================================================================
# SNAP-10A NaK coolant channel  --  THM sub-app (Layer 1, 3-D pin)
# =============================================================================
# Identical physics to mvp/thm.i, but the channel runs along z (the 3-D pin
# axis) instead of y, so orientation and the LayeredAverage direction are z.
# Launched automatically by solid_core.i (37 single-instance apps). SI units.
#
# UPGRADED July 21 2026 (uprate dossier A1/A2, per cardinal_validation/RUN_HERE.md):
#   A1  Fluid EOS = SimpleFluidProperties configured as a NaK-78 liquid (Foust/
#       Bomelburg 1972 props at the loop-mean T, plus a linear thermal_expansion so
#       density tracks the 755 -> 900 K span to <0.05%). This REPLACES an attempt to
#       use NaKFluidProperties directly: that class is a (p,T)-only incompressible
#       property library with NO sound speed, but THM's compressible FlowChannel1Phase
#       needs a complete (v,e) EOS (p_from_v_e, c_from_v_e, ...). A tabulated wrapper
#       cannot supply a sound speed the base class never computes. SimpleFluidProperties
#       is a complete EOS -- it is what this model ran on before A1, and matches how the
#       Cardinal openmc_fluid tutorial (IdealGas) and the MOOSE sodium THM case
#       (StiffenedGas) drive their fluids. See the July 2026 fluid-EOS research note.
#       density0 is the ZERO-T density, not the operating density; it is back-solved so
#       rho(T_mean) lands on NaK (the old block's 755.92 quietly gave ~640 kg/m3).
#   A2  Closures1PhaseSimple + constant f=0.02 + frozen Hw=5.01e4 ->
#       Closures1PhaseTHM with wall_ff_closure = cheng_todreas (tight-lattice
#       rod-bundle friction, P/D = 1.008) and wall_htc_closure = mikityuk
#       (liquid-metal rod-bundle Nusselt). The [ht] component's constant Hw is
#       REMOVED so the closure computes the wall HTC; the Hw aux/UserObject chain
#       below picks up the computed material property unchanged, so the solid
#       coupling now receives a physical, T- and flow-dependent htc.
# CASE FLOW (cardinal_validation/RUN_HERE.md): Case 1 (34 kWt) per-channel
# mdot = 0.0167541; Case 2 (79 kWt) mdot = 0.0197 (pump-coupled EOL flow).
# =============================================================================

T_in   = 755.37
mdot   = 0.0167541
p_out  = 4.0e5
A_flow = 9.530e-5
D_h    = 3.822e-3
P_hf   = 0.0997456
L      = 0.310515
n_ax   = 30

[GlobalParams]
  initial_p   = ${p_out}
  initial_vel = 0.233
  initial_T   = ${T_in}
  closures    = thm_closures
  fp          = nak
[]

[FluidProperties]
  # NaK-78 as a COMPLETE liquid EOS for THM. Foust/Bomelburg eutectic properties
  # evaluated at the per-case loop-mean temperature (nak78_properties.py).
  # thermal_expansion carries the density variation across the channel span, and
  # bulk_modulus supplies the sound speed the compressible flow solver requires
  # (~1150 m/s; Mach ~2e-4 at 0.23 m/s -- a numerical closure, not a physical
  # driver). Verified: density matches NaK to <0.05% over 755-900 K.
  # Case 1 (34 kWt, mean ~786.5 K) is shown. For Case 2 (79 kWt, mean ~826 K) use:
  #   density0 = 967.07   thermal_expansion = 3.149e-4   cp = cv = 872.37
  #   viscosity = 1.7914e-4   thermal_conductivity = 26.567
  [nak]
    type = SimpleFluidProperties
    density0             = 964.06      # ZERO-T ref; yields rho = 755.1 kg/m3 at 786.5 K
    thermal_expansion    = 3.111e-4    # NaK-78 beta at the loop mean (1/K)
    bulk_modulus         = 1.0e9       # sets sound speed ~1150 m/s (numerical closure)
    cp                   = 879.31
    cv                   = 879.31      # cp=cv for a liquid; e = cv*T governs the T rise
    viscosity            = 1.8758e-4
    thermal_conductivity = 26.260
  []
[]

[Closures]
  [thm_closures]
    type = Closures1PhaseTHM
    wall_ff_closure  = cheng_todreas   # A2: tight-lattice rod-bundle friction
    wall_htc_closure = mikityuk        # A2: liquid-metal rod-bundle Nusselt
  []
[]

[AuxVariables]
  [Hw]
    family = MONOMIAL
    order  = CONSTANT
    block  = pipe
    # Seed with the legacy constant so the FIRST solid<->THM exchange sees a
    # physical htc instead of an uninitialized 0 (the aux kernel overwrites it
    # with the mikityuk value from the first timestep_end onward).
    initial_condition = 5.01e4
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
    # A2 bundle geometry for the cheng_todreas / mikityuk closures.
    # NO constant f: the closure supplies the friction factor.
    # NOTE (checked vs FlowChannel1Phase docs): bundle_array / subchannel_type are
    # NOT FlowChannel1Phase parameters; the closure derives them from the two below.
    heat_transfer_geom = HEX_ROD_BUNDLE
    PoD = 1.008
    pipe_location = INTERIOR
  []
  [outlet]
    type = Outlet1Phase
    input = 'pipe:out'
    p = ${p_out}
  []
  [ht]
    type = HeatTransferFromExternalAppTemperature1Phase
    flow_channel = pipe
    # NO constant Hw: the mikityuk closure computes the wall HTC (material
    # property 'Hw'), which the Hw aux -> Hw_uo chain hands to the solid.
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
  num_steps = 100000        # high cap; the parent's window bounds each call
  # steady_state_detection REMOVED (July 21 2026): it paid off when the solid took
  # one dt = 100 step (it cut ~400 sub-cycles per call). Under the warm-started
  # parent the solid steps dt = 1.0, so each call sub-cycles only ~4 THM steps,
  # there is nothing left to save, and a sub-app that declares itself steady and
  # stops advancing can fail later parent steps outright (abort_on_solve_fail).
  # The channel now integrates toward steady ACROSS outer steps, matching the
  # warm-start philosophy; convergence is judged at the parent (k, max_fuel_T,
  # heat closure), not inside each THM call.
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

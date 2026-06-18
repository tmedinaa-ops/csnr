# =============================================================================
# Layer 2: OpenMC-MAIN coupled driver, full 37-pin core  (restructured June 2026)
# =============================================================================
# WHY THIS FILE: the old layout made the SOLID the main app with OpenMC and THM
# both as timestep_end sub-apps. That is a fully-lagged Jacobi sweep on a stiff
# conjugate interface, so it crawled to steady (~250+ coupling steps, ~3 h)
# regardless of the solid time derivative or the source relaxation -- confirmed by a
# run that sat at the same state as the old transient at iteration 25.
#
# This is the documented Cardinal pattern (gas_assembly tutorial): OpenMC is the
# MAIN app, the solid conduction is a sub-app, and the cheap solid<->THM conjugate
# loop is converged INSIDE the solid sub-app while the expensive OpenMC eigenvalue
# solve fires only once per outer step. Converges in ~10-15 OpenMC solves.
#
#   OpenMC (THIS, main) --power--> solid_core.i (sub) --T_wall--> thm.i (37 chans)
#          <-- temperature --             <-- T_fluid / htc --
#
# RUN (from this dir; moose env; model.xml present; OPENMC_CROSS_SECTIONS set):
#   cardinal-opt -i openmc.i
#   mpiexec -np 10 ~/cardinal/cardinal-opt -i openmc.i --n-threads=2
#
# PREREQS (unchanged): snap.py model.xml (fig12_test, FLAG_FINE_DISCRETIZATION=True,
# FLAG_DISTRIB_COOLANT=True), core37.e, ENDF/B-VIII.0 data. Only the app hierarchy
# moved; the solid + THM physics are the validated Layer 1 pattern.
# =============================================================================

[Mesh]
  # same 37-pin mesh the solid uses, so OpenMC cells map to the conduction elements
  [core]
    type = FileMeshGenerator
    file = core37.e
  []
[]

[AuxVariables]
  [cell_temperature]    # what OpenMC actually applied (QA the feedback)
    family = MONOMIAL
    order = CONSTANT
  []
  [material_id]
    family = MONOMIAL
    order = CONSTANT
  []
  # Do NOT add cell_id / cell_instance here: this Cardinal build adds them
  # automatically (a manual copy collides and aborts). They land in openmc_out.e for
  # free. RADIAL DIAGNOSTIC: color core37 by cell_id (37 distinct values across the
  # pins = per-pin resolution OK) and by heat_source (the actual radial peaking).
[]

[AuxKernels]
  [cell_temperature]
    type = CellTemperatureAux
    variable = cell_temperature
    execute_on = timestep_end
  []
  [material_id]
    type = CellMaterialIDAux
    variable = material_id
  []
[]

[Problem]
  type = OpenMCCellAverageProblem
  verbose = true

  # Modest per-solve statistics: with constant relaxation the coupled solve converges
  # in ~10-15 OpenMC solves, so 20k/batch is plenty for the march. Take the final k
  # and source from ONE high-statistics STANDALONE solve at the converged temperature.
  particles = 20000

  # FULL CORE thermal power. Set the operating point you want here (34 kWt arXiv/shield;
  # FS-3 endurance ~40; the 10A/2 uprate toward 50). NaK rise scales as P / 545 W/K.
  power = 34000.0

  scaling = 100.0          # MOOSE mesh in meters -> OpenMC cm

  # 37 distinct pin universes live at coordinate level 1 (verified vs the Cardinal
  # lattice regression test). Do NOT raise to 2. If per-pin power looks flat, check
  # the cell_id AuxVar (must show 37 distinct values), not this.
  cell_level = 1

  temperature_blocks = 'fuel coating clad'   # solid T fed into these OpenMC cells
  check_equal_mapped_tally_volumes = true    # (cannot catch a 1-cell collapse; cell_id does)

  # Constant 0.5 relaxation damps the source feedback so the outer Picard converges
  # without oscillating -- the gas_assembly setting.
  relaxation = constant
  relaxation_factor = 0.5

  [Tallies]
    [heat_source]
      type = CellTally
      block = 'fuel'
      name = heat_source
    []
  []
[]

[MultiApps]
  [solid]
    type = FullSolveMultiApp
    input_files = 'solid_core.i'
    execute_on = timestep_end
    # FullSolve: each outer OpenMC step, run solid_core.i to completion so its
    # internal fixed-point loop converges the solid<->THM conjugate against the
    # frozen OpenMC heat source, then hand temperature back. This is what keeps
    # OpenMC to ONE eigenvalue solve per outer step.
  []
[]

[Transfers]
  [heat_to_solid]
    type = MultiAppGeneralFieldShapeEvaluationTransfer
    to_multi_app = solid
    source_variable = heat_source
    variable = power
    from_postprocessors_to_be_preserved = heat_source
    to_postprocessors_to_be_preserved = power_in
  []
  [temp_from_solid]
    type = MultiAppGeneralFieldShapeEvaluationTransfer
    from_multi_app = solid
    source_variable = T
    variable = temp
  []
[]

[Executioner]
  # Outer Picard loop = the OpenMC <-> temperature feedback. One OpenMC eigenvalue
  # solve per step; the source relaxation (0.5, above) damps it to steady over
  # ~10-15 steps, exactly like gas_assembly's num_steps=10. dt is just the step
  # counter (OpenMC has no time physics). Watch k and the solid's max_fuel_T
  # plateau over these steps; raise num_steps if either is still drifting at 15.
  type = Transient
  dt = 1.0
  num_steps = 15
[]

[Postprocessors]
  [heat_source]
    type = ElementIntegralVariablePostprocessor
    variable = heat_source
    block = 'fuel'
    execute_on = 'transfer initial timestep_end'
  []
  [k]
    type = KEigenvalue
    execute_on = 'timestep_end'
  []
[]

[Outputs]
  exodus = true
  csv = true               # openmc_out.csv: heat_source and k per outer step
[]

# TODO on the machine:
#  1. If KEigenvalue errors (name varies by Cardinal version), drop that PP; k also
#     prints to the console each outer step.
#  2. Watch the console: k should sit near 1.0009 and the solid's max_fuel_T should
#     plateau within ~10 outer steps. If max_fuel_T is still climbing at step 15, the
#     conjugate inner loop (solid_core.i fixed_point_max_its) needs more iterations,
#     not more outer steps.

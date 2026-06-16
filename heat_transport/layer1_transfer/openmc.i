# =============================================================================
# OpenMC neutronics wrapper  --  sub-app (Layer 1 two-way)
# =============================================================================
# Wraps the SNAP-10A unit pin (snap_unit_pin.py) as a Cardinal sub-app of the
# solid conduction hub (solid_3d.i). It tallies the kappa-fission heat source
# (sent up to the solid as 'heat_source') and receives the solid temperature
# back (Cardinal applies it to the OpenMC cells), closing the two-way loop.
#
# Pattern verified against:
#   cardinal test/tests/neutronics/feedback/lattice/openmc.i
#   cardinal tutorials/gas_compact_multiphysics (temperature feedback + scaling)
#
# Prereqs: run  python snap_unit_pin.py  (writes geometry/materials/settings.xml)
# and generate pin3d.e (see make_mesh.i). Cardinal launches this from solid_3d.i.
# =============================================================================

[Mesh]
  # same mesh the solid uses, so OpenMC cells map 1:1 to the conduction elements
  [pin]
    type = FileMeshGenerator
    file = pin3d.e
  []
[]

[AuxVariables]
  [cell_temperature]    # what OpenMC actually applied (for visualization/QA)
    family = MONOMIAL
    order = CONSTANT
  []
  [material_id]
    family = MONOMIAL
    order = CONSTANT
  []
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

  # per-pin power for the reflected unit cell = 34 kWt / 37
  power = 918.92

  # MOOSE mesh is in meters; OpenMC is in cm -> multiply MOOSE coords by 100
  scaling = 100.0

  # temperature feedback: take solid T on these blocks into OpenMC's cells
  temperature_blocks = 'fuel coating clad'
  cell_level = 0

  # Robbins-Monro relaxation stabilizes the Picard heat-source updates
  relaxation = robbins_monro

  [Tallies]
    [heat_source]
      type = CellTally
      block = 'fuel'
      name = heat_source
    []
  []
[]

[Executioner]
  # Large dt ON PURPOSE. This sub-app is NOT sub_cycling, so without this MOOSE
  # caps the master (solid_3d.i) time step to the sub-app's dt. The MOOSE default
  # dt is 1.0, which was silently clamping the whole coupled run to dt=1 (60 steps
  # = 60 s, far short of the ~1500 s steady target) no matter what solid_3d.i set.
  # OpenMC has no time physics here: one k-eigenvalue solve per master step, so a
  # huge dt just means "never constrain the master clock."
  type = Transient
  dt = 1e6
[]

[Postprocessors]
  [heat_source]      # integral used to conserve power on transfer to the solid
    type = ElementIntegralVariablePostprocessor
    variable = heat_source
    block = 'fuel'
    execute_on = 'transfer initial timestep_end'
  []
[]

[Outputs]
  exodus = true
[]

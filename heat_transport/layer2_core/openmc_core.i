# =============================================================================
# Layer 2: OpenMC neutronics sub-app for the full 37-pin core  (UNTESTED DRAFT)
# =============================================================================
# Same role as Layer 1's openmc.i, but the OpenMC model is the REAL snap.py core
# (HexLattice, 37 pins, vessel, Be reflector, drums) instead of the unit pin.
# Launched by solid_core.i. Hands the kappa-fission heat up to the solid and reads
# the solid temperature back.
#
# PREREQS (on your machine):
#  - Build snap.py's model.xml with the FEEDBACK flags ON, per the snap repo
#    CLAUDE.md: FLAG_FINE_DISCRETIZATION = True and FLAG_DISTRIB_COOLANT = True
#    (axial slicing + per-cell coolant clones, so OpenMC can take distributed
#    temperature and give an axial heat shape). Case fig12_test (783.15 K, NaK,
#    37 fresh SCA-4, drums at 94 deg) is the operating-condition coupled config.
#        cd ~/Documents/snap && conda activate openmc-env
#        # edit snap.py: FLAG_FINE_DISCRETIZATION=True, FLAG_DISTRIB_COOLANT=True
#        python snap.py fig12_test .
#    Confirm "Lattice mapping check OK (37/37)" prints.
#  - Put that model.xml where Cardinal runs (copy/symlink into this folder, or run
#    from the snap dir). Cardinal/OpenMC reads model.xml from the run directory.
#  - Same ENDF/B-VIII.0 data (OPENMC_CROSS_SECTIONS) as everything else.
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

  # Override the snap model.xml statistics for the COUPLED march. model.xml is built
  # for standalone production criticality (1,000,000 particles/batch), which is a
  # memory spike and ruinously slow when OpenMC re-solves every coupling step. The
  # relaxed march (robbins_monro) averages the source across the ~280 steps, so each
  # solve needs only modest statistics. 20k/batch is plenty here; take the final
  # reported k and source from one high-statistics STANDALONE solve at the converged
  # temperature, not from the march. (If it is still slow, also cut the batch count.)
  particles = 20000

  # FULL CORE power, not per-pin. All 37 pins are present now.
  # (34 kWt is the arXiv / shield design point; FS-3 endurance ran 39.5-40 kWt.
  #  If you switch power, change it here AND in the validation targets.)
  power = 34000.0

  # MOOSE mesh is in meters; OpenMC (snap.py) is in cm -> x100
  scaling = 100.0

  # cell_level: the snap geometry nests root -> cell_core(fill=HexLattice) ->
  # fuel_p{i} universes -> rod/tube/coolant cells. The pin cells therefore sit
  # one universe level below the lattice container. START AT 1 and verify; if the
  # mapping is wrong, try 2. The volume check below is what catches a wrong level.
  cell_level = 1

  # take the solid T on these blocks into the matching OpenMC cells
  temperature_blocks = 'fuel coating clad'

  # CATCH MAPPING DISTORTION: aborts if mapped tally volumes are uneven, which is
  # the usual symptom of a wrong cell_level or a mesh/geometry misalignment.
  check_equal_mapped_tally_volumes = true

  # Robbins-Monro relaxes the Picard heat-source updates across steps (same as L1)
  relaxation = robbins_monro

  [Tallies]
    [heat_source]
      type = CellTally
      block = 'fuel'        # tally kappa-fission on every pin's fuel cells
      name = heat_source
    []
  []
[]

[Executioner]
  # Large dt ON PURPOSE: this sub-app is not sub_cycling and OpenMC has no time
  # physics (one k-eigenvalue solve per master step), so a huge dt stops it
  # clamping the master clock. (This is the fix that bit Layer 1; keep it.)
  type = Transient
  dt = 1e6
[]

[Postprocessors]
  [heat_source]       # integral used to conserve power on transfer to the solid
    type = ElementIntegralVariablePostprocessor
    variable = heat_source
    block = 'fuel'
    execute_on = 'transfer initial timestep_end'
  []
  [k]                 # watch the coupled eigenvalue; should sit near 1.00086
    type = KEigenvalue
    execute_on = 'timestep_end'
  []
[]

[Outputs]
  exodus = true
[]

# TODO on the machine:
#  1. cell_level: 1 is the documented guess. If check_equal_mapped_tally_volumes
#     trips or mapping count != 37 fuel regions, bump to 2 and re-run. This is the
#     single most likely thing to need iteration.
#  2. The coupled k should land near the standalone fig12_test value 1.00086. A
#     large drift after coupling points at the temperature interpolation range or
#     the cell-to-element mapping, not the geometry (per ROADMAP validation note).
#  3. KEigenvalue postprocessor name can vary by Cardinal version; if it errors,
#     drop it (k also prints to the console) or use the documented current name.

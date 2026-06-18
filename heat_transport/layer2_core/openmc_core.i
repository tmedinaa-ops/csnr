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
  # RADIAL DIAGNOSTIC (added June 2026). These two settle the flat-power question in
  # one run: open solid_core_out_openmc0.e in ParaView and color core37 by cell_id.
  # 37 distinct values across the 37 pins = pins resolved as distinct cells (per-pin
  # power is real). One uniform value = the tally is collapsing (then revisit the
  # model.xml / cell_level). Also color by heat_source to see the actual peaking.
  [cell_id]
    family = MONOMIAL
    order = CONSTANT
  []
  [cell_instance]
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
  [cell_id]
    type = CellIDAux
    variable = cell_id
  []
  [cell_instance]
    type = CellInstanceAux
    variable = cell_instance
  []
[]

[Problem]
  type = OpenMCCellAverageProblem
  verbose = true

  # Override the snap model.xml statistics for the COUPLED march. model.xml is built
  # for standalone production criticality (1,000,000 particles/batch), which is a
  # memory spike and ruinously slow when OpenMC re-solves every coupling step. With
  # constant relaxation the coupled solve converges in ~10-25 fixed-point iterations
  # (one OpenMC solve each), so each solve needs only modest statistics. 20k/batch is
  # plenty here; take the final reported k and source from one high-statistics
  # STANDALONE solve at the converged temperature, not from the march.
  particles = 20000

  # FULL CORE power, not per-pin. All 37 pins are present now.
  # (34 kWt is the arXiv / shield design point; FS-3 endurance ran 39.5-40 kWt.
  #  If you switch power, change it here AND in the validation targets.)
  power = 34000.0

  # MOOSE mesh is in meters; OpenMC (snap.py) is in cm -> x100
  scaling = 100.0

  # cell_level: the snap geometry nests root -> cell_core(fill=HexLattice) ->
  # fuel_p{i} universes -> rod/tube/coolant cells. cell_level = 1 is CORRECT and is
  # verified against the Cardinal lattice regression test (test/tests/neutronics/
  # feedback/lattice uses cell_level=1 for exactly this root->cell(fill=lattice)->
  # pin-universe nesting): level 1 is where the 37 distinct pin universes/cells live.
  # Do NOT raise to 2 (that resolves SUB-pin cells and needs a finer mesh). If the
  # per-pin power still looks flat, the cause is NOT here: check the cell_id AuxVar
  # (must show 37 distinct values) and the THM partition. The volume check below can
  # NOT catch a collapse to one cell (one bin = trivially equal volumes), so cell_id
  # is the real diagnostic. Ref: cardinal.cels.anl.gov CellTally / pincell tutorial.
  cell_level = 1

  # take the solid T on these blocks into the matching OpenMC cells
  temperature_blocks = 'fuel coating clad'

  # CATCH MAPPING DISTORTION: aborts if mapped tally volumes are uneven, which is
  # the usual symptom of a wrong cell_level or a mesh/geometry misalignment.
  check_equal_mapped_tally_volumes = true

  # Relaxation damps the Picard heat-source updates so the coupled solve converges
  # without oscillating. Constant 0.5 is what the Cardinal gas_assembly tutorial (the
  # OpenMC+solid+THM analog of this model) uses; it converges in ~6-10 iterations and
  # beats robbins_monro (1/n averaging) for a short fixed-iteration march. The doc
  # calls 0.5 "necessary to accelerate the fixed point iterations ... otherwise
  # oscillations occur."
  relaxation = constant
  relaxation_factor = 0.5

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

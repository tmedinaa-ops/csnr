# =============================================================================
# 3-D single-pin mesh for Layer 1  --  PC (uprated ~30k-DOF) version
# =============================================================================
# Build:  cardinal-opt -i make_mesh.i --mesh-only pin3d.e
# Then inspect pin3d.e in ParaView/Peacock before coupling.
#
# This is the heavier mesh for the 20-core PC. num_sectors 8->12 and
# rings '4 1 1'->'16 2 2' refine the cross section so the conduction solve has
# ~30k degrees of freedom (48 azimuthal x 20 radial x 31 axial nodes ~= 3.0e4).
# Axial layers stay at 30 so thm.i and the CoupledHeatTransfers (both n_ax=30)
# are untouched. The Mac/two_way mesh stays at the lighter validated 8 / '4 1 1'.
#
# Honest note: for THIS single pin the source is flat (k_inf unit cell), so the
# temperature field is already mesh-converged at the lighter resolution. 30k DOF
# here is a throughput/scaling exercise to load the bigger machine, not added
# physics fidelity. The real DOF payoff is Layer 2 (the 37-pin core with real
# radial + axial peaking), where this resolution per pin actually buys accuracy.
#
# MUST regenerate pin3d.e after this change; the prebuilt pin3d.e in the bundle
# is the old coarse mesh and will be used silently if you skip the --mesh-only step.
#
# Geometry in SI (m); openmc.i uses scaling=100 to bridge to OpenMC's cm.
# =============================================================================

r_fuel = 0.0153924
r_coat = 0.0156210
r_clad = 0.0158750
L      = 0.310515
n_ax   = 30

[Mesh]
  # 2-D cross section: concentric rings fuel | coating | clad (no coolant ring;
  # the NaK is the THM 1-D channel, not part of the solid mesh)
  [xs]
    type = ConcentricCircleMeshGenerator
    num_sectors = 12              # per quadrant -> 48 azimuthal sectors
    radii = '${r_fuel} ${r_coat} ${r_clad}'
    rings = '16 2 2'             # 20 radial divisions total (fuel 16, coat 2, clad 2)
    has_outer_square = false
    preserve_volumes = true
    portion = full
  []
  # extrude to a 3-D pin along z
  [pin3d]
    type = AdvancedExtruderGenerator
    input = xs
    direction = '0 0 1'
    heights = '${L}'
    num_layers = '${n_ax}'
  []
  # name the three radial regions (ConcentricCircle numbers them 1,2,3 inward-out)
  [names]
    type = RenameBlockGenerator
    input = pin3d
    old_block = '1 2 3'
    new_block = 'fuel coating clad'
  []
  # The clad-NaK interface is the sideset 'outer' from ConcentricCircleMeshGenerator
  # (the outer cylindrical surface). solid_3d.i couples on 'outer'. Do NOT build a
  # radius-based sideset: a ParsedGenerateSideset by radius over-selects internal
  # clad faces.
  # axial end sidesets
  [bottom]
    type = ParsedGenerateSideset
    input = names
    combinatorial_geometry = 'z < 1e-6'
    normal = '0 0 -1'
    new_sideset_name = 'bottom'
  []
  [top]
    type = ParsedGenerateSideset
    input = bottom
    combinatorial_geometry = 'z > ${fparse L - 1e-6}'
    normal = '0 0 1'
    new_sideset_name = 'top'
  []
[]

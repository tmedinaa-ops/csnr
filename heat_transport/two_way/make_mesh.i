# =============================================================================
# 3-D single-pin mesh for Layer 1  (generate once, then both apps read pin3d.e)
# =============================================================================
# Build:  cardinal-opt -i make_mesh.i --mesh-only pin3d.e
# Then inspect pin3d.e in ParaView/Peacock before coupling.
#
# Mesh generation is the ONE block in Layer 1 to verify interactively, because
# generator boundary-naming varies a little by MOOSE version. If
# ConcentricCircleMeshGenerator behaves differently in your build, the reactor
# module's PolygonConcentricCircleMeshGenerator (compiled into Cardinal) is the
# robust purpose-built alternative for a fuel pin.
#
# Geometry in SI (m) so the conduction solve is SI; openmc.i uses scaling=100
# to bridge to OpenMC's cm.
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
    num_sectors = 8
    radii = '${r_fuel} ${r_coat} ${r_clad}'
    rings = '4 1 1'
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
  # The clad-NaK interface is already provided by ConcentricCircleMeshGenerator
  # as the sideset 'outer' (the outer cylindrical surface). solid_3d.i couples on
  # 'outer'. Do NOT build a radius-based sideset here: a ParsedGenerateSideset by
  # radius over-selects internal clad faces (it picked 2880 vs the true 960).
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

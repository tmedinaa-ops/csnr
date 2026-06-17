# =============================================================================
# Layer 2: 37-pin SNAP-10A core conduction mesh  (UNTESTED DRAFT)
# =============================================================================
# Build:  cardinal-opt -i make_core_mesh.i --mesh-only core37.e
# Then INSPECT core37.e in Peacock/ParaView before any coupled run.
#
# Strategy: reuse the validated single-pin cross-section (the same
# ConcentricCircleMeshGenerator that Layer 1's make_mesh.i uses, fuel|coating|clad
# rings, no coolant ring) and place 37 copies at the exact snap.py fuel positions
# with CombinerGenerator, then extrude to 3-D. The pins are separate solid bodies;
# they are NOT thermally connected through the mesh, which is correct: the only
# pin-to-pin coupling is through the NaK, and THM carries that. The NaK is the 1-D
# THM channel, never a solid block here.
#
# Why this over the reactor module (PolygonConcentricCircle + PatternedHex): that
# is the cleaner intended path (see ROADMAP_full_core.md), but its parameter names
# and hex orientation vary by MOOSE version and would be the first thing to debug.
# CombinerGenerator reuses a cross-section we KNOW meshes and the exact coordinates
# below, so it is the lower-risk first build. Switch to the reactor module later if
# you want a single conformal hex mesh with the coolant background retained.
#
# ALIGNMENT (the thing to verify): these positions are snap.py's fuel_positions
# (cm) / 100 -> m, with lattice center X0 = (0,0), pitch 3.2004 cm, orientation
# 'y'. Cardinal maps OpenMC<->MOOSE by absolute position with scaling=100, so this
# mesh (m) x100 must land on snap.py's geometry (cm). If a coupled run shows
# mapping errors or check_equal_mapped_tally_volumes trips, the cross-section
# orientation or a global rotation is the suspect, fix it here or with an OpenMC
# mesh rotation, NOT by nudging individual pins.
#
# Geometry SI (m). r's and L match snap.py r1/r2/r3 and 2*h (= 31.0515 cm).
# =============================================================================

r_fuel = 0.0153924
r_coat = 0.0156210
r_clad = 0.0158750
L      = 0.310515
n_ax   = 30

[Mesh]
  # --- one pin cross-section: fuel | coating | clad rings (no coolant) ---------
  [pin_xs]
    type = ConcentricCircleMeshGenerator
    num_sectors = 8                       # per quadrant -> 32 azimuthal sectors
    radii = '${r_fuel} ${r_coat} ${r_clad}'
    rings = '4 1 1'                       # keep modest; refine after it runs
    has_outer_square = false
    preserve_volumes = true
    portion = full
  []
  # --- 37 copies at the snap.py fuel coordinates (cm/100 = m) ------------------
  # Order is snap.py pin 1..37. CombinerGenerator copies pin_xs to each position
  # and merges same-named sidesets, so all 37 clad surfaces share the 'outer'
  # sideset (the NaK coupling surface). See the README for how the 3 representative
  # THM channels pick out center/mid/edge pins by position.
  [core_xs]
    type = CombinerGenerator
    inputs = 'pin_xs'
    positions = '
       0.0000000  0.0000000  0
       0.0277162  0.0160020  0
       0.0000000  0.0320040  0
      -0.0277162  0.0160020  0
      -0.0277162 -0.0160020  0
       0.0000000 -0.0320040  0
       0.0277162 -0.0160020  0
       0.0554325  0.0000000  0
       0.0554325  0.0320040  0
       0.0277162  0.0480060  0
       0.0000000  0.0640080  0
      -0.0277162  0.0480060  0
      -0.0554325  0.0320040  0
      -0.0554325  0.0000000  0
      -0.0554325 -0.0320040  0
      -0.0277162 -0.0480060  0
       0.0000000 -0.0640080  0
       0.0277162 -0.0480060  0
       0.0554325 -0.0320040  0
       0.0831488  0.0160020  0
       0.0831488  0.0480060  0
       0.0554325  0.0640080  0
       0.0277162  0.0800100  0
       0.0000000  0.0960120  0
      -0.0277162  0.0800100  0
      -0.0554325  0.0640080  0
      -0.0831488  0.0480060  0
      -0.0831488  0.0160020  0
      -0.0831488 -0.0160020  0
      -0.0831488 -0.0480060  0
      -0.0554325 -0.0640080  0
      -0.0277162 -0.0800100  0
       0.0831488 -0.0160020  0
       0.0831488 -0.0480060  0
       0.0554325 -0.0640080  0
       0.0277162 -0.0800100  0
       0.0000000 -0.0960120  0'
  []
  # --- name the rings (ConcentricCircle numbers them 1,2,3 inward-out) ---------
  [names]
    type = RenameBlockGenerator
    input = core_xs
    old_block = '1 2 3'
    new_block = 'fuel coating clad'
  []
  # --- extrude the whole 37-pin cross-section to a 3-D core -------------------
  [core3d]
    type = AdvancedExtruderGenerator
    input = names
    direction = '0 0 1'
    heights = '${L}'
    num_layers = '${n_ax}'
  []
  # axial end sidesets (same recipe as Layer 1; 'outer' already exists from the
  # cross-section generator, do NOT rebuild it by radius)
  [bottom]
    type = ParsedGenerateSideset
    input = core3d
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
  # Center the core on z=0 to match snap.py, whose fuel spans +-L/2, NOT 0..L.
  # Cardinal maps OpenMC<->MOOSE by ABSOLUTE position, so without this the fuel
  # elements (z=0..0.31) map above the real core (z=-0.155..+0.155) and the
  # coupling garbles. Done LAST, after the bottom/top sidesets are assigned at
  # z=0 and z=L, so they stay attached to the right faces; the translate just
  # shifts the whole mesh down by L/2 = 0.1552575 m. (Single-pin got away without
  # this because snap_unit_pin.py also ran 0..L.)
  [center]
    type = TransformGenerator
    input = top
    transform = TRANSLATE
    vector_value = '0 0 -0.1552575'
  []
[]

# TODO on the machine:
#  1. Confirm CombinerGenerator preserves the 'outer' sideset name across all 37
#     copies (--mesh-only then check sidesets in Peacock). If it renames them, add
#     a RenameBoundaryGenerator.
#  2. For the 3-channel representative coupling you need to distinguish center/mid/
#     edge pins. Easiest: build 3 SEPARATE CombinerGenerator groups (center pin;
#     a ring-2 pin; a ring-3 pin) with distinct sideset names (outer_c/outer_m/
#     outer_e) and combine, so each representative channel couples to its own
#     surface. The single merged 'outer' above is right for the full 37-channel
#     build, not the 3-channel reduction.
#  3. Decide refinement: rings '4 1 1' / 8 sectors is the cheap start. The 30k-DOF
#     '16 2 2' / 12 used on the PC single pin is the per-pin target once it runs.

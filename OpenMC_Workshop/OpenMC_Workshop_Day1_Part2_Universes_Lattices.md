# OpenMC Workshop, Day 1 (Part 2) — Universes and Lattices

Second notebook of Day 1. The point is building geometry efficiently: define a
piece once and repeat it, instead of writing the same surfaces thousands of
times. Two concepts do the work — universes and lattices. The hex-lattice part
at the end maps directly onto the SNAP-10A core, so that gets its own section.

---

## 1. Universes

A universe is a collection of cells. You already make one implicitly: the root
universe handed to the geometry object. The new idea is that a universe can be
repeated at many locations, and a single universe can be filled into a cell, the
same way a material fills a cell.

Why it matters: a reactor is the same pin cell repeated ~19,000 times. Building
those seven surfaces 19,000 times is absurd. Define the pin once as a universe,
then place it everywhere.

### Filling a universe into a cell

When you fill a cell with a universe instead of a material, picture looking down
through the cell at the universe underneath. The cell's region clips what you
see. Fill an infinite four-quadrant universe into a cylinder and you see a
circular window onto those quadrants; everything outside the cylinder is
undefined because you never gave it a fill.

```python
big_cell = openmc.Cell(name="big cell")
big_cell.region = -big_cylinder      # the window
big_cell.fill = quadrant_universe    # what shows through it
```

### Translations and rotations — perspective, not the universe itself

A cell that contains a universe can carry a `rotation` and a `translation`, and
they move the *view* of the universe inside that cell, not the universe. Plot the
universe on its own afterward and it is unchanged.

```python
big_cell.rotation = [0, 0, 45]     # degrees about x, y, z
big_cell.translation = [0, 4.5, 0] # shift the view in x, y, z
```

It is like tilting and sliding your head while looking through the window. This
is a building tool: you can offset or rotate a repeated sub-geometry without
rebuilding its surfaces. (You can also move the dividing planes of the universe
itself by editing a surface's `x0`/`y0`, which genuinely changes the universe —
distinct from moving the cell's view.)

### Mixing materials

Aside shown here: `openmc.Material.mix_materials` blends materials by fraction
(atom percent by default), useful for homogenized regions.

```python
q1 = openmc.Material.mix_materials([mat_A, mat_B], [0.10, 0.90])  # 10/90 ao
```

## 2. Boundary conditions in nested geometry — the trap

Boundary conditions live on surfaces, always. When you nest a universe inside a
cell, a particle travels through several surfaces that originally belonged to
different pieces, and the boundary condition it meets is whichever surface it is
actually crossing.

Two consequences worth holding onto:

- Forgetting a boundary condition fails loudly here. An infinite universe alone
  is fine (a neutron crossing an internal interface just enters the next defined
  region). But once you trap that universe inside a cylinder with no boundary
  condition on the cylinder, a neutron reaching the cylinder finds undefined
  space and the run errors with "no boundary conditions were applied to any
  surfaces." That message is a useful hint that you nested something and forgot
  the outer surface.
- Nesting can build a physically odd effective shape. If the inner universe's
  own planes are reflective but the outer cylinder is vacuum, a particle is
  reflected at the inner planes and killed at the cylinder. The combination is a
  real, if strange, geometry. Trace the path a particle actually takes through
  the nested layers before trusting the boundary behavior.

## 3. Unvisited geometry still costs memory

Stuff an infinite universe inside something small and the parts a neutron never
reaches are not deleted. `model.geometry.get_all_materials()` and
`get_all_cells()` still list them. They are stored, so they cost memory even
though they are never visited. Negligible for a toy problem, but a real
consideration when geometry gets large. The lesson: clipping a universe hides
geometry from the particles, it does not remove it from the model.

## 4. Composite surfaces

Instead of hand-building four planes for a box, OpenMC has composite surfaces
that assemble the region for you. The rectangular prism is the common one.

```python
prism = openmc.model.RectangularPrism(width=9, height=9, boundary_type="vacuum")
region = -prism                      # inside the box
```

(There is also a hexagonal prism, and a general plane `Ax+By+Cz+D=0` for
arbitrary flat faces. More composite surfaces come up in the next notebook.)

---

## 5. Lattices

A lattice is a structured pattern of universes — the answer to "how do I place
hundreds of thousands of pins." Think of a PWR assembly map: each symbol is a
universe (fuel pin, guide tube, burnable-poison pin, instrument tube). You build
the few unique universes once, then lay them out on a grid.

Build order: make the universes, make the lattice, set its geometry, set which
universe goes in each position, and set an `outer` universe for everything beyond
the filled positions.

### Two helpers for building pin universes

List comprehension for the concentric cylinders (a one-line loop):

```python
radii = [0.21, 0.23, 0.24, 0.43, 0.44, 0.48]
cyls = [openmc.ZCylinder(r=r) for r in radii]
```

The `pin` helper, which takes the dividing surfaces and the fills and returns a
universe — much shorter than writing every half-space by hand:

```python
mats = [fuel, void, zirc, void, pyrex, zirc, water]   # void is None
burn = openmc.model.pin(cyls, mats)
```

### Rectangular lattice

```python
lat = openmc.RectLattice()
lat.lower_left = [-7*pitch/2, -7*pitch/2]   # position of the grid corner
lat.pitch = [pitch, pitch]                  # cell size in x, y
lat.universes = [[fuel_pin, fuel_pin],      # top row
                 [guide_tube, fuel_pin]]    # bottom row
lat.outer = all_water_universe              # fills everything outside the grid
```

`universes` is a list of lists, written the way the grid looks: first inner list
is the top row. The grid is conceptually infinite — you only specified the
pitch, never a size — so anything outside the positions you listed is undefined
and will crash a plot or a run unless you set `outer`. The `outer` universe is
stamped into every unfilled cell. You only strictly need it if neutrons could
reach that space before another surface clips them.

For a full 17x17 assembly, don't type 289 entries. Fill everything with one
universe, then overwrite the few special positions by index:

```python
lat.universes = [[fuel_pin]*17 for _ in range(17)]
for (i, j) in guide_tube_positions:
    lat.universes[i][j] = guide_tube
```

To use the lattice, fill it into a cell (often a snug bounding prism), and that
cell's universe becomes the geometry root. Make the bounding prism reflective for
an infinite-array boundary, vacuum to let neutrons leak.

### Lattices inside lattices

A cell filled with a lattice is itself a universe, so you can place a whole
assembly-lattice as one entry of a core-lattice. This is how real reactor
geometry is built with few lines: one lattice for the pin layout of an assembly,
another lattice repeating the assembly across the core.

---

## 6. Hexagonal lattices — the SNAP-10A-relevant part

Fast reactors and space reactors pack pins in a triangular pitch, so they use a
hex lattice, not a rectangular one. SNAP-10A's core is exactly this: 37 fuel
elements in a hexagonal array. The API differs from the rectangular case in a
few ways.

```python
hexlat = openmc.HexLattice()
hexlat.center = (0, 0)        # center, not lower_left (a corner makes no sense)
hexlat.pitch = [pitch]        # one pitch value (the rows can't be independently stretched in 2D)
hexlat.outer = all_water      # same outer concept
```

Filling it: `universes` is again a list of lists, but ordered ring by ring from
the outermost ring inward, each ring listed from a fixed starting position around
the hexagon. Use `show_indices` to see the numbering before you fill, because hex
indexing is not intuitive:

```python
print(openmc.HexLattice.show_indices(num_rings=3))
```

For three rings the counts are 12 (outer), 6 (middle), 1 (center):

```python
outer  = [guide_tube] + [fuel_pin]*11
middle = [guide_tube] + [fuel_pin]*5
center = [fuel_pin]
hexlat.universes = [outer, middle, center]
```

You can overwrite individual positions by `[ring, position]` index the same way
as the rectangular case. By default the hexagon is pointy-side up; set
`orientation = 'x'` (or apply a rotation) for flat-side up.

### Mapping to the SNAP-10A core

This is the construct for your core neutronics model. The pieces line up with the
base set:

- Fuel-element universe via `openmc.model.pin`, with the documented radii: fuel
  1.53924 cm, samarium-oxide coating outer 1.56210 cm, Hastelloy-N clad outer
  1.58750 cm, then NaK/coolant outside. That is three surfaces and four fills in
  one `pin` call, instead of hand-building the half-spaces.
- A `HexLattice` with `pitch = 3.20040` cm (the documented lattice pitch),
  centered at the origin. Counting rings: center 1 + ring 6 + ring 12 + ring 18
  = 37, so four rings exactly fill the 37-element core. Mind that the documented
  active length 31.0515 cm and rod length 31.623 cm set the axial planes.
- `outer` set to the beryllium reflector universe (the six internal Be reflectors
  fill the voids inside the 316 SS vessel), so the space outside the 37 pins is
  reflector, not void.
- The four external control drums are not lattice positions — they are separate
  cells/universes around the vessel, since their reactivity worth (~$4.80 coarse
  span) is what you would tally by rotating them.

Caveat consistent with Part 1: the pin cell is k-eigenvalue and so is the core
criticality model — but the *shielding* problem is still fixed-source. The
lattice machinery here is for the core (criticality, drum worth, power shape),
not the LiH shield, which is a single homogenized source region feeding a
cone/sphere shield geometry.

---

## 7. Gotchas from this session

- Re-running the very first import/setup cell is required if you reopened or
  reset the notebook ("no module named openmc" just means the kernel restarted).
- Plotting bigger than a lattice's filled extent crashes unless `outer` is set —
  the grid is infinite and the unfilled cells are undefined.
- `.` vs `_`: underscores are just part of a name (`hex_lattice`); the dot calls
  a method that the object's class defines (`hex_lattice.show_indices()`). A
  material has no `show_indices` because it is not a method that makes sense for
  a material. The available methods depend on the class.
- Clipping a universe or lattice inside a snug box hides the overflow from
  neutrons but keeps it in memory (Section 3).

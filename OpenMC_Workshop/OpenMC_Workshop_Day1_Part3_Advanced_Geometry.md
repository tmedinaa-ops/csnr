# OpenMC Workshop, Day 1 (Part 3) — Advanced Geometry and Visualization

Third notebook of Day 1. April flagged this whole section as optional — it is
convenience functions and performance tooling, not new physics. Two things in it
matter for your work: the composite surfaces and surface-from-points helpers
(useful for the shield geometry), and the performance lesson about how OpenMC
tracks particles across cells (useful for not building a slow core model). TRISO
is the worked example but is not your fuel form, so treat that part as general
OpenMC literacy. The visualization tools are worth knowing for report figures and
for debugging geometry.

---

## 1. Composite surfaces

A plain surface (`openmc.XPlane(3)`) is one surface; you take its `+`/`-` half
space. A composite surface looks and behaves the same way — you still take half
spaces of it — but under the hood OpenMC assembles several primitive surfaces for
you. This saves building a box or a hexagon plane by plane.

```python
prism = openmc.model.RectangularPrism(width=10, height=5)   # oriented in z by default
cell = openmc.Cell(region=-prism, fill=water)               # -prism is "inside"
```

Useful options and the other composites shown:

- `corner_radius` rounds the corners (OpenMC places cylinders there). Small values
  round gently; large values start to deform the shape into something circular.
- `openmc.model.HexagonalPrism(edge_length=2, corner_radius=...)` — argument is the
  side length of the hexagon. Pointy-side up by default; `orientation='x'` flips it.
- `openmc.model.IsogonalOctagon(center, r1, r2)` — r1 is the half-width across the
  flat parallel sides, r2 the diagonal. (April admitted she only ever uses octagons
  in workshops; included for completeness.)
- `openmc.model.RightCircularCylinder(center_base, height, radius, axis='z')` — the
  "trash can" finite cylinder in one surface instead of a cylinder plus two planes.
- `openmc.model.ConicalFrustum` — a truncated cone in one surface. April did not
  reach this one, but the docs list it, and it is the right primitive for the
  SNAP-10A shield body (see Section 7).
- `openmc.model.Vessel` — a cylinder with semi-ellipsoid top and bottom heads, the
  natural fit for a casing with domed ends. Also `OrthogonalBox`, `Polygon`,
  `RectangularParallelepiped`, and the one-sided cones (`ZConeOneSided`, etc.).

The same gotcha from earlier holds: even though a composite is one object, you
still need the `+`/`-` sign. A bare surface name is not a region; the sign is what
turns it into a half space.

## 2. Surfaces from points

When you know the points but not the equation coefficients, OpenMC solves for them.

```python
p = openmc.Plane.from_points((0,0,0), (1,1,0), (1,1,5))   # plane through 3 points
c = openmc.Cylinder.from_points((0,0,0), (1,1,0), r=3)    # axis through 2 points, radius
```

These let you orient a plane or cylinder arbitrarily in space, not just along x,
y, or z. The catch is the half spaces: for a general tilted plane, "positive" and
"negative" are no longer obvious, and you may have to plug a test point into the
surface equation to learn which side is which. This is exactly the surface type
you need for the SNAP-10A shield, whose frustum and heads are not axis-aligned
boxes — see Section 7.

## 3. Random sphere packing (TRISO)

TRISO is a particle fuel: tiny uranium-oxide/oxycarbide kernels wrapped in
protective layers (one is silicon carbide, which holds fission products in and
tolerates high temperature), then pressed into pebbles or compacts. Modeling it
means placing hundreds of randomly located coated spheres. Not your fuel form
(SNAP-10A is U-ZrH), but the packing and the performance lattice below are
general tools.

OpenMC samples positions by random sequential addition — pick a random point in
the container, accept it if no existing sphere is within one diameter, repeat.
This caps how dense you can pack before it fails to place more, but it is fine for
moderate packing fractions.

```python
centers = openmc.model.pack_spheres(radius=1.0, region=-can, pf=0.30)  # or num_spheres=N
```

Build one particle as a universe of concentric layers using two helpers:

```python
radii = [0.5, 0.6, 0.7, 0.8]
spheres = [openmc.Sphere(r=r) for r in radii]            # list comprehension
regions = openmc.model.subdivide(spheres)                # N surfaces -> N+1 regions
particle = openmc.Universe()
for region, mat in zip(regions, layer_materials):
    particle.add_cell(openmc.Cell(region=region, fill=mat))
```

`subdivide` returns the regions between successive surfaces (inside the first,
between each pair, outside the last). Place a particle at each packed center with
the TRISO helper, which makes one cell per particle and applies the translation:

```python
trisos = [openmc.model.TRISO(radii[-1], particle, c) for c in centers]
```

The matrix (graphite, say) is everything outside every particle — a Swiss-cheese
region built by intersecting the complements:

```python
background = openmc.Intersection(~t.region for t in trisos)
matrix_cell = openmc.Cell(region=background, fill=graphite)
```

## 4. The performance lesson — worth keeping even if you never touch TRISO

A geometry can be correct and still slow. Two facts about how OpenMC tracks
particles drive this, and both matter for the SNAP-10A core.

First: OpenMC stops a particle at every cell boundary, even when the same material
is on both sides. It does not check whether the material matches, because the
check itself costs more than just stopping. So splitting one cube of fuel into
four abutting cubes gives the same answer but a slower run — the particle now
halts at the internal seams for no reason.

Second: a cell that touches N neighbors forces an N-surface search when a particle
leaves it. The TRISO matrix touches all 449 particle cells, so a neutron exiting
the matrix makes OpenMC search 449 surfaces to find which particle it enters next.
The picture looks fine; the tracking is quadratic-ish.

The fix is a search lattice — a performance-only Cartesian grid overlaid on the
geometry so a particle only searches the few particles in its current grid cell
(maybe 7 instead of 449):

```python
lat = openmc.model.create_triso_lattice(
    trisos, lower_left, pitch, shape=(5,5,5), background=graphite)
```

Choosing the grid size is trial and error — a few particles per cell is the
target; too fine and the lattice lookup itself costs more than it saves. Tune it
by timing the run, since nothing about the physics changes.

The general principle: build structured repetition as lattices, not loose cells.
A reactor is a lattice of assemblies, each itself a lattice of pins; because the
lattice is structured, OpenMC knows exactly which neighbor a particle enters
(index 3,2 going negative-x means index 4,2) with no search at all. The "dumb"
version — hand-building every cylinder and plane on a shifted grid — works but
throws away that advantage.

## 5. Geometry visualization

Four ways to look at a model, in rough order of effort:

Slice plots, the default. `model.geometry.plot()`, `universe.plot()`, or
`cell.plot()` draw a 2D slice. Fast, and still the most useful while building.

The Plot object, for scripted/batch images. Set it up and run in geometry mode
(not transport):

```python
plot = openmc.Plot()
plot.width = (20, 20)
plot.origin = (0, 0, 0)
plot.pixels = (400, 400)
plot.color_by = 'material'        # or 'cell'
plot.filename = 'xy_slice'
model.plots = openmc.Plots([plot])
model.plot_geometry()             # throws a ray per pixel, records the material hit
```

Lower pixel counts throw fewer rays and coarsen the image. (Default output has
historically been .ppm; newer OpenMC writes .png. If your viewer cannot open a
.ppm, that is the cause — read it with matplotlib `imread`/`imshow` instead.)

Ray-trace plots, for 3D. A wireframe version draws black edges between chosen
cells from a camera angle (`openmc.WireframeRayTracePlot`, older name
`ProjectionPlot`), and a solid version shades it like a real body with opaque
domains (`openmc.SolidRayTracePlot`). Both take a camera position and a look-at
point. Loop the camera angle to make a rotating GIF. Nice for a report figure,
overkill for daily work.

openmc-plotter, the official interactive GUI. Not in the Colab; install it
yourself:

```bash
pip install openmc-plotter
openmc-plotter        # run in a folder containing your model.xml
```

This is where the Python-to-C++ boundary becomes visible: running OpenMC writes a
`model.xml` (the real C++ input, assembled from your Python), and the plotter
reads that. The GUI does interactive slices, color-by-material, hover-to-inspect
(material, density, temperature), and — the part that earns its keep — "enable
overlap coloring" to find geometry mistakes visually. Keep this in mind for
debugging the shield and core builds.

## 6. Take-home exercises (optional, she will email them)

1. Critical search: build a box of U-235 at a fixed density and find the side
   length that makes it critical. Automate it — loop, call OpenMC, read k from the
   statepoint (`with openmc.StatePoint(path) as sp: sp.keff`), and stop when k
   crosses 1.
2. Same idea, but vary the material and find which gives the smallest critical
   box.
3. Build a "cigar" geometry to set dimensions, then visualize it three ways: a
   slice plot, a Plot object, and the openmc-plotter (optionally a ray trace).

These are good reps. The critical-search loop in particular is the pattern you
would reuse to find the SNAP-10A control-drum angle that brings the core to
k = 1, so exercise 1 is more than busywork for your purposes.

---

## 7. What actually transfers to SNAP-10A

Directly useful:

- Composite surfaces and `from_points`. The LiH shield is a 6-degree truncated
  cone with a torispherical top head and a hemispherical lower head inside a
  316 SS casing — none of it axis-aligned boxes. The purpose-built composite
  surfaces fit it directly: `openmc.model.ConicalFrustum` for the 6-degree
  truncated body, `openmc.model.Vessel` (cylinder with semi-ellipsoid heads) for
  the casing with its torispherical top and hemispherical lower head, and
  `Plane.from_points` for any tilted cut. Fall back to a raw `openmc.ZCone` /
  `ZConeOneSided` and `openmc.Sphere` only if a head shape is not a clean
  semi-ellipsoid. Let OpenMC assemble the half spaces instead of hand-deriving
  them, and expect to test a point against the surface equation to get the cone's
  inside/outside right.
- The performance principle. Build the homogenized shield and the core as few
  cells as the geometry honestly needs. For the 37-element core, the hex lattice
  from Part 2 is the "smart" build; resist subdividing it into loose cells.
- openmc-plotter with overlap coloring, for debugging the shield/core geometry,
  and the ray-trace plots for figures in the report.

Not your problem:

- TRISO packing and the search lattice. SNAP-10A fuel is U-ZrH in clad elements,
  not coated particles, so `pack_spheres` / `create_triso_lattice` do not apply.
  Worth understanding only so the performance reasoning carries over.

One caution consistent with the earlier parts: the critical-search and
lattice tooling all live on the core criticality (eigenvalue) side. The shield
stays a fixed-source run over a homogenized source region. Same geometry language,
different solver setup.

---

## 8. Question left open in the room — searched answer

Asked in the workshop, answered vaguely; researched afterward, not from the
workshop.

### Does nuclear thermal propulsion use TRISO fuel? (April: "a strong consideration") [resolved]

A student asked whether nuclear thermal propulsion (NTP) uses TRISO; April said it
was "a strong consideration" but did not elaborate. Modern NTP fuel development
pursues two main families, and coated-particle (TRISO-type) ceramic fuel is one of
them. The legacy NERVA/Rover engines used graphite-matrix "composite" and (U,Zr)C
carbide fuels, not TRISO. Current US work splits between (1) coated-particle /
TRISO-derived ceramic fuels and (2) CERMET (ceramic-metal — e.g. UO2 or UN kernels
in a tungsten or molybdenum matrix). So April's "strong consideration" is right:
coated-particle fuel is an active NTP candidate, including in recent HALEU NTP and
DRACO-era programs. The hard part is the hot-hydrogen environment, which attacks
oxide kernels and demands robust coatings/cladding to retain fission products —
the same retention property that makes TRISO attractive to begin with.

Not your fuel form for SNAP-10A (U-ZrH), but relevant to the broader space-nuclear
and NEP work in the CSNR project.

Sources: [NASA NTRS, "Assessment of Coated Particle Fuels for Space Nuclear Thermal Propulsion"](https://ntrs.nasa.gov/api/citations/20230002635/downloads/20230002635.pdf); [National Academies, "Space Nuclear Propulsion for Human Mars Exploration," Ch. 2 (Nuclear Thermal Propulsion)](https://www.nationalacademies.org/read/25977/chapter/4).

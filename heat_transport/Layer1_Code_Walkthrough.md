# Layer 1 heat transport: code walkthrough

This explains every file that runs in the Layer 1 coupled model, block by block,
so you can study what each piece does and why. Layer 1 is one SNAP-10A fuel pin,
solved three ways at once: OpenMC computes where the fission heat is deposited,
MOOSE conducts that heat through the fuel/coating/clad, and the Thermal
Hydraulics Module (THM) carries it away in the flowing NaK. The number that comes
out, the NaK outlet temperature, is the hot-side input to the energy-conversion
models.

Read this next to the files in `two_way/`. The PC bundle in `layer1_transfer/` is
the same code with a finer mesh and a longer run script; the differences are
flagged where they matter.

## The big picture

The model is a star. One app is the center (the "parent" or "hub"), and the other
two hang off it as "sub-apps." The hub is the solid conduction solve. OpenMC and
THM are its sub-apps. The hub drives the clock and asks the sub-apps to solve when
it needs them.

```
        heat_source  -->                  T_wall, htc -->
  OpenMC  ----------------->  SOLID (hub)  ----------------->  THM (NaK)
 openmc.i  <-- temperature   solid_3d.i    <-- T_fluid, htc      thm.i
              (the parent that owns the time stepping)
```

The three exchanges:

- OpenMC tells the solid how much heat is deposited in the fuel at each location
  (`heat_source`, in W/m^3). The solid tells OpenMC its temperature, which slightly
  shifts the cross sections.
- The solid tells THM how hot the clad outer wall is. THM tells the solid the
  local NaK bulk temperature and the heat-transfer coefficient. From those the
  solid applies a convective cooling boundary on the clad surface.

Execution order when you launch a run:

1. `snap_unit_pin.py` (run once) writes the OpenMC model to `geometry.xml`,
   `materials.xml`, `settings.xml`.
2. `make_mesh.i` (run once) builds the 3-D mesh `pin3d.e`.
3. `run_layer1.sh` launches `cardinal-opt -i solid_3d.i`.
4. `solid_3d.i` starts, and as its sub-apps it launches `openmc.i` and `thm.i`.
5. They iterate together to steady state; results land in `solid_3d.csv` and
   `thm_nak.csv`.

Two unit conventions to keep straight: MOOSE works in SI (meters, kelvin), OpenMC
works in centimeters, and the bridge is `scaling = 100` set inside `openmc.i`.
Two conda environments: `openmc-env` builds the XMLs (step 1), `moose` runs
Cardinal (steps 2 onward).

---

## File 1: run_layer1.sh (the launcher)

A plain shell script whose only job is to run Cardinal with the right arguments
and capture the output, so a stray command-line flag can never sneak in.

```bash
cd "$(dirname "$0")"
CARDINAL="${CARDINAL:-$HOME/cardinal/cardinal-opt}"
NP="${NP:-10}"
NT="${NT:-2}"
```

`cd` to the script's own folder so the relative filenames inside the inputs
resolve. `CARDINAL` is the path to the compiled Cardinal executable, overridable
with an environment variable. `NP` is the number of MPI ranks (processes), `NT`
the number of OpenMP threads per rank; their product is the total core count
used. The `${VAR:-default}` form means "use VAR if set, otherwise the default."

```bash
if [ ! -f pin3d.e ] || [ make_mesh.i -nt pin3d.e ]; then
  "$CARDINAL" -i make_mesh.i --mesh-only pin3d.e || { echo "mesh generation failed"; exit 1; }
fi
```

(Bundle version only.) If the mesh is missing or `make_mesh.i` is newer than the
mesh, rebuild `pin3d.e` first. `--mesh-only` tells Cardinal to build the mesh and
stop, not run a simulation. This is what makes the 30k-DOF mesh change take effect
automatically.

```bash
rm -f solid_3d.csv thm_nak.csv run_layer1.log
{ ... ; mpiexec -np "$NP" "$CARDINAL" -i solid_3d.i --n-threads="$NT"; } 2>&1 | tee run_layer1.log
```

Delete stale outputs so you never read an old run by mistake, then launch
Cardinal on `solid_3d.i` across `NP` ranks with `NT` threads each. `2>&1 | tee
run_layer1.log` writes everything to the screen and to a log file at the same
time. Note there are no `Executioner/...` arguments on the line: every solver
setting comes from the input file, which is deliberate.

---

## File 2: snap_unit_pin.py (builds the OpenMC neutronics model)

Python that uses the OpenMC library to describe the pin's geometry and materials,
then writes them to XML. It is the only Python in the run, and it produces the
files OpenMC reads.

```python
R_FUEL = 1.53924   # cm
R_COAT = 1.56210
R_CLAD = 1.58750
PITCH  = 3.20040
L      = 31.0515
T0     = 783.15    # K, design-average NaK temperature
```

Geometry in centimeters (OpenMC's native unit) from the arXiv Table I. `T0` is the
uniform starting temperature everywhere.

```python
fuel = openmc.Material(name="U-ZrH fuel")
fuel.add_element("U", 0.10, "wo", enrichment=93.0)
fuel.add_element("Zr", 0.90 * 0.98262, "wo")
fuel.add_element("H",  0.90 * 0.01738, "wo")
fuel.set_density("g/cm3", 6.0)
fuel.add_s_alpha_beta("c_H_in_ZrH")
```

The fuel is uranium-zirconium hydride, 10 wt% uranium at 93% enrichment, the rest
ZrH(1.6). `add_s_alpha_beta("c_H_in_ZrH")` is important for neutronics: hydrogen
bound in a zirconium hydride lattice scatters neutrons differently than free
hydrogen, and this loads the thermal-scattering data that captures that. The
coating (`Sm2O3`), clad (`Hastelloy N`, a nickel alloy given by its element
fractions), and `NaK-78` coolant follow the same pattern. Every material gets
`temperature = T0` so OpenMC picks the right cross-section temperature initially.

```python
fuel_or = openmc.ZCylinder(r=R_FUEL)
coat_or = openmc.ZCylinder(r=R_COAT)
clad_or = openmc.ZCylinder(r=R_CLAD)
xmin = openmc.XPlane(-half, boundary_type="reflective")  # and xmax, ymin, ymax, zmin, zmax
```

Surfaces: three nested cylinders for the fuel/coating/clad radii, and six planes
forming a box around the pin. `reflective` boundaries mean a neutron hitting the
wall bounces straight back, which mathematically turns this single pin into an
infinite repeating lattice of identical pins. That is why the axial power here is
flat: an infinite lattice has no leakage to tilt it. The real tilted shape comes
later, at full core.

```python
fuel_cell = openmc.Cell(name="fuel", fill=fuel, region=-fuel_or & +zmin & -zmax)
# coat_cell, clad_cell, nak_cell similarly
root = openmc.Universe(cells=[fuel_cell, coat_cell, clad_cell, nak_cell])
geometry = openmc.Geometry(root)
```

Cells are regions of space filled with a material. `-fuel_or` means "inside the
fuel cylinder," `+clad_or` means "outside the clad cylinder," and `&` is
intersection. The four cells (fuel, coating, clad, NaK) make up the universe.
These cell names matter: Cardinal maps the MOOSE mesh blocks onto these cells by
position.

```python
settings.run_mode = "eigenvalue"
settings.particles = 20000
settings.batches   = 120
settings.inactive  = 30
settings.temperature = {"method": "interpolation", "range": (300.0, 1500.0), "default": T0}
model.export_to_xml()
```

`eigenvalue` mode solves the critical chain reaction (computes k and the fission
distribution). 20000 particles per batch, 120 batches with the first 30 discarded
(those "inactive" batches let the fission source settle before tallying). The
temperature block tells OpenMC to interpolate cross sections between data
temperatures over 300 to 1500 K, which is what lets the solid feed back a changing
temperature. `export_to_xml()` writes the three XML files.

---

## File 3: make_mesh.i (builds the MOOSE mesh)

A MOOSE input run once with `--mesh-only` to produce `pin3d.e`, the finite-element
mesh both the solid and OpenMC sub-app read. Building it separately means you can
inspect it before committing to a long run.

```
[xs]
  type = ConcentricCircleMeshGenerator
  num_sectors = 8
  radii = '${r_fuel} ${r_coat} ${r_clad}'
  rings = '4 1 1'
  has_outer_square = false
  preserve_volumes = true
[]
```

Builds the 2-D cross section: concentric rings of fuel, coating, and clad. `radii`
are the three outer radii; `rings` is how many element layers each region gets (4
in the fuel, 1 each in coating and clad). `num_sectors` is the azimuthal
resolution per quadrant, so 8 means 32 wedges around the full circle.
`preserve_volumes` nudges the faceted mesh so its area matches the true circle.
There is no coolant ring because the NaK is not part of the solid mesh; it lives
in THM as a 1-D channel. (In the PC bundle this block is `num_sectors = 12`,
`rings = '16 2 2'`, which raises the mesh to about 30k degrees of freedom.)

```
[pin3d]
  type = AdvancedExtruderGenerator
  input = xs
  heights = '${L}'
  num_layers = '${n_ax}'
[]
```

Takes the 2-D disk and extrudes it along z into a 3-D cylinder, 30 axial layers
over the 0.31 m active length. `n_ax = 30` must match the axial discretization in
`thm.i` and in the coupling block of `solid_3d.i`, because the wall and fluid are
exchanged layer by layer.

```
[names]
  type = RenameBlockGenerator
  old_block = '1 2 3'
  new_block = 'fuel coating clad'
[]
```

The circle generator numbers the regions 1, 2, 3 from the center out. This renames
them to `fuel`, `coating`, `clad` so the rest of the model can refer to them by
name. The `bottom` and `top` sidesets that follow tag the two end faces (used as
insulated boundaries). The clad outer surface is already provided by the circle
generator as the sideset `outer`, which is what the NaK couples to.

---

## File 4: solid_3d.i (the hub, the parent app)

The center of the star. It owns the temperature field, the time stepping, and the
coupling to both sub-apps. This is the file `cardinal-opt -i` is pointed at.

```
[Mesh]
  [pin]
    type = FileMeshGenerator
    file = pin3d.e
  []
[]
```

Load the mesh built by `make_mesh.i`.

```
[Variables]
  [T]
    initial_condition = 783.15
  []
[]
```

`T` is the one thing this app actually solves for: temperature at every mesh node.
It starts everywhere at 783.15 K. In MOOSE a "Variable" (as opposed to an
"AuxVariable" below) is a true unknown the nonlinear solver computes.

```
[AuxVariables]
  [power]      # filled by the transfer from OpenMC
  [T_fluid]    # filled by CoupledHeatTransfers from THM
  [htc]        # heat-transfer coefficient, from THM
[]
```

AuxVariables are fields the solver does not compute but that are supplied from
outside, here by the sub-app transfers. `power` is the volumetric heat from
OpenMC, `T_fluid` and `htc` are the NaK bulk temperature and heat-transfer
coefficient from THM. `MONOMIAL`/`CONSTANT` means one value per element (a
piecewise-constant field), which is how the transferred data arrives.

```
[Kernels]
  [conduction]  type = HeatConduction          variable = T
  [time]        type = HeatConductionTimeDerivative  variable = T
  [source]      type = CoupledForce  variable = T  v = power  block = fuel
[]
```

Kernels are the terms of the equation being solved, here the heat equation.
`HeatConduction` is the conduction term (heat spreading through the solid),
`HeatConductionTimeDerivative` is the rho*cp*dT/dt storage term (how the material
heats up over time), and `CoupledForce` injects the `power` AuxVariable as a heat
source, restricted to the `fuel` block. Together they say: stored heat change =
conduction + fission heating.

```
[CoupledHeatTransfers]
  [interface]
    boundary = 'outer'
    T = T   T_fluid = 'T_fluid'   T_wall = T_wall   htc = 'htc'
    multi_app = thm
    T_fluid_user_objects = 'T_uo'   htc_user_objects = 'Hw_uo'
    orientation = '0 0 1'   length = ${L}   n_elems = ${n_ax}
  []
[]
```

This action sets up the conjugate (two-way) heat exchange with the NaK on the clad
outer surface (`outer`). It builds the convective cooling boundary condition on
the solid and wires the transfers to and from the `thm` sub-app: it sends the wall
temperature down to THM and pulls the fluid temperature and heat-transfer
coefficient back, layer by layer along the pin axis (`n_elems = n_ax`). The NaK
temperature rise then comes out as a result rather than being assumed, which is
how the run checks that energy is conserved.

```
[MultiApps]
  [openmc]  type = TransientMultiApp  input_files = 'openmc.i'  execute_on = timestep_end
  [thm]     type = TransientMultiApp  input_files = 'thm.i'     execute_on = timestep_end  sub_cycling = true
[]
```

Declares the two sub-apps. Each is its own full MOOSE/Cardinal problem launched
from this parent. `execute_on = timestep_end` runs them as the parent advances.
`sub_cycling = true` on THM lets it take many small internal steps (its own dt is
0.25 s) to span one big parent step, which it needs because the fluid develops
fast. OpenMC has no `sub_cycling` and instead sets a huge dt inside `openmc.i`
(explained there): it solves once per parent step and must not constrain the
parent clock.

```
[Transfers]
  [heat_from_openmc]
    type = MultiAppGeneralFieldShapeEvaluationTransfer
    from_multi_app = openmc   source_variable = heat_source   variable = power
    from_postprocessors_to_be_preserved = heat_source   to_postprocessors_to_be_preserved = power_in
  []
  [temp_to_openmc]
    to_multi_app = openmc   source_variable = T   variable = temp
  []
[]
```

The actual data movement. `heat_from_openmc` brings OpenMC's `heat_source` field
up into the `power` AuxVariable, and the `..._preserved` pair guarantees the total
wattage is conserved through the interpolation (so `power_in` always integrates to
the 918.92 W OpenMC reports). `temp_to_openmc` sends the solid temperature down so
OpenMC can re-evaluate cross sections. The THM transfers are not here because the
`CoupledHeatTransfers` action created them already.

```
[Materials]
  [fuel_mat]     GenericConstantMaterial   k = 22.484
  [coating_mat]  GenericConstantMaterial   k = 1.729
  [clad_k]       PiecewiseLinearInterpolationMaterial  property = thermal_conductivity  variable = T
                 x = '300 ... 1100'   y = '10.99 ... 27.08'
  [clad_rhocp]   GenericConstantMaterial   density + specific_heat
[]
```

Material properties the kernels need. Fuel and coating conductivities are
constants (the literature gives no defensible temperature curve for either in this
band). The clad is the one with a real temperature dependence, so `clad_k` is a
table of k versus T (the ORNL Hastelloy N correlation) that the solver looks up
using the local `T`; `clad_rhocp` supplies the clad's density and specific heat
separately so there is no overlap. Only `thermal_conductivity` affects the steady
answer; density and specific heat only set how fast the model marches there. Full
sourcing is in `k_of_T_sources.md`.

```
[Executioner]
  type = Transient   scheme = bdf2
  dt = 25.0   num_steps = 40
  fixed_point_max_its = 20   fixed_point_rel_tol = 1e-4   fixed_point_abs_tol = 1e-6
  solve_type = NEWTON   petsc_options_value = ' lu'
[]
```

How the problem is advanced. It is a pseudo-transient: time-step toward steady
state. `bdf2` is the time-integration scheme, `dt = 25` s per step, up to 40 steps
(1000 s of model time). The three `fixed_point_*` lines are the tight-coupling
control: each time step iterates the OpenMC/solid/THM exchange up to 20 times
until the coupled solution stops changing by more than the tolerance, instead of
exchanging once and moving on. That is what makes the run settle promptly rather
than creep. `NEWTON` with an `lu` direct solve handles the nonlinear conduction
solve inside each iteration.

```
[Postprocessors]
  [power_in]    ElementIntegralVariablePostprocessor  variable = power  block = fuel
  [max_fuel_T]  ElementExtremeValue  variable = T  block = fuel  value_type = max
  [wall_T_avg]  SideAverageValue  variable = T  boundary = 'outer'
[]
```

Postprocessors reduce the fields to single numbers each step. `power_in` integrates
the heat source over the fuel (must equal 918.9 W, the normalization check),
`max_fuel_T` is the peak fuel temperature (the safety-relevant number, target near
832 K), and `wall_T_avg` is the average clad surface temperature.

```
[Outputs]
  exodus = true
  [csv]      type = CSV      file_base = solid_3d
  [console]  show = 'power_in max_fuel_T wall_T_avg'
[]
```

Write the full field result to `solid_3d_out.e` (for ParaView), the postprocessor
history to `solid_3d.csv` (the file you read to check the plateau), and print the
three postprocessors to the screen each step.

---

## File 5: openmc.i (the OpenMC neutronics sub-app)

Wraps the OpenMC model as a Cardinal sub-app. It tallies where heat is deposited
and accepts the temperature feedback. It does not own a mesh of its own physics;
it reuses the solid's mesh so the cell-to-element mapping is one to one.

```
[Mesh]
  [pin]  type = FileMeshGenerator  file = pin3d.e  []
[]
```

Same mesh as the solid, so OpenMC's cells map cleanly onto the conduction
elements.

```
[Problem]
  type = OpenMCCellAverageProblem
  power = 918.92
  scaling = 100.0
  temperature_blocks = 'fuel coating clad'
  cell_level = 0
  relaxation = robbins_monro
  [Tallies]
    [heat_source]  type = CellTally  block = 'fuel'  name = heat_source  []
  []
[]
```

This is the heart of the file and it replaces the normal MOOSE "solve" with an
OpenMC run. `power = 918.92` sets the absolute wattage the tallied heat shape is
normalized to (this is the magnitude; OpenMC only provides the shape, the recurring
SNAP rule). `scaling = 100` converts MOOSE meters to OpenMC centimeters.
`temperature_blocks` lists which blocks receive the temperature feedback, and
`cell_level = 0` tells Cardinal at what depth in the OpenMC geometry the mapped
cells live. `relaxation = robbins_monro` damps the statistical noise between
coupled iterations so the heat source converges smoothly. The `CellTally` named
`heat_source` measures the kappa-fission heat (recoverable fission energy) in the
fuel, which is what gets sent up to the solid.

```
[Executioner]
  type = Transient
  dt = 1e6
[]
```

The fix that unblocked the whole model. OpenMC has no time physics here, it does
one eigenvalue solve per parent step. Because this sub-app is not sub-cycling, a
small dt would clamp the parent's time step down to it (the MOOSE default is 1.0,
which silently forced the entire coupled run to dt=1). A huge dt means this sub-app
never constrains the parent clock.

The `[AuxKernels]` (`CellTemperatureAux`, `CellMaterialIDAux`) just expose, for
visualization, the temperature OpenMC actually applied and the material in each
cell. The `[Postprocessors]` integral of `heat_source` is the value the conserving
transfer in the parent uses.

---

## File 6: thm.i (the NaK coolant channel sub-app)

A 1-D model of the sodium-potassium coolant flowing past the pin, built with the
Thermal Hydraulics Module. It takes the clad wall temperature from the solid and
returns the bulk fluid temperature and heat-transfer coefficient.

```
T_in   = 755.37     # K inlet
mdot   = 0.0167541  # kg/s per channel
A_flow = 9.530e-5   # m^2 flow area
D_h    = 3.822e-3   # m hydraulic diameter
P_hf   = 0.0997456  # m heated perimeter
```

Per-channel flow conditions, sized so 37 of these channels reproduce the full core
flow. The inlet is the reactor inlet temperature; at steady the outlet should be
about 62 K higher.

```
[FluidProperties]
  [nak]
    type = SimpleFluidProperties
    density0 = 755.92   viscosity = 1.8835e-4   thermal_conductivity = 26.2345
    cp = 879.903   cv = 879.903
  []
[]
```

NaK-78 as a constant-property liquid metal, the values from the arXiv Table II.
"Simple" means the properties do not vary with temperature, which is good enough at
the design point and is the thing to upgrade for the off-design 14 kWe study.

```
[Components]
  [inlet]   type = InletMassFlowRateTemperature1Phase   m_dot = ${mdot}   T = ${T_in}
  [pipe]    type = FlowChannel1Phase   orientation = '0 0 1'   length = ${L}   n_elems = ${n_ax}   A = ${A_flow}   D_h = ${D_h}
  [outlet]  type = Outlet1Phase   p = ${p_out}
  [ht]      type = HeatTransferFromExternalAppTemperature1Phase   flow_channel = pipe   P_hf = ${P_hf}
[]
```

THM is built from "components." `inlet` fixes the incoming flow rate and
temperature, `pipe` is the flow channel itself (along z, 30 elements to match the
solid), `outlet` sets the exit pressure. `ht` is the connection back to the solid:
`HeatTransferFromExternalAppTemperature1Phase` means the wall temperature comes
from another app (the solid), and THM computes how much heat the fluid picks up
over the heated perimeter `P_hf`. The `[UserObjects]` (`T_uo`, `Hw_uo`) average the
fluid temperature and heat-transfer coefficient into the 30 axial layers that get
sent back up.

```
[Executioner]
  type = Transient   scheme = bdf2
  dt = 0.25   num_steps = 100000
[]
```

THM steps at 0.25 s. The big `num_steps` is just a high ceiling; the parent
controls the real total time through sub-cycling, so THM takes 100 of its 0.25 s
steps to fill each 25 s parent step. The fluid residence time in the channel is
about 1.3 s, so 0.25 s resolves it well.

```
[Outputs]
  [out]  type = Exodus  show = 'T T_wall Hw'
  [csv]  type = CSV  file_base = thm_nak
[]
```

Writes the fluid fields for ParaView and the inlet/outlet temperatures to
`thm_nak.csv`, whose last row gives the converged NaK outlet, the deliverable of
the whole run.

---

## How one time step actually executes

Putting it together, here is what happens in a single 25 s parent step with tight
coupling on:

1. The parent begins the step and enters its fixed-point (Picard) loop.
2. It runs the OpenMC sub-app: OpenMC does an eigenvalue solve at the current
   temperature and produces the heat-source shape, normalized to 918.92 W.
3. That heat is transferred up into `power`, conserving the total.
4. The solid solves the heat equation for `T` with that source and the current NaK
   boundary, using Newton iterations.
5. The new wall temperature goes to THM; THM sub-cycles its 0.25 s steps across
   the 25 s and returns the NaK temperature and heat-transfer coefficient.
6. The parent checks whether `T` and the coupled fields changed less than the
   fixed-point tolerance. If not, it loops back to step 2 with the updated
   temperature; if yes, the step is converged and the clock advances 25 s.
7. The three postprocessors are written to `solid_3d.csv`, the NaK outlet to
   `thm_nak.csv`.

The temperatures rise over successive steps until the heat leaving in the NaK
equals the heat deposited (918.9 W). At that point `max_fuel_T` and the NaK outlet
stop changing, the rows in the CSVs go flat, and the run is at steady state.

## Glossary

- Parent / sub-app: the controlling problem and the problems it launches. Here the
  solid is the parent; OpenMC and THM are sub-apps.
- Variable vs AuxVariable: a Variable is a true unknown the solver computes (`T`);
  an AuxVariable is a field supplied from elsewhere (`power`, `T_fluid`, `htc`).
- Kernel: a term in the equation being solved (conduction, storage, source).
- Material: named properties (conductivity, density, specific heat) the kernels
  read.
- Transfer: moves a field or value between the parent and a sub-app.
- Postprocessor: reduces a field to one number per step (an integral, a max, an
  average).
- MultiApp: the mechanism that lets one app launch and drive another.
- sub_cycling: letting a sub-app take several of its own small steps inside one
  parent step.
- Fixed-point / Picard iteration: repeating the coupled exchange within a step
  until the apps agree, which is "tight coupling."
- kappa-fission: the recoverable heat energy released per fission, what OpenMC
  tallies as the heat source.
- Reflective boundary: a wall that bounces neutrons back, turning one modeled pin
  into an infinite lattice.

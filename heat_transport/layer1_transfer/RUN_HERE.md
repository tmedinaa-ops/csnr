# Layer 1 two-way run, transfer bundle

This folder is the SNAP-10A Layer 1 heat-transport model: a single 3-D fuel pin
with OpenMC supplying the fission heat, MOOSE conducting it, and the THM module
carrying it away in NaK. The job is to run it to thermal steady state and read
the plateau. It is self-contained except for two things the target PC must
provide: a Cardinal build and the OpenMC nuclear data (see Prerequisites).

The single pin is small and finishes in minutes on any machine. The reason to
move to a stronger PC is the step after this one (Layer 2, the full 37-pin core
coupled to the real snap.py), not this run. This bundle gets the working
single-pin model onto the new machine and confirms the toolchain there.

## What is in here

```
solid_3d.i          hub: 3-D pin conduction + OpenMC sub-app + THM sub-app  (run this)
thm.i               NaK channel (THM), launched automatically by solid_3d.i
openmc.i            OpenMC neutronics sub-app, launched automatically
make_mesh.i         regenerates pin3d.e if needed
snap_unit_pin.py    regenerates geometry/materials/settings.xml if needed
geometry.xml        pre-generated OpenMC geometry  (ready to use)
materials.xml       pre-generated OpenMC materials  (ready to use)
settings.xml        pre-generated OpenMC settings   (ready to use)
pin3d.e             pre-built 3-D mesh              (ready to use)
k_of_T_sources.md   conductivity sourcing (clad k(T), fuel/coating constants)
verify_energy_balance.py   independent validation targets (NaK rise, fuel T)
```

The XMLs and the mesh are pre-built, so you do not need to regenerate anything to
run. Keep all files in one flat folder and run from inside it; the inputs
reference each other by bare filename.

## Prerequisites on the target PC

1. Cardinal, built natively on this machine. The Mac `cardinal-opt` will not run
   here. Build it with OpenMC + MOOSE + THM enabled, NekRS disabled
   (ENABLE_NEK=false). The build steps and gotchas are in
   `Cardinal_MOOSE_Install_Guide.md` in the CSNR folder. Run from the moose conda
   env, the same one used to build it.
2. OpenMC nuclear data, ENDF/B-VIII.0 (HDF5), with the path exported:
   `export OPENMC_CROSS_SECTIONS=/path/to/endfb-viii.0-hdf5/cross_sections.xml`
   The XMLs reference nuclides by name and resolve against this at runtime.
3. (Only if you regenerate the XMLs) an openmc-env with OpenMC 0.15.x.

## Run it

From inside this folder, in the moose conda env, with OPENMC_CROSS_SECTIONS set:

```
mpiexec -np <ranks> <path>/cardinal-opt -i solid_3d.i --n-threads=<threads>
```

Match ranks x threads to the physical core count (e.g. -np 8 --n-threads=1 on an
8-core, -np 16 --n-threads=2 on a 16-core). Do not oversubscribe.

Optional regeneration, only if the mesh or XMLs do not load:

```
conda activate openmc-env && python snap_unit_pin.py     # rewrites the 3 XMLs
cardinal-opt -i make_mesh.i --mesh-only pin3d.e          # rebuilds the mesh
```

Mesh generation is the one version-sensitive step; the pre-built `pin3d.e` avoids
it. Inspect it in ParaView first if you do regenerate.

## What a correct run looks like

The executioner is fixed steps: dt = 25 s, num_steps = 60 (1500 s of model time,
about 4.6 thermal time constants). There is no auto-stop, so it runs all 60 and
you read the plateau.

- The `time` column steps 25, 50, 75, ... If it steps 1, 2, 3, the run picked up
  a stale file; stop and relaunch against this `solid_3d.i`.
- `power_in` holds 918.9 W on every step (this is the source normalization; check
  it first).
- `max_fuel_T` plateaus near 832 K, flat to under about 0.5 K over the last
  several steps. Far above 900 K means a source or conductivity problem.
- NaK outlet plateaus near 817 K, a 62 K rise from the 755.37 K inlet. Read the
  last row of `thm_nak.csv` (column `T_fluid_out`).

`verify_energy_balance.py` is the independent hand calculation of these targets;
run `python verify_energy_balance.py` to print them.

## Outputs to send back

After the run, the two small CSVs are all I need to confirm convergence:

```
solid_3d.csv     time, max_fuel_T, power_in, wall_T_avg   (per step)
thm_nak.csv      time, T_fluid_in, T_fluid_out            (NaK outlet per step)
```

Send the last several rows of each.

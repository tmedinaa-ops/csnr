# Cardinal / MOOSE install for SNAP-10A multiphysics

Written June 2026, vetted against the current MOOSE and Cardinal documentation. I cannot run installs on your Mac (my shell is a separate Linux sandbox), so this is the script for you to run, with the gotchas that bite on Apple Silicon. Commands are copy-paste, in order.

## Status: resolved, Cardinal builds and couples (June 15, 2026)

Done. cardinal-opt built on June 15 and the coupled smoke test passes: test/tests/neutronics/feedback/lattice runs to "Solve Converged!" with OpenMC handing a 500 W heat source into the MOOSE solid solve. The OpenMC plus MOOSE stack is live natively on the Mac, no NekRS.

The blocker was environment, not code. The failing build had been running under a Rosetta x86_64 Python with the moose conda env inactive, so MOOSE searched contrib/moose for libmesh and petsc instead of the conda env. It built once the shell had only the native arm64 moose env active, with PETSC_DIR and LIBMESH_DIR both resolving into that env, the OPENMC_FORCE_VENDORED_LIBS edit reverted with git checkout config/openmc.mk, make clobberall run to clear the wrong-arch artifacts, and make rerun. The original diagnosis and resume steps are kept below as the recovery procedure if it breaks again.

### Original blocker (kept for reference)

The install was partway in and blocked. The moose conda env was created and Cardinal was cloned to ~/cardinal, but `make` dies during the MOOSE prerequisite build, before OpenMC is ever reached. Full output is in ~/cardinal/build.log. The lines that matter:

```
ModuleNotFoundError: No module named 'yaml'
.../contrib/moose/.../hit.so (mach-o file, but is an incompatible architecture (have 'arm64', need 'x86_64'))
.../contrib/moose/libmesh/installed/contrib/bin/libmesh-config: No such file or directory
make: *** No rule to make target '.../contrib/moose/petsc/lib/petsc/conf/petscvariables'. Stop.
```

This is an architecture and environment mismatch, not an OpenMC problem. The `hit.so` library was compiled native arm64, but the Python importing it is x86_64 and is missing pyyaml, which moose-dev provides. So the build is running under a Rosetta x86_64 Python rather than the moose env's native arm64 Python. The build is also looking for libmesh and petsc inside contrib/moose, which is the non-conda layout, so the moose-dev conda env is not the active or detected environment during the build. This is gotcha 1 below showing up in practice: the osx-64 Rosetta openmc-env is leaking onto PATH, or the moose env itself was created osx-64.

The OPENMC_FORCE_VENDORED_LIBS ON to OFF edit that was tried does not address this. The build fails upstream of OpenMC, so that flag is irrelevant to this error, and the standard Cardinal conda build never sets it. Revert it and keep the build standard. Only revisit vendored libraries if a real OpenMC link error appears later.

### Resume here

1. Confirm what is active and its architecture, in the shell you build from:

```bash
conda info --envs
python -c "import platform, sys; print(platform.machine(), sys.executable)"   # want arm64
which -a python            # is an openmc-env or system x86_64 python first?
conda config --show subdir # osx-64 here means new envs default to Rosetta
```

2. If machine() prints x86_64, that is the bug. Two cases:
   - The moose env is native but openmc-env is leaking. Run `conda deactivate` until the prompt shows base, open a fresh terminal, then `conda activate moose` on its own. Confirm `python -c "import platform; print(platform.machine())"` says arm64 and `python -c "import yaml"` works.
   - The moose env itself is x86_64. Rebuild it native:

```bash
conda deactivate
conda env remove -n moose
CONDA_SUBDIR=osx-arm64 conda create -n moose moose-dev=2026.06.07=mpich
conda activate moose
conda config --env --set subdir osx-arm64
python -c "import platform; print(platform.machine())"   # must say arm64
```

3. Clear the wrong-arch build products so they rebuild under the right interpreter. From ~/cardinal run MOOSE's clean target, `make clobberall`, and if that target is missing delete the stale hit.so by hand. The earlier `rm -rf build/ install/` did not touch these.

4. Revert the vendored-libs edit and rebuild standard:

```bash
cd ~/cardinal
git checkout config/openmc.mk
./scripts/get-dependencies.sh
export ENABLE_NEK=false
export HDF5_ROOT=$CONDA_PREFIX
export LD_LIBRARY_PATH=$CONDA_PREFIX/lib:$LD_LIBRARY_PATH
export OPENMC_CROSS_SECTIONS=$HOME/openmc_data/endfb-viii.0-hdf5/cross_sections.xml
make -j8 MAKEFLAGS=-j8 2>&1 | tee build.log
```

The sign it is fixed: the build stops looking in contrib/moose/libmesh/installed, uses the conda libmesh and petsc, and the Python in the build is arm64.

## Recommendation first

Install the OpenMC + MOOSE half of Cardinal, natively on your Apple Silicon Mac, through MOOSE's conda environment, with NekRS turned off. That gives you exactly the coupling SNAP-10A needs: OpenMC neutronics talking to a MOOSE heat-conduction solve in a Picard loop, the Cardinal version of the hand-built loop in your Day 3 notes and of the arXiv 2505.04024 coupling. It does not give you NekRS CFD, and you do not need it. The NaK loop is a conduction and convection problem MOOSE can carry, not a spectral-element CFD problem.

This updates the project note that filed Cardinal under HPC-only. That note is right about the full stack: NekRS is GPU and HPC territory, and it will not even build inside MOOSE's conda environment. But the OpenMC path is CPU-only and MOOSE now supports Apple Silicon natively, so the coupled neutronics-thermal build runs on your machine. Reserve HPC for the day you want NekRS CFD of the coolant or a mesh too large for the Mac.

Do not let this block a first result. The openmc.lib Picard loop from your Day 3 notes needs zero new install and can produce a first coupled SNAP-10A temperature-feedback number now, against a simple Python thermal model. Build Cardinal as the production tool in parallel, and use openmc.lib as the proof of concept. The honest caveat both ways: the openmc.lib back-end is a toy thermal model, Cardinal is the real one.

## Three gotchas specific to your setup

1. Keep it clear of your Rosetta openmc-env. Your standalone OpenMC is the osx-64 build under Rosetta. Cardinal builds its own OpenMC from a submodule, native arm64 inside the moose env. They are separate toolchains, which is fine, but the openmc-env must NOT be active when you build or run Cardinal. Run `conda deactivate` until no openmc env shows in the prompt, then `conda activate moose`. Cardinal's own docs say it directly: do not use OpenMC's conda env here, and do not build OpenMC separately.

2. NekRS off, and it is mandatory. MOOSE's conda environment is incompatible with NekRS's bundled HYPRE. You must `export ENABLE_NEK=false` or the build fails. Not a limitation for SNAP-10A.

3. Reuse your existing cross sections. Point Cardinal at the ENDF/B-VIII.0 library you already have (the path in your .zshrc). Same data as your validation policy, so Cardinal and standalone OpenMC stay comparable.

## Steps

You already have Miniforge from the openmc-env setup, so skip the Miniforge install. If `conda` is not on PATH in a fresh shell, fix that before continuing.

### 1. MOOSE conda environment (native arm64)

```bash
conda config --add channels https://conda.software.inl.gov/public
conda create -n moose moose-dev=2026.06.07=mpich
conda activate moose
```

Use the current `moose-dev` pin from the MOOSE conda page if 2026.06.07 has rolled; Cardinal expects a recent moose-dev. If activation complains about the macOS SDK, install the SDK version it names (it wants a supported Command Line Tools release).

### 2. Clone and build Cardinal (OpenMC path, no NekRS)

```bash
conda activate moose          # confirm no openmc-env is active first
cd $HOME
git clone https://github.com/neams-th-coe/cardinal.git
cd cardinal
./scripts/get-dependencies.sh   # pulls MOOSE, OpenMC, NekRS submodules

export ENABLE_NEK=false
export HDF5_ROOT=$CONDA_PREFIX
export LD_LIBRARY_PATH=$CONDA_PREFIX/lib:$LD_LIBRARY_PATH
export OPENMC_CROSS_SECTIONS=$HOME/openmc_data/endfb-viii.0-hdf5/cross_sections.xml

make -j8 MAKEFLAGS=-j8
```

Put those four exports in ~/.zshrc so they persist. Only the cross-sections line overlaps your current setup, and it is the same file you already point standalone OpenMC at. A successful build leaves a `cardinal-opt` executable in the cardinal directory. Budget real resources: about 30 GB of disk, 16 GB of RAM is comfortable, and the first build is long because it compiles MOOSE and OpenMC from source.

### 3. Verify with the coupled smoke test

```bash
echo $OPENMC_CROSS_SECTIONS                 # must not print an empty line
cd test/tests/neutronics/feedback/lattice
mpiexec -np 2 ../../../../../cardinal-opt -i openmc_master.i --n-threads=2
```

This is an OpenMC + MOOSE temperature-feedback lattice, the smallest version of the SNAP-10A coupling. If it runs to a converged step, the stack works. That input file is also your starting template: it is the Cardinal equivalent of the Picard loop in your Day 3 notes.

## SNAP-10A tie-in

The feedback/lattice test is the pattern you port your fig12-validated snap.py model into. OpenMC carries the neutronics at the v1.0-fig12 geometry, Cardinal hands the kappa-fission heat to a MOOSE conduction model of the fuel and NaK, MOOSE returns temperatures, and the loop iterates to the coupled k. Your build-spec coupled target (k near 1.00086, fuel and fluid temperatures within about 3 K of NAA-SR-9903) is the convergence check. Set the OpenMC temperature-interpolation range to cover the NaK loop and fuel band from the base set before the first coupled run, the same lesson as the Day 3 multiphysics note.

For the energy-conversion side, Cardinal does not model the thermoelectrics. The converter is the boundary condition: the NaK outlet temperature MOOSE produces is the hot-junction input to the separate Python thermoelectric model built from NAA-SR-11955 Table 2. Keep those two models decoupled for now.

## If you have CMU cluster access

If you can get on a CMU cluster, build there for anything heavy. A from-source build there (without conda) also unlocks NekRS if you later want CFD of the NaK, and you get more cores for the coupled runs. Cardinal's HPC shell-environment settings are documented at cardinal.cels.anl.gov/hpc.html. For the Mac, the conda path above is the right call.

## Sources

- Cardinal build with conda: https://cardinal.cels.anl.gov/with_conda.html
- Cardinal getting started: https://cardinal.cels.anl.gov/start.html
- MOOSE conda environment: https://mooseframework.inl.gov/getting_started/installation/conda.html
- MOOSE system requirements (Apple Silicon supported): https://mooseframework.inl.gov/getting_started/installation/index.html

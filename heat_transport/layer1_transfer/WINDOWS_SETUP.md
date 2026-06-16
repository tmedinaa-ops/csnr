# Standing up the toolchain on a Windows PC (via WSL2)

MOOSE and Cardinal do not build natively on Windows. The route is WSL2, which is
a real Linux kernel inside Windows, and then the standard Linux conda build. This
is actually a cleaner build than the Apple Silicon one in
`Cardinal_MOOSE_Install_Guide.md`: linux-64 is the platform the MOOSE and
Cardinal conda packages are built for, so the Rosetta and architecture gotchas
from the Mac do not apply here.

Budget: the first Cardinal build compiles MOOSE and OpenMC from source, so plan
on ~30 GB of disk and a build that runs for a while. Give WSL2 at least 16 GB of
RAM (step 1b) or the build can be killed mid-compile.

Two WSL2 rules that save grief:
- Build and run inside the Linux home (`~`, i.e. `/home/<you>`), NOT under
  `/mnt/c`. The Windows drive mounted at `/mnt/c` is slow and mishandles symlinks
  and permissions, which breaks the MOOSE/OpenMC build. Only cross into `/mnt/c`
  to copy the bundle in (step 6).
- Run all the Linux commands below inside the Ubuntu (WSL2) shell, not PowerShell,
  except step 1a.

## 1a. Install WSL2 + Ubuntu (PowerShell, as Administrator)

```powershell
wsl --install -d Ubuntu-22.04
```

Reboot if prompted, then launch "Ubuntu" from the Start menu and create your
Linux username and password. Everything from here runs in that Ubuntu shell.

## 1b. Give WSL2 enough RAM (PowerShell or Notepad)

Create `C:\Users\<you>\.wslconfig` with:

```
[wsl2]
memory=24GB
processors=8
```

Then in PowerShell: `wsl --shutdown`, and reopen Ubuntu. Adjust to your machine
(leave a few GB for Windows).

## 2. Miniforge (conda), inside Ubuntu

```bash
cd ~
curl -L -O https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh
bash Miniforge3-Linux-x86_64.sh -b -p $HOME/miniforge3
source $HOME/miniforge3/etc/profile.d/conda.sh
conda init bash
exec bash      # reload the shell so conda is on PATH
```

## 3. MOOSE conda environment (native linux-64)

```bash
conda config --add channels https://conda.software.inl.gov/public
conda create -n moose moose-dev=2026.06.07=mpich
conda activate moose
```

If `2026.06.07` has rolled, use the current `moose-dev` pin from the MOOSE conda
page. No `CONDA_SUBDIR` games are needed on Linux; the env is native x86-64.

## 4. Clone and build Cardinal (OpenMC path, NekRS off)

```bash
conda activate moose
cd $HOME
git clone https://github.com/neams-th-coe/cardinal.git
cd cardinal
./scripts/get-dependencies.sh        # pulls MOOSE, OpenMC, NekRS submodules

export ENABLE_NEK=false              # mandatory: NekRS is incompatible with the conda HYPRE
export HDF5_ROOT=$CONDA_PREFIX
export LD_LIBRARY_PATH=$CONDA_PREFIX/lib:$LD_LIBRARY_PATH

make -j8 MAKEFLAGS=-j8 2>&1 | tee build.log
```

A successful build leaves `cardinal-opt` in `~/cardinal`. Put the three exports
in `~/.bashrc` so they persist across shells.

## 5. OpenMC nuclear data (ENDF/B-VIII.0, HDF5)

Download the ENDF/B-VIII.0 HDF5 archive from the official OpenMC data page,
https://openmc.org/official-data-libraries/ (file is `endfb-viii.0-hdf5.tar.xz`,
a few GB). From the Ubuntu shell, with the archive in `~`:

```bash
cd $HOME
mkdir -p openmc_data && cd openmc_data
mv ~/endfb-viii.0-hdf5.tar.xz .      # or wget/curl the link from the page directly
tar -xJf endfb-viii.0-hdf5.tar.xz
echo 'export OPENMC_CROSS_SECTIONS=$HOME/openmc_data/endfb-viii.0-hdf5/cross_sections.xml' >> ~/.bashrc
source ~/.bashrc
echo $OPENMC_CROSS_SECTIONS           # must print the path, not an empty line
```

This is the same library as the validation policy, so the new PC stays
comparable to the Mac and the standalone OpenMC runs.

## 6. Verify Cardinal with the coupled smoke test

```bash
conda activate moose
cd ~/cardinal/test/tests/neutronics/feedback/lattice
mpiexec -np 2 ../../../../../cardinal-opt -i openmc_master.i --n-threads=2
```

If it runs to a converged step, the stack works. This is the same OpenMC+MOOSE
feedback pattern as the SNAP-10A coupling.

## 7. Bring the bundle in and run it

Copy `layer1_transfer.zip` to Windows (e.g. into Downloads), then from Ubuntu:

```bash
cp /mnt/c/Users/<you>/Downloads/layer1_transfer.zip ~/
cd ~ && unzip layer1_transfer.zip -d layer1_transfer
cd layer1_transfer
conda activate moose
mpiexec -np 8 $HOME/cardinal/cardinal-opt -i solid_3d.i --n-threads=1
```

Match `-np` to your physical core count (8 here for an 8-core; raise it on a
bigger CPU). See `RUN_HERE.md` for the expected plateau values and what to send
back. The XMLs and mesh in the bundle are pre-built, so nothing needs
regenerating.

## 8. Optional: openmc-env, only if you regenerate XMLs or move to Layer 2

```bash
conda create -n openmc-env openmc
conda activate openmc-env
# OPENMC_CROSS_SECTIONS from step 5 is already exported
python snap_unit_pin.py     # rewrites geometry/materials/settings.xml
```

Not needed for the Layer 1 run itself. Useful later for the full-core (Layer 2)
work, which also needs the snap repo.

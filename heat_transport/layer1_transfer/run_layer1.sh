#!/usr/bin/env bash
# Layer 1 two-way run -- PC version (20-core defaults, auto mesh regen).
# Runs solid_3d.i with ONLY the parameters in the file (dt=25, num_steps=60).
# No Executioner/ overrides, full path to the binary, so neither command history
# nor shell aliases can inject a stray dt here.
#
# Use from the moose conda env with OPENMC_CROSS_SECTIONS set:
#   conda activate moose
#   bash run_layer1.sh
#
# Defaults to -np 10 --n-threads=2 (20-way) for a 20-core machine. Override:
#   NP=16 NT=1 bash run_layer1.sh
# It regenerates pin3d.e whenever make_mesh.i is newer (so a mesh change like the
# ~30k-DOF uprate takes effect instead of silently reusing the old coarse mesh),
# and writes run_layer1.log for inspection.

cd "$(dirname "$0")"
CARDINAL="${CARDINAL:-$HOME/cardinal/cardinal-opt}"
NP="${NP:-10}"
NT="${NT:-2}"

# regenerate the mesh if it is missing or make_mesh.i changed since it was built
if [ ! -f pin3d.e ] || [ make_mesh.i -nt pin3d.e ]; then
  echo "pin3d.e missing or stale -> regenerating from make_mesh.i ..."
  "$CARDINAL" -i make_mesh.i --mesh-only pin3d.e || { echo "mesh generation failed"; exit 1; }
fi

# clear stale run outputs so there is no chance of reading an old run
rm -f solid_3d.csv thm_nak.csv run_layer1.log

{
  echo "===== run_layer1.sh (PC) ====="
  echo "binary    : $CARDINAL"
  echo "input     : $(pwd)/solid_3d.i"
  echo "file dt   : $(grep -E '^[[:space:]]*dt[[:space:]]*=' solid_3d.i)"
  echo "file steps: $(grep -E '^[[:space:]]*num_steps[[:space:]]*=' solid_3d.i)"
  echo "mesh      : $(grep -E 'num_sectors|rings =' make_mesh.i | tr -s ' ')"
  echo "layout    : -np $NP --n-threads=$NT  (NO Executioner overrides on the line)"
  echo "=============================="
  mpiexec -np "$NP" "$CARDINAL" -i solid_3d.i --n-threads="$NT"
} 2>&1 | tee run_layer1.log

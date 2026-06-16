#!/usr/bin/env bash
# Layer 1 two-way run. Runs solid_3d.i with ONLY the parameters in the file
# (dt=25, num_steps=60). No Executioner/ overrides, full path to the binary,
# so neither command history nor shell aliases can inject dt=1 here.
#
# Use from the moose conda env with OPENMC_CROSS_SECTIONS set:
#   conda activate moose
#   bash run_layer1.sh
#
# It writes run_layer1.log so the run can be inspected after the fact.
# Override ranks/threads/binary with env vars: NP=8 NT=1 bash run_layer1.sh

cd "$(dirname "$0")"
CARDINAL="${CARDINAL:-$HOME/cardinal/cardinal-opt}"
NP="${NP:-4}"
NT="${NT:-2}"

# clear stale outputs so there is no chance of reading an old dt=1 run
rm -f solid_3d.csv thm_nak.csv run_layer1.log

{
  echo "===== run_layer1.sh ====="
  echo "binary    : $CARDINAL"
  echo "input     : $(pwd)/solid_3d.i"
  echo "file dt   : $(grep -E '^[[:space:]]*dt[[:space:]]*=' solid_3d.i)"
  echo "file steps: $(grep -E '^[[:space:]]*num_steps[[:space:]]*=' solid_3d.i)"
  echo "layout    : -np $NP --n-threads=$NT  (NO Executioner overrides on the line)"
  echo "========================="
  mpiexec -np "$NP" "$CARDINAL" -i solid_3d.i --n-threads="$NT"
} 2>&1 | tee run_layer1.log

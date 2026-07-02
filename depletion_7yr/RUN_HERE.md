# 7-year depletion runs (PC package)

Confirms the fitted legs of the 7-year mission simulation (../SNAP-10A_7yr_Mission_Simulation.md) with measured OpenMC depletion curves. Two runs, one command each, sized for the 20-core PC. This folder is self-contained except for the snap model and the depletion chain, both set up once below.

## One-time setup (PC, WSL)

1. Environment: `conda activate openmc-env`. Data path must be the Linux one:
   `export OPENMC_CROSS_SECTIONS=/home/csnr_labuser/lib80x_hdf5/cross_sections.xml`
   (never the \\wsl.localhost\ Windows path).

2. WSL gotchas (known, recorded in the project notes):
   `export HDF5_USE_FILE_LOCKING=FALSE` (add to ~/.bashrc), and before any re-run
   `rm -f summary.h5 statepoint*.h5` inside the run directory.

3. Model: the runs load the snap repo's combined model.xml at the validated fig12_test
   operating condition. In `~/snap`, generate it per that repo's CLAUDE.md (the
   fig12_test case writes model.xml), then either leave it at `~/snap/model.xml` or
   point `MODEL_XML` at wherever it lands. Pull the repo first: `cd ~/snap && git pull`
   (if CRLF complains on a fast-forward: `git fetch origin && git reset --hard origin/master`).

4. Depletion chain (one download): OpenMC needs a chain XML separate from the
   cross sections. Get the ENDF/B-VIII.0 chain from https://openmc.org/depletion-chains/
   and save it as `~/openmc_data/chain_endfb80.xml`, or set `CHAIN_FILE` to your path.
   If only the ENDF/B-VII.1 PWR chain is handy it is adequate for this purpose (the
   quantities compared are k(t) slope and U inventory, not minor-actinide detail).

## Run (from this folder, ~/csnr/depletion_7yr)

```
POWER_W=79100  python run_depletion_7yr.py     # ~7.2 yr predicted reactivity horizon
POWER_W=120000 python run_depletion_7yr.py     # ~5.1 yr predicted reactivity EOL
```

Each run: 22 depletion steps (fine early steps for the xenon/samarium transient,
half-year steps after year 1), 20k particles x 140 batches per step, so roughly
22 short eigenvalue solves; expect an hour-class run per case on the 20-core box,
not an overnight. Results land in `run_79kWt_7yr/` and `run_120kWt_7yr/`
(depletion_results.h5, gitignored).

Optional phone ping when done, reusing the tested notifier pattern:
`POWER_W=79100 python run_depletion_7yr.py && curl -d "79kWt depletion done" ntfy.sh/$NTFY_TOPIC`

## Read

```
RUN_DIR=run_79kWt_7yr  python read_depletion_7yr.py
RUN_DIR=run_120kWt_7yr python read_depletion_7yr.py
```

Prints k(t), reactivity slope, burnup rate, and the reactivity EOL, each against its
analytic target, and writes `depletion_summary.csv` (small, committable) so the Mac
can plot and fold the measured curves back into simulate_7yr.py.

## What decides what

| Measured quantity | Analytic value it tests | If it disagrees |
|---|---|---|
| burnup %/yr at 79 kWt | 0.75 (spread 0.60-0.75) | rescales every burnup crossing and the qualified-envelope MWh in the 7-yr simulation and the trade-off papers |
| reactivity slope at 79 kWt | ~106 pcm/yr (Service Life Report) | moves the ~7.2 yr horizon and the ~82 kWt 7-year power cap |
| reactivity slope at 120 kWt | ~153 pcm/yr (linear fit) | moves the 5.1 yr EOL of the mech-pump case; tests the fit's linearity in P |
| EOL vs 767 pcm cold excess | budget bookkeeping | if k(t) hits its floor well off prediction, the cold-excess anchor or the fit is wrong, and the Service Life Report numbers need revisiting |

One honest scope note: the run depletes at the fixed 783 K operating temperature
field. Temperature feedback on the depletion trajectory is second-order for these
purposes (the coefficient is -1.46 pcm/K and the drum trim holds temperature), but a
coupled depletion is the Cardinal-era refinement if the slopes land close to their
targets and the residual matters.

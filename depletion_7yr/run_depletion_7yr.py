#!/usr/bin/env python3
"""
run_depletion_7yr.py -- 7-year OpenMC depletion of the SNAP-10A operating model.

Confirms the two fitted legs of the 7-year mission simulation
(CSNR/SNAP-10A_7yr_Mission_Simulation.md) with measured curves:
  - burnup rate vs the 0.75 %/yr-at-79-kWt estimate (and the 0.60 scaling spread)
  - reactivity consumption vs the linear fit rate = 1.154*P_kwt + 14.8 pcm/yr
    (Service Life Report anchors: 61 pcm/yr at 40 kWt, 106 at 79)
  - the predicted reactivity EOL: ~7.2 yr at 79 kWt, ~5.1 yr at 120 kWt

The model is the snap repo's validated fig12_test operating condition (783 K design
average, drums positioned to criticality, k = 1.00033 +/- 34 pcm). This script does
NOT rebuild the model; it loads the combined model.xml the snap repo generates.

Environment knobs (all optional):
  MODEL_XML   path to the snap model.xml   [default: ~/snap/model.xml]
  CHAIN_FILE  depletion chain xml          [default: ~/openmc_data/chain_endfb80.xml]
  POWER_W     fission power in watts       [default: 79100]
  TIME_YEARS  mission length               [default: 7]
  RUN_DIR     output directory             [default: run_<P>kWt_<Y>yr]
  PARTICLES / BATCHES / INACTIVE           [default: 150000 / 250 / 50, high-stat]

Usage on the PC (WSL, openmc-env; see RUN_HERE.md for the one-time setup):
  POWER_W=79100  python run_depletion_7yr.py
  POWER_W=120000 python run_depletion_7yr.py
Then: python read_depletion_7yr.py RUN_DIR=<dir>
"""
import os
import sys
from pathlib import Path

import openmc
import openmc.deplete

# ---------------- knobs -------------------------------------------------------------
def _env(name, default):
    v = os.environ.get(name)
    return v if v not in (None, "") else default

MODEL_XML = Path(_env("MODEL_XML", str(Path.home() / "snap" / "model.xml"))).expanduser()
CHAIN_FILE = Path(_env("CHAIN_FILE", str(Path.home() / "openmc_data" / "chain_endfb80.xml"))).expanduser()
POWER_W = float(_env("POWER_W", "79100"))
TIME_YEARS = float(_env("TIME_YEARS", "7"))
# High-statistics default (July 2026): the 1-year clean run showed the reactivity slope
# from the old 20k-particle settings was inflated by Monte-Carlo noise (it read -337 to
# -453 pcm/yr at ~720 pcm k-noise; the clean run read -319 at ~180 pcm noise). These
# settings give ~200 active batches x 150k particles, roughly 15x the histories of the
# old default, targeting ~180-200 pcm k-sigma so the 7-year slope is trustworthy. It is
# an hours-class run on the 20-core PC. For a quick geometry/plumbing test, override down,
# e.g. PARTICLES=20000 BATCHES=140 INACTIVE=40.
PARTICLES = int(_env("PARTICLES", "150000"))
BATCHES = int(_env("BATCHES", "250"))
INACTIVE = int(_env("INACTIVE", "50"))
RUN_DIR = Path(_env("RUN_DIR", f"run_{POWER_W/1e3:.0f}kWt_{TIME_YEARS:.0f}yr"))

# fuel volume: 37 pins x pi x r_fuel^2 x active length (arXiv 2505.04024 Table I,
# r 1.53924 cm, L 31.0515 cm). Only used if the model carries no volume already.
FUEL_VOLUME_CM3 = float(_env("FUEL_VOLUME_CM3", "8550.8"))

for p, what in ((MODEL_XML, "MODEL_XML (generate it in the snap repo, see RUN_HERE.md)"),
                (CHAIN_FILE, "CHAIN_FILE (download a depletion chain, see RUN_HERE.md)")):
    if not p.exists():
        sys.exit(f"missing {p}\n  -> set {what}")

# ---------------- model -------------------------------------------------------------
model = openmc.Model.from_model_xml(str(MODEL_XML))

# transport settings sized for a per-step eigenvalue trend, not a benchmark
model.settings.particles = PARTICLES
model.settings.batches = BATCHES
model.settings.inactive = INACTIVE

# mark the U-ZrH fuel depletable and give it its volume.
#
# IMPORTANT (audit July 2026): the fig12_test HexLattice fills the whole core with a
# SINGLE shared fuel material (correct for k-eigenvalue, which is why fig12 validated).
# OpenMC's documented behavior is that a shared material depletes as ONE lumped region
# unless you differentiate it (usersguide/depletion.rst: "Without any instructions,
# OpenMC will deplete a single material, and all of the fuel pins will have an identical
# composition"). So exactly one material carries the whole core's flux; any other
# U-bearing materials in model.xml are unplaced orphans that never flux (verified: 74 of
# 75 stayed byte-frozen in every run). The volume that matters is that ONE placed
# material's, and it must equal the TOTAL core fuel volume (FUEL_VOLUME_CM3 = 8550.8),
# because that material geometrically occupies the whole core. Giving it 1/N of the core
# (an earlier mistaken "fix") makes its specific power N x too high and burns it to 100%
# in ~2.5 yr -> k collapse. So set the full core volume here; divide-equally handles the
# per-pin split only when DIFF is on.
DIFF = os.environ.get("DIFF", "0") not in ("0", "", "false", "False")

fuel_mats = []
for m in model.materials:
    names = {n[0] if isinstance(n, tuple) else str(n) for n in m.nuclides}
    if any(str(n).startswith("U23") for n in names):
        m.depletable = True
        if m.volume is None:
            m.volume = FUEL_VOLUME_CM3    # full core volume on the placed shared material
        fuel_mats.append(m)
if not fuel_mats:
    sys.exit("no uranium-bearing material found in the model; check MODEL_XML")
print(f"marked {len(fuel_mats)} U-bearing material(s) depletable; the placed one carries "
      f"the full {FUEL_VOLUME_CM3:.0f} cm3 core, power {POWER_W/1e3:.1f} kWt, "
      f"{TIME_YEARS:.0f} years, DIFF={'on (per-pin)' if DIFF else 'off (0-D lumped core)'}")

# ---------------- timesteps ----------------------------------------------------------
# Fine early steps resolve xenon/samarium buildup; half-year steps carry the trend.
first_year = [0.5, 1.0, 2.0, 4.0, 8.0, 15.0, 30.0, 60.0, 90.0, 154.75]   # sums to 365.25
later = [182.625] * int(round((TIME_YEARS - 1.0) * 2))
timesteps = first_year + later
assert abs(sum(timesteps) - TIME_YEARS * 365.25) < 1.0

# ---------------- run ---------------------------------------------------------------
RUN_DIR.mkdir(parents=True, exist_ok=True)
os.chdir(RUN_DIR)

# DIFF off (default): deplete the shared fuel material as one 0-D lumped core. This is
#   what the buggy runs actually computed on their placed material, and it is correct for
#   core-average burnup rate, reactivity slope, and EOL (the quantities this study needs).
# DIFF on: differentiate the shared material into one material per lattice instance so each
#   pin burns on its local spectrum (peaking-resolved). diff_volume_method="divide equally"
#   splits the full-core FUEL_VOLUME_CM3 across the instances (openmc docs). Heavier, and
#   worth a 2-step smoke test first (confirm >1 material shows Cs137) before a 7-yr run.
if DIFF:
    op = openmc.deplete.CoupledOperator(model, chain_file=str(CHAIN_FILE),
                                        diff_burnable_mats=True,
                                        diff_volume_method="divide equally")
else:
    op = openmc.deplete.CoupledOperator(model, chain_file=str(CHAIN_FILE))

# CECM (predictor-corrector) is more stable than bare predictor for the half-year steps;
# set INTEGRATOR=predictor to fall back to the original explicit scheme.
if os.environ.get("INTEGRATOR", "cecm").lower() == "predictor":
    integrator = openmc.deplete.PredictorIntegrator(op, timesteps, power=POWER_W,
                                                    timestep_units="d")
else:
    integrator = openmc.deplete.CECMIntegrator(op, timesteps, power=POWER_W,
                                               timestep_units="d")
integrator.integrate()
print(f"\ndone: {RUN_DIR}/depletion_results.h5")
print("read it with: RUN_DIR=" + str(RUN_DIR) + " python read_depletion_7yr.py")

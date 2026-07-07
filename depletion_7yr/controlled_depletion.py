#!/usr/bin/env python3
"""
controlled_depletion.py -- deplete SNAP-10A with the control drums re-searched to
criticality at every step, so the fuel always burns in the true operating spectrum
and the drum reactivity consumed gives the operational reactivity horizon directly.

This is the gold-standard version of the reactivity-lifetime calculation. It differs
from the bare run in that the drums are rotated out each step to hold k = 1 rather
than left fixed while the core sags subcritical. Expect it to CONFIRM, not overturn,
the bare-run slope: the drums move only a few degrees to recover a couple thousand
pcm over the mission, and the composition change is identical, so the operating
spectrum is close to the fixed-drum spectrum. Its real payoff is (1) removing the
last doubt about spectrum drift, and (2) reporting the horizon as "drum reactivity
consumed vs available excess" instead of the messy Delta-k-vs-cold-excess bookkeeping.

WIRING REQUIRED. The one model-specific piece is a function that rebuilds the snap
model at a given drum angle carrying a given set of depleted materials. Import it
from the snap repo (snap.py builds fig12_test with drum parameters) and plug it into
build_at_drum() below. The drum only needs to sweep a few degrees around the
operating orientation, which stays inside the rotation window snap.py's geometry is
valid over (large rotations lose particles; small ones near the operating angle are
fine). Run a 2-step smoke test and confirm the drum angle moves monotonically and k
holds at 1.0 +/- a few hundred pcm before launching the full 7-year loop.

Run in openmc-env with OPENMC_CROSS_SECTIONS and a depletion chain set.
"""
import os
from pathlib import Path

import numpy as np
import openmc
import openmc.deplete

# ----------------------------------------------------------------------- knobs
CHAIN_FILE = Path(os.environ.get("CHAIN_FILE",
                  str(Path.home() / "openmc_data" / "chain_endfb80.xml"))).expanduser()
POWER_W = float(os.environ.get("POWER_W", "79100"))
TIME_YEARS = float(os.environ.get("TIME_YEARS", "7"))
PARTICLES = int(os.environ.get("PARTICLES", "50000"))
BATCHES = int(os.environ.get("BATCHES", "120"))
INACTIVE = int(os.environ.get("INACTIVE", "40"))
RUN_DIR = Path(os.environ.get("RUN_DIR", f"run_ctrl_{POWER_W/1e3:.0f}kWt"))
FUEL_VOLUME_CM3 = float(os.environ.get("FUEL_VOLUME_CM3", "8550.8"))

# operating drum orientation and the search bracket around it (degrees).
DRUM0 = float(os.environ.get("DRUM0", "0"))          # BOL critical orientation
DRUM_BRACKET = (float(os.environ.get("DRUM_MIN", "-20")),
                float(os.environ.get("DRUM_MAX", "40")))   # search window (out = +)
DRUM_WORTH_PCM = float(os.environ.get("DRUM_WORTH_PCM", "5925"))  # total worth, for the horizon

# same fine-then-coarse steps as the bare run
first_year = [0.5, 1.0, 2.0, 4.0, 8.0, 15.0, 30.0, 60.0, 90.0, 154.75]
timesteps_d = first_year + [182.625] * int(round((TIME_YEARS - 1.0) * 2))


# --------------------------------------------------------- model builder (WIRE ME)
def build_at_drum(angle_deg, materials=None):
    """Return an openmc.Model of fig12_test with the drums at `angle_deg`, optionally
    carrying `materials` (the depleted set from the previous step).

    WIRE THIS to the snap repo. The cleanest form:

        import sys; sys.path.insert(0, str(Path.home()/"snap"))
        import snap                      # the model builder from arXiv 2505.04024
        def build_at_drum(angle_deg, materials=None):
            model = snap.build_model(case="fig12_test", drum_angle=angle_deg)
            if materials is not None:
                model.materials = materials         # carry depleted comps forward
            # mark the placed fuel material depletable with the full core volume
            for m in model.materials:
                if any(str(n).startswith("U23") for n in
                       (x[0] if isinstance(x, tuple) else x for x in m.nuclides)):
                    m.depletable = True
                    if m.volume is None:
                        m.volume = FUEL_VOLUME_CM3
            model.settings.particles = PARTICLES
            model.settings.batches = BATCHES
            model.settings.inactive = INACTIVE
            return model

    If snap.py exposes the drum as a rotation on a cell/universe rather than a
    build-time argument, set that rotation here instead (cell.rotation = (0,0,angle)).
    """
    raise NotImplementedError("wire build_at_drum() to the snap model builder; see docstring")


# ------------------------------------------------------------- critical drum search
def search_critical_drum(materials):
    """Find the drum angle that makes k = 1 with the current materials."""
    angles, keffs = openmc.search_for_keff(
        lambda a: build_at_drum(a, materials),
        bracket=list(DRUM_BRACKET),
        target=1.0, tol=1e-3, print_iterations=True,
        run_args={"output": False},
    )
    return angles  # the critical angle


# ----------------------------------------------------------------------- main loop
def main():
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    os.chdir(RUN_DIR)

    materials = None       # first step uses fresh comps from the builder
    angle = DRUM0
    log = []               # (t_years, drum_angle, k, drum_reactivity_pcm)
    t_days = 0.0

    for i, dt in enumerate(timesteps_d):
        # 1. rotate drums to criticality at the current composition
        angle = search_critical_drum(materials)
        model = build_at_drum(angle, materials)

        # 2. one depletion step in that critical geometry (predictor is fine per step;
        #    the criticality search is what stabilises the trajectory, not the integrator)
        op = openmc.deplete.CoupledOperator(model, chain_file=str(CHAIN_FILE))
        integ = openmc.deplete.PredictorIntegrator(op, [dt], power=POWER_W, timestep_units="d")
        integ.integrate()

        # 3. read k and the depleted materials back for the next step
        res = openmc.deplete.Results("depletion_results.h5")
        _, k = res.get_keff(time_units="d")
        k_here = k[-1, 0]
        materials = res.export_to_materials(len(res) - 1)

        # drum reactivity consumed = worth of the angle moved from the operating point,
        # a proxy is the excess the drums had to supply to hold k=1 (angle vs worth curve
        # from run_drum_total.py). Here we log the angle; convert with your worth curve.
        t_days += dt
        log.append((t_days / 365.25, angle, k_here))
        print(f"step {i:2d}  t={t_days/365.25:5.2f} yr  drum={angle:7.2f} deg  k={k_here:.5f}")

    # ------------------------------------------------------------------- horizon
    log = np.array(log)
    tyr, ang = log[:, 0], log[:, 1]
    # rate at which the drums are pulled out (deg/yr past the Xe/Sm transient)
    sel = tyr >= 0.33
    if sel.sum() >= 2:
        dang_dt = np.polyfit(tyr[sel], ang[sel], 1)[0]
        print(f"\ndrum withdrawal rate (t>0.33 yr): {dang_dt:.2f} deg/yr")
        print("horizon = (angle remaining to the fully-out stop) / this rate.")
        print("Convert the angle axis to pcm with run_drum_total.py's worth curve, then")
        print(f"horizon_pcm = usable excess / (reactivity withdrawal rate); total worth "
              f"available {DRUM_WORTH_PCM:.0f} pcm.")
    np.savetxt("controlled_horizon.csv", log, delimiter=",",
               header="time_yr,drum_angle_deg,keff", comments="")
    print("wrote controlled_horizon.csv")


if __name__ == "__main__":
    main()

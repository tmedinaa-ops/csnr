# Cardinal coupled validation of the uprate ceiling (PC handoff)

This is the capstone validation for the existing-core uprate case. Everything up to here was
computed in the analytic thermal model and the standalone OpenMC model on the Mac. This run,
on the Windows/WSL2 Cardinal box, confirms the chain in the fully coupled 3-D solve, and in
particular checks the one thing the analytic model cannot see: whether temperature feedback
shifts the radial power peaking at the uprated power. It runs on the PC because the full 37-pin
coupled solve is the heavy job; the Mac did the authoring and the standalone runs.

Read this start to finish before running. The base decks are `heat_transport/layer2_core/`
(they sync to the PC via git). The MOOSE syntax for the property and friction upgrades is in
`heat_transport/uprate/Implementation_Research_Dossier.md` (components A1 and A2). Environment
setup is in `Cardinal_MOOSE_Install_Guide.md` and `heat_transport/layer1_transfer/WINDOWS_SETUP.md`.

## What this validates and why

The analytic chain concluded the existing core uprates to ~79 kWt (fuel-limited at the 970 K
hydride wall), with the NaK leaving the core at ~897 K, which a Stirling at a 475 K radiator
turns into ~14.6 kWe. Two pieces of that rest on models the coupled solve can check directly:

1. The hot-side temperature (NaK mixed-mean outlet) at the uprated power.
2. The peak fuel temperature, which sets the ceiling, and the radial peaking behind it. The
   per-pin OpenMC extraction gave a static (no-feedback) radial peaking of 1.317. The coupled
   solve adds Doppler and hydride temperature feedback, which can redistribute power toward the
   cooler edge and flatten the peak slightly at high power. If it flattens, the real ceiling is
   a little higher than 79 kWt; if it sharpens, a little lower. Either way this is the number to
   confirm.

## The two cases to run

Run the design point first to prove the deck reproduces the validated result, then the uprate.

### Case 1: design point, 34 kWt (must reproduce)

Inputs: `power = 34000` W, core inlet 755.37 K, total NaK flow 0.6199 kg/s (per-channel
0.0167541 kg/s). Targets it must hit:

| quantity | target | source |
|---|---|---|
| coupled k-eff | ~1.0006 | Layer 2 / fig12_test |
| mixed-mean NaK outlet | 817.7 +/- a few K | analytic + Layer 2 |
| peak fuel centerline | ~850 K | analytic with the measured 1.317 peaking |
| radial peaking (hot pin / avg) | ~1.32 | OpenMC per-pin extraction |

The peak fuel target is ~850 K, NOT the 867 K in the original Layer 2 report. The 867 came from
the assumed 1.56 peaking; the measured per-pin peaking is 1.317, which the coupled OpenMC solve
will produce on its own. If the coupled run lands near 850 K and ~1.32 peaking, it confirms the
1.317 finding in 3-D and supersedes the 1.56.

### Case 2: uprate ceiling, 79 kWt (the new result)

Inputs: `power = 79000` W (scale the OpenMC kappa-fission magnitude, do not touch geometry),
inlet 755.37 K, total NaK flow ~0.73 kg/s (per-channel ~0.0197 kg/s; this is the pump-coupled
end-of-life flow from `uprate/em_pump_curve.py` at the uprated temperature). Targets:

| quantity | target | meaning |
|---|---|---|
| mixed-mean NaK outlet | ~897 K | the Stirling hot side (feeds G1) |
| peak fuel centerline | ~970 K | the fuel wall that sets the ceiling |
| radial peaking | ~1.3, watch for feedback shift | the thing the coupled solve adds |

If the coupled peak fuel at 79 kWt comes out below 970 K, the ceiling is higher than the analytic
79 kWt (feedback flattened the peak); if above, lower. Report the number either way.

## Deck changes: ALREADY APPLIED (July 21 2026)

The A1/A2 upgrades and the convergence fixes below are now IN the committed decks; a
`git pull` delivers them. Nothing to hand-edit except the case switches:

- `thm.i` carries NaKFluidProperties (A1) and Closures1PhaseTHM with cheng_todreas +
  mikityuk on the bundle geometry (A2); the constant f and the frozen Hw = 5.01e4 are
  gone, so the wall HTC is now computed, not imposed.
- `openmc.i` runs the solid as a warm-started TransientMultiApp (state persists across
  outer steps instead of resetting cold each step, the 73%-closure stall mode).
- `gen_per_pin.py` emits solid_core.i retimed to the parent (dt = 1.0, open-ended) with
  interface relaxation on the stiff wall exchange (relaxation_factor = 0.7,
  transformed_variables = 'T_fluid'). Re-run `python gen_per_pin.py` after pulling.
- `thm.i` no longer uses steady_state_detection (it saved sub-cycles only under the old
  one-big-step timing and could hard-fail the warm-started parent); the channels now
  integrate toward steady across outer steps.

Case switches (set BOTH together): `openmc.i` `power = 34000` for Case 1 / `79000` for
Case 2, and `thm.i` per-channel `m_dot = 0.0167541` (Case 1) / `0.0197` (Case 2).

## If it still will not converge

The stall physics: the wall-to-fluid coupling is stiff (htc ~5e4, the solid sheds 34 kW
across a ~0.6 K wall-fluid gap). The applied fixes attack exactly that (warm start +
interface relaxation). If max_fuel_T is still climbing at outer step 15, raise
`num_steps` in openmc.i first (warm-started steps are cheap), then the solid's
`fixed_point_max_its`; if it oscillates instead, drop the solid's `relaxation_factor`
toward 0.5. The single pin (`two_way/`), which converged this same coupling, is the
cheap place to reproduce any remaining misbehavior. The OpenMC-as-main architecture
keeps the eigenvalue solves to ~15, so the cost is the conjugate inner loop, not the
neutronics.

## Run commands (WSL2, moose conda env, cardinal-opt built)

```
conda activate moose
export OPENMC_CROSS_SECTIONS=~/path/to/endfb-viii.0-hdf5/cross_sections.xml
cd ~/csnr/heat_transport/layer2_core
python gen_per_pin.py                       # regenerate solid_core.i (gitignored)
# build model.xml for the case (openmc-env, on either machine):
#   python ~/snap/snap.py fig12_test .      # or copy the validated model.xml in
mpiexec -np 10 ~/cardinal/cardinal-opt -i openmc.i --n-threads=2
```

The PC's nuclear data is currently lib80x; for a clean match to the Mac and the validation
policy, point OPENMC_CROSS_SECTIONS at the endfb-viii.0-hdf5 set.

## What to send back

The two CSV/console results (k-eff, mixed-mean NaK outlet, peak fuel, radial peaking) for 34 and
79 kWt, plus the ParaView peak-fuel and power-distribution fields if easy. With those I will:
close the validation (or revise the ceiling if feedback shifted the peaking), update G1's kWe with
the coupled hot side, and mark the uprate case coupled-model-verified rather than
analytically-verified. If the conjugate still will not converge after the warm-start fix, send the
last `solid_3d.csv` / `thm_nak.csv` and the run log and I will help debug the relaxation.

## Targets at a glance

| case | power | flow (per ch) | NaK outlet | peak fuel | peaking |
|---|---|---|---|---|---|
| design | 34 kWt | 0.01675 kg/s | 817.7 K | ~850 K | ~1.32 |
| uprate | 79 kWt | ~0.0197 kg/s | ~897 K | ~970 K | ~1.3, watch feedback |

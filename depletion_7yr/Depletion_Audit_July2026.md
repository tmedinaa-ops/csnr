# Depletion audit: why k collapsed, and what the runs actually say

This supersedes `Depletion_79kWt_7yr_Findings.md` and `Depletion_120kWt_7yr_Findings.md`. Those two documents identified a real reporting error but drew the wrong fix from it. The deep audit below finds the true root cause, corrects the fix, and recovers usable numbers from the runs already in hand.

## Short version

The fig12_test model fills the whole core with a single shared fuel material. That is correct for a k-eigenvalue solve, and it is why fig12 validated. But OpenMC depletes a shared material as one lumped region unless you tell it otherwise, so the entire core's fission was dumped into one burnable material while the other 74 U-bearing materials in the file sat frozen and unused. Every run has this. It is documented OpenMC behavior, not a model error per se, but it has to be handled deliberately.

The three uploaded runs split as follows. The two 7-year runs (79 and 120 kWt) gave that one lumped material the full-core volume, which is the right volume for a material that occupies the whole core, so they depleted the core correctly as a 0-D lump. Reading the material that actually fissions (not the 75-material sum) recovers physical burnup and reactivity curves from them right now. The third run (my attempted "fix") shrank that material's volume to 1/75 of the core while it still absorbed all the core's power, so its specific power was 75x too high and it burned to 100% in 2.5 years, collapsing k to 0.006. That run is the artifact, and my volume patch caused it.

## How the audit got here

The tell was that k moved far more than the recorded burnup could justify, in every run. Tracing it:

1. Total atoms and the H1 moderator inventory stay flat, so it is not moderator loss.
2. Of 75 depletable materials, exactly one ever builds fission products. The other 74 are byte-frozen at their starting composition across all steps, in all three runs. So 74 materials are defined and marked depletable but never see flux.
3. Per-material burnup at 3.5 years in the broken run runs from 0% (74 materials) to 100% (one material), mean 1.33%, which is just 100%/75. The whole core's fissions are landing in one pin-sized material.
4. BOL k is 0.999 in every run, and when that one material burns out, k goes to 0.006. A full core of fuel is present for transport, but depleting the one lumped material empties the whole core. That only happens if the one material geometrically occupies the whole core, which confirms the shared-material picture.

OpenMC's own documentation states it plainly: "Without any instructions, OpenMC will deplete a single material, and all of the fuel pins will have an identical composition at the next transport step." The fix is `diff_burnable_mats=True`, which differentiates the shared material into one material per lattice instance so each depletes on its local spectrum, with the original material's volume divided across the instances.

## The compensating-error trap

This is why the earlier "divide the volume by 75" fix was exactly backwards. Two errors were cancelling in the 7-year runs:

- The depletion lumps all core power into one material (should be spread over the pins).
- The original script gave that material the full-core volume, 8550.8 cm3.

Whole-core power divided by whole-core volume is the correct specific power, so the lumped material burned at the right core-average rate and produced a physical k(t). My patch removed the second error (volume to 1/75) but left the first, so whole-core power now divided by one-pin volume, 75x too hot, and the core burned to destruction. The lesson: the volume assigned to a lumped depletion material has to match the volume it actually occupies in the geometry, which here is the whole core.

## What the 79 and 120 kWt runs actually say

Reading the one material that fissions (its composition is the core average, since it is the whole core):

| quantity | 79.1 kWt | 120 kWt | analytic anchor |
|---|---|---|---|
| U-235 burnup rate | 0.84 %/yr | 1.28 %/yr | 0.75 / 1.14 |
| total-U burnup rate | 0.63 %/yr | 0.95 %/yr | (0.60-0.75) / 1.14 |
| reactivity loss, BOL to 7 yr | 2758 pcm | 3925 pcm | - |
| slope past Xe/Sm equilibrium (t>0.33 yr) | -337 pcm/yr | -457 pcm/yr | -106 / -153 |
| one-time Xe/Sm + early equilibrium | ~620 pcm | ~826 pcm | - |

The k(t) curves are smooth and monotonic (1.001 to 0.974 at 79 kWt, to 0.963 at 120 kWt), and the burnup is close to the analytic anchors, a bit above on U-235 and a bit below on total-U depending on basis. So the burnup leg is confirmed and roughly where the mission simulation assumed.

The reactivity slope is the open question. At about -337 pcm/yr (79 kWt) it is roughly three times the Service Life anchor of 106 pcm/yr. That gap is expected in direction: this is a bare depletion with the drums held fixed at their BOL-critical position, so it measures the uncompensated reactivity loss, while the 106 pcm/yr anchor is the drum-controlled operational net. But a 3x gap is larger than "uncompensated vs compensated" alone should explain, and it deserves a clean rerun before any reactivity-horizon or 82 kWt cap number is revised. Two things also inflate the raw slope: the runs are only 20k particles x 100-140 batches so k carries ~70 pcm of Monte Carlo noise per point, and the reactivity budget bookkeeping (comparing to a 767 pcm cold excess while the trajectory already includes ~600-800 pcm of one-time Xe/Sm) is an apples-to-oranges comparison that should be redone with the equilibrium poisons separated out.

Bottom line on the existing runs: trust the burnup, treat the reactivity slope as provisional and on the high side, and do not use the reported EOL of under a year (it is the cold-excess bookkeeping mismatch, not a physical end of life).

## The fix, and how to rerun

`run_depletion_7yr.py` and `read_depletion_7yr.py` are patched:

- The run script gives the placed fuel material the full core volume (reverting my bad divide-by-75) and adds a `DIFF` switch. `DIFF` off is the 0-D lumped core, correct for core-average burnup, reactivity slope, and EOL, which is what this study needs. `DIFF=1` turns on `diff_burnable_mats=True` with `diff_volume_method="divide equally"` for a peaking-resolved per-pin depletion. It also defaults to `CECMIntegrator` (predictor-corrector) instead of bare predictor for stability on the half-year steps; set `INTEGRATOR=predictor` to revert.
- The read script now computes burnup only over materials that actually fissioned (final-step Cs137 above a floor), which is correct in both the lumped case (one whole-core material) and the differentiated case (every pin), instead of averaging over the 74 frozen orphans.

Recommended sequence on the PC:

1. Sanity rerun, 0-D lumped, more particles for a clean slope: raise `PARTICLES` to ~50k and rerun 79 and 120 kWt with `DIFF` off. Confirm the reader prints "1 fissioning material (0-D lumped core)" and a reactivity slope. This gives the defensible core-average reactivity leg.
2. If per-pin peaking in the burnup matters, do a 2-step smoke test with `DIFF=1` first and confirm the reader reports many fissioning materials, before committing to a full 7-year differentiated run.
3. Separate the one-time Xe/Sm equilibrium from the burnup slope when comparing to the 106 and 153 pcm/yr Service Life anchors, and decide whether the drums should be re-critical-searched each step (a controlled depletion) rather than held fixed.

Files: `depletion_audit_figure.png` (k(t) for the two good runs and the runaway, core-average burnup, and the one-material-takes-all bar chart), plus the per-run corrected summary CSVs already written.

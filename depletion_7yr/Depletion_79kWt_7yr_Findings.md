> SUPERSEDED July 2026 by `Depletion_Audit_July2026.md`. The volume observation below is real but the fix it implies (divide volume by 75) is wrong: the true root cause is that the fig12 lattice shares one fuel material, so the core depletes as a 0-D lump. Read the audit for the corrected diagnosis and the usable numbers.

# 7-year depletion at 79.1 kWt: what the run says, and the volume bug in it

The PC run finished 23 depletion steps at 79.1 kWt over 7 years. Reading it back against the analytic targets gives a split verdict: the burnup leg is confirmed once a bookkeeping bug is corrected, and the reactivity/EOL leg cannot be read off this run at all because the same bug corrupts it. Fix the run script and rerun before touching the reactivity numbers; the burnup finding already stands.

## The bug

`run_depletion_7yr.py` assigned the whole-core fuel volume (`FUEL_VOLUME_CM3 = 8550.8`) to every depletable material instead of splitting it across them. The fig12_test model carries 75 uranium-bearing material divisions, so the run modeled 75 x 8550.8 = 641,310 cm3 of fuel, 75 times the real 8551 cm3. That put 355 kg of U-235 in the core against SNAP-10A's real loading of about 4.75 kg. The correct per-material volume is 8550.8 / 75 = 114 cm3. The one-line fix is in the patched script: split the core volume across the fuel materials rather than giving each the full core.

## What is still correct

The absolute physics is not affected by the volume error, because OpenMC normalizes the flux to the requested power using the real geometry, not `material.volume`. Two independent checks confirm the run burned fuel at the right absolute rate:

- Cs-137 built up to 3.19e22 atoms. At a 6.23% cumulative fission yield that is about 5.1e23 fissions.
- 79.1 kWt over 7 years is 1.75e13 J, which at 200 MeV per fission is 5.45e23 fissions.

Those agree to 94%, so the power normalization and the absolute burn are sound. The problem is entirely in the denominator used to express burnup as a percentage, and in the number densities the transport solver saw.

## Burnup leg: confirmed

Absolute U-235 consumed over 7 years is 7.19e23 atoms. Divided against the true inventory rather than the 75x-inflated one:

| basis | 7-year burnup | rate | analytic target |
|---|---|---|---|
| file as-written (inflated) | 0.059% | 0.008 %/yr | (artifact) |
| total U, corrected | 4.42% | 0.63 %/yr | 0.75 (spread 0.60-0.75) |
| U-235, corrected | 5.93% | 0.85 %/yr | 0.75 |

The corrected number lands inside the analytic band and near its top. This is the leg that rescales every burnup crossing and the qualified-envelope energy in the 7-year mission simulation and the trade-off papers, so the good news is that it holds: the 0.60 to 0.75 %/yr estimate was right, settling around 0.63 %/yr on a total-uranium basis. The 1% burnup crossing is at roughly 1.5 years at 79 kWt, consistent with what the mission simulation used.

## Reactivity / EOL leg: do not use this run

As measured, k falls from 1.00092 to 0.97403, a 2758 pcm loss over 7 years, giving a fitted slope of about -316 pcm/yr and a reactivity EOL (767 pcm cold excess spent) of 0.88 years. That misses the analytic and Service Life Report anchors badly (-106 pcm/yr, about 7.2 years).

This trajectory is not believable and it is not a real disagreement with the Service Life Report. It is internally inconsistent: the recorded composition barely moved (U-235 density down 0.08%, fission products diluted 75x by the inflated volume), and a composition change that small cannot drop k by 2758 pcm. The same volume error that deflated the burnup also froze the U-235 density and diluted the poisons that the transport solver evaluated at each step, so the k(t) this run produced does not correspond to the true composition path. Whatever drove the observed k decline, it is an artifact of the broken volume, not the physical reactivity loss.

The honest read: the reactivity slope, the 7.2-year horizon, and the 82 kWt seven-year power cap cannot be confirmed or corrected from this file. They need a rerun with the fixed volumes. The 0.88-year EOL here should be ignored.

## Do next

1. Rerun with the patched `run_depletion_7yr.py` (volume now split across fuel materials). `POWER_W=79100 python run_depletion_7yr.py`, then read it back.
2. On the corrected run, check whether the reactivity slope lands near the Service Life anchor of about 106 pcm/yr and the EOL near 7.2 years. If it does, the mission simulation's reactivity leg is validated end to end. If it does not, the cold-excess anchor or the linear rate fit needs revisiting.
3. The 120 kWt run has the same bug and needs the same rerun.

Files: `depletion_79kWt_summary_corrected.csv` (k, sigma, reactivity, corrected burnup per step), `depletion_79kWt_diagnostic.png` (k(t) and corrected-vs-file burnup).

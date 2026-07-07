> SUPERSEDED July 2026 by `Depletion_Audit_July2026.md`. The burnup leg here holds, but the volume framing and the implied fix are corrected in the audit (the lattice shares one fuel material; the core depletes as a 0-D lump).

# 7-year depletion at 120 kWt: same volume bug, burnup leg confirmed

The 120 kWt run carries the identical fuel-volume over-count as the 79 kWt run (see `Depletion_79kWt_7yr_Findings.md` for the full diagnosis). Each of the 75 depletable materials was assigned the whole-core fuel volume (8550.8 cm3), so the run modeled 355 kg of U-235 instead of SNAP's ~4.75 kg, a 75x over-count. The verdict is the same: burnup leg confirmed after correcting the denominator, reactivity/EOL leg unusable until rerun with the patched script.

## Power check passes

Cs-137 built up to 4.83e22 atoms, implying about 7.75e23 fissions. 120 kWt over 7 years is 8.27e23 fissions expected. Those agree to 94%, so the absolute burn is right and only the burnup percentage and the transport composition are corrupted by the volume error.

## Burnup leg: confirmed, and it validates the projection

| basis | 7-year burnup | rate | reference |
|---|---|---|---|
| file as-written (inflated) | 0.089% | 0.013 %/yr | (artifact) |
| total U, corrected | 6.70% | 0.958 %/yr | analytic 1.14; my projection 0.96 |
| U-235, corrected | 8.98% | 1.28 %/yr | — |

The corrected 120 kWt total-U burnup is 0.958 %/yr, matching the power-scaled projection from the 79 kWt run (0.63 x 120/79.1 = 0.96) to two significant figures. This confirms two things: burnup is linear in power as expected, and the 75x correction factor is robust across both runs.

Both measured runs come in below their analytic anchors. The analytic 1.14 %/yr for 120 was just the 0.75 %/yr anchor scaled by power, and the real burnup is about 16% lower at both powers (0.63 vs 0.75 at 79, 0.96 vs 1.14 at 120). So the burnup crossings and the qualified-envelope energy are roughly 16 to 19% more favorable than the 7-year mission simulation and the trade-off papers assumed. The 1% burnup crossing at 120 kWt moves from the assumed ~0.9 years out to about 1.04 years. This is a real correction to fold back into `simulate_7yr.py` once the reactivity leg is also confirmed.

## Reactivity / EOL leg: do not use

As measured, k falls from 1.00092 to 0.96309, a 3833 pcm loss, fitted slope about -441 pcm/yr, reactivity EOL 0.40 years. That misses the analytic anchors (-153 pcm/yr, 5.1 years) even harder than the 79 kWt case did, and for the same reason: the inflated volume freezes the U-235 density and dilutes the fission products the transport solver evaluates, so this k(t) does not track the true composition. The recorded composition change cannot produce a 3833 pcm swing. Ignore the 0.40-year EOL.

## Do next

Rerun both cases with the patched `run_depletion_7yr.py` (volume now split across fuel materials): `POWER_W=79100` and `POWER_W=120000`. On the corrected runs, confirm the reactivity slopes land near the Service Life anchors (~106 and ~153 pcm/yr) and the EOLs near 7.2 and 5.1 years. The burnup leg is already settled at ~16% below the analytic anchor for both.

Files: `depletion_120kWt_summary_corrected.csv`, `depletion_120kWt_diagnostic.png`.

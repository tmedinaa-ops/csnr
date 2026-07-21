# Peaking statistics: resolving gap item 2's double-bookkeeping (statistical half)

July 21 2026. Gap item 2 of `14kWe_Verification_Gap_Analysis.md` said the report
treats the 1.317 radial peaking two ways at once: as a measurement in the headline
ceiling and as a 1.20 to 1.45 ignorance band in the sensitivity section, and that if
the tally is trusted the fix is to report its statistical error and retire the band.
This note records the statistical error, extracted from the existing
`pin_extract/statepoint.100.h5` (no new run), by `~/Documents/snap/extract_pin_sigma.py`.

## Result

Radial peaking (hot pin / core average) = 1.3169 +/- 0.0003 at 1 sigma, 0.024%
relative. The tally behind it is 1e6 particles x 90 active batches (9e7 active
histories), which is why the error is this small. Per-pin relative sigmas run 0.024%
to 0.033% across all 37 pins. The hot pin is the center pin (#1) and its identity is
unambiguous: the next pins (#2 at 1.2529, #5 at 1.2513) sit far outside statistics.

Placed against the old band: the 1.20 edge is about 375 sigma below the measurement
and the 1.45 edge about 427 sigma above it. The band and the measurement were never
compatible descriptions of the same quantity; the band was pre-measurement ignorance
and should be retired from the sensitivity bookkeeping.

## Caveats, sized

Batch-to-batch correlation in eigenvalue tallies understates the true sigma, commonly
by a small factor. Taking the error 10x larger (0.3%) changes nothing downstream.
Cell-to-pin reduction assumes independent cell variances and handles the hot-pin vs
core-total covariance as cov(p_h, T) = var(p_h); both are approximations at the same
harmless scale. The residual non-statistical uncertainties on peaking are model-form
(nearest-pin partition on a 161x161 mesh, geometry fidelity) and, the operative one,
the temperature-feedback shift at power, which the static tally cannot see.

## The bookkeeping rule this sets up

Carry peaking in the report as: measured 1.317, statistical error negligible
(+/- 0.0003), operative uncertainty = feedback shift bounded by the Cardinal coupled
runs (`cardinal_validation/RUN_HERE.md`, Case 1 at 34 kWt confirming ~1.32 coupled,
Case 2 at 79 kWt measuring the shift at power). Once Case 2 reports, the sensitivity
section's peaking row becomes "1.317 +/- (Cardinal shift)" and the 1.20 to 1.45 row
is deleted. Until Case 2 reports, the honest interim statement is that the headline
ceiling band excludes feedback shift, not that peaking is uncertain to +/- 0.13.

Item 2 closes when the Cardinal numbers land. The statistical half is closed here.

## Files

- `~/Documents/snap/extract_pin_sigma.py` (post-processor, rerunnable)
- `~/Documents/snap/pin_power_sigma.csv` (per-pin power, peaking, 1-sigma column)
- source data: `~/Documents/snap/pin_extract/statepoint.100.h5` (June run, untouched)

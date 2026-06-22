# uprate/ -- the thermal-hydraulic uprate ceiling

This is the home for the binding study of the 14 kWe effort: how far the existing
SNAP-10A core can be uprated in thermal power before the coolant, the clad, or the EM
pump stops it. It is Group A plus the B1/B2 sweep of the structural roadmap
(`../../energy_conversion/SNAP-10A_14kWe_Structural_Roadmap.md`). Self-contained, the
same pattern as `haleu_test/` and `stirling_cycle_concept/`.

The architecture decision (from the roadmap): the friction and pump physics that bound
the uprate are 1-D channel closures, so the ceiling is computed here in the cheap
analytic model, and the stiff coupled Cardinal solve is reserved for spot-validating the
result. The full research backing, sources, and the MOOSE/Cardinal equivalents are in
`Implementation_Research_Dossier.md`.

## Files

| file | component | what it is |
|---|---|---|
| `nak78_properties.py` | A1 | temperature-dependent NaK-78 rho, cp, k, mu; anchored to arXiv Table II |
| `channel_hydraulics.py` | A2 | Cheng-Todreas tight-lattice friction and per-channel pressure drop |
| `em_pump_curve.py` | A3 | SNAP-10A EM pump H-Q curve from the NAA-SR-11879 design point |
| `sweep.py` | B1/B2 | the uprate sweep: marches power, reads the fuel / clad / pump limits |
| `sensitivity.py` | B2 | how firm the ceiling is: varies each input, ranks the levers |
| `make_figures.py` | -- | regenerates the analytical figures in `figs/` for the dossier |
| `life_check.py` | F1 | fuel/clad limits, fast fluence vs limits, H-redistribution life |
| `Implementation_Research_Dossier.md` | -- | research backing, sources, figures, MOOSE syntax |
| `Phase2_Reactivity.md` | Phase 2 | temperature coefficient and drum worth vs the uprate demand |
| `Material_Life_F1.md` | F1 | material limits confirmed, fluence life, hydrogen-redistribution cost |

## Run

```
python3 nak78_properties.py     # validates against arXiv Table II (783.15 K)
python3 channel_hydraulics.py   # validates against MOOSE Cheng-Todreas source
python3 em_pump_curve.py         # pump curve and design-point check
python3 sweep.py                 # the ceiling; --p-max / --step to extend
```

Pure NumPy, runs on the Mac in any Python with NumPy. No OpenMC or Cardinal needed.

## Status (June 2026)

Built and self-validating: A1, A2, A3, and the B1/B2 sweep. The sweep reproduces the
34 kWt design point (mixed outlet 818 K, peak fuel 867 K).

Reading (radial peaking now measured): `extract_pin_power.py` measured the radial peaking at
**1.317** (1M particles x 100 batches, fig12_test), below the 1.56 the sweep had borrowed from
Layer 2's power-density field, which double-counted axial peaking. The lower, correct peaking
raises every ceiling:

- flow held at design: 76.5 kWt
- pump-coupled, begin-of-life: 89.8 kWt
- pump-coupled, end-of-life: 79.1 kWt

The mission-relevant end-of-life number is **~79 kWt** (was ~66 with the assumed 1.56). Within
the pump-coupled cases the temperature lever (+13 kWt) and the pump's mission-life degradation
(-11 kWt) roughly offset. The peaking correction was worth ~13 kWt, all favourable, and it
firmly tilts the reading toward "same reactor run harder" being viable rather than the redesign
being forced.

Open items that tighten the number, in order:
- Spot-validate the ~79 to 90 kWt ceiling in the coupled Cardinal model for feedback-shifted
  peaking, after the conjugate convergence fix (C1). This is the first job that needs the PC.
- On the Cardinal side, swap `SimpleFluidProperties` for the built-in `NaKFluidProperties`
  and select the `cheng_todreas` closure (dossier, MOOSE paths for A1 and A2).

Done since the first cut: clad k(T) added (negligible); NAA-SR-11879 retrieved and digitized;
the above-1000 F extrapolation validated against the 1056 F flight point (~6% optimistic); pump
life degradation added (Figure 33); analytical figures generated (`make_figures.py` -> `figs/`,
embedded in the dossier); radial peaking MEASURED at 1.317 via `extract_pin_power.py`, replacing
the assumed 1.56 and lifting the end-of-life ceiling from ~66 to ~79 kWt; Phase 2 reactivity
done (temperature coefficient -1.56 pcm/K, drum worth ~5925 pcm, `Phase2_Reactivity.md`);
component F1 done (970 K / 977 K limits confirmed and sourced, fast fluence not limiting,
hydrogen redistribution the real uprate life cost, `Material_Life_F1.md`).

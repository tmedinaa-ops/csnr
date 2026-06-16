# Stirling cycle concept branch

Created June 15 2026. A self-contained branch off the energy_conversion work, the same idea as the haleu_test branch off the snap model: duplicate the files, change one thing on purpose, and leave the parent untouched. Here the change is that the reactor temperature and power are now knobs you turn, and the Stirling converter responds to them.

## What is different from the parent

The parent `energy_conversion/stirling_converter.py` holds the Stirling's relative efficiency as a fixed band, 0.30 to 0.46 of Carnot. That is fine at one operating point but wrong the instant you start raising the reactor temperature, because a regenerative engine captures a larger fraction of Carnot as the hot-to-cold span widens. So in this branch the relative efficiency is a function of the temperature ratio, anchored to two real points:

| machine | T_cold / T_hot | relative efficiency |
|---|---|---|
| SNAP-10A (775 / 590 K) | 0.76 | 0.30 |
| Kilopower (950 / 475 K) | 0.50 | 0.46 |

It interpolates in the ratio and clamps to a sane 0.20 to 0.50. It is a two-point anchored model, not a Schmidt cycle solve, so treat about plus or minus 0.05 as its uncertainty. It reproduces both anchors: set the knobs to Kilopower's 950 and 475 K and the explorer returns 23.0 percent overall, which is Kilopower's stated system efficiency, and set them to SNAP's 775 and 590 K and it returns 7.2 percent, the SNAP-temperature estimate from the parent comparison.

## How to run it

The knobs are environment variables, all defaulting to the SNAP-10A baseline, so the model with no arguments is plain SNAP.

```bash
conda activate openmc-env        # any python3 works; only stdlib + matplotlib used
python stirling_concept.py                                   # SNAP baseline
T_HOT_K=1050 python stirling_concept.py                      # hotter, same reactor power
T_HOT_K=1050 Q_THERMAL_KWT=80 python stirling_concept.py     # hotter and bigger
T_HOT_K=950 T_COLD_K=475 python stirling_concept.py          # Kilopower anchor check
python make_concept_charts.py                                # the two-panel chart
```

The knobs:

| variable | meaning | default |
|---|---|---|
| `T_HOT_K` | hot-side temperature to the converter | 775 |
| `T_COLD_K` | radiator / cold-side temperature | 590 |
| `Q_THERMAL_KWT` | reactor thermal power | 34 |
| `HEAT_FRACTION` | fraction of reactor heat reaching the converter | 0.938 |
| `TARGET_KWE` | requirement to test against | 14 |

For each setting the explorer prints the overall efficiency, the electrical output, the radiator area, the specific power, and then how far it is from the 14 kWe target, including the reactor power it would take at the current temperatures and the hot-side temperature it would take at the current reactor power.

## What it says about 14 kWe

The baseline, a Stirling on SNAP's reactor exactly as it is, makes 2.3 kWe, six times short of 14. Three findings come straight out of turning the knobs:

The reactor power is not optional. At SNAP's 34 kWt, no hot-side temperature reaches 14 kWe. Even pushed to 1600 K the output tops out near 10 kWe, because 34 kWt of heat times any believable efficiency is not enough. The requirement is a thermal-power problem first.

Temperature is the efficiency lever. Holding the radiator at SNAP's 590 K, the overall efficiency climbs from 7 percent at 775 K to about 22 percent at 1150 K, as both the Carnot ceiling and the captured fraction rise. That roughly triples the output per kilowatt of reactor heat.

Reaching 14 kWe needs both, and the radiator matters too. With SNAP's 590 K radiator it takes roughly an 80 kWt reactor at about 1050 K, or a smaller reactor at a higher temperature. Dropping the radiator toward Kilopower's 475 K lifts the efficiency further and lowers the reactor power needed. The `stirling_concept_charts.png` figure shows the family: output versus hot-side temperature for 34, 56, 80, and 120 kWt reactors, against the 14 kWe line.

## Caveats to keep attached

The relative-efficiency curve is anchored to two points and assumed linear between them. It is good for a concept trade and not for sizing a real engine; the idealized-Stirling tier would replace it with a regenerator-effectiveness calculation.

This branch does not run OpenMC. The reactor temperature and power are inputs here. Turning them up is a reactor redesign, not a setting, and the HALEU work already showed SNAP's core is leakage-bound, so an 80 kWt core at 1050 K means more fuel, a better reflector, and refractory or heat-pipe hot-end materials. The criticality and coupled-thermal side of that redesign is the OpenMC and Cardinal work in the snap repo, and this branch is the conversion half that tells you what temperature and power to aim the reactor at.

And the standing one: every kilowatt of advantage here is bought with a moving machine that has to run untended for years. KRUSTY's answer was many small convertors with redundancy, and any 14 kWe design on this path should carry that.

## Files

- `stirling_converter.py`, modified, temperature-dependent relative efficiency.
- `stirling_concept.py`, the explorer with the reactor knobs and the 14 kWe solver.
- `make_concept_charts.py` and `stirling_concept_charts.png`, the figure.
- `snap10a_te_converter.py`, copied in unchanged so the branch is self-contained.

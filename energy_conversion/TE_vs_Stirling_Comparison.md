# SNAP-10A thermoelectric vs Stirling, on the same reactor

Built June 15 2026. The question: keep SNAP-10A's reactor exactly as the OpenMC model has it and swap only the power conversion, thermoelectric out, Stirling in. How much more electricity, and at what cost in mass and radiator?

## How the comparison is set up

The OpenMC model is the heat source, not the converter. It fixes the reactor thermal power, about 31.9 kWt into the converter at the design point, and the temperatures the converter works between: average NaK 775 K on the hot side, average radiator 590 K on the cold side. Both converters face the same Carnot ceiling, 23.8 percent, and the one that captures more of it wins. None of the neutronics changes between the two.

The fair part is that the Stirling is held to SNAP's temperatures, not KRUSTY's. KRUSTY's Stirlings ran hot, a hot end near 950 to 1073 K, while SNAP's NaK is about 775 K. Handing the Stirling KRUSTY's temperatures would compare two reactors, not two converters, so the Stirling here is derated to SNAP's cooler and much smaller temperature ratio.

## The Stirling model

At the agreed grain the Stirling overall efficiency is the Carnot ceiling times a relative efficiency, the fraction of Carnot a real convertor captures. NASA's Kilopower is the anchor. Its design point is 23 percent system efficiency at 950 K hot and 475 K cold, where Carnot is 50 percent, so the relative efficiency is 0.46. The KRUSTY ground test showed about 35 percent at the convertor and 25 percent at the system.

SNAP's temperature ratio is much smaller than Kilopower's, a 23.8 percent Carnot against 50 percent, and a Stirling's relative efficiency falls as the ratio shrinks, because the fixed parasitic losses take a larger share of a smaller ideal work. There is no clean Stirling datum at SNAP's temperatures, so I carry a band rather than invent a point: an optimistic case that holds Kilopower's 0.46, and a conservative case derated to 0.30. The band is the honest output.

## Results

| metric | thermoelectric | Stirling, low | Stirling, high |
|---|---|---|---|
| relative efficiency (of Carnot) | 7.7% | 30% | 46% |
| overall efficiency | 1.82% | 7.1% | 11.0% |
| electrical output | 581 We | 2278 We | 3493 We |
| radiator area | 5.8 m^2 | 5.4 m^2 | 5.1 m^2 |
| PCS mass, estimate | 70 kg | 52 kg | 59 kg |
| specific power | 8.3 W/kg | 43 W/kg | 59 W/kg |

The radiator model reproduces SNAP's stated 5.8 m^2 to within 2 percent, which is the check that the heat-rejection side is set up correctly before any Stirling number is trusted.

## What the numbers say

A Stirling on the same reactor delivers about 2.3 to 3.5 kWe against the thermoelectric's 0.58 kWe, four to six times the electricity from the same 31.9 kWt of reactor heat. It does that by capturing 30 to 46 percent of the Carnot ceiling where the thermoelectric captures 7.7 percent. That single contrast is the whole story of static versus dynamic conversion.

Specific power moves even harder, five to seven times the thermoelectric's 8.3 W/kg, because the Stirling makes far more power from a conversion system of similar or lighter mass. This survives ignoring the mass estimate: even at the full 70 kg of the SNAP converter, the Stirling would still be four to six times better. The power gain carries the conclusion, not the soft balance-of-system mass.

The radiator is the counterintuitive part. It barely shrinks, from 5.8 m^2 to about 5.1 to 5.4 m^2. At SNAP's temperatures the converter still rejects most of the 32 kW it takes in, 28 to 30 kW against the thermoelectric's 31 kW, so the radiator stays nearly the same size. A radiator only shrinks when efficiency is high enough that most of the heat leaves as electricity, and SNAP's modest temperatures keep both converters far short of that. So the Stirling's advantage shows up as power and mass, not as a smaller radiator.

## The caveat the efficiency number hides

This is an efficiency and mass comparison, and the Stirling wins both decisively. It leaves out the reason SNAP chose thermoelectric in 1965, which is that it has no moving parts. A thermoelectric converter is solid state, vibration free, and ran the mission with nothing to wear out. A Stirling has a moving piston and displacer, and making one survive years in space unattended is the exact problem NASA spent decades on and only demonstrated at reactor scale with KRUSTY in 2018. So the honest reading is that the Stirling offers four to six times the power per unit of reactor heat and several times the specific power, in exchange for the reliability and lifetime risk of a dynamic machine. For SNAP-10A's one-year 1965 demonstration the static converter was the right call. For a modern mission where the efficiency and mass gains matter, the trade has shifted, which is precisely why Kilopower is a Stirling design.

## Honest limits

The relative-efficiency band, 0.30 to 0.46, is the main uncertainty, and it is wide on purpose because no one has run a Stirling at SNAP's exact temperatures. The Stirling mass is the softest input, built from a Kilopower convertor specific mass plus a radiator scaled from SNAP's and a flat balance allowance, which is why the robustness check is there. And this is a converter-grain comparison, Carnot times a relative efficiency, not a cycle-resolved Stirling model. That is the right fidelity for the question asked and the wrong fidelity for designing an actual engine.

## Files

- `stirling_converter.py`, the Stirling efficiency, radiator, and mass model.
- `compare_te_stirling.py`, the fixed-heat-source comparison harness.

## Sources

- KRUSTY Reactor Design (Poston et al., Nuclear Technology 2020), the uploaded paper: hot end and fuel near 800 C, reactor ~4 kWt. https://www.tandfonline.com/doi/full/10.1080/00295450.2020.1725382
- KRUSTY ground test results and Kilopower power conversion (NASA NTRS): convertor ~35 percent, system ~25 percent. https://ntrs.nasa.gov/api/citations/20180007389/downloads/20180007389.pdf
- Higher-power Kilopower design concepts (Gibson, NASA NTRS): 23 percent system at 950 K / 475 K, convertor specific mass. https://ntrs.nasa.gov/api/citations/20200001569/downloads/20200001569.pdf
- SNAP-10A converter design point: NAA-SR-11955 Table 2, via local SNAP-10A_Model_Base_Set.md Section 3 and SNAP-10A_Validation_Targets.csv.

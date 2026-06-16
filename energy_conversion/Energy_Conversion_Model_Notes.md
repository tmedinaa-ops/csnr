# SNAP-10A energy conversion model, step one

Built June 15 2026. This is the design-point reproduction called for by the validation policy: get the NAA-SR-11955 Table 2 numbers out of the lumped-couple equations first, then move to temperature-dependent SiGe properties later. It does that, and it turned up a correction to one number in the base set.

## What the model is

A lumped model of the SNAP-10A thermoelectric converter, the SiGe direct-conversion stage that sat between the NaK loop off the reactor and the radiator. The converter is 1440 N-P couples in two parallel electrical paths. Each couple carries three constants: a sum Seebeck coefficient S, an electrical resistance R0, and a thermal conductance K. The code is the converter-level form from NAA-SR-11955 (section 5.2a of the equations file): open-circuit voltage, internal resistance, current and terminal voltage at a load ratio, and the two junction heat balances whose difference is the electrical power.

Files in this folder:
- `snap10a_te_converter.py`, the model and a fitter that back-solves S, R0, K from the operating point.
- `validate_te_converter.py`, the Table 2 comparison.
- `sige_properties.py`, the RTG-grade Si80Ge20 property proxy (Seebeck, resistivity, thermal conductivity vs T), with per-property confidence flags and sources.
- `crosscheck_seebeck.py`, the material cross-check of the back-solved constants.

The model takes prescribed junction temperatures. It is decoupled from the neutronics-thermal stack on purpose, per the project decision. When the Cardinal side is producing NaK outlet temperatures, that temperature becomes the hot-side input here, but the two stay separate models for now.

## Result

The fitted constants are S = 479 uV/K, R0 = 3.89 mohm, K = 0.113 W/K per couple. With them the model reproduces Table 2 to better than 0.2 percent on every quantity: 581 We, 28.5 V, 20.4 A, 1.40 ohm, 31.90 kWt in, 31.32 kWt out, 1.82 percent overall, 7.65 percent device, 23.8 percent Carnot.

The cold-side heat is the honest check. K is fit to close the hot-side balance at 31.90 kWt, so reproducing that is circular. The cold-side rejection of 31.32 kWt is not fit to anything, and the model lands on 31.319. The energy balance closes: hot minus cold equals the electrical power to a fraction of a watt, and the three independent ways of computing that power (circuit E times I, the junction-heat difference, and the couple Seebeck-minus-Joule sum) all agree at 581.4 W.

The figure of merit comes out at ZTbar = 0.35 at a mean junction temperature of 674 K. That is the right neighborhood for the heavily doped SiGe of the early 1960s, below modern SiGe near 0.5 to 1, which is a useful sign the back-solved constants are physical rather than just curve-fit. About 84 percent of the heat input conducts straight through the legs without converting (the N K dT term dominates the hot-side balance), which is the physical reason a device that is 7.65 percent efficient at the material level delivers only 1.82 percent overall.

## Correction to the base set

The base set and equations file currently record the back-solved Seebeck as 518 uV/K. That value is an artifact and should be changed to about 479 uV/K.

The 518 figure pairs the stated open-circuit voltage, 61.7 V, with the loaded junction dT of 165.6 K. Those belong to two different states. If you carry 518 uV/K into a forward solve, the circuit power (E times I) and the heat-balance power disagree by about 16 percent, 581 W against 676 W. That gap is the tell that the constant is wrong, not that the model is.

The self-consistent value uses the loaded operating point. At the design load the open-circuit voltage implied by the terminal voltage and current is E + I R = 28.5 + 20.4 times 1.40 = 57.1 V, and 57.1 V over the 165.6 K loaded dT gives 479 uV/K. With that value all three power calculations agree, which is the whole point.

## The 61.7 V open-circuit reading is not an error

The base set flags the 61.7 V as an apparent mismatch to reconcile. It reconciles cleanly. Open circuit means zero current, which means no Peltier heat is being pumped out of the hot junction. Under load the Peltier term removes about 5.3 kW from the hot junction (N i S T_hj in the balance); remove the load and the hot junction runs hotter and the cold junction cooler, so the junction spread widens. At 479 uV/K, 61.7 V corresponds to a dT of 179 K, about 13 K wider than the 166 K loaded spread. So 57.1 V loaded and 61.7 V open are the same converter at two operating states, not a contradiction. A later version with a real hot-side thermal resistance would predict that 13 K swing instead of inferring it.

## Caveats

These are effective design-point constants, not material property curves. They are pinned at one junction-temperature pair and one load, so the model is only trustworthy near the design point until S(T), sigma(T), and k(T) for SiGe go in. It also assumes fixed junction temperatures rather than solving the hot-side thermal path, which is why the open-circuit dT is inferred rather than predicted. Both are the next step, not this one.

## Material cross-check, June 15

The lumped constants only agreed with the point they were fit to, which is partly circular. To break that, I checked them against published SiGe material data over the junction band. The cleanest test is the Seebeck, because it is geometry-free: the couple Seebeck is just |alpha_n| + |alpha_p|, no leg dimensions involved.

The honest limit going in is that SNAP's exact 67/33 arsenic-doped curves are the classified gap, so the proxy is RTG-grade Si80Ge20 (20 percent Ge), fits anchored to Basu 2014 (n-type) and Dismukes 1964 (p-type). Two files carry it: sige_properties.py holds the proxy curves with per-property confidence flags, and crosscheck_seebeck.py runs the comparison.

The proxy couple Seebeck averages 377 uV/K over 591 to 757 K, against the 479 uV/K back-solved from Table 2, so the back-solved value sits about 27 percent above the leaner alloy. That is the right order and the right direction. SNAP's richer germanium and its cooler, lower-doping design point both raise the Seebeck above RTG-grade material, and a modest doping reduction alone covers a 27 percent gap. The figure of merit is rougher, proxy ZT 0.18 against the back-solved 0.35, because it compounds the Seebeck difference with the proxy's looser resistivity and thermal conductivity; scaling the proxy Seebeck up to 479 already moves its ZT to about 0.29.

What this establishes is that the back-solved constants are consistent with SiGe material physics, not a fitting artifact, a second anchor independent of the design point they were fit to. What it does not establish is SNAP's absolute resistivity and thermal conductivity. The proxy misses the couple R0 times K product by roughly a factor of two, so predicting off-design R0(T) and K(T) still needs the real 67/33 curves. The Seebeck check is solid; the rest is order of magnitude.

## Next

Get the real 67/33 As-doped SiGe property curves to replace the RTG-grade proxy, from the RCA "Development of Thermoelectric Modules for SNAP 10A" series or AI memos NAA-SR-MEMO-10126 and NAA-SR-11205 (classified or unretrieved so far), or read them off NAA-SR-11955 Figures 43 to 50, which plot couple performance against temperature. With real curves the model becomes predictive off the design point and the ZT check tightens. After that, the degradation behavior against the same figures, where measured device efficiency drifts to about 6.0 to 6.5 percent over the mission.

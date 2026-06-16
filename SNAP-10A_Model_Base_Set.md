# SNAP-10A Model Base Set

Inputs needed to build the OpenMC and MOOSE/Cardinal models, organized by the four focus areas: shielding, reactor and fuel, energy conversion, and components/system. Every value carries its source. Where a report disagrees with another or a number could not be found, it is flagged. Validation numbers (the documented results to check a model against) live in the companion file SNAP-10A_Validation_Targets.csv.

Compiled 2026-06-08 from primary Atomics International reports on OSTI plus the 2025 OpenMC/Cardinal paper (arXiv 2505.04024). The arXiv tables are the cleanest single reconciled input set, because they were assembled for exactly this toolchain; the 1960s reports are the primary authority where they are legible.

## How to read the confidence flags
- high: stated as a clear number in a retrieved primary report or the arXiv paper.
- medium: from a primary report but OCR-degraded, derived, or design-vintage dependent.
- low: from a secondary source, or digitized off a hand-drawn figure.

---

## 1. Shielding

Primary report: NAA-SR-MEMO-8768 (flux comparison). Geometry and materials: NAA-SR-9901 (mechanical design), NAA-SR-9898 Vol III (component development), NAA-SR-MEMO-8969 (FMC-N Monte Carlo). The report holding the absolute dose-rate budget and the numeric core buckling, NAA-SR-9647, has no full text on OSTI and is the main open gap.

### Geometry
- Type: shadow shield, truncated cone (6 degree half-apex angle) with a torispherical top head and hemispherical lower head, sitting directly below the core. (NAA-SR-9901 p.6, p.18; NAA-SR-9898 Vol III p.17)
- LiH block: max diameter 21.125 in (53.66 cm), length 27.469 in (69.77 cm), weight 180.0 lb, top spherical radius ~19 in. (NAA-SR-9901 Table 1 p.7, Fig 3 p.14)
- 316 SS casing: outer diameter 23.1875 in (58.9 cm), internal diameter 18.000 to 21.843 in, casing length 20.906 in (53.1 cm). (NAA-SR-9901 Table 1, Fig 7)
- Lower head: hemispherical 316 SS, outer spherical radius 11.016 in, height 11.234 in. (NAA-SR-9901 Table 1 p.7)
- Axial anchors from core center (FMC-N): top of LiH at 5.82 cm penetration, parabola-to-cone junction 71.5 cm, bottom of shield 91.5 cm, reference dose plane 284.3 cm (17.5 ft from core bottom). (NAA-SR-MEMO-8969 body)
- Total shield assembly weight limit: 225 lb. (NAA-SR-9898 Vol III p.18)
- No tungsten or separate gamma-shield layer. LiH provides adequate gamma attenuation on its own. (NAA-SR-9901 p.13)

### Materials
- Shield: cold-pressed LiH, single block, density 0.7 g/cc at 700°F design point. (NAA-SR-MEMO-8768 Experimental Results). STF test slabs were 0.756 g/cc.
- Operating temperature: average ~800°F, max 838°F at bottom, 770°F at top; spec max 823°F at converter attachment. LiH melts at 1270°F. (NAA-SR-9901 Sec VI)
- Can and internal honeycomb: Type 316 SS (honeycomb is 0.001 in foil, 1 in cells). Casing backfilled with helium to 1 atm. (NAA-SR-9901 Sec IV) Note FMC-N omitted the honeycomb from the shield composition. (NAA-SR-MEMO-8969 p.3)

### Source definition
- Core thermal power for shield design: 34 kW. (NAA-SR-9901 p.11; NAA-SR-9898 Vol III p.17)
- Neutron source (FMC-N): fission spectrum, 0.0919 to 18.0 MeV, 35 groups equal in lethargy, split into source bands with fission fractions 0.8051 (0.1 to 3.099 MeV), 0.1647 (3.099 to 5.715), 0.0295 (5.715 to 10.54), 0.000685 (10.54 to 18). (NAA-SR-MEMO-8969 p.5, Table 3)
- Buckling: transverse term B = (2.405/R)^2, R = shield radius; AIM-6 and DTK ran a core buckling iteration; shield modeled as a stack of cylindrical slabs of varying radii and temperature-dependent densities. (NAA-SR-MEMO-8768 p.3). The numeric core buckling is not printed legibly and likely lives in NAA-SR-9647.

### FMC-N homogenized atom densities (atoms/cm^3 x 1e24), first-cut material cards
(NAA-SR-MEMO-8969 Table 1 p.16; fuel can/grid modeled as pure iron, NaK as pure sodium)
- Core: H 0.05454, Li 0.00167, Nb 0.004708, Fe 0.02917, U-235 0.001251
- Reflector: Be 0.123
- Upper plenum: Fe 0.01154; Lower plenum: Fe ~0.02336
- Shield (LiH): Li 0.0540, H 0.0540 (stoichiometric, consistent)
- Interface column is OCR-garbled; verify against the original before use.

### Tweakable parameters and credible ranges
- LiH density: 0.7 to 0.756 g/cc (design vs test slab).
- LiH removal cross section: 0.128 to 0.170 cm^-1 (old value to STF upper bound); 0.156 is the recommended default.
- Shield thickness, cone angle, dose-plane distance: fixed by geometry above, vary only to test sensitivity.
- Source spectrum and power: 34 kW default; see the reactor section for the 30 to 40 kW vintage spread.

---

## 2. Reactor and fuel

Cleanest reconciled set: arXiv 2505.04024 Tables I and II. Transient and kinetics behavior: BOOMER (NAA-SR-8414), TRANCORE-10A (NAA-SR-MEMO-9589), startup performance NAA-SR-9720. FUSAK (NAA-SR-11400) is not on OSTI in full text, so fuel hydrogen-physics numbers come from BOOMER Appendix D instead.

### Core geometry (arXiv 2505.04024 Table I)
- 37 fuel elements, hexagonal array.
- Active length 31.0515 cm; fuel rod length 31.623 cm; lattice pitch 3.20040 cm.
- Fuel radius 1.53924 cm; samarium-oxide coating outer radius 1.56210 cm; cladding outer radius 1.58750 cm (clad thickness ~0.0254 cm).
- Core vessel internal radius 11.27125 cm, external 11.34999 cm.

### Fuel (arXiv 2505.04024 Sec II)
- Uranium-zirconium hydride (U-ZrH), 10 wt% uranium, U-235 enriched to 93 wt%. Fuel designation SCA-4.
- Cladding: Hastelloy N. Inner surface coated with thin samarium oxide to suppress hydrogen diffusion.
- H/Zr atom ratio: not found (treated as a variable hydrogen concentration in the 1960s codes, not a fixed input). Total fuel mass / U-235 loading: not found.

### Coolant (arXiv 2505.04024 Table II)
- NaK-78. Mass flow 0.6199 kg/s. Inlet 755.37 K, outlet 816.48 K, average 783.15 K.
- Properties: density 755.92 kg/m^3, viscosity 1.8835e-4 Pa·s, cp 879.903 J/kg·K, k 26.2345 W/m·K.
- Original NAA-SR-9720 design temps run hotter (core inlet ~856°F, outlet ~986 to 1010°F); design-vintage difference, flag if it matters.

### Reflector and control (arXiv 2505.04024 Sec II)
- Six internal beryllium side reflectors fill voids inside the 316 SS cylindrical core vessel.
- External beryllium reflector: a static attached part plus four control drums.
- Coarse-drum worth: brings reactor from ~$6.40 to ~$1.60 subcritical, about $4.80 total; per-drum worth not separately stated. (NAA-SR-9720 p.49)

### Kinetics (the hard-to-recover set)
- beta-eff: not found as an explicit number; the codes read six-group beta and lambda from data cards, illegible in the scans. If you need exact 1960s kinetics, NAA-SR-9903 or the ORNL benchmark report (Krass and Goluoglu 2005) are the next places to look; otherwise a standard U-235 thermal six-group set is the fallback.
- Lifetime ratio l/beta* ~1600 for the SNAP 10A/2 system. (NAA-SR-MEMO-9589 p.12)
- Temperature coefficients: prompt fuel coefficient is negative but the temperature-dependent term is OCR-garbled; upper and lower grid-plate coefficients are -0.05 ¢/°F each. (NAA-SR-9720 Table 5). FS-3 measured an overall prompt coefficient of -0.29 ± 0.02 ¢/°F. (NAA-SR-11397)

### Power
- Thermal: 34.0 kW modeled (arXiv Table II); 30 kWt cited as design rating (secondary); 38 to 41 kW in NAA-SR-9720; 39.5 to 40 kWt during the FS-3 ground endurance test (NAA-SR-11397). Use 34 kW to match the arXiv model and the shield design point.
- Electrical: 500 to 510 We design.

### Tweakable parameters and credible ranges
- U-235 enrichment 93 wt% (fixed by design); hydrogen concentration / H/Zr is the main fuel knob but needs a sourced value first.
- Thermal power 30 to 41 kWt across vintages.
- NaK flow and inlet temperature per Table II, with the hotter NAA-SR-9720 design temps as the upper bound.
- Control-drum angle sets reactivity; coarse-drum span ~$4.80.

---

## 3. Energy conversion

Retrieved June 2026. This was the thinnest area; it is now the best-sourced of the non-shielding areas. The design-and-test report NAA-SR-11955 (Rocklin, Johnson, Lepisto, Mike, Willard; AI; June 1966; declassified 24 May 1973) was located full text on the UNT Digital Library (ark:/67531/metadc1033338, OSTI 4470988) and mined page by page. It gives the full nominal design point, the converter architecture, the materials, and the governing equations. Every value below is from it unless flagged. NAA-SR-Memo-6515 (Cooper 1961, electrical characteristics under power degradation) is abstract-only on OSTI (4841291) with no scan, and is superseded for design values by 11955's Table 2.

### Nominal design point (NAA-SR-11955 Table 2, primary)
- Electrical: initial power 581 We, terminal (closed-circuit) voltage 28.5 V, open-circuit voltage 61.7 V steady-state, current 20.4 A, internal resistance 1.40 ohm. 28.5 x 20.4 = 581, self-consistent.
- Thermal: heat input 31.90 kWt, heat rejected 31.32 kWt (balance closes to power), radiator 62.5 ft^2 at temperature (= 5.8 m^2), fin effectiveness 0.90, emissivity 0.89.
- Efficiency: overall 1.82%, device (material) 7.65%, Carnot (avg NaK to avg radiator) 23.8%. The three are mutually consistent (581/31900 = 1.82%; device x Carnot = overall). This confirms the ~1.8% figure as primary and kills the competing 5-6% number, which was the device-level value misread as system.
- Temperatures (deg F): NaK inlet 987 / outlet 883 / avg 935; hot junction max 954 / min 850 / avg 902; cold junction max 656 / min 552 / avg 604; radiator avg 603. Converter NaK inlet = reactor outlet = 987 F = 530.6 C.
- Requirements (Table 1): 581 We initial and at least 500 We over a one-year mission at 28.5 V; weight 151 lb max; radiator 65 ft^2 max, conical frustum 52-in base; reliability 0.989.

### Converter architecture (NAA-SR-11955 p.12, primary, resolves the old module-count conflict)
- 2880 SiGe elements = 1440 N-P couples total.
- A leg assembly is three modules welded in series: A module 20 elements (nearest reactor), B module 24, C module 28, totaling 72 elements in series. The three differ in length, element spacing, and platelet size because of the conical taper.
- 40 leg assemblies in parallel, bolted to the conical support, make the converter. Legs are cross-connected in parallel at each radiator platelet, and cross-connected leg pairs are wired in series to form a two-parallel-path circuit. So n = 2 parallel paths, each 720 couples at 28 V and ~10 A, combining to 20 A. The secondary "40 modules / 2880 pellets" confused leg assemblies with modules; "540 unicouples in 6 panels" was wrong for SNAP-10A.

### Materials (NAA-SR-11955 p.15-16, primary)
- SiGe alloy, 70 at% Si / 30 at% Ge nominal design, 67 at% Si / 33 at% Ge actually used.
- Tungsten hot shoes; copper hot straps; aluminum radiator platelets that double as the cold-junction current path, so no cold-side electrical insulator is needed. N-leg degradation phase is germanium-arsenic (As-doped). NaK tube wrapped in gold-coated molybdenum foil to keep emissivity low. Compensating pads isolate the brittle SiGe from expansion mismatch.
- Fabrication by RCA under AI subcontract. PbTe was evaluated and dropped in favor of SiGe.
- Weight (Table 3): 142.9 lb dry, 154 lb wet, 265 lb/kWe. TE elements (SiGe + W shoes) 36.8 lb, radiator 32.7 lb, NaK tubes 25.4 lb.

### Effective lumped couple properties (derived from the design point, for validation)
Back-solved from Table 2 with the report's own equations; these let a model reproduce the design point exactly:
- Sum Seebeck per couple S_N + S_P ~= 266 uV/degR (~479 uV/K), from Eoc = (N/n)(S)(THJ - TCJ) using the loaded open-circuit voltage Eoc = V + I*R = 28.5 + 20.4*1.40 = 57 V (NOT the 61.7 V open-circuit reading, which belongs to the wider open-circuit dT), N 1440, n 2, avg DT 298 degF. Using 61.7 V here gives 518 uV/K and makes circuit power and heat-balance power disagree by ~16% (581 vs 676 W); 479 uV/K is self-consistent. See energy_conversion/Energy_Conversion_Model_Notes.md.
- Resistance per couple R0 ~= 3.9 milliohm, from R = N R0 / n^2 = 1.40 ohm.
- Thermal conductance per couple K ~= 0.11 W/K, from the hot-junction heat balance against 31.90 kWt input.
These are effective design-point constants, not the temperature-dependent curves.

### NaK loop and EM pump
- Liquid-metal DC conduction thermoelectric EM pump. Final report NAA-SR-11879 "SNAP-10A Thermoelectric Pump" exists at OSTI 4516323; related OSTI 4450502 (NaK pump development summary) and 4116470 (NaK pump evaluation). Full text not yet pulled; loop flow and pump power still to extract.
- Converter NaK inlet 987 F (530.6 C); arXiv modeled reactor outlet 816.48 K (543 C), about 13 C higher.

### Qualification numbers (NAA-SR-11955 Conclusions, printed p.110, primary)
- Specific power 3.75 W/lb, reliability 0.996 at 50% confidence, power degradation under 6% in the first year, accelerated tests showing a minimum two-year life at design temperatures. SiGe modules in the SNAP-10A configuration ran over 14,000 hr at 1300 F (and 1500 F for shorter times), the basis AI cited for scaling to 15-20 kWe.

### Remaining gaps
1. SiGe temperature-dependent property curves (Seebeck, electrical resistivity, thermal conductivity vs T). 11955 gives the design-point lumped values above and plots measured converter performance and efficiency vs operating time in Figures 43-50 (degradation curves normalized to 920 F avg NaK; read off the page images, device eff ~6.0-6.5%, overall ~1.3-1.5%, both slightly below the 7.65% and 1.82% design as expected from real degradation), but no property-vs-temperature table. Correction (June 2026): NAA-SR-Memo-6670 (Bergdorf, Aug 1961, OSTI 4786094) was retrieved full text on UNT (metadc1060042) and is the WRONG source. It is a PbTe element test-apparatus and method memo (the word silicon never appears; PbTe throughout), predating the SiGe selection. It documents AI's measurement technique (matched-load internal resistance from a 5 A AC IR drop, open-circuit voltage off spot-welded Fe wires, Seebeck and resistance curves taken 300-900 F at 100 F intervals at a 900/600 F junction set) but no SiGe data. Per 11955's own reference list (printed p.111), the SiGe module and material source is the RCA report series "Development of Thermoelectric Modules for SNAP 10A" (Progress Reports 1-3, 1962) and "Phase III, Development and Fabrication of Thermoelectric Modules for SNAP 10A" (Quarterly Reports 1-4, 1962-63), plus AI module memos NAA-SR-MEMO-10126 (Block and Willard, "High Temperature Performance Testing and Evaluation of Type VF Modules," June 1964) and NAA-SR-11205 (Willard, module post-mortem, 1965, classified CRD). Those RCA reports, or the canonical RCA Ge-Si property literature (Dismukes et al., J. Appl. Phys. 1964, heavily doped Ge-Si to 1300 K), are the next target for clean alpha(T), sigma(T), k(T). None retrieved yet.
2. Measured flight performance. NAA-SR-11955 Figures 43-53 hold FS-3 and FS-4 data (Fig 51 FS-4 flight converter performance, printed p.104) as graphs; pull page images if a measured-vs-design target is wanted.
3. EM pump loop flow and power from NAA-SR-11879.

---

## 4. Components / system

Scope still to be defined by you. Useful pieces already in hand:
- Reflector and control-drum worth fall out of the OpenMC neutronics for free (see reactor section).
- Whole-power-unit dynamics, control specs, and stability are in the SNAP 10A Total System Simulation, NAA-SR-MEMO-6721, which was not located on OSTI under that number; the annotated bibliography (NAA-SR-Memo-12023, OSTI 4077974) should give its catalog entry.
- Startup and control dynamics: NAA-SR-9720 and the PSM-2 analog simulator.
- The qualification-test reports (bearings, resistors) are hardware test data, not physics models.

Tell me which components you want and I will map each to its report and benchmark.

---

## Open gaps and conflicts (read before building)
- NAA-SR-9647 (absolute neutron and gamma dose rates at the dose plane, numeric core buckling): no OSTI full text. Main shielding gap.
- Fluence-limit energy cutoff conflict: NAA-SR-9901 states the 1e12 nvt limit at >0.1 MeV; NAA-SR-9898 Vol III states >1.0 MeV. Resolve before using as a target.
- Thermal power vintage spread: 30 / 34 / 38 to 41 / 39.5 to 40 kWt. Pick one per study and state it.
- FUSAK (NAA-SR-11400): not on OSTI in full text; fuel hydrogen physics substituted from BOOMER Appendix D.
- Energy conversion: converter design reports not retrieved; SiGe and all converter numbers are secondary/unconfirmed.
- Total System Simulation (NAA-SR-MEMO-6721): not located.

# CSNR Project Direction

Consolidated July 13 2026; hot-side firm-up July 15 2026 (f_heat sourced to 0.978, net 14.12 -> 14.72 kWe;
hot loop pinned 3.5 m; 5 K held by a 2.17 mm jacket gap; cold + hot interfaces handed off as ICDs). Every
number here is current. REGENERATION COMPLETE (July 17 2026): the paper, manuscript, briefing deck,
technical spec (now Rev D: enabling condition 0.415/0.405 per ICD-002, margin policy cited), the two ICDs
and equation_chain.py all agree with the 14.72 source of truth (backups *_pre_fheat_backup / _RevC_backup).
Two deliberate exceptions, stated in the documents themselves: the paper/manuscript Table II + Fig. 6 pump
ladder stays on the 0.938 comparability basis (caption says so), and the equations/assumptions sheet remains
the heat-pipe ALTERNATIVE branch's sheet with a page-1 STATUS note pointing to Table III for the adopted
design. New since July 17: SNAP-10A_Margin_Policy.docx (NOTE-003, margin_policy.py: adverse stacks on the
built radiator; band-edge convertor and 10x manifold are unrecoverable, exclusion-by-test items) and
shielding/shield_dose_scaling.py (payload plane 2.28x flight environment at the uprate, ~8 kg LiH to hold it). Panel compliance limits
per the regenerated Fig. 5: 462 K at the design power, 469 K at the ceiling (supersedes the 468 K note
below where they differ). Mass fix July 17: design_point_450k_pumped.py M_POWER_SYSTEM 369 -> 352 kg
(the 9 kg pinned hot loop replacing the 26 kg placeholder), stack 747 kg; script and spec now agree. The full chronological record, including
superseded numbers and the reasoning that produced them, is in Project_History_Archive.md; that file
is history, not instruction, and nothing should be quoted from it without checking it against this one.

## What this project is
Policy analysis at CSNR on SNAP-10A and the regulation of space nuclear systems. Tomas is in the
policy lane, not the reactor engineering lane. The through line is how NSPM-20 and its lineage would
treat a SNAP-10A class reactor today, and what that means for future nuclear electric propulsion.

## Settled conclusions (do not relitigate without new evidence)
- SNAP-10A's safety mechanism and disposal plan would pass modern regulation. Its operational orbit was its disposal orbit, reached by the Atlas-Agena and verified before startup, and the reactor shut down nuclearly safe in a stable, long-lived orbit. That substantially meets NPR 8715.26, and a high disposal orbit is still an accepted destination.
- The mission ended on a payload fault, the Agena voltage regulator, not the reactor or the disposal, and it failed safe. The one honest caveat is debris, since the later NaK coolant release would draw Orbital Debris Program Office attention.
- HEU and reactor category mean more scrutiny and a higher tier, not a failure.
- The core regulatory shift to make the argument around is the move from a deterministic population dose standard in 1965 to NSPM-20's probabilistic 25 rem at one in a million.
- 14 kWe does NOT need a bigger reactor. It needs the flown reactor run harder, converted better, and rejected colder. This reframe is the project's engineering contribution and it is defended, not asserted.

## THE ADOPTED DESIGN (frozen baseline) -- read this before touching any number
The configuration the project moves forward with. It is Section XI + Table IV of the paper, and every
value comes from energy_conversion/nak_only_stirling/design_point_450k_pumped.py.

Organizing principle: take the least reactor power that meets the requirement, spend the margin so
gained on the FUEL rather than on the output, and buy the remaining electricity from conversion and
rejection, which cost mass rather than fuel life.

- Core: unchanged flight article, 37-pin U-ZrH, Be reflector, four drums. No geometry change.
- Power: 77.4 kWt, THROTTLED 1.7 kWt under the 79.1 kWt EOL fuel-limited ceiling, so the design does not sit on its own wall.
- Fuel loading: ZONED, fissile-conserving ring loading at tilt 0.10 (four distinct pin loadings). Peaking 1.317 -> 1.214, hot pin 949 K (21 K under the 970 K wall; unzoned at the same power sits at 966 K). Costs 60 pcm. Adopted for MARGIN, not output: it buys zero electricity, because the mixed coolant outlet is power/flow and does not care about the radial shape of the source.
- Coolant: NaK-78, SINGLE loop, no intermediate heat exchanger, 0.642 kg/s, 755 K in / 894 K out.
- Primary pump: FSP-lineage annular linear induction pump (ALIP), THROTTLED to design flow, 0.11 kWe. An ENDURANCE decision, not a power one: the flight TEM pump loses 13%/yr of drive and forces a compounding derate, while the throttled ALIP holds output flat for as long as the fuel lasts.
- Hot side: direct NaK annular jacket on the Stirling heater heads. NO heat pipes, NO IHX. 5 K drop, heater cap 889 K. The 5 K is a GAP requirement, not fins: a 2.17 mm annular gap raises the NaK film coefficient enough to hold it on the bare collar (hot_jacket_gap.py). Fins are inefficient here (liquid-metal fin efficiency ~0.3), so the old "2.2x bare-collar area" framing is superseded. The hot loop is SHORT, 3.5 m developed (compact 8-convertor ring, hot_loop_length.py); that shortness is what keeps the parasitic loss small.
- Conversion: 8 Kilopower-class free-piston Stirling convertors, helium working gas, 1.89 kWe gross each, redundancy as the answer to moving parts. Carnot 45.7% x rel 0.436 = 19.9% overall.
- Cold side: pumped NaK rejection loop, 3.0 kg/s through a 75 mm bore (0.24 kWe), into DIRECT-NaK radiator panels at 450 K, 32.7 m2, rejecting 60.6 kW. Cold junction 482.8 K = panel + the 32.8 K rejection stack.
- Fluids: exactly TWO in the whole system, NaK outside the convertors and helium inside them. No sodium, no potassium, no water.
- Output: 15.07 kWe gross - 0.35 kWe pumps = 14.72 kWe NET against the 14.0 kWe requirement. This rests on f_heat 0.978, SOURCED July 15 2026 by parasitic_heat_loss.py (itemized, MLI-radiation-dominated ~2.2% loss), replacing the un-sourced 0.938. It CARRIES MLI-PERFORMANCE RISK: if the refractory insulation degrades toward eps ~0.1, f_heat falls to ~0.95 and net gives back ~0.4 kWe, so 14.72 is an eps=0.05 number. 1.1 kWe of reserve at the 79.1 kWt ceiling (15.12). Met for any panel at or below 462 K (468 K spending reactor reserve).
- Mass: 352 kg power system (42 W/kg), 747 kg flight stack. Primary line is 9 kg at the pinned 3.5 m hot loop (was 26 kg at the 20 m placeholder).
- Margins: fuel 21 K, clad 37 K (939.8 K against the 977 K limit).
- Binding limit: FUEL BURNUP. At 77.4 kWt the 1% qualified envelope is reached at 1.2 yr (U-235 basis, the conservative one). Every year beyond that is bought from an irradiation test, not from analysis.
- The one condition on the result: the convertor must deliver >= 0.415 of Carnot at the design point, 0.405 at the ceiling (KRUSTY measured 0.46; the pre-f_heat figure was 0.43, superseded, matches ICD-002). No reactor or radiator lever recovers it, because the panel already sits at its limit. State it, do not bury it. Second condition: f_heat 0.978 is an emissivity-0.05 number; MLI degradation toward 0.1 returns ~0.4 kWe, covered by the ceiling reserve.

REJECTED, with the number that rejected it:
- Thermoelectric conversion: caps this heat source near 5.4 kWe; 14 kWe would need couple ZT ~3.7, which no bulk material has.
- Bare-grid hot-channel orificing: the open P/D 1.008 lattice mixes an imposed flow bias away (retained fraction ~0.05), realized output 13.2 kWe, the reference point back again. Retained ONLY as a shrouded-2-3-zone option, a core-internals redesign, NOT in the baseline.
- Inlet chilling: strictly dominated, it chills the converter hot side at the same time.
- Fuel overtemperature: dies in ~30 K, the clad hits its own 977 K limit. S8ER cracked a majority of clads at sustained higher temperature.
- Ti/K heat pipes on the hot side: removed in favor of the direct NaK jacket.
- FSP mechanical centrifugal pump: SmCo magnets cap ~350 C against a loop whose coldest point runs ~480 C.
- Pump ladder upper rungs (120-181 kWt): excluded, they assume heat a leakage-bound core cannot make.
- Enrichment zoning: ~an order of magnitude worse pcm per unit of flattening than loading zoning, and edge-capped near tilt 0.09.
- U-Mo fuel: not a swap in either direction. U-10Mo packs ~25x the uranium into the same volume and removes the moderator; a buildable core is KRUSTY-class (~6x the fissile), which is a different reactor.
- Heat-pipe cold end (72.9 kWt / 14.60 kWe): a real alternative architecture, documented in energy_conversion/heatpipe_coldend/, but NOT adopted.

## Source-of-truth rules (these have bitten before, follow them)
1. design_point_450k_pumped.py is THE source of truth for every chain number. If a document disagrees with it, the document is wrong; regenerate the document.
2. NEVER quote a peak-fuel temperature and a fuel ceiling from different flow policies. Everything thermal comes from sweep.py at the pump-coupled EOL flow. hot_channel_analytic.py is the old Layer-2 close-out model and is hardwired to the DESIGN flow (0.620 kg/s); do not mix it in.
3. Carnot is evaluated at CONVERTOR JUNCTIONS, never at a coolant or panel temperature. Both endpoints of the relative-efficiency law are junctions (SNAP 902 F / 604 F; KRUSTY 950 K / 475 K). This error has been made twice, once on each end of the machine.
4. The cold junction is DERIVED from the panel through the rejection stack (fin 12 K + half the 21 K coolant rise + 10 K cooler approach = 32 K). The stack is not a constant: its dominant term is Q/(m cp), so it grows with waste heat. Do not freeze it across a power sweep.
5. Radial peaking is the PIN-INTEGRATED factor, 1.317, applied with the 1.40 axial factor separately. The 1.56 seen in older figures is a local power-density peak that folds axial in; using it as a radial factor double-counts.
6. Every script carries a design-point self-check that must pass before its output is trusted. If you add a script, add the self-check. If a self-check passes while the numbers are wrong, the self-check is anchored to a stale value; fix the anchor.

## Deliverables: what is current
- SNAP-10A_NSPM20_14kWe_Paper.docx -- THE PUBLICATION DOCUMENT. 12 sections, 9 figures, 4 tables. Table III is the assumption register (14 rows: value, what it is worth, how it closes). Table IV is the adopted design. Standard for this document: present and defend the numbers, state the methodology as current, expose and argue the ASSUMPTIONS rather than the thought process. No self-correction narrative anywhere, and nothing hidden either.
- SNAP-10A_NSPM20_14kWe_Manuscript.docx -- the working manuscript the paper was built from. Keep for drafting; the paper is what ships.
- SNAP-10A_Equations_and_Assumptions.docx -- companion equation/assumption sheet. NOTE: its A1-A12 register is the HEAT-PIPE branch's, not the adopted pumped-loop design's; the paper's Table III supersedes it for the adopted design.
- SNAP-10A_System_Technical_Specification.docx (CSNR-SNAP10A-SPEC-001, Rev. C) -- the power-system datasheet, subsystem by subsystem, every row flagged Defended/Assumed/Open with a firm-up tracker (Sec 14). CURRENT at 14.72 kWe. Regenerated by outputs/gen_spec.js.
- SNAP-10A_ColdLoop_Interface_Control_Document.docx (CSNR-SNAP10A-ICD-001, Rev. B) -- the interface the RADIATOR team designs to. One knob: effective panel temperature (<=462 K nominal). Backed by cold_interface.py.
- SNAP-10A_HeaterHead_Interface_Control_Document.docx (CSNR-SNAP10A-ICD-002, Rev. A) -- the interface the STIRLING CONVERTOR vendor designs to. One knob: relative efficiency (>=0.415). Backed by hot_interface.py.
- SNAP-10A_NaK_Tube_Diameter_Calc.docx (CSNR-SNAP10A-NOTE-002) -- shareable bore-sizing memo; 75 mm ID held (66 mm now permitted post-f_heat, held as dP margin).
- SNAP-10A_Firmup_Change_Record.md -- the running change log for the cold+hot firm-up (f_heat, clad, wall gauge, interfaces). Read this to see what moved and what is now stale.
- SNAP-10A_UZrH_Test_Reduction_Argument.docx (CSNR-SNAP10A-QUAL-001) -- the fuel-requalification policy memo.
- SNAP-10A_HALEU_Conversion_Preliminary.docx -- the HALEU paper.
- SNAP-10A_CSNR_Briefing.pptx -- the deck, 24 slides, now ON the resolved chain and the adopted design (July 13 2026). Backup of the pre-fix version: SNAP-10A_CSNR_Briefing_pre_resolved_backup.pptx. Six figures were swapped (temp coefficient, output-vs-panel, architecture, pump curves, levers-vs-life, endurance clocks); slide 17's three-loop/heat-pipe schematic was replaced by energy_conversion/nak_only_stirling/generate_adopted_architecture.py (SNAP-10A_Adopted_Architecture.png), which reads its numbers live from the design point.
- SNAP-10A_Thermoelectric_Report.docx -- standalone energy-conversion primer.
- Manuscript_Internal_Consistency_Audit.md -- the audit that produced the current numbers, and the record of what was fixed.

SUPERSEDED, do not quote: SNAP-10A_14kWe_Verification.docx (R2), SNAP-10A_Power_Tradeoff_Study.docx, SNAP-10A_120kWt_MechPump_Verification.docx, SNAP-10A_7yr_Mission_Simulation.md, Path_to_14kWe_Verified.md, Uprate_Workstream_Report.md, SNAP-10A_Service_Life_Report.md, Energy_Output_vs_Lifespan_Tradeoff.md, and every kWe figure produced before the July 13 cold-side audit. They are optimistic by 1.5 to 2.3 kWe and several carry the stale -1.56 pcm/K and 14.6 kWe numbers.

## PMAD workstream (July 14 2026) -- explored, NOT in the paper
The paper's narrative is the production of 14 kWe from the core and the Stirlings. It ends at
the alternator terminals, and that boundary is deliberate: the power management and distribution
(PMAD) beyond the alternator is a separate engineering problem and is out of scope for the paper.
This is a scoping decision, not a gap to be closed. Do not fold the PMAD material into the paper
unless the scope of the paper itself is later widened.

Code and figures live in energy_conversion/pmad/. The workstream stands on its own and is kept for
future use, so nothing here is superseded, but two facts from it are worth carrying forward:

1. BOUNDARY DISCIPLINE. The paper's headline "14.12 kWe net" is single-phase AC at the convertor
   terminals with the two NaK pumps subtracted. It is correct for the paper's scope. It is NOT a
   usable-bus number. The PMAD chain shows that after the convertor controllers, the bus cable and
   the pump inverter, holding 14.0 kWe at a 120 VDC user bus needs the core re-throttled to ~81.5
   kWt (from 77.4). Never quote the terminal number and a bus number as if they were the same
   quantity. If the paper ever grows a system section, this is the first thing to reconcile.
2. WHAT THE WORKSTREAM FOUND (recorded so it is not re-derived): adopted architecture is a 120 VDC
   bus (AEPS-compatible), 8 per-convertor ACUs in the NASA GRC NETS-2021 topology (series PFC cap +
   diode rectifier + GaN DCM boost + analog PI stroke control, no FPGA), a hot 800 K dump-load panel
   as the loss-of-load backup, and an aluminium bus stood off the radiator. The PFC capacitor is the
   PRIMARY overstroke defence, not the dump load. Self-start is a CENTERING-SPRING property (specify
   it), not free heat: KRUSTY/ASC needed motoring. The DCM boost caps the alternator at ~74 Vrms.
   A startup battery (~67 kg at a 6 h checkout) and the PFC capacitor volume were booked nowhere in
   the project before this. Sources: NASA GRC NETS-2021 (Barth), 40 kWe FSP (Oleson), AEPS qual.

## HALEU refractory exploration (Li-7 + Nb-1Zr, axial_reflector/) -- EXPLORATORY, a DIFFERENT reactor
Started July 22 2026, off the HALEU route. It asks whether the de-enriched HALEU core can be made
critical, and with the least beryllium, by changing coolant, clad, loading, and reflector shape. By
the end it is a lithium-cooled, niobium-clad, TRIGA-loaded refractory core, i.e. SP-100 class. It is
NOT the adopted SNAP design and it is NOT SNAP: the flown-article policy argument that the paper
rests on does NOT cover this reactor. Keep it quarantined from the paper, deck, and spec, like the
radiator "straw" work. Recorded so it is not re-derived and so the open gate below can be built in a
new session. Everything below is STATIC EIGENVALUE on the snap haleu_test model, U-ZrH kept.

- Loading ladder (NaK/Hastelloy): U_MULT=3 (m3) k=0.869; U_MULT=4 (m4) k=0.889. Loading is the big
  fissile lever, lifting the radial-Be ceiling from ~0.976 (m3, cannot reach critical) to 0.994 (m4).
- Coolant/clad swap (li_nb_base_reactivity.py: NaK->Li-7 99.99at%, Hastelloy-N + Ni steels ->Nb-1Zr):
  worth +969 pcm on m3, +710 on m4 (loading dilutes the coolant/clad absorption); it also amplifies
  reflector worth ~450 pcm on a cleaner core. SMALL levers. Natural lithium is strongly NEGATIVE
  (Li-6 poison), so Li-7 enrichment is mandatory.
- First critical config (hybrid_reflector_sweep.py MATSWAP=li_nb on m4): radial Be only crosses k=1 at
  ~17.5 cm / 182 kg Be, no liner, no ring. The hydride LINER is dead (caps BELOW critical, adds ZrH
  mass); do not revisit it.
- Minimum-Be critical config (refl_sphere_scan.py, REFL_R sphere on m4 Li/Nb): critical near-sphere
  R~22.8 cm / ~37 kg Be; buildable-with-margin R=24 cm / 50.4 kg Be / +1,751 pcm. The SPHERE is the
  biggest beryllium lever (5x lighter than the radial cylinder, because it reflects the axial 30% the
  cylinder leaks), and it beats the HALEU study's original ~65 kg U_MULT=3 sphere. Recipe, settled:
  near-sphere geometry + higher loading + clean coolant/clad, NOT the liner, NOT a radial shell.
- Files in axial_reflector/: Hybrid_Reflector_Design_Note.md (running record, Results 1-3),
  Leakage_Split_Prediction.md (measured 70/30 radial/axial), hybrid_reflector_sweep.py (MATSWAP=li_nb
  applies the swap to every variant), li_nb_base_reactivity.py, refl_sphere_scan.py. Models live at
  snap/haleu_test/m3, m4, runs_sphere_m4/ (gitignored; rebuild with
  `U_MULT=4 [REFL_SHAPE=sphere REFL_R=24] python snap.py haleu_test <outdir>`).

THE OPEN GATE -- BUILD THIS NEXT: hydrogen-loss life of the Nb-clad ZrH core. Every number above is a
day-one eigenvalue. Niobium is a hydrogen getter, so the Nb clad drains hydrogen out of the ZrH over
the mission; that reactivity drift is invisible to a static k and is the same order as the +1,751 pcm
buffer at R=24. Until it is modeled, "critical" is provisional. Target config for the calc: m4
(U_MULT=4) Li-7/Nb, R=24 sphere, +1,751 pcm buffer, against the mission length. Pieces exist in the
snap repo's life_test/ (run_h_worth_lib.py: ~-560 pcm per %H removed; run_cold_excess.py bridges pcm
to %-of-excess). What must be ADDED: the Nb uptake rate, how fast hydrogen partitions from ZrH into
the niobium (Nb-H solubility/thermodynamics at the ~900 K clad temperature), which sets the drain
rate. drain rate x hydrogen worth = pcm/yr; compare to the buffer over the mission. If the drift
exceeds the buffer, the config walks subcritical and the 50 kg was spent on a reactor that does not
survive its own life.

## Where the code lives
- energy_conversion/nak_only_stirling/ -- THE CHAIN. design_point_450k_pumped.py (source of truth; F_HEAT now 0.978), cold_side_audit.py (the resolved cold-side stack), hot_side_direct.py (the adopted direct-NaK heater jacket; its Q_ENGINE=72.6e3 is STALE, superseded by hot_jacket_gap.py at f_heat 0.978), hot_side.py (retained ONLY as the validation anchor for the NaK film coefficient, 16,053 W/m2K, reproduced against Langlois), rejection_loop.py, rejection_pump_sizing.py (its primary-line 20 m and gross 14.55 are STALE; see hot_loop_length.py and the current design point). FIRM-UP SCRIPTS (July 15 2026, all self-checked): loop_pressure.py (hydraulic + static pressures both loops; found the 18 kPa cover-gas vapor floor), cold_pipe_wall.py (cold-line wall gauge; surfaced the radiator meteoroid-armor open item), cold_interface.py (radiator panel-temperature coupling, ICD-001), parasitic_heat_loss.py (sources f_heat 0.978, MLI-radiation-dominated, carries MLI risk), hot_loop_length.py (pins the 3.5 m hot loop, reconciles f_heat), hot_jacket_gap.py (holds 5 K with a 2.17 mm gap, not fins), hot_interface.py (convertor relative-efficiency coupling, ICD-002).
- energy_conversion/stirling_cycle_concept/stirling_converter.py -- the eta = Carnot x rel law and its two junction anchors.
- energy_conversion/ -- the thermoelectric work: snap10a_te_converter.py (reproduces NAA-SR-11955 Table 2 to <0.2%), snap10a_te_predictive.py (runs off-design), sige_properties_v2.py, te_to_14kwe.py, te_materials.py.
- energy_conversion/heatpipe_coldend/ -- the alternative architecture. Self-contained, not adopted.
- energy_conversion/pmad/ -- the electrical workstream (alternator terminals to thruster). NOT in the paper, see the PMAD note below. pmad_design.py is its source of truth and reads design_point_450k_pumped.py live. generate_pmad_schematic.py (block diagram), generate_pmad_layout.py (to-scale vehicle elevation with the LiH umbra), generate_pmad_3d_viewer.py (writes an interactive Three.js HTML from pmad_design.py, so the model cannot drift). Self-checks pass.
- heat_transport/uprate/ -- the reactor side. sweep.py (ceiling, outlet, peak fuel, peak clad; the ONLY thermal model to quote from), nak78_properties.py (A1), channel_hydraulics.py (A2, Cheng-Todreas), em_pump_curve.py (A3, TEM from NAA-SR-11879 Fig 14 + the measured ALIP curve), life_check.py (F1: the 970 K fuel and 977 K clad limits are SOURCED, not placeholders), subchannel_crossflow.py (the orificing gate, phi ~ 0.05 bare), power_ladder_resolved.py (Table II and Fig 6), consistency_recheck.py, make_fig_endurance.py, make_fig_p2_temp_coeff.py.
- heat_transport/ -- the Cardinal/MOOSE model. README.md first. layer2_core/ is the 37-pin coupled model (OpenMC-as-main); cardinal_validation/ is the PC spot-validation. hot_channel_analytic.py is the Layer-2 analytic close-out: design-flow only, see rule 2.
- heat_transport/system_loop/ -- reactor-to-radiator in one THM solve. Open deck validated on the PC; the recirculating deck is built, not yet run.
- depletion_7yr/ -- the depletion package and its findings.
- fuel_tradeoff/ -- the U-ZrH vs U-Mo decision memo, the comfort-band scripts, the PCS CAD handoff (pcs_cad_sizing.py, the interface diagram), the drawings, the parts schedule, and build_3d.py.
- axial_reflector/ -- the leakage-split work (leakage_split.py, reflector_sweep.py) AND the HALEU refractory exploration (Li-7 + Nb, sphere reflector): hybrid_reflector_sweep.py, li_nb_base_reactivity.py, refl_sphere_scan.py, Hybrid_Reflector_Design_Note.md. EXPLORATORY, a different reactor, see the exploration section above; NOT the adopted design.
- Documents/snap (separate repo) -- the OpenMC core model. snap.py, case fig12_test. Branches: haleu_test/, peaking_test/ (zoning), umoly_test/ (built, not yet run). Read its own CLAUDE.md first.

## Validated results that stand
- Neutronics: fig12_test reproduces the published coupled k within 53 pcm (1.00033 +/- 34 vs 1.00086 +/- 24). Tag v1.0-fig12-validated. HexLattice conversion gave ~300x tracking speed with unchanged physics.
- Temperature coefficient: -1.46 +/- 0.05 pcm/K (1M particles, 300 active batches). Cold excess 767 pcm off the validated eigenvalue, 738 pcm off the sweep's own 300 K point; defect 734 pcm.
- Drum worth: 5,980 +/- 28 pcm by material swap. Unreflected k = 0.944.
- Radial peaking: 1.317 pin-integrated, measured on a 1M-particle per-pin tally. Axial 1.40.
- Thermal: at the flown 34 kWt, NaK outlet 817.7 K, hot-channel outlet 852.6 K, peak fuel ~850 K, ~120 K under the wall. Confirmed by independent hand calculation.
- Uprate ceiling: 76.5 kWt held-flow, 89.8 BOL pump-coupled, 79.1 EOL pump-coupled (unzoned); 86.5 kWt EOL zoned.
- Thermoelectric: reproduces NAA-SR-11955 Table 2 to <0.2% (581 We, 1.82% overall). The Seebeck reconciles at 479 uV/K once the 61.7 V is recognized as the open-circuit state; the flown relative efficiency is 0.083 of Carnot, which agrees with the ZT couple formula's 0.084 at ZT 0.35.
- Architecture: reproduces Langlois 2006 (ADA453034) to the digits, radiator 404.9 m2, panel temps within 2 K, HX offset 29.3 K.
- Depletion (79.1 kWt, 1 yr, 22 steps, correct 4.75 kg U-235 inventory, ~18 pcm noise): 0.85 %/yr U-235, 0.63 %/yr total-U (inside the assumed 0.60-0.75 band), U-235 4750 -> 4710 g, 0.61 g Pu bred. 1% envelope at 1.2 yr (U-235) / 1.6 yr (total-U). Reactivity consumption 319 pcm/yr with the drums frozen; a 7-yr mission spends 2,230 pcm of the 5,980 pcm of drum worth.
- HALEU: de-enriched to 19.75 wt% the core falls to k = 0.7245, ~38,000 pcm subcritical. The core is leakage-bound (k-inf 1.37-1.50, ~40% leakage), so loading saturates near k = 0.93 even at 45 wt%. Recovery needs TRIGA-class loading PLUS ~65 kg of added Be reflector. HALEU conversion is a fuel-and-reflector redesign, not an isotope swap. Consequence that generalizes: on a leakage-bound core, reflector worth per kg beats fissile worth per kg.
- Zoning: peaking 1.318 -> 1.214 at tilt 0.10, ~60 pcm by warm-chained differential worth (~17 pcm noise floor). Held-flow ceiling 76.5 -> 83.0 kWt.

## Open items, ranked
1. Coupled Cardinal validation (heat_transport/cardinal_validation/, PC). The capstone: hot-side temperatures and the feedback-shifted peaking. 3-D neutronics already confirm the standalone eigenvalue (k 1.0003-1.0008). The solid-THM conjugate is stiff and was at 73% heat closure under interface relaxation; the next lever is warm-starting the solid (FullSolveMultiApp -> TransientMultiApp in openmc.i). WATCH OUT: the solid's power_imbalance postprocessor is misleading (it is a SideDiffusiveFluxIntegral and always closes by Gauss); the real check is the sum of the 37 THM heat_added against power_in.
2. Drum-controlled depletion (drums re-searched to critical each step) so the quantity computed is drum travel spent, not a frozen-geometry eigenvalue drifting from a cold reference. This is what converts 319 pcm/yr into an operational reactivity margin.
3. Step-refined 7-year depletion. The coarse 7-yr run reproduces 1-yr burnup to three digits (0.628 vs 0.631 % total-U) but is 2x more negative in reactivity at 1 yr: the discrepancy is TIME DISCRETIZATION (11 predictor-only steps), not neutronics. Keep the predictor-corrector integrator and refine the steps.
4. Subchannel or CFD solve to pin the orificing retained fraction (currently a reduced-order capacity estimate bracketed by its ducted and open limits).
5. Routed layout to close the rejection loop's first-order sizing (129 kg, 0.24 kWe, 75 mm bore over 20 m). The loop's pressure drop has no anchor of the quality the hot side enjoys.
6. f_heat = 0.938 is a flight budget, not a computed piping and shield loss. Worth 0.3 kWe per 0.02.
7. BISON access through INL's NCRC is the long pole for the fuel-qualification demonstration; request early. Once granted it installs by conda and runs natively on Apple Silicon.

## Environments
- Mac (authoring, small runs): OpenMC 0.15.3 in conda env `openmc-env` (osx-64 under Rosetta via miniforge). `conda activate openmc-env` every session. Data ENDF/B-VIII.0 at ~/openmc_data/endfb-viii.0-hdf5/cross_sections.xml, OPENMC_CROSS_SECTIONS in ~/.zshrc. Smoke test: OpenMC_Workshop/pincell.py. Cardinal builds and couples natively on Apple Silicon in the `moose` conda env (NOT openmc-env); cardinal-opt at ~/cardinal/cardinal-opt. Install and recovery steps in Cardinal_MOOSE_Install_Guide.md.
- PC (heavy compute): Windows + WSL2 Ubuntu, 20 cores / 64 GB. Gotchas, all resolved, recorded so they do not recur: (1) run cardinal-opt in the `moose` env, not openmc-env, because openmc-env's mpiexec is OpenMPI/PMIx while cardinal-opt links MPICH; (2) `export HDF5_USE_FILE_LOCKING=FALSE` and rm stale summary.h5/statepoint*.h5 before re-running OpenMC; (3) use the Linux data path, never the \\wsl.localhost\ one; (4) on a CRLF conflict during a fast-forward pull, `git fetch origin && git reset --hard origin/<branch>`.
- Sync: git, one private repo each. github.com/tmedinaa-ops/csnr (this folder, main) and github.com/tmedinaa-ops/snap (master), SSH per-machine key. Generated XML, meshes, statepoints, h5 and run CSVs are gitignored and regenerate locally. On the PC, clone into the WSL home, never /mnt/c.
- Unattended runs: heat_transport/cardinal_validation/run_and_notify.sh parses the result CSVs and pushes a one-line summary to a phone via ntfy.sh. Set NTFY_TOPIC.

## Sources: retrieved, and the gaps that remain
- Retrieved and mined: NAA-SR-11955 (power conversion; Table 2 design point, 2880 SiGe elements, hot junction 902 F / cold 604 F), NAA-SR-11879 (thermoelectric EM pump; Fig 14 head-flow digitized, Fig 33 the 13%/yr decay), NAA-SR-11934 (SNAPSHOT flight performance), Langlois 2006 (ADA453034), Polzin 2010 and Geng-Reid 2017 (the ALIP).
- The dissociation-pressure closure is NOT a gap: open literature closes it (Libowitz 1962, Wang-Olander 1995, Simnad 1981; H2 pressure depends on H/Zr and T only, U-independent). FUSAK is not the redistribution code and its report number is unverifiable; the real one is HYREP (NAA-SR-Memo-9193, no full text). BOOMER and TRANCORE-10A are kinetics codes, not fuel-performance codes; do not cite them as such.
- Still open: the SiGe temperature-dependent property curves (classified CRD; NAA-SR-11955 Figs 43-50 would close resistivity and degradation), NAA-SR-9647 (absolute dose rates), the Total System Simulation (NAA-SR-MEMO-6721, not located).
- Shielding is build-ready and unbuilt: full LiH frustum geometry, FMC-N source spectrum, homogenized atom densities, and validation numbers (0.156 cm^-1 removal cross section, the factor-of-six mating-plane reduction, the 0.0359 attenuation ratio).

## Working notes
- Build spec for any new model: SNAP-10A_Model_Base_Set.md, SNAP-10A_Validation_Targets.csv, SNAP-10A_Model_Equations.md. Load all three. Load OpenMC_Coding_Best_Practices.md before writing OpenMC.
- Validation policy: reproduce the report's published number with its geometry and data FIRST, then vary. This is what earns the right to explore the design.
- Citation styles are not uniform across deliverables. The slides and literature review use Chicago; the older report keeps its original numbered style.
- Follow the user's saved writing style and the Obsidian vault CLAUDE.md rules. Natural conversational prose, no em-dashes, no emphasis formatting, take positions.

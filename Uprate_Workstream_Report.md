# SNAP-10A uprate workstream: what was done, why, and the code

Prepared June 2026. This report documents one working thread of the CSNR SNAP-10A modeling
effort, from a structural roadmap through to a verified electrical-output number. It records
the reasoning behind each choice and explains what each piece of code does, so a colleague can
follow the logic, challenge it, and rerun it. The thread asked one
question and answered it: can the existing SNAP-10A reactor reach the project's 14 kWe
requirement by being run harder, rather than by being replaced with a bigger reactor.

The answer is yes. The existing core, uprated to its verified thermal-hydraulic ceiling of
about 79 kWt, with a Stirling converter and a colder radiator, reaches about 14.6 kWe. Every
link in that chain is now a computed or sourced number rather than an assumption.

## 1. The starting point and why the work was re-cut

The project already had a verification roadmap (`energy_conversion/Power_Uprate_Verification_Roadmap.md`)
organized by question: Phase 0 land the coupled model, Phase 1 the uprate ceiling, and so on.
The request that opened this thread was to turn that into a structural roadmap, meaning the
discrete things that have to be built rather than the questions to answer.

The reason this mattered is that a phase-by-phase study plan hides the dependencies. Re-cutting
it as a component register (`energy_conversion/SNAP-10A_14kWe_Structural_Roadmap.md`) made the
critical path explicit: a coolant-and-pump physics layer the models did not have (components
A1, A2, A3), wrapped in a power sweep that reads three limits (B1, B2), chained into the
Stirling output (G1), with reactivity (Phase 2) and material life (F1) as parallel and
downstream pieces. Laying it out this way surfaced two things immediately. First, the whole
kWe uncertainty sat in the thermal uprate, which is a thermal-hydraulics result, not a
neutronics one. Second, the MOOSE side of the coolant physics was largely already built into
the framework, so the new code was mostly the analytic model and the cross-checks.

## 2. Cross-cutting choices, and why

A few decisions shaped everything that followed.

**Analytic-first, Cardinal for spot-validation.** The verification roadmap assumed the uprate
sweep would run in the coupled Cardinal model. I argued against that as the default. The
friction and pump physics that bound the uprate are one-dimensional channel closures, and the
analytic hot-channel model already reproduced the design point cheaply. The coupled solve, by
the Layer 2 report's own account, is brutally stiff and did not converge. Gating the entire
uprate answer on fixing that stiffness would have been a large time sink for a result the
analytic model gives directly. So the sweep runs in the analytic model, and the coupled
Cardinal solve is reserved for validating two or three points, which is what the PC handoff
bundle now sets up. This was the single most consequential methodology call, and the work bore
it out: the analytic chain produced a complete, defensible answer on the Mac alone.

**Validation policy: reproduce the design point first, then go off-design.** Every module
carries a self-check against the 34 kWt design point before it is trusted off-design. This is
the project's standing policy and it caught real problems (the per-pin peaking discrepancy
below would have been invisible without it).

**Research before building.** Each physics component started with a literature pass (often
parallel subagents) to get the actual correlations and limits, then the code was built from
those numbers. The alternative, coding from memory and citing sources afterward, produces
plausible-looking modules that are subtly wrong. The NaK viscosity, the Cheng-Todreas
coefficients, the Simnad correlation, and the Hastelloy-N limits were all pinned to sources
first.

**A figure for everything.** Partway through, the standing practice became: whenever a module
produces a result, it also produces analytical figures, regenerated from the live model so they
cannot drift from the numbers. The figures are embedded in the relevant writeups.

**Safe, reversible model knobs.** The neutronics changes to the validated `snap.py` were all
added as environment-variable knobs that default to the baseline, so the validated model is
unchanged unless a knob is explicitly set. This kept the production model trustworthy while
making it sweepable.

## 3. Component A1: temperature-dependent NaK-78 properties

`heat_transport/uprate/nak78_properties.py`

The gap: the models carried NaK as constants, and the Cardinal side used a room-temperature
density (866 kg/m3) that is wrong for an 800 K loop by about 13 percent. The uprate pushes
outlet temperatures up, so the properties have to move with temperature.

The research returned the NaK-78 correlations for density, specific heat, conductivity, and
viscosity, traced to Foust's 1972 Sodium-NaK Engineering Handbook and a NASA density fit. The
code implements these with one design choice worth explaining: an anchoring mode. The raw
literature correlations reproduce the arXiv Table II values (the numbers the validated model
already uses) to within about 1 to 3 percent. To keep bit-for-bit continuity with the
validated baseline while still letting the properties respond to temperature, the default mode
shifts each correlation by a constant, or scales the viscosity, so it passes exactly through
the Table II value at 783 K and carries the literature slope around it. The function
`validate()` prints both the anchored and raw columns against Table II, and the SNAP operating
band. The module also exposes a CSV writer for the MOOSE tabulated-properties format, though
the larger finding made that mostly unnecessary.

The larger finding from the MOOSE research: the framework ships a built-in `NaKFluidProperties`
object, the same eutectic NaK-78 from the same Foust handbook, temperature-dependent and
needing no code. So on the Cardinal side, A1 is a one-block swap of `SimpleFluidProperties` for
`NaKFluidProperties`. The Python module exists for the analytic sweep and as an independent
cross-check.

## 4. Component A2: tight-lattice channel hydraulics

`heat_transport/uprate/channel_hydraulics.py`

The gap: the uprate is bounded by the coolant, not the fuel, so the flow has to be charged a
pumping head. Nothing in the project did this; flow was free.

Two things came out of the research. First, a geometry clarification: the pitch-to-diameter
ratio is 1.008 based on the clad outer diameter, which is the correct surface for the coolant.
One research thread reported 1.0396 using the fuel-meat radius, which is the wrong diameter for
a hydraulic calculation. The analytic hot-channel model already used the clad radius, so the
two are consistent. Second, the Cheng-Todreas correlation coefficients for a hexagonal interior
subchannel, which I took directly from the MOOSE source `ADWallFrictionChengMaterial.C` rather
than a textbook, so the analytic friction factor and any later coupled run agree by
construction. The module reproduces the MOOSE source's check value (laminar Cf = 62.075 at
P/D = 1.05).

A subtlety the code handles explicitly: the THM material in MOOSE hard-splits laminar and
turbulent at Reynolds 2100 and skips the transition blend, whereas the physical Cheng-Todreas
form blends between two Reynolds bounds. The SNAP channel runs at Reynolds about 7300, in the
transition band, so the difference matters. The module offers both, `mode='three_regime'` for
the physical answer and `mode='moose'` for exact agreement with a THM run. On the validity
question, P/D = 1.008 sits at the tight edge of the correlation's range; the code documents that
the near-touching laminar geometry carries extra uncertainty, and that a smooth-tube fallback
would under-predict the friction by about a factor of three and is not safe here.

The design-point result: the bare-core friction is only about 0.6 kPa, small against the 7.58
kPa pump head, which correctly says the loop resistance is dominated by the converter and
piping, not the core.

## 5. Component A3: the EM pump, and the report retrieval

`heat_transport/uprate/em_pump_curve.py`

The gap: the uprate ceiling depends on whether the pump can push the flow a higher-power core
needs, which requires the pump head-flow curve. That curve lives in NAA-SR-11879, flagged
across the project as not retrieved.

This component went through the most revision, and the story is worth keeping because it changed
the answer twice.

The first version used the design point recovered from a modern paper (El-Genk 2023, citing the
1966 report): 7.58 kPa at 3 m3/hr. Lacking the full curve, it used a half-stall placeholder
(the design flow sits at half the short-circuit flow). The sweep with this placeholder put the
uprate ceiling near 65 kWt and leaned toward "redesign needed."

Then the report itself was retrieved. The fetch tool returns empty for the OSTI scan because it
is a JavaScript viewer, but the full 86-page document loads in a browser, and reading it there
found Figure 14, the pump pressure-versus-flow curves at three NaK temperatures. Digitizing it
replaced the placeholder with real data and produced the result that mattered: pump performance
rises strongly with NaK temperature (the stall head goes 2.0, 2.4, 2.8 psi over 800, 900, 1000
F). The pump is thermoelectrically driven, so a hotter core both needs and gets more pumping.
This is the coupling the placeholder was guessing, and it lifted the begin-of-life ceiling by
about 10 kWt.

Reading further (pages 51 to 52) found two more numbers. A measured flight operating point at
1056 F NaK delivering 14.4 gpm, which validates the model's extrapolation above the 1000 F curve
ceiling to within 6 percent. And the pump's life degradation, a 13 percent flow loss over a year
from thermoelectric decay (Figure 33). The module carries the temperature dependence, the flight
validation, and an end-of-life degradation factor. The net effect: the begin-of-life temperature
lever and the end-of-life degradation nearly cancel, which is why the sustained ceiling lands
back near the original estimate but now for an understood reason.

The honest open item, documented in the code: the measured curves stop at 1000 F, which is the
pump's qualification ceiling, so the uprate's higher outlet temperature is a short extrapolation,
bounded by the 1056 F flight point.

## 6. Components B1 and B2: the uprate sweep and its sensitivity

`heat_transport/uprate/sweep.py`, `sensitivity.py`

The sweep marches reactor power up and reads the fuel and clad temperatures under two flow
policies: flow held at design, and flow set by the real pump curve coupled to the core outlet
temperature. The coupled policy iterates, because flow sets the outlet temperature, which sets
the pump curve, which sets the flow. It reproduces the 34 kWt design point as its acceptance
test.

The sensitivity study answered a question before chasing inputs: how firm is the ceiling. It
varies each input one at a time and ranks the movers. The result reordered the priorities. The
achievable flow is the dominant lever, which is why the pump report mattered most; the radial
peaking is second; inlet temperature, the wall value, and the clad conductivity are all
secondary. Doing this before pinning any single input is the disciplined order, and it is what
pointed the next effort at the pump curve and then the peaking.

## 7. The per-pin peaking, and a discrepancy resolved

`snap/extract_pin_power.py`

The sensitivity flagged radial peaking as the second-largest lever, and the sweep had borrowed
1.56 from the Layer 2 report. So the real peaking was measured: an OpenMC run injected a fine
kappa-fission mesh into the snap model and reduced it to per-pin powers by nearest-pin
assignment. The script was validated end to end on the Mac with a synthetic self-test before the
real run.

The real run (1,000,000 particles) gave a radial peaking of 1.317, not 1.56, with a clean
monotonic radial profile. This needed explaining rather than accepting. The reconciliation: the
1.56 was a local power-density peak read off the 3-D field, which folds in axial peaking, whereas
1.317 is the pin-integrated radial factor. The sweep applies the axial factor separately, so the
correct radial factor is the pin-integrated 1.317, and using 1.56 double-counted axial peaking
and was over-conservative. Forcing 1.56 back into the sweep reproduces the old 64.6 kWt, which
confirms the bookkeeping. The corrected, lower peaking raised the end-of-life ceiling from about
66 to about 79 kWt. This is a good example of the validation policy earning its place: without
the design-point cross-check the discrepancy would have passed unnoticed.

## 8. Phase 2, part 1: the temperature coefficient

`snap/run_temp_coeff.py`, with the `TEMP_K` knob in `snap.py`

The reactivity question for the uprate is whether the core has the feedback and control to hold
the uprated power. The temperature coefficient is the feedback. The `TEMP_K` knob overrides the
whole-core cross-section temperature, and the script sweeps it and reads k-eff.

The result is a coefficient of about -1.56 pcm/K, firmly negative, the U-ZrH prompt feedback
that makes the reactor self-regulating. It validates itself: at 783 K the run reproduces the
validated fig12_test k-eff. A negative coefficient is favourable for the uprate, since a hotter
core is more stable. What it sets is the demand on control: the core sheds about 734 pcm from
cold to design and another 175 pcm to a 900 K uprated condition. The honest scope note in the
code: this is the cross-section (nuclear) coefficient, so density and expansion feedback are
extra and would make the full coefficient somewhat more negative.

## 9. Phase 2, part 2: the drum worth, and an honest dead end

`snap/run_drum_worth.py`, then `snap/run_drum_total.py`, with the `DRUM_DELTA` and `DRUM_FILL`
knobs

This is the part where a method failed and the failure was reported as a failure rather than
dressed up.

The drums are beryllium reflector sectors that rotate in a void cavity, so the first approach
rotated them and read the reactivity. The first knob was an absolute angle, and the sweep through
0 degrees lost particles: the drum cut-plane geometry is only valid near the operating
orientation, and a large rotation makes a degenerate, coincident-surface configuration. The fix
was a delta-from-baseline knob anchored on the validated geometry, plus skip-on-failure so one
bad angle does not abort the run. But that only moved the wall: any large rotation degenerates,
and within the small valid window (about plus or minus 10 degrees) the reactivity moves only
about 100 pcm, comparable to the Monte Carlo noise. The run produced a jagged, non-monotonic
curve. The right thing was to say plainly that the result was noise-limited and not usable, not
to quote a spurious worth from it.

The better approach sidesteps rotation. The `DRUM_FILL` knob fills the four beryllium sectors
either present (baseline) or void (drums effectively rotated out), a material swap at the fixed
operating geometry, so there is no rotation and no lost particles, and the signal is the full
reflector worth, thousands of pcm, far above noise. The result: a total drum reflector worth of
about 5925 pcm, which is about 6.5 times the roughly 910 pcm the temperature swing demands. This
is an upper bound on the true rotational control worth, because a rotated-out drum still has its
beryllium on the far side reflecting a little, but the margin is so large that even a heavily
discounted rotational worth clears the demand. So control authority is ample, and the precise
rotational worth, which would need the drum geometry generalized for arbitrary rotation, is not
required to reach that conclusion.

## 10. Component F1: material and fluence life

`heat_transport/uprate/life_check.py`

The ceiling rests on two temperature walls (970 K fuel, 977 K clad) that were placeholders, and
it assumed the parts survive the mission. F1 confirmed both and checked the irradiation life.

The fuel wall: SNAP fuel is U-ZrH at H/Zr about 1.65. The limit is the hydrogen dissociation
pressure, which stresses the clad. The module implements the Simnad correlation and reproduces
his published values (0.11 atm at 700 C, 91 atm at 1150 C). At the 970 K wall the pressure is
only about 0.18 atm, three orders of magnitude below the roughly 140 atm at TRIGA's 1150 C peak
limit. So 970 K is a conservative sustained-service limit (clad creep plus hydrogen permeation
and redistribution), not an acute burst limit, which is why the core has real headroom below it.
The clad wall (977 K, Hastelloy-N creep) is confirmed and essentially coincident with the fuel
wall.

Fast fluence is not life-limiting even at the uprate. SNAP is a very low power-density core, so
the fast fluence is only about 1e19 per year at design, about 3.7e19 at the uprated power, against
a clad embrittlement threshold near 1e21 and a beryllium reflector limit near 1e22, leaving one
to three orders of magnitude of margin. The real life cost of the uprate is hydrogen
redistribution, which accelerates about two to three times at the hotter fuel temperature. This
is the mechanism that actually limited the real SNAP-10A, and it sets the trade between uprate
power and mission length, more than fluence or clad stress. So F1 confirms the ceiling and points
at hydrogen life, not material damage, as the thing to watch.

## 11. Component G1: the verified electrical output

`energy_conversion/g1_uprate_to_kwe.py`

G1 chains the verified ceiling into the Stirling model. The thermal model gives the ceiling power
(about 79 kWt end-of-life) and the NaK outlet temperature there (about 897 K, because the fuel
runs to the 970 K wall with a roughly 75 K fuel-to-coolant drop). After a 25 K heat-exchanger
drop the Stirling hot end sees about 872 K. At that hot side, a 475 K radiator, and 79 kWt, the
Stirling model gives about 14.6 kWe, with a 26 m2 radiator and about 178 kg of system. The target
is met for any radiator at or below about 485 K.

The verified case beats the earlier briefing's assumed Route A at lower reactor power (79 versus
85 kWt) because the real hot side is hotter than the 800 K the briefing assumed. The fuel-limited
ceiling runs the NaK to about 897 K, and a hotter hot side lifts the efficiency. The full
write-up is `energy_conversion/Path_to_14kWe_Verified.md`.

## 12. The thm.i input provenance

A side question in the thread asked where the THM flow-channel inputs came from. The answer is
documented in `heat_transport/thm_inputs_provenance.md`: the temperatures, flow, heat-transfer
coefficient, and the four NaK property values all come from the arXiv 2505.04024 Tables I and II
(the paper the snap model reproduces); the inlet 755.37 K traces to Magee, Dufoe and Gordon's
1964 Atomics International thermal-performance report; the geometry terms are derived from the
same Table I dimensions; and a few equation-of-state parameters (the outlet pressure, the bulk
modulus, the thermal expansion) are nominal numbers that `SimpleFluidProperties` requires but
that do not affect the steady forced-convection result, because NaK is effectively
incompressible at these conditions.

## 13. Changes to the validated snap.py

Three environment-variable knobs were added to `snap.py`, all defaulting to the baseline so the
validated model is unchanged unless a knob is set:

- `TEMP_K`: overrides the whole-core temperature, for the temperature coefficient.
- `DRUM_DELTA`: rotates the four drums together by a delta from the operating baseline, for the
  rotational drum sweep (kept for the differential worth and as the entry point if the geometry
  is later generalized).
- `DRUM_FILL`: fills the drum sectors with beryllium or void, for the material-swap total worth.

The model compiles and these defaults reproduce the validated result. Any commit of these should
note that they do not move k-eff at default.

## 14. File map

Analytic uprate model, `heat_transport/uprate/`:
- `nak78_properties.py` (A1), `channel_hydraulics.py` (A2), `em_pump_curve.py` (A3)
- `sweep.py` (B1/B2), `sensitivity.py`, `life_check.py` (F1)
- `make_figures.py` (regenerates the figures), `figs/`
- `Implementation_Research_Dossier.md`, `Phase2_Reactivity.md`, `Material_Life_F1.md`, `README.md`

Neutronics, `snap/`:
- `extract_pin_power.py` (per-pin peaking), `run_temp_coeff.py`, `run_drum_worth.py`,
  `run_drum_total.py`
- `snap.py` knobs: `TEMP_K`, `DRUM_DELTA`, `DRUM_FILL`

Energy conversion, `energy_conversion/`:
- `g1_uprate_to_kwe.py` (G1), `Path_to_14kWe_Verified.md`
- `SNAP-10A_14kWe_Structural_Roadmap.md` (the structural roadmap)

Documentation, `heat_transport/`:
- `thm_inputs_provenance.md`, `cardinal_validation/RUN_HERE.md` (the PC handoff)

## 15. Honest caveats and what is not done

The result is analytically verified, not yet coupled-model verified. The two items that remain,
both documented and neither threatening the conclusion: the coupled Cardinal solve on the PC
should confirm the hot-side temperature and check whether temperature feedback shifts the radial
peaking at the uprated power (the handoff bundle sets this up), and the EM pump curve above 1000 F
NaK is a short extrapolation validated to the 1056 F flight point within 6 percent.

Smaller open items: the temperature coefficient is the cross-section term only, so density
feedback would add to it; the fast fluence is an estimate from power and geometry that an OpenMC
energy-filtered tally would pin; the precise rotational drum worth would need the drum geometry
generalized; and the fuel-makeup excess-reactivity sweep (the U_MULT knob on the HEU core) is the
remaining Phase 2 piece. None of these moves the headline.

## 16. Conclusion

The thread replaced each soft assumption in the 14 kWe case with a model result or a sourced
number, and the conclusion flipped. The existing SNAP-10A core clears every gate that can be
tested analytically: a thermal-hydraulic ceiling near 79 kWt, a real and temperature-coupled
pump curve, a self-regulating reactivity coefficient with ample drum authority, confirmed
material limits with fluence margin to spare, and a verified output near 14.6 kWe. The project
opened with "14 kWe needs a bigger reactor." The defended position now is "14 kWe needs the same
reactor run harder, plus a Stirling converter and a colder radiator," with the costs named: a
radiator about five times larger, the moving-parts reliability trade the Stirling brings, and a
mission-length-versus-power trade set by hydrogen redistribution. The coupled Cardinal validation
is the one piece left to turn this from analytically verified into coupled-model verified.

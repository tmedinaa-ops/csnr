# Controlled depletion: confirming the reactivity horizon

This gates the axial-reflector and pseudo-breeder branches, because both are fixes for a reactivity horizon that is only as real as the slope it is built on. Two scripts here: `horizon_from_bare.py` extracts the horizon from the runs you already have, and `controlled_depletion.py` is the gold-standard run that re-searches the drums to critical each step.

## What the existing runs already say

Run `horizon_from_bare.py depletion_results.h5 79.1`. It separates the one-time xenon/samarium equilibrium from the slow burnup slope, then computes horizon = 767 pcm budget divided by the burnup slope, which is exactly the calculation behind the project's 7.2-year number, just with the measured slope instead of the anchor.

Result at 79 kWt: the burnup slope is 337 plus or minus 20 pcm/yr, the horizon is 2.3 years, against the project's 7.2. At 120 kWt it is 457 pcm/yr and 1.7 years against 5.1. The plus or minus 20 is the Monte-Carlo scatter on the slope, and it is nowhere near large enough to close a three-fold gap. So the horizon shortfall is not noise. Figure: `reactivity_horizon.png`.

That is the headline, and it is uncomfortable: if the model is right, the reactivity horizon at 79 kWt is closer to 2 years than 7, which would put it in the same range as the fuel-burnup limit (~1.5 years to 1% burnup) rather than comfortably past it. Both mission clocks would then land near 1.5 to 2.5 years, and a 7-year mission needs both fuel requalification and a real reactivity-margin gain, which is what the reflector branch is for.

## Why the bare run is close to the truth, and what the controlled run adds

The bare depletion holds the drums fixed at their BOL critical orientation. As the core burns, k sags to about 0.97. That sag is small and it comes from composition, not from drum absorption, so the neutron spectrum stays close to the operating condition throughout. The reactivity slope from the bare run is therefore close to what a critical-drum run would give. This is why `horizon_from_bare.py` is a legitimate first answer and not just a stopgap.

The controlled run refines two things. It removes the last bit of spectrum drift by rotating the drums out a few degrees each step to hold k exactly at 1, so the fuel always burns in the true operating spectrum. And it reports the horizon the operationally correct way, as drum reactivity consumed against available excess and drum travel, rather than as a Delta-k compared to a 767 pcm budget that mixes cold and hot references. Be honest about the expectation: the drums move only a few degrees to recover a couple thousand pcm over the mission and the composition change is identical, so the controlled slope should confirm the bare slope, not rescue the 7.2-year number. If you are hoping the controlled run brings 337 back down to the 106 anchor, it almost certainly will not.

## So where does the gap with the 106 pcm/yr anchor come from

Three candidates, in order of likelihood. First, power and definition: the Service Life anchors were taken on the derated flight core burning about 0.26 %/yr; this run burns 0.84 %/yr at 79 kWt, roughly three times faster, and the reactivity-per-burnup times that faster burn lands near the measured slope. The anchor may simply be a lower-power number that does not extrapolate linearly. Second, real physics: the core is leakage-bound HEU with almost no bred plutonium (4 g in 7 years), so each percent of burnup costs more reactivity than a core with a breeding buffer, and the model may be correctly telling you the uprated core sheds reactivity fast. Third, and least likely given the plus or minus 20 noise, some residual modeling error. The controlled run plus a check of how the 106 anchor was defined should settle which.

## Running the controlled version

`controlled_depletion.py` is a framework with one model-specific piece to wire: `build_at_drum(angle, materials)`, which rebuilds the fig12 model at a given drum angle carrying the depleted materials. The docstring shows the exact form to import from snap.py. The drum only sweeps a few degrees around the operating orientation, which stays inside the rotation window the snap geometry is valid over, so the large-rotation particle-loss problem from run_drum_worth.py does not bite here.

Protocol: wire `build_at_drum`, run a 2-step smoke test, confirm the drum angle moves monotonically outward and k holds at 1.0 within a few hundred pcm, then launch the full run at 50k particles. Read the drum-angle-versus-time curve, convert the angle axis to pcm with run_drum_total.py's worth curve, and the horizon is the usable excess divided by the withdrawal rate. Compare against the 2.3-year bare estimate; they should agree.

## Gate for the other branches

Do this before spending effort on end reflectors or a fertile blanket. If the controlled run confirms ~2 years, the reactivity horizon is the binding constraint and the reflector's margin gain becomes the priority lever. If checking the anchor definition shows the 106 number was never comparable and the true operating horizon is longer, the urgency drops and the reflector stays a nice-to-have. Either way, confirm the number before building the fix.

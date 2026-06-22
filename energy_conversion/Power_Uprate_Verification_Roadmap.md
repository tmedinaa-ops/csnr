# Verification roadmap: maximum power from the existing SNAP-10A

Goal: confirm or kill the claim that the existing core, with no change to fuel
type, working fluid, or size, can deliver roughly 10 to 16 kWe (central ~13),
against the flown 0.58 kWe. The estimate is the product of three multipliers:
converter swap (~4.5x), colder radiator (~2x), and thermal uprate (2 to 3x).

The first two are anchored to the Stirling model and are solid. The whole
uncertainty sits in the uprate, and the uprate is bounded by the coolant and the
materials, not by the fuel (the fuel is derated almost sevenfold). So this roadmap
is mostly a thermal-hydraulics and reactivity verification, run on the models the
project already has: snap.py for neutronics, the heat_transport Cardinal model for
the coupled thermal solve, and the energy_conversion Stirling model for the output.
Validation philosophy is unchanged: reproduce the 34 kWt design point first, then
go off-design.

## Phase 0: land Layer 2 (prerequisite)

The coupled 37-pin Cardinal model is the workhorse for the uprate study, so it has
to converge and validate before any off-design number is trustworthy. Finish the
run already going: channel-sum heat removal climbing to 34 kW, peak fuel settling
around 840 to 855 K, hot-channel outlet near 817 to 825 K, and the radial peaking
coming out as a result. Pass when Layer 2 reproduces the as-flown design point
(34 kWt, ~62 K NaK rise, ~840 K peak fuel) within tolerance. Until then, off-design
is built on sand.

## Phase 1: the thermal-hydraulic uprate ceiling (the binding study)

This is where the kWe uncertainty lives, so it is first after Layer 2. The question:
hold the hot side at 800 K and push reactor power up, how far before the coolant or
the clad stops you?

The Cardinal model needs three pieces it does not yet have:

- Temperature-dependent NaK properties (currently constant; a known gap). Use the
  sodium and potassium property libraries Cardinal compiles, or a NaK-78 fit.
- A lattice pressure-drop and friction model for the P/D = 1.008 bundle, so flow
  costs pumping head. Computable from the geometry, or from SNAP thermal-hydraulic
  reports.
- The electromagnetic pump head-flow curve. Pull NAA-SR-11879 (the EM pump report,
  OSTI 4516323, flagged as not-yet-retrieved) for the pump capacity.

Then sweep reactor power upward in the coupled model (scale the OpenMC kappa-fission
magnitude, hold inlet at 755 K) and at each power read three limits: peak fuel
against the ~970 K hydride wall, peak clad against the Hastelloy N limit, and the
NaK flow required against what the pump can deliver into the rising pressure drop.

Output: the maximum sustainable kWt at 800 K, which turns the assumed 2.5x into a
computed number. This single result sets the kWe within its band.

## Phase 2: reactivity and control for the uprate (parallel, in snap.py)

Uprating at constant temperature needs little extra reactivity, but it needs control
authority and confirmed feedback. Three OpenMC runs:

- Control drum worth: rotate the four drums across their range and record the
  reactivity swing, confirming there is authority to hold the uprated power and to
  shut down.
- Excess reactivity and the power/temperature coefficient: confirm the core stays
  critical with margin at the uprated temperatures and that the negative U-ZrH
  feedback is the expected magnitude (it is what the uprate fights).
- Fuel makeup: apply the HALEU branch's loading knob (U_MULT) to the HEU core to see
  how much excess reactivity higher uranium loading buys and where under-moderation
  saturates it; a short H/Zr sensitivity sweep alongside. This quantifies what fuel
  makeup adds to the reactivity budget without changing fuel type.

Output: confirmation that the core has the reactivity and control to run and hold
the Phase 1 power, and a number for what makeup contributes.

## Phase 3: power flattening (snap.py plus Layer 2)

The hottest pin caps the reactor, so flattening the radial peaking raises the
average power at the fixed hot-pin limit. Take the peak-to-average from Layer 2,
then study two flatteners: fuel zoning (per-ring enrichment or loading, lower center
and higher edge) and hot-channel coolant orificing. Re-run the coupled solve with
the flattened profile.

Output: the extra average power available at the same peak fuel temperature, a
multiplier that stacks on the Phase 1 uprate.

## Phase 4: material and fluence life (OpenMC plus literature)

Higher power is higher flux, so confirm the parts survive the mission. From the
uprated flux compute the fast fluence on the clad and the reflector against their
damage limits, and the hydrogen-loss rate of the hydride at the higher fuel
temperature. This is the constraint that may cap either the uprate or the mission
length, and it is the one most likely to pull the achievable number down.

Output: the lifetime at the uprated power, and whether it meets the mission.

## Phase 5: chain it for the verified kWe

Feed the Phase 1 maximum kWt and its hot-side temperature into the Stirling model at
the chosen radiator temperature, and read the integrated electrical output with the
real uprate ceiling instead of the assumed 2.5x. Size the radiator area and mass at
that cold side. Output: the verified kWe replacing the 13, with its radiator and mass
cost, and a clear statement of which limit (pump, clad, fluence) set the ceiling.

## Critical path and priority

Phase 0 then Phase 1 is the spine, because the uprate is the soft assumption and it
is a thermal-hydraulics result. Phase 2 runs in parallel in snap.py. Phases 3 to 5
refine and convert. The single highest-value next step after Layer 2 converges is
the pump curve plus the pressure-drop model plus the off-design coupled run, because
that one study collapses most of the kWe band.

## What this reframes

If Phase 1 shows the existing core can be uprated to roughly 85 kWt at 800 K, then
the project's earlier "14 kWe needs a bigger reactor" becomes "14 kWe needs the same
reactor run harder," and the bigger-and-hotter redesign moves from necessary to
optional. If Phase 1 shows the pump or the clad caps the uprate near, say, 60 kWt,
then the kWe lands around 9 to 11 and the redesign is back on the table. Either way,
Phase 1 is the decision.

## New data to acquire

- NAA-SR-11879, the EM pump report, for the pump head-flow curve.
- A NaK-78 pressure-drop and friction basis for the tight lattice.
- Hastelloy N and U-ZrH temperature and fast-fluence limits (Simnad and the hydride
  reports already in the bibliography).
- Temperature-dependent NaK-78 properties for the Cardinal THM side.

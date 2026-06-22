# Wringing maximum power from SNAP-10A, fixed fuel type, fluid, and size

Working notes, June 2026. The question driving this thread: before changing fuel
type, working fluid, or core size, how much more electrical power can the existing
SNAP-10A design produce? Two halves, the converter side and the reactor side.

## Converter side: capture more of the same heat

Numbers from `stirling_cycle_concept/stirling_concept.py`, anchored to SNAP and
Kilopower.

- Thermoelectric, as flown: 1.82 percent overall, about 0.58 kWe from 34 kWt.
- Stirling on the same reactor, SNAP temperatures (800 K hot, 590 K radiator):
  8.3 percent, 2.6 kWe. The static-to-dynamic swap is the big single jump, about
  4.5x, and it rides the existing reactor.

### The cold side is the unblocked Carnot lever

Efficiency is Carnot times relative efficiency, and Carnot = 1 - T_cold/T_hot is
symmetric in the two temperatures. Raising the hot side hits the U-ZrH fuel wall.
Lowering the cold side does not; its only cost is radiator area. At a fixed 800 K
hot side, dropping the radiator:

| radiator | Carnot | overall | output | radiator area |
|---|---|---|---|---|
| 590 K | 26.2% | 8.3% | 2.6 kWe | 5.3 m^2 |
| 475 K | 40.6% | 16.4% | 5.2 kWe | 11.5 m^2 |
| 400 K | 50.0% | 23.0% | 7.3 kWe | 21.1 m^2 |

The 475 K row is the headline: 5.2 kWe, the same efficiency you would get from
pushing the hot side to 1000 K, but with no fuel change. You buy it with radiator
area (about 2x) rather than a fuel requalification. Radiator area scales as one
over T^4, so there is an optimum, not "colder is always better." Two diagrams were
drawn for this in chat: the efficiency-lever bar chart and a physical layout sketch
of the Stirling-converted unit (small reactor, shield, redundant Stirling cluster,
large radiator). Export them to SVG when needed.

Other converter-side levers: recover the heat-path loss (SNAP's TE hot junction sat
44 K below the 800 K NaK, free span if the converter taps the NaK more directly),
and modern static converters (segmented skutterudite/half-Heusler thermoelectrics
roughly double SNAP's SiGe while keeping no moving parts).

## Reactor side: the fuel is wildly derated

This is the bigger surprise. Computed from the snap.py geometry:

- U-235 inventory: 4.77 kg (37 pins, 8.55 L of fuel, 10 wt% U at 93 percent).
- Burnup at 34 kWt: 12.4 g/yr, which is 0.26 percent of inventory per year. The
  fuel-inventory-limited life is about 380 years, so life is never fuel-limited.
- Thermal margin: peak fuel about 840 K at 34 kWt against a U-ZrH hydride wall near
  970 K, so 130 K of headroom. The fuel-to-coolant conduction drop is only about
  23 K because U-ZrH conducts well, so the fuel temperature tracks the coolant.
- Fuel-limited power ceiling at the same coolant temperatures: about 226 kWt, 6.7x
  the design power, before the fuel centerline reaches its wall.

So the 34 kWt was the thermoelectric's appetite and the 1965 mission, not the
reactor's capability. The power is sitting in the core.

### Geometry is already maxed (so size change is the only fuel-volume lever)

- Lattice pitch / pin diameter = 1.008, pins all but touching, only 10.7 percent
  interstitial NaK.
- Fuel fills 94 percent of each clad tube; outer pins reach within 0.8 mm of the
  vessel wall; fuel column fills 94 percent of the vessel height.
- So within the present vessel the only added fuel is closing the fuel-clad gap,
  about 3 percent. More fuel volume means a bigger core (taller, or a 5th ring to
  61 pins, or both reaching about 84 kWt), which is the deferred "change size"
  path and is logged separately under the geometry analysis.

### Same-hardware power levers (no change to fuel type, fluid, size)

1. Uprate. Push reactor power up at the same hot-side temperature by raising NaK
   flow and adding control reactivity. The fuel does not notice until roughly
   200 kWt. The real binding limits are the EM pump and the pressure drop in the
   tight P/D=1.008 lattice, the Hastelloy clad temperature, and neutron fluence on
   clad and reflector (material life). Plausible same-core uprate is about 2 to 3x,
   70 to 100 kWt, which multiplies the electricity directly.

2. Fuel makeup. Enrichment is already maxed at 93 percent. The makeup knob inside
   U-ZrH is uranium loading: SNAP is 10 wt% U, TRIGA-class hydride goes to 45 wt%.
   More U is excess reactivity, which is what you spend to run higher power against
   the strong negative temperature feedback and to extend life. Diminishing returns
   apply, the HALEU work showed loading saturates because the core is leakage-bound,
   and more U dilutes the ZrH moderator toward a harder spectrum. The H/Zr ratio is
   a second makeup knob, more hydrogen is more moderation and reactivity but a lower
   dissociation wall, so it trades against the thermal margin. Fuel makeup buys the
   reactivity to enable the uprate, not power directly.

3. Flatten the power. The hottest pin caps the whole reactor, the limit is local,
   not average. Flattening the radial peaking (enrichment or loading zoning low in
   the center and high at the edge, reflector tuning, or hot-channel flow orificing)
   lets the average power rise while the peak pin stays at its wall. Layer 2 is the
   model that produces the radial peaking to flatten.

4. Colder loop inlet. Running the whole NaK colder (colder radiator return) spends
   each degree of inlet drop as fuel-wall margin for more power, and it raises
   conversion efficiency at the same time. It couples to the cold-side radiator
   lever above.

### Bottom line

Same core, same U-ZrH, same NaK, same envelope: roughly 2 to 3x the power and
electricity is plausible from uprating, flattening, and a colder loop, with fuel
makeup supplying the reactivity. The fuel ceiling is about 6.7x. The wall is hit at
the coolant, the clad, and material fluence, never at the fuel's fission capacity.
Changing size, fuel type, or fluid only becomes necessary past that coolant-and-
materials wall.

## Open items to model

- Uprate ceiling needs the real EM pump curve and the lattice pressure-drop and
  clad-temperature limits, none of which the converter-grain model carries.
- Power flattening needs the Layer 2 radial peaking, then a zoning or orificing
  study against the hot-pin limit.
- The reactivity cost of uprating and the worth of higher U loading are snap.py
  OpenMC runs, the HALEU branch is the template for the loading knob.

# Stirling power conversion, and the path to 14 kWe

Written June 15 2026 to brief the team. This explains how the Stirling converter works, why it beats SNAP-10A's thermoelectric, and what it would actually take to reach the 14 kWe requirement, because that last part has a hard physics wall in it.

## The one-line version

Swapping SNAP-10A's thermoelectric for a Stirling gets you four to six times the electricity from the same reactor, but it does not get you to 14 kWe. Nothing does on SNAP's reactor. At SNAP's temperatures, 32 kWt of reactor heat can make at most 7.6 kWe even with a thermodynamically perfect converter, and 14 kWe is nearly double that. Fourteen kilowatts needs a hotter and bigger reactor as well as the better converter.

## How a free-piston Stirling convertor works

A Stirling engine moves a fixed charge of gas, helium in these machines, back and forth between a hot space and a cold space, and takes work out of the gas expanding while it is hot and being compressed while it is cold. The cycle has four moments:

1. The gas sits in the hot space, takes in reactor heat, and expands, pushing on a piston. This is where work comes out.
2. The gas is shuttled to the cold space.
3. In the cold space the gas is compressed, which costs less work than the hot expansion gave back, because cold gas pushes back less. The difference is the net output.
4. The gas is shuttled back to the hot space and the cycle repeats.

Four parts do this:

- The hot end takes reactor heat. In KRUSTY it is the tip of a sodium heat pipe running off the core, around 950 to 1070 K.
- The cold end dumps waste heat to the radiator.
- The displacer is a light piston that shuttles the gas between the hot and cold spaces and sets the timing.
- The power piston is the heavy one the expanding gas pushes against. Its motion is the output.

The part that makes a Stirling efficient, and the one worth dwelling on with the team, is the regenerator. It is a porous metal matrix the gas flows through on the way between hot and cold. When hot gas passes toward the cold side the regenerator soaks up its heat, and when the gas returns the regenerator hands that heat back. Without it, all that heat would be dumped to the radiator and re-supplied by the reactor every single cycle, and the efficiency would collapse. With it, the cycle runs close to Carnot. The regenerator is the reason a Stirling captures 30 to 50 percent of the Carnot ceiling where the thermoelectric captures under 10.

Two design choices let it survive in space. It is a free-piston machine, meaning the pistons are not tied to a crankshaft; they bounce on gas springs and are timed by the gas dynamics, so there is no mechanical linkage to wear out. And the power piston drives a linear alternator directly, a magnet moving through a coil, so the back-and-forth motion becomes alternating current with no gearbox or rotary bearing. The whole unit is hermetically sealed. That architecture is what took decades to mature, and is why KRUSTY in 2018 was a milestone rather than a routine bolt-on.

## Why it beats the thermoelectric

The thermoelectric converter is solid state. Heat flows down the SiGe legs and the Seebeck effect skims a little electricity off along the way, but most of the heat conducts straight through to the cold side unconverted. That is the physics behind its low number, 7.7 percent of the Carnot ceiling and 1.82 percent overall. A Stirling does not let heat pass through unused. The regenerator recycles it and the piston extracts real work, so it captures several times more of the same ceiling. On SNAP's reactor that is 2.3 to 3.5 kWe against the thermoelectric's 0.58, at several times the watts per kilogram. The cost is moving parts, which the thermoelectric does not have. That was the trade SNAP made in 1965, when surviving a year mattered more than efficiency.

## The 14 kWe problem

Here is the wall. Efficiency cannot beat the Carnot limit, and that limit is set only by the hot and cold temperatures, not by the converter. SNAP runs its NaK hot side near 775 K and its radiator near 590 K, so the Carnot ceiling is 23.8 percent. Multiply that by the 32 kWt the reactor delivers and the answer is 7.6 kWe. That is the most any converter could ever produce on SNAP's reactor at SNAP's temperatures, and the requirement is almost twice it. So 14 kWe is not a converter problem and cannot be reached by changing the box in the middle.

## Three levers, and what each is worth

Reaching 14 kWe means moving some combination of three things.

1. The converter. Thermoelectric is out. To make 14 kWe at 1.82 percent you would need 770 kWt of reactor, absurd for this class. Stirling is effectively mandatory.

2. The temperature. Raising the hot side from SNAP's 775 K to KRUSTY's 1050 to 1070 K lifts the Carnot ceiling from 23.8 percent to about 53 percent, which roughly doubles the achievable efficiency and halves the reactor power you need. It is not a free dial. It means trading SNAP's pumped NaK loop for sodium heat pipes and refractory hot-end materials, which is the KRUSTY architecture.

3. The reactor power. Whatever efficiency you land on, the reactor has to supply 14 kWe divided by it.

The thermal power needed for 14 kWe, by combination:

- Thermoelectric at SNAP temps: about 770 kWt. Off the table.
- Stirling at SNAP temps, 7 to 11 percent: about 130 to 200 kWt, four to six times SNAP's reactor.
- Stirling at KRUSTY temps, 25 to 30 percent: about 47 to 56 kWt, only one and a half to two times SNAP's reactor.

Temperature and converter together do most of the work. A Stirling running hot needs only a modestly bigger reactor; a Stirling held at SNAP's cool temperatures needs a much larger one.

## The recommended path

Build toward a hotter, roughly twice-as-powerful reactor feeding Stirling convertors, which is a higher-power Kilopower rather than a warmed-over SNAP. In the order I would model it:

1. Commit the conversion side to Stirling and keep the Carnot-times-relative-efficiency model, anchored to Kilopower, to set the efficiency target at whatever hot-end temperature you pick.
2. Raise the design hot-end temperature toward 1050 K and switch the heat-transport assumption from the pumped NaK loop to sodium heat pipes. Recompute the Carnot ceiling and the required thermal power.
3. Scale the reactor in the OpenMC model to about 50 to 56 kWt at the new temperature. This is where the HALEU work already pointed: SNAP's core is leakage-bound, so a higher-power core is a redesign with more fuel and a better reflector regardless, not a tweak. Re-find criticality and re-run the coupled thermal solve at the higher power and temperature.
4. Chain the two models. Reactor thermal power and hot-end temperature come out of OpenMC and Cardinal and feed the Stirling efficiency model, which returns net electrical power. Confirm 14 kWe with margin for degradation and off-design.
5. Size the radiator at the new power. At 14 kWe and 25 percent efficiency the reactor rejects about 42 kW, so the radiator grows to roughly 12 to 15 m² depending on rejection temperature, around three times SNAP's. That is a real mass and deployment item, not an afterthought.

## The caveat to keep saying out loud

Everything above is efficiency, power, and mass, and on those the Stirling-plus-hot-reactor path wins clearly. It buys that with moving parts in a machine that has to run untended for years. KRUSTY de-risked this by using many small convertors with redundancy, one per heat pipe, so a single failure is survivable. Any 14 kWe design on this path inherits the reliability problem and should inherit that redundancy answer. SNAP chose thermoelectric to avoid the problem entirely. Taking it on in exchange for the power should be a conscious decision, not a footnote.

## Companion files

- `te_vs_stirling_diagram.svg`, the side-by-side schematic for the briefing.
- `te_vs_stirling_comparison.png`, the four-panel design-point comparison.
- `path_to_14kwe.png`, electrical output versus reactor thermal power with the 14 kWe line.
- `TE_vs_Stirling_Comparison.md`, the underlying analysis and sources.
- `compare_te_stirling.py` and `stirling_converter.py`, the models behind the numbers.

# Axial reflector branch: buying back reactivity on a leakage-bound core

Self-contained branch (like haleu_test and nak_only_stirling). It tests one idea and its companion: SNAP-10A leaks a large fraction of its neutrons, so reducing that leakage should recover reactivity, and end reflectors are a cheap place to do it. The companion idea, a fertile blanket that breeds on the leakage instead of only reflecting it, lives in `Pseudo_Breeder_Analysis.md`.

## Why this came up

The 7-year depletion (see ../depletion_7yr/Depletion_Audit_July2026.md) showed the core shedding reactivity at roughly 337 pcm/yr at 79 kWt, about three times the Service Life anchor. Two facts frame the fix. The HALEU study already showed the core is leakage-bound: k-inf sits at 1.37 to 1.50 while k-eff is near 1.0, so on the order of a quarter to a third of the fission neutrons leave the system. And the burnup depletion showed almost no plutonium bred (about 4 grams over 7 years), so there is no breeding buffer slowing the reactivity loss. The core is HEU with a soft, hydride-moderated spectrum, and it leaks.

## The one distinction that governs everything here

Reflection changes static margin, not the loss rate. Adding beryllium reduces leakage, raises k-eff, and hands you more excess reactivity to spend. It does not slow how fast reactivity is lost, because that is set by the burnup and fission-product buildup at a fixed power, which a reflector does not touch. So a reflector extends the horizon by giving you more runway at the same descent rate.

Horizon = usable excess reactivity / loss rate. If end reflectors add, say, 2000 pcm of usable excess and the loss stays 337 pcm/yr, that is roughly six extra years of runway. On a core that leaks this much, that is potentially decisive for a 7-year mission, which is why "thicker beryllium reflector first" is already the top-ranked endurance lever in the trade-off study. Axial reflection is a specific, possibly cheaper instance of it.

## Verify the premise before building anything

The claim that SNAP-10A's ends were bare is not settled in the literature. Most descriptions stress the radial system: six internal beryllium wedges, an external static radial reflector, and the four B4C-tipped control drums. At least one source says the fuel was "surrounded by radial and axial beryllium reflectors." So the ends may already carry reflection. Confirm it against the actual geometry in the arXiv 2505.04024 model in the snap repo before designing an end cap. If the ends are already reflected, this branch is moot and the lever is radial thickness instead.

## Experiment sequence

1. Confirm the reactivity slope is even real. It came from a bare depletion with drums fixed and only 20k particles. Run the clean controlled depletion first (drums re-searched to critical each step, ~50k particles). If the loss rate comes back near 106 pcm/yr, the horizon was never as short as the dirty run implied and the urgency drops. Do not engineer a fix for a number you have not confirmed.

2. Measure where the leakage goes. `leakage_split.py` wraps the whole geometry in one mesh cell and tallies net current through the faces, giving the axial (top plus bottom) versus radial (side) split at BOL. SNAP's core is roughly equant, about 31 cm of active fuel across a similar diameter, so you cannot assume axial dominates. If leakage is radial-heavy, thickening the radial reflector beats end caps. If axial is a real fraction and the ends are bare, end reflectors win. Measure, then decide.

3. Build the reflector variant and price it. `Axial_Reflector_Variant_Guide.md` specifies the geometry change: beryllium regions above and below the active fuel, thickness matched to the ~5 cm radial reflector, inside the existing outer radius, with the axial vacuum boundary moved out to enclose them. Measure the static Δk (the worth), the reduction in drum demand, and then re-deplete the variant through the fixed ../depletion_7yr/run_depletion_7yr.py to see how much horizon it actually buys.

## Side effects to watch, both good and bad

Axial reflectors flatten the axial power shape, which quietly helps the peaking lever the uprate work depends on. That is a real bonus. Against that: they change drum worth and shutdown margin, and SNAP's safety concept was literally reflector ejection, so a permanent end reflector has to fit that logic rather than defeat it. Beryllium adds (n,2n) multiplication and photoneutron sources. And the ends are not empty space, they carry the NaK inlet and outlet plena, the grid plates, and structure, so thick beryllium there is a real mechanical intrusion and a mass line, not a free surface to fill.

## Position

End reflectors are a credible way to recover reactivity margin on a core that leaks as much as this one, and the margin they add could translate into years of horizon. But they add runway rather than slowing the burn, the slope they would be compensating is not yet confirmed, and whether the ends are even bare is unverified. So the honest order is: confirm the slope, measure the leakage split, check the ends against the real geometry, and only then cut beryllium end caps. The breeding companion in the next file is the harder, heavier, lower-yield way to spend the same neutrons, and it is worth reading precisely because it shows why reflection is the first move.

Files: `leakage_split.py` (axial vs radial leakage tally), `Axial_Reflector_Variant_Guide.md` (geometry change + depletion recipe), `Pseudo_Breeder_Analysis.md` (the fertile-blanket thought experiment).

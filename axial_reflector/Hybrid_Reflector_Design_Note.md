# Spending less beryllium: the hybrid reflector study

Written July 22 2026. This turns the leakage-split finding into a design question with a
number at the end: on the HALEU route, what is the least beryllium that recovers the
reactivity target, and how much does a hydride liner save. Read `Leakage_Split_Prediction.md`
for the measurement (70.4% radial / 29.6% axial) this is built on.

## The reframe

The HALEU recovery penciled in roughly 65 kg of added beryllium (TRIGA-class loading plus
reflector). The goal here is not to remove that beryllium, it is to spend less of it by
putting it only where it earns its mass and letting a cheaper lever cover part of the gap.
Three findings drive the design:

- leakage is radial, so all configs are radial-only. No axial caps. The ends carry the
  minority 30% at low yield, so beryllium there is close to wasted.
- a hydride liner does the thermalizing return cheaply per kilo. Put it inside the
  beryllium; the beryllium behind then only supplies (n,2n) and bulk albedo, which is what
  it is actually good for. Same worth, less beryllium.
- worth saturates with thickness. The script reports the beryllium where each config first
  reaches the target, so you never buy beryllium on the flat part of the curve.

## What the script does

`hybrid_reflector_sweep.py` sweeps added radial beryllium for each config, computes worth
against a fixed baseline, and interpolates the beryllium thickness and mass at the target.

- A `be_only`: beryllium shell against the core. The reference.
- B `liner_be`: a fixed hydride liner (`LINER_CM`, ZrH by default, YH2 optional) against the
  core, beryllium behind it.
- C `ring_be`: one added fuel ring, then beryllium. This needs the `snap.py` hook, because
  the generic wrap cannot grow the core. It is the fork below.

Output is the money line: beryllium mass at target for A and B, and the kilograms saved. It
also prints total added mass (beryllium + liner), because the liner is denser than beryllium
and is not free. The point is to cut the constrained material, beryllium, which can be worth a
small total-mass penalty, but the note has to show that penalty rather than hide it.

## The ring fork, resolved by running A and B first

You were unsure whether to grow the core. Do not decide it up front. Run A and B. If the
liner-plus-beryllium config reaches the target on reflector mass alone at a beryllium number
you are happy with, the ring stays on the shelf and the flight-article story is intact. If A
and B both miss the target on the swept range, the script says so explicitly, and that miss is
the signal to wire config C. So the fork is decided by whether the reflector-side savings are
enough, not by a guess now.

## Setting the target

`TARGET_WORTH_PCM` is the reactivity the reflector must buy back on the HALEU core. Set it to
the gap between the HALEU-loaded k (memory: saturates near 0.93 with TRIGA loading) and the
criticality-plus-margin you need (criticality is about 7500 pcm from 0.93; add drum swing and a
burnup-horizon margin on top). Default is 7500 pcm as a placeholder; replace it with the real
number from the depletion horizon once you fix the mission length.

Run it against the HALEU model, not fig12, for the real answer. The fig12 HEU core leaks less,
so it understates reflector worth. Point `MODEL_XML` at the `haleu_test` model and set
`EXPECT_KBASE` to that core's baseline so the self-check passes.

## Revalidation this triggers (price it in the same study, not after)

- a thermalizing liner drives a thermal flux peak at the core edge, raising radial peaking.
  It leans on the zoning lever (tilt 0.10). Re-run the peaking tally on the winning config.
- the liner runs hot at the reflector radius. ZrH will want to dissociate there; YH2 is the
  temperature-stable pick but confirm the `c_H_in_YH2` S(a,b) is in your data before trusting
  a YH2 run (the script warns if it is missing).
- drum worth and shutdown margin shift with the extra reflection. Re-search the drums to
  critical on the winning config and record the new drum demand.
- SNAP's safety concept was reflector ejection. A liner bonded to the core changes what
  ejecting the reflector does to reactivity; the hybrid has to fit that logic, not defeat it.
- all of this is in scope only because the HALEU route is already a fuel-and-reflector
  redesign. None of it applies to the frozen flight baseline.

## Run it

Mac (small check) or PC (production). In `openmc-env`, `OPENMC_CROSS_SECTIONS` set:

```bash
conda activate openmc-env
cd <CSNR repo>/axial_reflector

# HALEU route, real target. Point MODEL_XML at the haleu_test model and set its baseline k.
MODEL_XML=~/snap/model_haleu.xml EXPECT_KBASE=0.93 KBASE_TOL=0.03 \
    TARGET_WORTH_PCM=7500 LINER_CM=2 LINER_MAT=zrh \
    OMP_NUM_THREADS=20 PARTICLES=200000 BATCHES=150 INACTIVE=30 \
    python hybrid_reflector_sweep.py
```

Sweep the liner thickness to find the beryllium-minimising liner (the saving is not monotonic
in liner thickness; too thick over-thermalizes and parasitically absorbs):

```bash
for L in 1 2 3 4; do
  echo "=== liner $L cm ==="
  MODEL_XML=~/snap/model_haleu.xml EXPECT_KBASE=0.93 KBASE_TOL=0.03 \
      TARGET_WORTH_PCM=7500 LINER_CM=$L PARTICLES=200000 BATCHES=150 \
      python hybrid_reflector_sweep.py | tail -6
done
```

First-run checks: verify the layers landed where you expect with a `plots.xml`
(`color_by material`) before trusting any k, and confirm the self-check line prints OK (if the
baseline k is off `EXPECT_KBASE` the run aborts, which means the wrong model loaded). To enable
config C, wire the `snap.py` hook in `build_variant()` (Option A) and set `WIRE_RING=1`.

## Result (U_MULT=3, LINER_CM=2 ZrH, measured July 22 2026, PC)

Baseline: U_MULT=3 (TRIGA-loaded, 25 wt% U), REFL_R=0, k = 0.869. Gap to critical 15,083 pcm.

Two findings, both negative for the original hypothesis.

**1. Radial beryllium alone cannot make this core critical.** Config A (be only) worth climbs then
saturates: 3 cm gives +4960 pcm, but the curve flattens hard, +11,811 at 16 cm and only +12,485 at
24 cm (283 kg Be, k = 0.975). The ceiling is k ~ 0.976, about 2,600 pcm short of critical, and 60 kg
of extra beryllium past 12 cm buys almost nothing. This is the leakage split realised: a radial shell
kills the radial 70% of leakage, but the axial 30% is a floor it cannot touch, and on a core this far
subcritical that floor is enough to hold k below 1. To close the last stretch you need axial
reflection (a near-sphere or end caps, which is why the HALEU study's R~25 cm sphere reached critical
where this cylinder does not) or more loading.

**2. The 2 cm ZrH liner is a net loss at the worths this core needs.** It helps only while beryllium
is thin: liner-only is worth +3750 pcm, and through ~6 cm Be config B leads A (at 6 cm, +8505 vs
+7977). Above ~7-8 cm the curves cross and B falls behind, and B's ceiling (k ~ 0.959, +10,729 pcm)
is ~1,750 pcm BELOW A's. The hydride thermalizes neutrons before they reach the beryllium and then
parasitically absorbs a share of them (H and Zr capture), which lowers the achievable ceiling. Even
where B does save beryllium at a fixed sub-ceiling target (~14 kg at the +6,869 pcm point), it adds
~30 kg of ZrH to do it, so it trades a constrained material for a larger total mass, and it cannot
reach the worths that matter here at all.

**Verdict.** The liner does not pay on this core, and radial-only reflection cannot reach criticality
regardless of liner. The beryllium-minimising path is not the liner. It is, in order: (a) raise
uranium loading toward saturation first, because that buys reactivity with uranium rather than
beryllium and shrinks the 15,083 pcm gap the reflector must close; (b) reflect BOTH faces once the gap
is small enough, since the axial floor is what caps a radial shell. Next run: build U_MULT=4 (m4) and
re-baseline; if it starts near 0.90-0.93 the reflector burden roughly halves. Only test LINER_CM=1
if a thinner liner is wanted for the thin-Be regime; the 2 cm result already rules the liner out for
the recovery-sized worths.

Correction to the earlier leakage-split guidance: "spend beryllium radially, axial caps are
low-yield" holds for trimming a small margin near critical, where radial is 70% of the leakage. It
does NOT hold for closing a deep subcritical gap, where the radial reflector saturates and the
unreflected axial 30% becomes the binding constraint. Different regimes, opposite conclusions.

## Result 2 (m4 + Li-7/Nb-1Zr, first critical config, measured July 22 2026, PC)

Two levers stacked onto the m3 case closed the gap. Loading m3 -> m4 (U_MULT 3 -> 4) lifted the
NaK baseline from 0.869 to 0.889 and the radial-Be ceiling from ~0.976 to 0.994, still short. The
Li-7 + Nb-1Zr swap then added ~710 pcm of floor on m4 (less than m3's ~970, because more uranium
dilutes the coolant/clad absorption) plus ~450 pcm of reflector amplification (a cleaner-absorbing
core returns reflected neutrons at higher worth; the be-only worth edge over NaK grows with
thickness). Together that was the ~1,160 pcm that tips m4 over.

Measured, m4 Li/Nb, radial be-only: k = 0.99880 at 16 cm, 1.00280 at 20 cm, 1.00525 at 24 cm.
**First critical configuration in the study: crosses k = 1 at ~17.5 cm of radial beryllium,
~182 kg, no liner and no ring.** U_MULT=4, Li-7 coolant, Nb-1Zr clad and structure.

Liner: definitively out. Config B tops at k = 0.98948 at 24 cm (303 kg Be + 44 kg ZrH) and never
reaches critical. On the one core that can go critical, the liner drags it back under. Do not build it.

Three caveats on "critical," in order of how much they matter.
1. Hydrogen life is the gate, not k. The excess is thin (+280 pcm at 20 cm, +520 at 24 cm) and the
   Nb clad is a hydrogen getter, so it pulls hydrogen out of the ZrH over the mission, which is a
   negative-reactivity drift the static eigenvalue cannot see and which is the same order as the
   excess. Until the hydrogen-loss life of a Nb-clad hydride core is modeled, this criticality is
   provisional. This is the real open item.
2. 182 kg of beryllium is heavy and is the wrong shape. A radial cylinder cannot reflect the axial
   ends, so it overpays for the 70% it can catch. A near-sphere (snap.py REFL_R) works both faces;
   the HALEU study reached critical on U_MULT=3 with a ~65 kg sphere. refl_sphere_scan.py finds the
   minimum-Be critical sphere on this m4 Li/Nb core; expect well under half the radial mass.
3. This is no longer SNAP. Li-cooled, Nb-clad, refractory, TRIGA-loaded: SP-100-class. The
   flown-article policy argument does not apply to it. It answers "can the HALEU core be made
   critical," yes, but as a different reactor.

Next: refl_sphere_scan.py (REFL_R sphere on m4 Li/Nb) for the minimum-beryllium critical point,
then the Nb/hydride hydrogen-loss life, which decides whether any of this survives the mission.

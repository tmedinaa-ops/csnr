# OpenMC Workshop, Day 3 (Part 2) — Using OpenMC Correctly

The last notebook: performance habits and, more importantly, the statistics that
decide whether a result is trustworthy. The whole workshop deliberately used bad
particle/batch numbers to keep runs fast; this session is how to pick them for
real. The intercycle-correlation point at the end is the one that matters most for
your coupled k_eff validation, so it gets a flag. The opening chatter (gulag, My
Little Pony) is skipped. Settings names were checked against the openmc.Settings
docs.

---

## 1. Parallelization and the batches-vs-particles trade

OpenMC uses MPI and OpenMP. On a laptop you are just threading, and OpenMC uses
all available threads by default, so you rarely think about it. The thing to know:
at the end of every batch OpenMC synchronizes — it reduces (sums) the tally scores
that were accumulated across parallel workers. That synchronization is overhead and
happens once per batch. So for the same total particle count, fewer batches with
more particles each is faster than many batches with few particles. Running 1000
particles as 2 batches of 500 synchronizes twice; as 50 batches of 20 it
synchronizes 50 times for the same work. The run log's timing statistics break this
out (cross-section read time, time accumulating tallies). The takeaway: use a high
particle count per batch.

## 2. Lattices vs flat geometry

A lattice is faster to track than a flat geometry that hand-builds every cell and
surface, even when the two model the identical thing. The reason is the same as in
the Day 1 notes: in a structured lattice OpenMC knows exactly which cell a particle
enters when it crosses a boundary (top-left going right means the next index), with
no search. In a flat geometry it must work out what is on the other side of each
surface. The workshop's demo (a 7x6 assembly as a lattice vs 42 hand-built cells)
ran 2-3x faster as a lattice, measured by the particles-per-second calculation rate
in the timing output. The exact factor depends on the model; the direction does not.

The nuance, when asked whether to always minimize surface crossings: generally yes,
but it is a trade-off, not a law. A composite surface like a hexagon is six planes
under the hood, so the distance-to-surface calculation is more expensive per
crossing; sometimes more, simpler surfaces beat fewer, complex ones. For practical
purposes: if you can build it as a lattice, do.

## 3. Reproducibility and the seed

The random number seed defaults to 1, so re-running the same model gives the exact
same answer every time (`settings.seed` changes it). This is why running one model
cell twice reproduces k to the last digit.

A related conceptual point, and a useful guard against bad intuition: systems do not
scale. Doubling a box's size and doubling the particle count does not reproduce the
same k_eff — critical size is a real physical quantity, and the energy spectrum of a
small system differs from a large one. You cannot model a cheap miniature and scale
up. (Relevant to SNAP-10A: you cannot shrink the geometry for faster runs.)

## 4. The four settings, and what a batch actually is

```python
settings.particles = 100000          # neutron histories per generation
settings.inactive = 200              # discarded batches (source convergence)
settings.batches = 1200              # total; active = batches - inactive
settings.generations_per_batch = 1   # default; >1 fights intercycle correlation (Sec 7)
```

A generation is the birth-to-death of a set of particles: you start N neutrons,
track each random walk until it dies (by fission or absorption), and the fission
sites it leaves become the source for the next generation. A batch is one or more
generations (default `generations_per_batch = 1`, so batch = generation). After a
generation, k_eff is just a ratio: the number of next-generation fission sites
divided by the N particles you ran.

Inactive batches are run but not tallied, while the fission source converges away
from your initial guess. Active batches are the ones you tally over. The two are
chosen for entirely separate reasons — inactive for source convergence, active for
statistical error.

## 5. Inactive batches and source convergence

The starting source is a guess; the first batches tally a source that has not
settled, so they are discarded. The workshop demonstrated the cost of getting this
wrong: a deliberately bad source (uniform over the bottom half of a 300 cm pin)
with a heating mesh tally, run at 10, 20, 100, 500 inactive batches. At 10-20 the
heat map is still bottom-heavy; by ~100 the top half fills in; even 500 was not
quite symmetric for a geometry that must be symmetric. Run too few inactive batches
and you tally the wrong problem — you get a precise, low-uncertainty answer that is
garbage. A better initial source (uniform over the full height) converges in fewer
inactive batches. The recommended starting source from the Day 2 notes — a bounding
box constrained to fissionable material — is the practical default.

Rough guidance: hundreds of inactive batches; large reactors can need thousands.
Smaller systems, where a neutron can cross the whole geometry in one generation,
converge faster. OpenMC solves the eigenvalue problem by power iteration, so the
convergence rate is a property of the system (its dominance ratio), which is why
there is no universal number.

## 6. Shannon entropy — the quantitative convergence check

Eyeballing a tally is imprecise. Shannon entropy is a single number that measures
whether the fission source has become stationary. Overlay a mesh, count fission
events per bin, and compute the entropy each batch; when it stops changing, the
source has converged.

```python
settings.entropy_mesh = mesh          # a RegularMesh over the geometry
# after the run, read it from the statepoint:
with openmc.StatePoint(sp_path) as sp:
    entropy = sp.entropy              # one value per batch; plot vs batch
```

The plot starts high or low and flattens to a noisy plateau; pick the inactive
count where it levels off (the workshop's case plateaued around 100-200 batches,
matching the visual tally study). Run with more particles to make the plateau
cleaner. Turn the entropy mesh OFF for production runs — computing it each batch
slows the code.

## 7. Active batches, statistical error, and intercycle correlation

Active-batch count sets the statistical error: 4x the active batches halves the
standard deviation (the 1/sqrt(N) law). The clean way to target an error is a tally
or k-eff trigger (Day 2 Part 2), which keeps running until the threshold is met.

Now the subtle and important part. The 1/sqrt(N) law and the standard deviation
OpenMC reports both assume the batches are independent, like coin flips. They are
not: each batch's source sites come from the previous batch's fission sites, so
generations are correlated. This is intercycle correlation, and its consequence is
that OpenMC's reported standard deviation underestimates the true variance. The mean
is fine; the uncertainty is optimistic.

This bites when you need a tight k uncertainty. OpenMC might report 9 pcm on k_eff,
but rerun the same model with different seeds and the spread of answers might be
30 pcm — the real uncertainty. The fix is `generations_per_batch > 1`: running
several generations between recorded batches decorrelates them (batch three's source
is several generations removed from batch two's, like your DNA being far from a
great-grandparent's but close to a parent's). The workshop's demonstration runs the
model 50 times with different seeds and shows the seed-to-seed standard deviation
exceeding any single run's reported value.

---

## 8. What this means for SNAP-10A

Three things carry directly into your validation work.

The lattice performance result confirms the Day 1 call: build the 37-element core
as a `HexLattice`, not loose cells. For a small fast-ish core where neutrons cross
quickly, that is both the faster and the correct-by-construction choice.

Source convergence and Shannon entropy apply to every criticality run you do — the
core k_eff, the control-drum search, the coupled multiphysics loop. Set an
`entropy_mesh` over the core and confirm the plateau before trusting tallies or a
drum-angle search result. The SNAP core is small, so it should need fewer inactive
batches than a PWR, but verify rather than assume.

Intercycle correlation is the one to take seriously for the coupled k_eff
validation. The build spec's coupled target is k_eff = 1.00086 +/- 0.00024 (24 pcm).
If that 24 pcm is an OpenMC-reported standard deviation, intercycle correlation
means the true uncertainty is larger — possibly enough to matter when you compare
against NAA-SR-9903 or the arXiv coupled value and ask whether agreement is within
uncertainty. Before treating a 24 pcm band as real, either raise
`generations_per_batch` or run a handful of seeds and look at the actual spread.
Reporting an optimistic uncertainty is exactly the kind of thing a reviewer of the
modeling work would catch, so it is worth getting right in the validation writeup.

No searched-answer section: the substantive questions here (whether systems scale,
whether to always minimize surfaces, how to detect too-few inactive batches) were
all answered in the room.

---

This is the last notebook of the workshop; April then transitioned the group to
SNAP-10A discussion. The full note set covers Day 1 (Monte Carlo basics, geometry,
lattices, advanced geometry), Day 2 (sources, tallies, spatial tallies, criticality
search), and Day 3 (depletion, multiphysics, and these best practices).

# OpenMC Workshop, Day 3 (Part 3) — Running the SNAP-10A Model from the Terminal

A short hands-on session: running an existing SNAP-10A OpenMC model (`snap.py`)
from the command line instead of a notebook, and observing it. Most of the
recording is install/WSL troubleshooting and off-topic chatter, so this note keeps
only the workflow and the model observations, which are directly relevant since
this is your reactor. Command-line flags were checked against the openmc docs.

---

## 1. The script-and-executable workflow (vs the notebook)

Outside a notebook, OpenMC runs in two steps, because the Python build and the C++
transport solve are separate:

1. `python snap.py` — runs the model-building script, which writes the XML input
   files (geometry.xml, materials.xml, settings.xml, tallies.xml). It does NOT run
   transport.
2. `openmc` — the executable reads those XML files from the current directory and
   runs the simulation, writing a statepoint.
3. `python post.py` — a small post-processing script opens the statepoint, pulls a
   tally, reshapes it, and plots it (the notebook's inline plotting, externalized).

The recurring trap all session: editing `snap.py` does nothing until you re-run
`python snap.py` to regenerate the XML, and that still does not run transport until
you run `openmc`. "I ran it" was ambiguous — building the XML and running the solve
are two commands. The model.run() convenience of the notebook bundles all of this
into one call; the CLI does not.

## 2. openmc command-line flags (verified against docs)

Run from the directory holding the XML files, or pass that directory as an argument.
Flags:

- `-n, --particles N` — N particles per generation/batch (override the file, e.g.
  `openmc -n 1000` for a quick low-statistics run so it finishes on a laptop).
- `-s, --threads N` — number of OpenMP threads (defaults to all).
- `-p, --plot` — plotting mode.
- `-c, --volume` — stochastic volume calculation.
- `-g, --geometry-debug` — check for cell overlaps after each particle move.
- `-r, --restart <file>` — restart from a statepoint or particle-restart file.
- `-t, --track` — write particle tracks.

`openmc.run()` in the Python API is equivalent to running `openmc` from the CLI.

## 3. Persistent environment for local runs

To avoid re-typing setup every session, put the environment activation and data
paths in the shell startup file (`.bashrc` for WSL/Linux, `.zshrc` on the Mac), so
they run automatically:

```bash
# in ~/.bashrc (WSL) or ~/.zshrc (Mac)
conda activate openmc-env
export OPENMC_CROSS_SECTIONS=/path/to/cross_sections.xml
export OPENMC_CHAIN_FILE=/path/to/chain.xml      # needed if you deplete
```

Keeping the cross-section library on fast local storage (not a network/iCloud
folder) makes the data load quickly at the start of every run.

## 4. The recurring carbon library mismatch

The same nuclide-naming issue from Day 1 resurfaced. Some libraries store carbon as
a single lumped `C0`; others split it into `C12`, `C13` (and `C14`). A model
written with `C0` fails against a library that only has the isotopes, and vice
versa. The fix is to match the nuclide names to the library you actually have
(ENDF/B-VIII.0 here), or comment out the offending nuclide. This is the same family
of error as the O16 crash — a library/name mismatch, not a physics problem.

## 5. Adding a tally to a script-based model

To get any output you must add the tally to the build script, not type it live:

```python
tally = openmc.Tally()                 # capital T; lowercase 'tally' is not a class
tally.scores = ['kappa-fission']       # 'scores' is plural; mind the spelling
mesh = openmc.RegularMesh()
mesh.lower_left, mesh.upper_right = ... # over the model extent
mesh.dimension = (20, 20, 20)
tally.filters = [openmc.MeshFilter(mesh)]
model.tallies = [tally]
```

Then re-run `python snap.py` (regenerate XML) and `openmc` (solve), and read it back
in `post.py`. The live debugging was almost entirely typos: `tally` vs
`openmc.Tally`, `score` vs `scores`, misspelled `kappa-fission`. Spelling and
capitalization are load-bearing.

## 6. Observations on the SNAP-10A model itself

This is the project-relevant part. The `snap.py` model used here was pre-built (by
someone else) and has some rough edges worth knowing before you adopt or rebuild it:

- It uses an older OpenMC API in places — for example setting the bounding box via
  an explicit lower-left/upper-right rather than `model.bounding_box`. Expect to
  modernize it.
- The NaK coolant is the material filling the space between fuel elements (visible
  in the plotter by hovering). The model is at a single uniform temperature — no
  multiphysics feedback applied yet.
- It is not optimized: a large, flat-ish geometry that runs slowly (~125-400
  particles/second on the workshop laptops), and the settings file defaults to ~1e6
  particles, which is why a default run takes a long time. Building the core as a
  proper lattice (Day 1 Part 2 / Day 3 Part 2 performance notes) is the obvious
  improvement.
- k_eff came out around 1.00267 (combined estimator) at only 1000 particles — high
  uncertainty, so treat the digits as rough, but the model sits slightly
  supercritical, consistent with a near-critical design and with the build spec's
  coupled target of k = 1.00086.

A mentor note worth carrying forward: this standalone, uniform-temperature run lands
a bit above the coupled value in the build spec. That direction is exactly what the
Day 3 multiphysics physics predicts — at realistic hot operating temperatures,
Doppler broadening and reduced coolant density lower k, the negative feedback. So
the gap between a cold/uniform standalone k and a hot coupled k is the temperature
feedback showing up, not an error. It is a sensible first sanity check on the
coupled model when you build it. (Caveat: the 1000-particle uncertainty is large and
the standalone model's exact temperature was not stated, so confirm before leaning
on the comparison.)

---

Tomorrow's session was slated for Cardinal (the OpenMC-MOOSE multiphysics coupler),
which April flagged as harder to install and needing heat-transfer background — the
heavier tool behind the Day 3 Part 1 multiphysics workflow, and the one the build
spec reserves for a heavier machine or HPC.

# OpenMC Coding Best Practices and Methods

A practical checklist for building the SNAP-10A OpenMC models, distilled from the
April Novak workshop notes (Day 1-3, in OpenMC_Workshop/ and the Obsidian vault)
and verified against docs.openmc.org. Load this alongside the build spec
(SNAP-10A_Model_Base_Set.md, SNAP-10A_Validation_Targets.csv,
SNAP-10A_Model_Equations.md) when writing OpenMC. Each item points to the note with
the full reasoning.

## Environment and runtime

- Activate the environment first every session: `conda activate openmc-env`. Every
  new terminal starts in base; the prompt should read (openmc-env).
- Data via environment variables in the shell startup file (`~/.zshrc`):
  `OPENMC_CROSS_SECTIONS` (ENDF/B-VIII.0) and, for depletion, `OPENMC_CHAIN_FILE`,
  on fast local storage, not iCloud/network.
- Two ways to run. Notebook `model.run()` bundles build + solve. The CLI is three
  steps: `python build.py` writes the XML, `openmc` runs the solve, a `post.py`
  reads the statepoint and plots. For real work prefer scripts over notebooks
  (April's own habit), and split materials into an importable, verified module.
- Useful `openmc` CLI flags: `-n N` (particles/generation, for quick low-stat
  runs), `-s N` (threads), `-g` (geometry-debug, checks cell overlaps), `-p`
  (plot), `-r file` (restart). [Day 3 Part 2, Part 3]

## Geometry — correctness and performance together

- Use lattices for repeated structure: 2-3x faster, because OpenMC knows the next
  cell on a boundary crossing with no search. Build the 37-element core as a
  `HexLattice` (pitch 3.20040 cm, 4 rings = 37). [Day 1 Part 2, Day 3 Part 2]
- Use the purpose-built composite surfaces for the shield: `openmc.model.ConicalFrustum`
  (6-degree LiH body), `openmc.model.Vessel` (cylinder with domed heads, the 316 SS
  casing), `RightCircularCylinder`. Let OpenMC assemble the half-spaces. [Day 1 Part 3]
- Do not subdivide cells unnecessarily — OpenMC stops a particle at every cell
  boundary even when the material is identical on both sides. [Day 3 Part 2]
- Do not hardcode IDs; they vary between runs. Find cells by name or via the root
  universe (`model.geometry.get_all_cells()`, then match `.name`). [Day 2 Part 2]
- Always set boundary conditions on the outer surfaces (vacuum or reflective) or the
  run errors with "no boundary conditions." [Day 1 Part 2]
- Plot as you build; use `openmc-plotter` with overlap coloring to debug geometry.
- Geometry does not scale — you cannot shrink the model for cheaper runs. [Day 3 Part 2]

## Materials

- `add_element('U', enrichment=...)` does the U-235/U-238 bookkeeping. Use
  `add_element('O', ...)` rather than `add_nuclide('O16', ...)` to dodge library
  name mismatches (the recurring O16 / carbon-C0-vs-isotopes crash). [Day 1, Day 3 Part 3]
- Add S(alpha,beta) for thermal scatterers (`add_s_alpha_beta('c_H_in_H2O')`).
  Central for thermal systems; secondary for the fast shield unless you tally
  thermal flux in it. [Day 1]
- For homogenized regions (the FMC-N core/shield densities), add each nuclide with
  its number density in atom/b-cm and call `set_density('sum')`. [Day 2]

## Sources

- Default recommended criticality source: `Box` over `model.bounding_box` with
  `constraints={'fissionable': True}` to reject sites outside fuel. [Day 2]
- The shield is fixed-source: `run_mode='fixed source'`, with either the FMC-N
  spectrum prescribed via `IndependentSource` (for matching the report) or a
  surface source extracted from a core criticality run (`surf_source_write` with
  `cellfrom`, then `surf_source_read`). [Day 2]

## Tallies and normalization

- Monte Carlo records only what you score. A tally is scores + filters; no filter
  means whole phase space. [Day 2]
- Results are per source particle, geometry in cm, energy in eV. To get physical
  units multiply by source rate S and divide by volume (a single mesh element for a
  mesh tally, the whole problem otherwise). [Day 2, Day 2 Part 2]
- Eigenvalue runs: get S by imposing the core power through a `kappa-fission`
  heating tally. Ratios (the validation targets — mating-plane factor, 0.0359
  attenuation, removal cross section) cancel S and volume, so they need no
  normalization. [Day 2]
- Read with `get_values`, `get_pandas_dataframe`, or `get_slice` (for VTK/ParaView).
  Always report uncertainty (relative error). [Day 2, Day 2 Part 2]

## Statistics and convergence — the trust checklist

- Many particles per batch, few batches: less end-of-batch synchronization and less
  intercycle correlation. [Day 3 Part 2]
- Inactive batches converge the fission source; verify with Shannon entropy
  (`settings.entropy_mesh`, then `statepoint.entropy` should plateau). Turn the
  entropy mesh off for production. Too few inactive batches gives a precise but
  wrong answer. [Day 3 Part 2]
- Active batches set statistical error (4x batches -> half the std dev). Use triggers
  (`keff_trigger`, or `openmc.Trigger` on a tally) to run until a tolerance is met,
  for production runs. [Day 2 Part 2, Day 3 Part 2]
- Intercycle correlation: OpenMC's reported standard deviation is optimistic because
  batches are not independent. Before trusting a tight k uncertainty (e.g. the
  coupled target k = 1.00086 +/- 24 pcm), raise `generations_per_batch` or run a few
  seeds and check the actual spread. [Day 3 Part 2]
- Seed defaults to 1, so runs are reproducible; change `settings.seed` to resample.
- Variance reduction (weight windows) is mandatory for the deep-penetration LiH
  shield — analog Monte Carlo will not reach the dose plane, and triggers do not
  substitute. [Day 1, Day 2]

## Depletion

- Set the volume of depleted materials; deplete only the fuel. Chain file must match
  the cross-section library and the spectrum (epithermal for SNAP-10A, not pure
  thermal); use a reduced chain for speed. [Day 3]
- `openmc.deplete.CoupledOperator(model, chain)` + an integrator
  (`PredictorIntegrator` simplest; higher-order ones tolerate bigger steps). Read
  with `Results.get_keff` / `get_atoms` / `get_reaction_rate`.
- Time steps under ~1 month, ~1 day for the first month; `operator.heavy_metal` gives
  the max-step ratio; `diff_burnable_mats=True` deplete lattice positions separately. [Day 3]

## Multiphysics

- Couple in memory through the C API (`openmc.lib.init/run/reset/finalize`,
  `run_in_memory`, `find_cell`) — the lightweight local alternative to a full
  Cardinal build for a first SNAP-10A temperature-feedback test. [Day 3]
- Temperature: `settings.temperature = {'default':..., 'method':'interpolation',
  'range': (covering NaK 755-816 K and fuel ~805-853 K)}`. Set per-cell temperature
  and density for the feedback. [Day 3]
- Set run parameters (e.g. `particles`) BEFORE `openmc.lib.init()` — they are fixed
  at init and will not change inside the session loop. [Day 3]
- Use relaxation to damp Picard oscillation between iterations. [Day 3]

## Validation policy (from the build spec)

- Reproduce the reports' published numbers first using their geometry and data, then
  switch to modern 3D geometry and ENDF/B-VIII. Validate against their numbers.
  Ratios are the most robust targets because they need no normalization.

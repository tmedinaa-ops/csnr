# Layer 2 fixes (June 2026): correct readout, then an OpenMC-main restructure for speed

This records two rounds of fixes and why the second was necessary.

## Round 1 (readout + a speed attempt that failed)

The first 37-pin run had three problems: ~3-hour runtime, a fluid energy balance that
did not close (channels summed to 44 kW vs 34 kW supplied), and a near-flat radial
power (all 37 outlets within 0.35 K).

Fixes that ARE correct and stay:
- thm.i: replaced mdot*cp*(T_out - 755.37), which differenced biased cell-centroid side
  averages, with `ADHeatRateConvection1Phase` (`heat_added`), the integrated wall flux
  the solver actually applied. This is the conserving per-channel power.
- openmc.i: cell_level stays 1 (verified vs the Cardinal lattice regression test; the
  flat radial was NOT a cell_level error). cell_id / cell_instance are Cardinal
  auto-outputs -- do not add them manually (it aborts).

The speed attempt that FAILED: removing the solid `HeatConductionTimeDerivative` and
cutting num_steps. The rerun sat at the SAME state as the old transient at iteration 25
(max fuel T ~793 K vs the converged ~856 K, still climbing; conjugate only ~30%
equilibrated). The thermal mass was never the bottleneck -- the README always said so.

## Round 2 (the real fix): OpenMC-main restructure

Root cause (researched, cited): the SOLID-as-main layout put OpenMC and THM both on
timestep_end, after the solid. Every physics reacted to one-iteration-stale neighbor
data -- a fully-lagged Jacobi sweep on a stiff conjugate interface (Hw ~5e4) -- and
fixed_point_max_its=1 disabled any in-step iteration to catch up. That is why it crawled
regardless of the time derivative or the relaxation method.

The documented Cardinal pattern (gas_assembly tutorial, OpenMC+solid+THM) is the fix:
OpenMC is the MAIN app; the cheap, stiff solid<->THM conjugate loop is converged INSIDE
the solid sub-app while the expensive OpenMC eigenvalue solve fires only once per outer
step. Refs: cardinal.cels.anl.gov/tutorials/openmc_fluid.html ;
mooseframework.inl.gov/syntax/Executioner/FixedPointAlgorithms/.

Architecture now:
```
  openmc.i (MAIN, Transient num_steps=15, OpenMC relaxation 0.5)
    --power-->  solid_core.i (FullSolveMultiApp; Transient, no time deriv,
                              fixed_point_max_its=50 converges the conjugate)
                  --T_wall-->  thm.i  (37 NaK channels, sub_cycling, unchanged)
    <-- temperature --            <-- T_fluid / htc (CoupledHeatTransfers) --
```

Files:
- openmc.i        NEW main app (OpenMC problem + solid sub-app + power/temperature transfers).
- solid_core.i    now a SUB-app: removed the openmc MultiApp and its two transfers; the
                  executioner is now the conjugate fixed-point loop (num_steps=1,
                  fixed_point_max_its=50, rel_tol 1e-4, accept_on_max). THM coupling unchanged.
- thm.i           unchanged from Round 1 (heat_added PP, steady_state_detection).
- openmc_core.i   RETIRED (superseded by openmc.i; left in place, no longer referenced).

## How to run

From layer2_core/ (moose env, model.xml present, OPENMC_CROSS_SECTIONS set):

    cardinal-opt -i openmc.i
    # or parallel:
    mpiexec -np 10 ~/cardinal/cardinal-opt -i openmc.i --n-threads=2

NOTE the entry point is openmc.i now, NOT solid_core.i. Expect ~15 OpenMC solves
(~15-30 min), not 350.

## Output names changed (nested apps)

Outputs are now prefixed by the main app: openmc_out.* (OpenMC: heat_source, k, cell_id,
cell_instance, temp), openmc_out_solid0.* (the solid: T, power), and the THM channels are
nested deeper. Glob flexibly. The check script:

```
python3 - << 'PY'
import glob, csv
def rows(f): return [r for r in csv.DictReader(open(f)) if r]
thm = sorted(f for f in glob.glob("*thm*[0-9]*.csv"))
Q  = [float(rows(f)[-1]['heat_added'])  for f in thm]
To = [float(rows(f)[-1]['T_fluid_out']) for f in thm]
n, tot = len(Q), sum(Q); avg = tot/n
print(f"channels={n}  SUM heat_added={tot:.0f} W  per-ch mean={avg:.0f} peak/avg={max(Q)/avg:.3f}")
print(f"outlet T min={min(To):.1f} max={max(To):.1f} spread={max(To)-min(To):.1f} K")
# k and convergence from the OpenMC main csv:
oc = rows(glob.glob("openmc_out.csv")[0])
print("k per outer step:", [round(float(r['k']),5) for r in oc][-6:])
PY
```

## What to check on this run, in order

1. It SOLVES (no setup error). The new pieces most likely to trip: FullSolveMultiApp +
   CoupledHeatTransfers, the temp/power transfer names, the KEigenvalue PP name. All
   fail at setup in seconds.
2. CONVERGENCE: max_fuel_T (solid console) should plateau near ~856 K within ~10 outer
   steps, and k near 1.0009. If max_fuel_T is still climbing at step 15, the inner
   conjugate loop needs more iterations -- raise solid_core.i fixed_point_max_its, and/or
   add interface relaxation (relaxation_factor=0.7, transformed_variables='T_fluid').
3. CONSERVATION: SUM heat_added across the 37 THM csvs should equal power_in (~34 kW),
   not 44 kW and not 10 kW (10 kW was the un-converged Round-1 number).
4. RADIAL: peak/avg of heat_added and the outlet spread; cross-check by coloring
   openmc_out.e by cell_id (37 distinct) and heat_source (peaked) in ParaView.

## Tunables most likely to need a pass (all cheap, fail/observe fast)

- solid_core.i fixed_point_max_its (50) and the interface relaxation, if the conjugate
  is slow to close.
- openmc.i num_steps (15), if k / max_fuel_T still drift.
- Only once converged and conserving: set the operating power in openmc.i `power =`.

## Round 3 (the actual radial/conservation fix): axial bin alignment

The OpenMC-main restructure fixed convergence speed (k stable), and ParaView confirmed the
solid `power` is peaked ~1.5x (center hot) -- so neutronics and the OpenMC->solid transfer
are correct. But the 37 channels still removed a flat ~568 W each and only 21 of 34 kW
reached the NaK. Root cause (verified against MOOSE source): the `CoupledHeatTransfers`
action builds its axial layer bins from `position`, spanning position.z .. position.z+length.
make_core_mesh.i centers the solid on z in [-L/2,+L/2] (a TransformGenerator TRANSLATE), but
the block had `position = '0 0 0'`, so the bins ran z in [0,+L]. LayeredBase::getLayer then
clamped every z<0 clad face into layer 0 and left the top bins empty, smearing each pin's
wall-T profile flat and under-delivering heat. The (x,y) nearest-point partition over the
shared 'outer' sideset was always correct (the common z in the 37 points cancels).

FIX (solid_core.i, one line): `position = '0 0 0'` -> `position = '0 0 -0.1552575'` (-L/2).
After this, center-vs-edge channels should differ by the ~1.5x peaking and total heat_added
should close toward power (~34 kW). If a residual heat gap remains, it's the inner conjugate
fixed-point budget (raise solid_core.i fixed_point_max_its, or warm-start by switching the
solid MultiApp from FullSolveMultiApp to TransientMultiApp). Robust fallback if the shared-
sideset partition still misbehaves: 37 per-pin sidesets (RenameBoundaryGenerator before
CombinerGenerator) + one single-channel CoupledHeatTransfers per pin. Ref: MOOSE
CoupledHeatTransferAction / NearestPointLayeredSideAverage / LayeredBase source; discussion #28926.

## Round 4 (the real partition fix): per-pin sidesets

The z-bin fix (Round 3) had zero effect -- heat stayed perfectly uniform at 570 W x 37 =
total. Root cause, verified against MOOSE source: the CoupledHeatTransfers action does NOT
support partitioning ONE shared 'outer' sideset across N position-keyed channels. There is no
test for >1 partition point; the mode collapses to a whole-boundary average, so every channel
got 1/37 of the total. The only source-tested configuration is N single-channel couplings,
each on its OWN sideset with its OWN single-instance THM app.

solid_core.i is now GENERATED by gen_per_pin.py (do not hand-edit it; edit the generator):
it splits 'outer' into 37 per-pin sidesets (outer_p01..outer_p37, by (x,y) proximity to each
pin center, restricted to the existing 'outer' faces), and emits 37 single-channel
CoupledHeatTransfers blocks + 37 single-instance THM apps (thm01..thm37). openmc.i and thm.i
are unchanged. Re-run `python gen_per_pin.py` if pin_positions.txt or the physics changes.

VERIFY THE MESH FIRST (cheap): `cardinal-opt -i solid_core.i --mesh-only solid_check.e`, then
confirm each outer_pNN sideset is nonzero and ~equal (one pin's clad surface). Only then run
the coupled model. If a sideset comes out empty/over-selected, widen/narrow RSEL2 in the
generator or switch the criterion to an annular clad-radius test (see the partition research).
Success on the coupled run: per-channel heat_added spreads ~1.3-1.5x (matching the power peak),
outlet spread tens of K, SUM heat_added -> ~power (34 kW). Ref: MOOSE CoupledHeatTransferAction
source (no multi-point test); per-pin single-channel is the canonical form.

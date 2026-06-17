# Layer 1 cp-accelerated steady cross-check

Self-contained copy of `../layer1_transfer/` whose only physics change is the
solid heat capacity, cut 4x, to reach steady fast. Everything else (geometry,
mesh, OpenMC model, THM channel, conductivities, the energy-closure check) is
identical.

## Why this exists

Two jobs.

1. It proves the heat-capacity acceleration is steady-exact. At steady `dT/dt = 0`,
   the time-derivative term vanishes, so `rho*cp` cannot affect the converged
   temperatures, and the NaK outlet is fixed by the energy balance
   `P / (mdot*cp_NaK)`, which has no solid cp in it. The claim is only believable
   once measured: this run must land on the same steady numbers as the long
   `layer1_transfer` march. If it does, the trick is validated.

2. Once validated, this is the fast iterate config. The full `layer1_transfer`
   march needs ~360 OpenMC solves to clear ~6 tau at the real ~1200-1500 s time
   constant. Cutting cp 4x shrinks tau to ~300-375 s, so `dt=50 / num_steps=50`
   (2500 s, ~7-8 tau) reaches the same steady state in ~50 solves.

## What changed vs layer1_transfer

Only `solid_3d.i`:

- `specific_heat` cut 4x in all three solid materials: fuel 300 -> 75,
  coating 400 -> 100, clad 578 -> 144.5 J/kg-K. `thermal_conductivity` is
  UNTOUCHED, because that is what sets the steady temperature.
- Executioner `dt = 50`, `num_steps = 50` (retuned to the shorter tau).

`openmc.i`, `thm.i`, `make_mesh.i`, `snap_unit_pin.py`, `run_layer1.sh`,
`k_of_T_sources.md` are byte-for-byte copies. `thm.i` keeps the `heat_removed`
and `power_imbalance` postprocessors, so the same physical convergence check
applies here.

## Run it (PC, moose env, OPENMC_CROSS_SECTIONS set)

It is self-contained, so it writes its own XMLs, mesh, and output CSVs in this
folder and does not collide with `layer1_transfer`. That means it can run
concurrently on spare cores while the long march runs (see the parallelism note
in the heat_transport README).

```
conda activate openmc-env && python snap_unit_pin.py   # writes the OpenMC XMLs here
conda activate moose
bash run_layer1.sh                                      # runs solid_3d.i in this folder
```

To run it next to the long march on, say, 6 of the 20 cores:

```
NP=6 NT=1 bash run_layer1.sh
```

## Pass criterion

Same steady values as `layer1_transfer`:

- NaK outlet (thm_nak.csv, last row, `T_fluid_out`) at 817.7 K
- `power_imbalance` -> 0 (under ~9 W, ~1% of 918.92)
- `max_fuel_T` flat at ~826-832 K

If those match within Monte-Carlo noise, the cp acceleration is exact and this
becomes the default config for everything downstream. If `max_fuel_T` or the
outlet differs by more than the noise band, something other than cp changed by
accident, check the diff against `layer1_transfer/solid_3d.i`.

## Stacking the next speedup

The cp cut is the time-axis lever. The independent lever is per-solve cost:
dropping `inactive` 30 -> ~10 (the source is warm-started across steps) and
`particles` 20000 -> ~10000 in `snap_unit_pin.py`, with a single full-statistics
solve at the converged temperature for the reported numbers. Apply that here and
this run gets both multipliers.

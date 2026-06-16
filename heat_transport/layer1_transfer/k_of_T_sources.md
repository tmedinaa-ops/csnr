# Thermal conductivity sourcing for the solid materials

This records where the fuel, coating, and clad conductivities in `solid_3d.i`
come from, why only the clad is temperature-dependent, and what the reference
model used. The conductivity is what sets the steady radial temperature drop and
therefore the peak fuel temperature, so it is the input that has to be
defensible. Density and specific heat only set how fast the model marches to
steady, so they are left at the prior constants.

## What the reference model used

The arXiv 2505.04024 SNAP 10A/2 Cardinal paper (the model this whole workstream
validates against) lists constant conductivities in its Table II:

| Material | arXiv Table II | prior heat_transport value |
|---|---|---|
| U-ZrH fuel | 22.484 W/m-K | 18.0 |
| Sm2O3 coating | 1.729 W/m-K | 1.5 |
| Hastelloy N clad | 18.852 W/m-K | 23.6 |

All three differed from the reference, and the clad differed the most and in the
wrong direction. 23.6 W/m-K is the Hastelloy N correlation read at about 700 C
(973 K), but the clad runs near 510 to 545 C (783 to 820 K), where the same
correlation gives about 18 to 19. So the prior model overstated clad
conductivity by roughly 25 percent. The clad drop is small either way (a few
tenths of a kelvin), so the peak fuel temperature barely moved, but the value
was not defensible. The new k(T) reproduces the paper's 18.852 at the design
point and corrects the off-design behavior the 14 kWe study needs.

## Hastelloy N clad: temperature-dependent, sourced

k(T) = 9.77 - 3.2e-4 T + 1.46e-5 T^2   (W/m-K, T in kelvin)

This is the ORNL Molten Salt Reactor / Molten Salt Demonstration Reactor
correlation for Hastelloy N, reproduced in the Gen3 CSP thermophysical-property
database, which traces it to the Haynes International physical-property sheet.
Checks:

- At 300 K it gives 11.0 W/m-K, matching the Haynes room-temperature value (~11.5).
- At 800 K it gives 18.86 W/m-K, matching the arXiv Table II clad value of
  18.852, which means the paper used this same curve evaluated near 800 K.
- It rises monotonically through the service range, as a nickel alloy should.

Implemented as a `PiecewiseLinearInterpolationMaterial` table sampled every 100 K
from 300 to 1100 K with linear extrapolation on, so the 14 kWe runs that push the
clad hotter stay on the curve rather than clamping. Confidence: medium-high. The
correlation is for the Hastelloy N service range and the SNAP band sits inside it.

## U-ZrH fuel: constant on purpose

Value used: 22.484 W/m-K (the arXiv Table II value).

The literature is consistent that U-ZrH1.6 conductivity is about 18 W/m-K and
nearly independent of temperature from room temperature to ~773 K (Simnad,
GA-A16029, the canonical TRIGA-fuel reference; Tsuchiya et al., J. Nucl. Mater.
289 (2001) on 45% U-ZrH1.6, measured "nearly independent of temperature"). So a
constant is the honest representation here: there is no defensible slope to add
in the 750 to 850 K band.

The open question is the magnitude, 18 (literature) versus 22.484 (the reference
paper). I defaulted to the paper's 22.484 so all four materials are consistent
with the validation reference at the design point. The cost of that choice is
small and known: higher k means a smaller fuel-internal drop, so 22.484 predicts
a peak fuel temperature about 3 K lower than 18 would (~13 K internal drop at 18,
~10 K at 22.484). If you would rather make the literature value primary and treat
the paper as the cross-check, change the one number in `fuel_mat` to 18.0; the
peak fuel temperature rises by ~3 K and becomes the conservative bound.
Confidence: medium. The temperature-independence is well supported; the
magnitude carries the 18-to-22.484 spread.

## Sm2O3 coating: constant, weakest link

Value used: 1.729 W/m-K (the arXiv Table II value).

Pure samaria conductivity is poorly characterized. The closest measured data is
samaria-doped zirconia thermal-barrier coatings at about 1.26 W/m-K near 760 C,
which is a different material. Rare-earth sesquioxides sit in the 1 to 3 W/m-K
range with weak temperature dependence. There is no usable T-curve, so the
coating stays constant at the reference value. The coating is thin but its
conductivity is low, so it carries roughly a 4 to 5 K drop, the second largest
after the fuel-internal drop. This is the material to revisit first if the peak
fuel temperature ever needs to be tighter than a few kelvin. Confidence: low.

## Net effect on the result

Peak fuel temperature is essentially unchanged from the prior single-pin value
(~826 to 832 K versus the MVP's 829 K), because the clad correction is sub-kelvin
and the fuel-k change is a few kelvin. The point of this pass is not to move the
number, it is to make every conductivity traceable to a source and to give the
clad the real temperature dependence the off-design 14 kWe study will turn.

## Sources

- M. Dalinger et al., "Multiphysics Modeling of SNAP 10A/2 Space Reactor with
  Cardinal," arXiv:2505.04024, Table II (fuel 22.484, coating 1.729, clad 18.852).
- Gen3 CSP Thermophysical Properties Database, Hastelloy N
  (https://gen3csp.gatech.edu/hastelloy-n/), citing the Haynes International
  Hastelloy N physical-property sheet; ORNL/MSDR Hastelloy N k(T) correlation.
- M. T. Simnad, "The U-ZrHx Alloy: Its Properties and Use in TRIGA Fuel,"
  GA-A16029 (1980); summary value ~18 W/m-K, nearly flat in T.
- K. Tsuchiya et al., "Thermal properties of hydride fuel 45% U-ZrH1.6,"
  J. Nucl. Mater. 289 (2001) 329, U-ZrH1.6 conductivity nearly independent of T
  to ~773 K.

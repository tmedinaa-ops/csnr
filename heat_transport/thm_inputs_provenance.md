# Where the thm.i inputs come from

Every input in the THM NaK flow-channel deck (`thm.i`), traced to its source, with a
confidence flag. The short version: the temperatures, flow, heat-transfer coefficient, and
the four real NaK properties all come from the same paper that the whole snap model is built
against (arXiv 2505.04024, Tables I and II); the geometry terms are derived from that paper's
dimensions; and a few EOS parameters are nominal numbers that do not affect the steady
forced-convection result.

## The primary reference

M. Dalinger, E. Merzari, T. Nguyen, M. Seneca, R. Martineau, "Multiphysics Modeling of SNAP
10A/2 Space Reactor with Cardinal," Nuclear and Emerging Technologies for Space (NETS 2025),
arXiv:2505.04024. https://arxiv.org/abs/2505.04024 (PDF https://arxiv.org/pdf/2505.04024).
This is the paper the snap OpenMC model reproduces (validated at tag v1.0-fig12-validated),
and its Table I gives the core geometry, Table II the NaK-78 properties, flow, inlet
temperature, and the clad-to-NaK heat-transfer coefficient. The fig12_test operating case in
`snap_config.py` cites it directly (Sec. V.A), and for the inlet/outlet temperatures cites the
original Atomics International source, Magee, Dufoe, and Gordon, "SNAP 10A Reactor Thermal
Performance," AI, 1964.

## Input-by-input

| input | value | source | confidence |
|---|---|---|---|
| `T_in` | 755.37 K | NaK core inlet (cold leg), arXiv Table II; originally Magee/Dufoe/Gordon 1964 design-average | primary |
| `mdot` | 0.0167541 kg/s | per channel = arXiv Table II total core flow 0.6199 kg/s / 37 pins | primary |
| `Hw` | 5.01e4 W/m^2-K | clad-to-NaK heat-transfer coefficient, arXiv Table II (constant) | primary |
| `L` | 0.310515 m | active fuel length, arXiv Table I (snap.py half-height h1 = 15.52575 cm) | primary |
| `density0` | 755.92 kg/m^3 | NaK-78 at 783.15 K, arXiv Table II (from Foust 1972) | primary |
| `viscosity` | 1.8835e-4 Pa-s | NaK-78 at 783.15 K, arXiv Table II | primary |
| `thermal_conductivity` | 26.2345 W/m-K | NaK-78 at 783.15 K, arXiv Table II | primary |
| `cp` | 879.903 J/kg-K | NaK-78 at 783.15 K, arXiv Table II | primary |
| `A_flow` | 9.530e-5 m^2 | per-rod hex unit-cell flow area = (sqrt3/2) p^2 - (pi/4) D^2, from Table I geometry | derived |
| `D_h` | 3.822e-3 m | hydraulic diameter = 4 A_flow / (pi D) = D[(2 sqrt3/pi)(P/D)^2 - 1] | derived |
| `P_hf` | 0.0997456 m | heated perimeter = pi x clad OD (D = 0.031750 m) | derived |
| `initial_vel` | 0.233 m/s | starting guess = mdot / (rho A_flow); converges, not an independent input | derived |
| `initial_T` | = `T_in` | starting temperature = inlet | primary |
| `n_ax` | 30 | axial element count; numerical discretization (matches the mesh) | numerical |
| `initial_p` / `p_out` | 4.0e5 Pa | nominal loop pressure; sets the EOS level only | nominal |
| `cv` | 879.903 J/kg-K | set equal to cp (liquid metal is nearly incompressible, so cv ~ cp) | nominal |
| `thermal_expansion` | 2.5e-4 1/K | nominal NaK value (the A1 density slope implies ~3.1e-4); only enters buoyancy | nominal |
| `bulk_modulus` | 1.0e9 Pa | nominal SimpleFluidProperties stiffness; numerical, not thermally important | nominal |

## Notes worth keeping

The geometry numbers are self-consistent and reduce to the same hydraulic diameter two ways.
`A_flow` here is the per-rod flow area (the hex unit cell, two interior subchannels' worth per
rod), while the friction model in `uprate/channel_hydraulics.py` uses the single interior
subchannel (exactly half, 4.765e-5 m^2). Both are correct for their purpose, and the hydraulic
diameter is identical either way, because the per-rod area and the per-rod wetted perimeter
(pi D) both scale by the same factor of two. The clad outer diameter D = 0.031750 m and pitch
P = 0.0320040 m give P/D = 1.008, the tight lattice everything else is built on.

The nominal entries (`p_out`, `cv`, `thermal_expansion`, `bulk_modulus`) do not affect the
steady forced-convection temperature solution. NaK is effectively incompressible at these
conditions, so the absolute pressure level and the bulk modulus set the equation-of-state
behavior without changing the thermal answer, and the thermal expansion only matters if
buoyancy competes with the forced flow, which it does not at 0.23 m/s. They are there because
`SimpleFluidProperties` requires them, not because a SNAP source specified them.

`SimpleFluidProperties` holds these four NaK numbers CONSTANT at the 783.15 K design point.
That is fine for reproducing the design point but wrong for the uprate, where the outlet runs
hotter. The fix is already built: `uprate/nak78_properties.py` (component A1) provides the
temperature-dependent NaK-78 correlations anchored to these same Table II values, and MOOSE
ships a built-in `NaKFluidProperties` object (the same Foust 1972 eutectic data) that drops in
for `SimpleFluidProperties` with no code. See `uprate/Implementation_Research_Dossier.md`,
component A1, for the swap.

## Sources

- arXiv:2505.04024, Dalinger et al., NETS 2025 (Tables I and II): the direct source of the
  temperatures, flow, HTC, geometry, and NaK property values.
- Magee, Dufoe, Gordon, "SNAP 10A Reactor Thermal Performance," Atomics International, 1964:
  the original inlet 755.37 K / outlet 816.48 K design temperatures, cited by the paper and by
  `snap_config.py`. (Cited via the paper; not independently retrieved here.)
- O. J. Foust (ed.), Sodium-NaK Engineering Handbook Vol. I, Gordon & Breach / USAEC, 1972:
  the ultimate source of the NaK-78 property values that Table II carries.
  https://www.osti.gov/biblio/4631555

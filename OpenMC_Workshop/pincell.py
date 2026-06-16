"""
PWR pin-cell model in OpenMC
Reconstructed from April Novak's OpenMC workshop, Day 1 (the "hello world" of
Monte Carlo transport). Cleaned up and corrected for the bugs that came up live.

What this models: the smallest repeatable unit of a pressurized water reactor.
A single fuel rod (UO2 pellet, helium gap, cladding) sitting in water, with
reflective radial boundaries so it behaves like one cell of an infinite lattice.
Run mode is k-eigenvalue (criticality), so the answer is k_eff.

Run it with:
    python pincell.py
You need OpenMC installed and a cross-section library configured (the
OPENMC_CROSS_SECTIONS environment variable pointing at a cross_sections.xml).
In the workshop Colab that was done for you; on your own machine see
https://openmc.org/official-data-libraries/

Notes on faithfulness to the workshop:
  - The pellet/clad radii here are the standard OpenMC tutorial values. The radii
    April dictated live (0.46955, etc.) were arbitrary placeholders she read off
    the notebook, so I used the canonical set instead. Structure is identical.
  - Oxygen is added with add_element('O', ...), NOT add_nuclide('O16', ...).
    The live O16 crash was a cross-section library mismatch: the Colab library
    (ENDF/B-VII.1) stores oxygen differently than O16-as-a-nuclide expects.
    add_element sidesteps it by expanding to whatever oxygen the library has.
  - The joke "lead in the fuel/water" from the workshop is left out.
  - The helium gap is modeled as void (fill=None), which is the standard
    neutronics approximation. Real helium is in the comment below if you want it.
"""

import openmc

# ---------------------------------------------------------------------------
# 1. MATERIALS
# A material needs two things: which nuclides are present, and the density.
# OpenMC auto-assigns IDs; don't track them yourself.
# ---------------------------------------------------------------------------

# Cladding. Pure zirconium via natural-abundance element expansion.
# (Real cladding is Zircaloy, an alloy. Pure Zr is the teaching simplification.)
zirconium = openmc.Material(name="zirconium clad")
zirconium.add_element("Zr", 1.0)         # 100% Zr, natural isotopic mix
zirconium.set_density("g/cm3", 6.5)

# Fuel: enriched UO2. add_element('U', enrichment=...) does the U-235/U-238
# atom-fraction bookkeeping for you (the worst kind of intro homework problem).
# enrichment is in weight percent U-235.
uo2 = openmc.Material(name="UO2 fuel")
uo2.add_element("U", 1.0, enrichment=3.5)  # 3.5 wt% U-235
uo2.add_element("O", 2.0)                  # two oxygens per uranium
uo2.set_density("g/cm3", 10.0)

# Moderator/coolant: light water.
# THE IMPORTANT PHYSICS LINE is add_s_alpha_beta. At thermal energies a neutron
# no longer scatters off an isolated free atom; it sees the molecular bonds and
# lattice (vibrational modes). The S(alpha,beta) table is that correction.
# OpenMC will NOT add it for you. For any thermal system, pause and ask whether
# your scatterers need one. Water does. Omit it and your answer is physically
# wrong even though the code runs fine.
water = openmc.Material(name="water moderator")
water.add_element("H", 2.0)
water.add_element("O", 1.0)
water.set_density("g/cm3", 1.0)
water.add_s_alpha_beta("c_H_in_H2O")       # hydrogen bound in water

# Optional: real helium gap instead of void. Uncomment and set gap fill=helium.
# helium = openmc.Material(name="helium gap")
# helium.add_element("He", 1.0)
# helium.set_density("g/cm3", 0.0001785)

materials = openmc.Materials([uo2, zirconium, water])

# ---------------------------------------------------------------------------
# 2. GEOMETRY  (constructive solid geometry)
# Surfaces are written as f(x,y,z)=0. Each surface splits space into a negative
# half-space (-surface, where f<0) and a positive half-space (+surface, f>0).
# You build regions by intersecting (&), unioning (|), and complementing (~)
# half-spaces, then fill a cell with a material.
# ---------------------------------------------------------------------------

# Radii (cm). Three infinite cylinders along z give the three concentric rings.
fuel_outer_radius = openmc.ZCylinder(r=0.39)   # fuel pellet surface
clad_inner_radius = openmc.ZCylinder(r=0.40)   # inside of cladding (gap is thin)
clad_outer_radius = openmc.ZCylinder(r=0.46)   # outside of cladding

# Square water box, side length = lattice pitch. Reflective so the single pin
# acts like one cell of an infinite array (effectively a 2D infinite lattice).
pitch = 1.26
left  = openmc.XPlane(x0=-pitch / 2, boundary_type="reflective")
right = openmc.XPlane(x0=+pitch / 2, boundary_type="reflective")
front = openmc.YPlane(y0=-pitch / 2, boundary_type="reflective")
back  = openmc.YPlane(y0=+pitch / 2, boundary_type="reflective")

# Axial extent. Vacuum top and bottom: a neutron that crosses is killed.
top    = openmc.ZPlane(z0=+150, boundary_type="vacuum")
bottom = openmc.ZPlane(z0=-150, boundary_type="vacuum")
layer  = +bottom & -top                         # the finite-height slab

# Cells = region + fill.
fuel_cell = openmc.Cell(name="fuel")
fuel_cell.region = -fuel_outer_radius & layer
fuel_cell.fill = uo2

gap_cell = openmc.Cell(name="gap")
gap_cell.region = +fuel_outer_radius & -clad_inner_radius & layer
gap_cell.fill = None                            # void (helium approximated away)

clad_cell = openmc.Cell(name="clad")
clad_cell.region = +clad_inner_radius & -clad_outer_radius & layer
clad_cell.fill = zirconium

water_cell = openmc.Cell(name="moderator")
water_cell.region = (
    +clad_outer_radius & +left & -right & +front & -back & layer
)
water_cell.fill = water

root_universe = openmc.Universe(cells=[fuel_cell, gap_cell, clad_cell, water_cell])
geometry = openmc.Geometry(root_universe)

# ---------------------------------------------------------------------------
# 3. SETTINGS
# Eigenvalue (criticality) run. The neutron source comes from fission, which is
# proportional to the flux we're solving for, so OpenMC starts from a guessed
# source (default: a point source at the origin, Watt fission spectrum,
# isotropic) and iterates. The first `inactive` batches let that guessed source
# settle before any tallying; they are thrown away.
# ---------------------------------------------------------------------------

settings = openmc.Settings()
settings.particles = 1000     # neutrons per batch
settings.inactive = 10        # discarded batches (source convergence)
settings.batches = 100        # total batches -> 90 active, tallied
# Default source is fine for this problem. To set it explicitly:
# point = openmc.stats.Point((0, 0, 0))
# settings.source = openmc.IndependentSource(space=point)

# ---------------------------------------------------------------------------
# 4. (optional) TALLIES
# Day 1 ran no tallies, so k_eff is the only result. Monte Carlo only records
# what you ask it to. A flux/fission tally over the fuel cell would look like:
# ---------------------------------------------------------------------------
# tally = openmc.Tally(name="fuel reactions")
# tally.filters = [openmc.CellFilter(fuel_cell)]
# tally.scores = ["flux", "fission"]
# tallies = openmc.Tallies([tally])

# ---------------------------------------------------------------------------
# 5. BUILD AND RUN
# ---------------------------------------------------------------------------

model = openmc.Model(geometry=geometry, materials=materials, settings=settings)
# model.tallies = tallies  # uncomment if you defined tallies above

if __name__ == "__main__":
    # Quick geometry sanity plot (writes a PNG, needs matplotlib).
    # root_universe.plot(width=(pitch, pitch), basis="xy", pixels=(400, 400))

    statepoint_path = model.run()
    print(f"\nDone. Results written to: {statepoint_path}")
    # k_eff is printed in the run log and stored in the statepoint file:
    #   with openmc.StatePoint(statepoint_path) as sp:
    #       print(sp.keff)

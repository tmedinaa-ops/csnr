"""
snap_unit_pin.py
======================================================================
A single SNAP-10A fuel pin as a reflected unit cell, built for use as
the Layer 1 two-way coupling TESTBED (OpenMC <-> MOOSE conduction <->
THM). It is intentionally small and self-contained, built from the
base-set numbers rather than from snap.py, so the coupling mechanics
(heat source out, temperature back) can be debugged at single-pin scale
before scaling to the real 37-pin snap model at Layer 2.

What it is: one pin (U-ZrH fuel / Sm2O3 coating / Hastelloy N clad) in a
square NaK cell with reflective sides and ends -> an infinite lattice,
k_inf. The axial power is therefore flat; that is fine for testing the
feedback loop. The realistic axial shape comes from the 37-pin model via
extract_heat_source.py (Layer 0) and from full-core coupling (Layer 2).

Run on the Mac in the openmc-env:
    conda activate openmc-env
    cd two_way && python snap_unit_pin.py        # writes geometry/materials/settings.xml
Then Cardinal drives it through openmc.i.

Sources: arXiv 2505.04024 Sec II + Table I; SNAP-10A_Model_Base_Set.md Sec 2.
H/Zr is not in the primary reports (base-set gap); 1.6 is the standard SNAP
hydride value and is flagged as an assumption.
======================================================================
"""

import openmc

# ---- geometry (cm; OpenMC native units) -------------------------------------
R_FUEL = 1.53924
R_COAT = 1.56210
R_CLAD = 1.58750
PITCH = 3.20040
L = 31.0515                       # active length
T0 = 783.15                       # K, design-average NaK temp (initial everywhere)

# ---- materials --------------------------------------------------------------
# U-ZrH SCA-4: 10 wt% U at 93% enrichment, balance ZrH(1.6).
# Within ZrH1.6: H mass frac = 1.6*1.008/(91.224+1.6*1.008) = 0.01738.
fuel = openmc.Material(name="U-ZrH fuel")
fuel.add_element("U", 0.10, "wo", enrichment=93.0)
fuel.add_element("Zr", 0.90 * 0.98262, "wo")
fuel.add_element("H", 0.90 * 0.01738, "wo")
fuel.set_density("g/cm3", 6.0)
fuel.add_s_alpha_beta("c_H_in_ZrH")     # thermal scattering: H bound in ZrH
fuel.temperature = T0

coating = openmc.Material(name="Sm2O3 coating")
coating.add_element("Sm", 2)
coating.add_element("O", 3)
coating.set_density("g/cm3", 7.4)
coating.temperature = T0

clad = openmc.Material(name="Hastelloy N clad")   # Ni-Mo-Cr, approximate
clad.add_element("Ni", 0.71, "wo")
clad.add_element("Mo", 0.16, "wo")
clad.add_element("Cr", 0.07, "wo")
clad.add_element("Fe", 0.04, "wo")
clad.add_element("Si", 0.01, "wo")
clad.add_element("Mn", 0.008, "wo")
clad.add_element("C", 0.0006, "wo")
clad.add_element("Al", 0.0014, "wo")
clad.set_density("g/cm3", 8.86)
clad.temperature = T0

# NaK-78: 78 wt% K, 22 wt% Na; density from arXiv Table II (0.75592 g/cc)
nak = openmc.Material(name="NaK-78")
nak.add_element("K", 0.78, "wo")
nak.add_element("Na", 0.22, "wo")
nak.set_density("g/cm3", 0.75592)
nak.temperature = T0

materials = openmc.Materials([fuel, coating, clad, nak])

# ---- geometry (square reflected cell, finite z window for 3D mapping) --------
fuel_or = openmc.ZCylinder(r=R_FUEL)
coat_or = openmc.ZCylinder(r=R_COAT)
clad_or = openmc.ZCylinder(r=R_CLAD)

half = PITCH / 2.0
xmin = openmc.XPlane(-half, boundary_type="reflective")
xmax = openmc.XPlane(+half, boundary_type="reflective")
ymin = openmc.YPlane(-half, boundary_type="reflective")
ymax = openmc.YPlane(+half, boundary_type="reflective")
zmin = openmc.ZPlane(0.0, boundary_type="reflective")
zmax = openmc.ZPlane(L, boundary_type="reflective")

fuel_cell = openmc.Cell(name="fuel", fill=fuel, region=-fuel_or & +zmin & -zmax)
coat_cell = openmc.Cell(name="coating", fill=coating,
                        region=+fuel_or & -coat_or & +zmin & -zmax)
clad_cell = openmc.Cell(name="clad", fill=clad,
                        region=+coat_or & -clad_or & +zmin & -zmax)
nak_cell = openmc.Cell(name="nak", fill=nak,
                       region=+clad_or & +xmin & -xmax & +ymin & -ymax & +zmin & -zmax)

root = openmc.Universe(cells=[fuel_cell, coat_cell, clad_cell, nak_cell])
geometry = openmc.Geometry(root)

# ---- settings ---------------------------------------------------------------
settings = openmc.Settings()
settings.run_mode = "eigenvalue"
settings.particles = 20000
settings.batches = 120
settings.inactive = 30
settings.source = openmc.IndependentSource(
    space=openmc.stats.Box((-half, -half, 0.0), (half, half, L), only_fissionable=True)
)
# temperature feedback for Cardinal: interpolate ENDF/B-VIII.0 temperature grid
settings.temperature = {"method": "interpolation", "range": (300.0, 1500.0),
                        "default": T0}

model = openmc.Model(geometry, materials, settings)
model.export_to_xml()
print("Wrote geometry.xml, materials.xml, settings.xml for the SNAP-10A unit pin.")
print("Cells: fuel / coating / clad / nak  (cell_level = 0 for Cardinal).")
print("Reflective on all six faces -> k_inf testbed; axial power is flat by design.")

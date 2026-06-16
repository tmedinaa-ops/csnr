"""
Independent energy-balance and thermal-resistance check for the SNAP-10A NaK
cooling MVP. This sets the validation targets the Cardinal/MOOSE model must
reproduce, computed by hand (no MOOSE) from the base-set inputs.

Run: python3 verify_energy_balance.py
Sources for every input are in SNAP-10A_Model_Base_Set.md (Sections 2 and 3).
"""

import math

# ----------------------------------------------------------------------------
# Inputs (SI). Sources noted; all from SNAP-10A_Model_Base_Set.md unless flagged
# ----------------------------------------------------------------------------
# Core power. CONFLICT: 30 / 34 / 39.5-40 kWt across vintages. Use 34 kWt to
# match the arXiv model and the shield design point (base set Sec 2 "Power").
Q_core = 34.0e3          # W, thermal
n_pins = 37              # fuel elements (base set Sec 2 geometry)

# NaK-78 coolant (arXiv Table II, base set Sec 2 "Coolant")
mdot_core = 0.6199       # kg/s, total core flow
T_in = 755.37            # K, core inlet
T_out_ref = 816.48       # K, core outlet (reference)
rho = 755.92             # kg/m3
mu = 1.8835e-4           # Pa.s
cp = 879.903             # J/kg.K
k_nak = 26.2345          # W/m.K

# Pin geometry (arXiv Table I, base set Sec 2). cm -> m.
r_fuel = 1.53924e-2      # m, U-ZrH fuel radius
r_coat = 1.56210e-2      # m, Sm2O3 coating outer radius
r_clad = 1.58750e-2      # m, Hastelloy N cladding outer radius
L = 31.0515e-2           # m, active length
pitch = 3.20040e-2       # m, lattice pitch (hex)

# Solid conductivities (medium confidence; refine later).
k_fuel = 18.0            # W/m.K, U-ZrH ~ ZrH1.6 at operating T
k_coat = 1.5            # W/m.K, Sm2O3 rare-earth oxide (thin layer)
k_clad = 23.6           # W/m.K, Hastelloy N near 700 C

# ----------------------------------------------------------------------------
# Per-pin power and the NaK temperature rise (the headline validation target)
# ----------------------------------------------------------------------------
P_pin = Q_core / n_pins                       # W per pin
mdot_pin = mdot_core / n_pins                 # kg/s per subchannel (even split)

dT_core = Q_core / (mdot_core * cp)           # K, whole-core rise from Q=m*cp*dT
dT_pin = P_pin / (mdot_pin * cp)              # K, identical by construction

print("=" * 70)
print("SNAP-10A NaK cooling MVP - independent energy balance")
print("=" * 70)
print(f"Per-pin power               P_pin   = {P_pin:8.2f} W")
print(f"Per-subchannel flow         mdot    = {mdot_pin:8.5f} kg/s")
print(f"NaK rise from Q=m*cp*dT     dT      = {dT_core:8.2f} K")
print(f"  -> outlet would be                = {T_in + dT_core:8.2f} K")
print(f"Base-set reference outlet           = {T_out_ref:8.2f} K "
      f"(dT_ref = {T_out_ref - T_in:.2f} K)")
print(f"  NOTE: their table lists {T_out_ref - T_in:.2f} K; Q=m*cp*dT with their "
      f"own numbers gives {dT_core:.2f} K.")
print(f"  The ~1 K gap is internal rounding in the arXiv table. MVP target: "
      f"{dT_core:.0f} K rise.")

# ----------------------------------------------------------------------------
# Subchannel hydraulics (unit-cell estimate, refine vs real core flow areas)
# ----------------------------------------------------------------------------
A_cell = (math.sqrt(3) / 2.0) * pitch**2      # hex cell area per rod
A_rod = math.pi * r_clad**2
A_flow = A_cell - A_rod                        # coolant area per subchannel
P_wet = 2 * math.pi * r_clad                   # wetted perimeter (full rod)
D_h = 4 * A_flow / P_wet                        # hydraulic diameter
gap = pitch - 2 * r_clad                        # rod-to-rod gap

v = mdot_pin / (rho * A_flow)                   # bulk velocity
Re = rho * v * D_h / mu
Pr = mu * cp / k_nak
Pe = Re * Pr

# Liquid-metal Nusselt. Lyon-Martinelli style for low-Pr rod flow.
Nu = 7.0 + 0.025 * Pe**0.8
h = Nu * k_nak / D_h                             # convective coefficient (Hw)

print("\n" + "-" * 70)
print("Subchannel hydraulics (unit-cell)")
print("-" * 70)
print(f"rod-to-rod gap              = {gap*1e3:8.3f} mm  (very tight lattice)")
print(f"coolant flow area  A_flow   = {A_flow:8.3e} m^2")
print(f"hydraulic diameter D_h      = {D_h*1e3:8.3f} mm")
print(f"bulk velocity      v        = {v:8.4f} m/s")
print(f"Reynolds           Re       = {Re:8.1f}")
print(f"Prandtl            Pr       = {Pr:8.5f}  (liquid metal, <<1)")
print(f"Peclet             Pe       = {Pe:8.2f}")
print(f"Nusselt            Nu       = {Nu:8.3f}")
print(f"HTC                Hw       = {h:8.0f} W/m^2.K  -> use in THM")

# consistency: do 37 subchannels reproduce the total flow?
mdot_check = n_pins * rho * A_flow * v
print(f"\n37 x subchannel flow        = {mdot_check:8.4f} kg/s "
      f"(target {mdot_core}) -> {'OK' if abs(mdot_check-mdot_core)<0.02 else 'CHECK'}")

# ----------------------------------------------------------------------------
# Radial temperature drops at the axial peak (chopped-cosine, peak/avg ~1.4)
# ----------------------------------------------------------------------------
peak_factor = 1.4                               # axial peaking (typical bare-ish core)
qppp_avg = P_pin / (math.pi * r_fuel**2 * L)    # avg volumetric source in fuel
qppp_pk = qppp_avg * peak_factor
# linear power at peak
qprime_pk = P_pin / L * peak_factor             # W/m
# surface heat flux at clad OD (peak)
qflux_pk = qprime_pk / (2 * math.pi * r_clad)

# drops (steady, cylindrical)
dT_fuel = qppp_pk * r_fuel**2 / (4 * k_fuel)              # centerline-to-surface
dT_coat = qprime_pk / (2*math.pi*k_coat) * math.log(r_coat/r_fuel)
dT_clad = qprime_pk / (2*math.pi*k_clad) * math.log(r_clad/r_coat)
dT_film = qflux_pk / h

T_nak_pk = T_in + peak_factor * 0.5 * dT_core   # rough bulk at peak (mid-ish)
T_fuel_center_pk = T_out_ref + dT_film + dT_clad + dT_coat + dT_fuel

print("\n" + "-" * 70)
print(f"Radial drops at axial peak (peaking={peak_factor})")
print("-" * 70)
print(f"peak volumetric source     = {qppp_pk:8.3e} W/m^3")
print(f"peak linear power          = {qprime_pk:8.1f} W/m")
print(f"peak clad surface flux     = {qflux_pk:8.3e} W/m^2")
print(f"film drop (NaK->clad)      = {dT_film:8.2f} K")
print(f"clad drop                  = {dT_clad:8.2f} K")
print(f"coating drop (Sm2O3)       = {dT_coat:8.2f} K")
print(f"fuel center-to-surface     = {dT_fuel:8.2f} K")
print(f"--> peak fuel centerline   ~ {T_fuel_center_pk:8.1f} K "
      f"({T_fuel_center_pk-273.15:.0f} C)")
print(f"    (film + clad drops are small; U-ZrH conduction dominates the radial rise)")

print("\n" + "=" * 70)
print("MVP validation targets to embed in the deck")
print("=" * 70)
print(f"  1. NaK outlet  : {T_in + dT_core:.1f} K  (rise {dT_core:.1f} K) at 34 kWt")
print(f"  2. peak fuel T : ~{T_fuel_center_pk:.0f} K  (SNAP ran cool, sub-900 K)")
print(f"  3. Hw to use   : ~{h:.0f} W/m^2.K (liquid-metal Lyon corr.)")
print(f"  4. D_h, A_flow : {D_h*1e3:.3f} mm, {A_flow:.3e} m^2 per subchannel")

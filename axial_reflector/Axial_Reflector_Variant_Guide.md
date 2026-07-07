# Building the axial-reflector variant of the snap model

This is the geometry change and the run recipe. It lives here rather than as drop-in code because the core is assembled in the snap repo's `snap.py` (the arXiv 2505.04024 model), which is not in this folder. The change is small and belongs in that file, next to where the radial reflector and the axial fuel boundaries are defined. Treat the current numbers as placeholders to replace with the model's actual dimensions.

## What to add

The active fuel occupies roughly the region z in [-L/2, +L/2] with L about 31 cm, inside a radial reflector of about 5 cm of beryllium out to some outer radius R_out. Right now the top and bottom of that fuel column are (per the premise being tested) capped by structure and coolant plena, not beryllium. The change is to insert a beryllium disc at each end.

For each end:

- A beryllium cylinder, radius equal to the core/reflector outer radius R_out (so it caps the whole cross section the neutrons see), thickness t_ax. Start with t_ax = 5 cm to match the radial reflector, then sweep 2, 5, 8, 10 cm to find where the worth saturates.
- Place it immediately outside the active fuel: top disc spanning z in [+L/2, +L/2 + t_ax], bottom disc z in [-L/2 - t_ax, -L/2].
- Move the axial vacuum boundary out to enclose the new discs (z = +/- (L/2 + t_ax + small gap)). This is the step that is easy to forget; if the old vacuum plane still sits at the fuel end, the reflector is outside the problem and does nothing.
- Use the same beryllium material object the radial reflector uses (same density, same S(a,b) thermal scattering data for Be), so the comparison is clean.

## Code pattern (adapt to snap.py's actual surfaces and universe)

```python
# assumes the model already defines: be (beryllium material),
# r_out (outer radial surface radius), zt/zb (top/bottom of active fuel),
# and that the core universe is placed in a bounding cell.
import openmc

t_ax = 5.0                      # cm, axial reflector thickness (sweep this)
gap  = 0.0                      # cm, any structural gap fuel-to-reflector

# radial extent the caps span (cap the whole cross-section)
r_cap = openmc.ZCylinder(r=r_out)

# axial planes: fuel top zt, fuel bottom zb (zt > zb)
top_lo = openmc.ZPlane(z0=zt + gap)
top_hi = openmc.ZPlane(z0=zt + gap + t_ax)
bot_hi = openmc.ZPlane(z0=zb - gap)
bot_lo = openmc.ZPlane(z0=zb - gap - t_ax)

# new outer vacuum boundary, moved out past the caps
z_vac_top = openmc.ZPlane(z0=zt + gap + t_ax + 0.1, boundary_type="vacuum")
z_vac_bot = openmc.ZPlane(z0=zb - gap - t_ax - 0.1, boundary_type="vacuum")

top_cap = openmc.Cell(fill=be, region=-r_cap & +top_lo & -top_hi)
bot_cap = openmc.Cell(fill=be, region=-r_cap & +bot_lo & -bot_hi)

# add top_cap and bot_cap to the root universe, and rebuild the outer
# bounding cell so its axial faces are z_vac_bot .. z_vac_top instead of the
# old fuel-end planes. Everything radial stays as-is.
```

The one thing to get right is that the reflector cells sit between the fuel and the new vacuum plane, with no leftover void or old boundary in between. Plot it (plots.xml, color_by material) and confirm you see beryllium above and below the fuel before trusting any k.

## Measurements to take

1. Static worth. Run k-eff for the baseline and for each t_ax. The worth is Δρ = (k_ax − k_base)/(k_ax·k_base)·1e5 pcm. This is the margin the caps buy at BOL.

2. Drum-demand reduction. With the extra reflection, re-search the drums to critical (the DRUM_FILL / drum-angle knobs in snap.py). The reduction in the drum angle needed to hold k = 1 is the operational headroom the caps free up.

3. Leakage recheck. Re-run `leakage_split.py` on the variant. Axial leakage should drop; confirm the reflector is doing what the tally predicted.

4. Horizon. Deplete the variant through ../depletion_7yr/run_depletion_7yr.py (DIFF off is fine for the horizon question). Compare the reactivity trajectory and the EOL against the bare-end baseline. The horizon gain is the payoff.

## What a good result looks like, and what would kill it

If axial leakage was, say, 10 to 15 percent of the neutron balance and the caps recover most of it, expect something on the order of 1000 to 3000 pcm of static worth, which at ~337 pcm/yr is multiple years of added horizon. That would make end caps a strong, low-mass lever.

It dies if any of these is true: the ends turn out to already be reflected (worth near zero), leakage is radial-dominated (caps barely move k, thicken the radial reflector instead), or the mechanical intrusion into the NaK plena and grid plates makes 5 cm of beryllium at each end impractical. Price the mass too: beryllium is about 1.85 g/cc, so a 5 cm cap at the core radius is a few kilograms per end, which competes directly with the radiator and convertor mass in the 14 kWe stack.

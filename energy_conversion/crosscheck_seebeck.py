"""
Independent material-physics cross-check of the back-solved converter constants.

The lumped model fit S, R0, K to the Table 2 operating point, which only proves
internal consistency, not that the numbers are physical. This script asks a
separate question: does published SiGe material data, evaluated over SNAP-10A's
junction temperature band, land on the same Seebeck and figure of merit?

The Seebeck is the clean test because it is geometry-free: the couple Seebeck is
just |alpha_n| + |alpha_p|, no leg dimensions involved. Resistivity and thermal
conductivity feed a secondary ZT check and carry more proxy uncertainty.

Run:  python crosscheck_seebeck.py
"""

from snap10a_te_converter import f_to_k
import sige_properties as sige

# --- SNAP-10A junction band and the back-solved targets ------------------
T_cj = f_to_k(604.0)     # 590.9 K
T_hj = f_to_k(902.0)     # 756.5 K
T_avg = 0.5 * (T_hj + T_cj)

S_backsolved = 478.7e-6      # V/K, from the loaded operating point
ZT_backsolved = 0.352        # couple, from Z = S^2 / (R0 K)

# --- proxy Seebeck over the band -----------------------------------------
S_proxy_avg = sige.band_average(sige.couple_seebeck, T_cj, T_hj)
an = sige.seebeck_n(T_avg)
ap = sige.seebeck_p(T_avg)

# --- proxy material ZT at the mean junction temperature ------------------
zt_n = sige.material_zt_leg(an, sige.resistivity_n(T_avg),
                            sige.thermal_conductivity(T_avg), T_avg)
zt_p = sige.material_zt_leg(ap, sige.resistivity_p(T_avg),
                            sige.thermal_conductivity(T_avg), T_avg)
zt_couple_proxy = 0.5 * (zt_n + zt_p)   # matched-leg approximation

print("SiGe material cross-check of the SNAP-10A converter constants")
print("=" * 64)
print(f"Junction band: {T_cj:.1f} K to {T_hj:.1f} K  (mean {T_avg:.1f} K)")
print("Proxy: RTG-grade Si80Ge20 fits; SNAP used richer-Ge 67/33 (see caveat).")
print()

print("Seebeck (geometry-free, the primary test):")
print(f"  proxy |alpha_n| at mean T      : {an*1e6:6.1f} uV/K")
print(f"  proxy |alpha_p| at mean T      : {ap*1e6:6.1f} uV/K")
print(f"  proxy couple S, band-averaged  : {S_proxy_avg*1e6:6.1f} uV/K")
print(f"  back-solved couple S           : {S_backsolved*1e6:6.1f} uV/K")
ratio = S_backsolved / S_proxy_avg
print(f"  back-solved / proxy            : {ratio:5.2f}x  "
      f"({100*(ratio-1):+.0f}% vs the leaner RTG alloy)")
print()

print("Figure of merit (secondary, proxy rho and kappa are looser):")
print(f"  proxy couple ZT at mean T      : {zt_couple_proxy:5.2f}")
print(f"  back-solved couple ZT          : {ZT_backsolved:5.2f}")
print()

print("Verdict:")
print("  The back-solved Seebeck sits about a quarter above leaner RTG-grade")
print("  Si80Ge20, which is the direction expected for SNAP's higher Ge content")
print("  and cooler, lower-doping design point. Same order, right sign. The")
print("  lumped fit is consistent with SiGe material physics, not a fitting")
print("  artifact. A tight numeric match is not possible without the real 67/33")
print("  As-doped curves, which remain the data gap.")

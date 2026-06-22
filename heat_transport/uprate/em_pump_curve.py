#!/usr/bin/env python3
"""
em_pump_curve.py -- SNAP-10A electromagnetic pump head-flow characteristic, now built
from the ACTUAL report figure (component A3 of the uprate roadmap).

SOURCE, retrieved June 2026: NAA-SR-11879, "SNAP-10A Thermoelectric Pump. Final Report",
K. A. Davis, Atomics International, 15 July 1966 (OSTI 4516323). The full 86-page scan was
read in the OSTI viewer. Figure 14 (p. 24), "Pressure vs Flow at Indicated NaK Temperatures
for Pump SN-010", gives the pump's H-Q curves at three NaK temperatures plus the SNAP-10A
system (loop) resistance curve and the design point. This replaces the earlier half-stall
placeholder with digitized data.

WHAT FIGURE 14 SHOWS (digitized below):
- Three developed-pressure vs flow lines, roughly linear, descending, at 800 / 900 / 1000 F
  NaK. Axes are pressure [psi] and flow [US gpm].
- Pump performance RISES strongly with NaK temperature: the stall (zero-flow) head goes
  about 2.0 -> 2.4 -> 2.8 psi from 800 -> 900 -> 1000 F, roughly +0.4 psi per 100 F. This is
  the thermoelectric coupling: the pump is driven by TE elements whose output grows with the
  NaK (hot-junction) temperature, so a hotter core both needs and GETS more pumping. This is
  the key result for the uprate: raising reactor power raises the NaK temperature, which
  lifts the pump curve and lets it deliver more flow.
- Design point: 13 gpm at 1.1 psi for 1010 F NaK, i.e. 3 m3/hr at 7.58 kPa. This matches the
  loop side exactly (arXiv Table II flow 0.6199 kg/s / 755.92 = 2.95 m3/hr = 13.0 gpm) and
  the El-Genk 2023 citation (1.10 psi). The design point is a REQUIREMENT on the system
  curve; the 1000 F pump curve sits above it, so the pump runs with margin.

UNITS: the digitized data is psi and gpm (as plotted); the public API is SI (Pa, m3/s, K).
"""
import numpy as np

# --- unit conversions --------------------------------------------------------------
PSI = 6894.757            # Pa per psi
GPM = 6.309020e-5         # m3/s per US gpm

# --- design point (loop side, cross-checked to Figure 14) --------------------------
MDOT_DESIGN = 0.6199                      # kg/s total NaK (arXiv Table II)
Q_DESIGN    = MDOT_DESIGN / 755.92        # 8.201e-4 m3/s = 13.0 gpm
DP_DESIGN   = 1.10 * PSI                  # 7.58 kPa developed head at design flow
K_LOOP_DESIGN = DP_DESIGN / Q_DESIGN ** 2 # system resistance dP = K Q^2 (Pa/(m3/s)^2)

# --- digitized Figure 14 pump curves: stall head and slope per NaK temperature ------
# linear fits dP[psi] = stall - slope*Q[gpm] to the plotted data points.
# 1000 F is the qualification ceiling of the MEASURED H-Q curves; above it the model
# extrapolates, validated against the flight point below.
FIG14_T_F   = np.array([800.0, 900.0, 1000.0])   # NaK temperature [F]
FIG14_STALL = np.array([2.00, 2.39, 2.80])       # zero-flow head [psi]
FIG14_SLOPE = np.array([0.0779, 0.0911, 0.0967]) # head fall [psi per gpm]

# --- flight operating data, NAA-SR-11879 pp. 51-52 (FS-4, SNAP-10A in space) ---------
# A measured operating point ABOVE the Figure 14 curve ceiling, used to validate the
# extrapolation: at passive control the NaK was 1056 F and the pump delivered 14.4 gpm.
FLIGHT_T_F, FLIGHT_GPM = 1056.0, 14.4

# Life degradation: Figure 33 shows the delivered flow falling from ~14.3 gpm (start) to
# ~12.5 gpm at ~9000 hr at a constant 1010 F NaK, i.e. ~13% flow loss over the mission,
# from thermoelectric power degradation. EOL_HEAD_FACTOR scales the developed head so the
# operating flow reproduces that ~12.5 gpm end-of-life point (the Q^2 loop makes flow
# insensitive to head, so a modest flow loss implies a larger head loss). Spec minimum
# flows were 13.2 / 11.2 / 10.4 gpm at start / 90 days / 1 year.
EOL_HEAD_FACTOR = 0.65


def _T_K_to_F(T_K):
    return (np.asarray(T_K, float) - 273.15) * 9.0 / 5.0 + 32.0


def _stall_slope(T_K):
    """Interpolate (and, beyond 800-1000 F, linearly extrapolate) the stall head and
    slope at NaK temperature T_K. Returns (stall_psi, slope_psi_per_gpm). Extrapolation
    above 1000 F is flagged by the caller; the data only covers 800-1000 F."""
    T_F = float(_T_K_to_F(T_K))
    stall = np.interp(T_F, FIG14_T_F, FIG14_STALL)
    slope = np.interp(T_F, FIG14_T_F, FIG14_SLOPE)
    if T_F > 1000.0:                       # linear extrapolation beyond the data
        stall = FIG14_STALL[-1] + (FIG14_STALL[-1] - FIG14_STALL[-2]) / 100.0 * (T_F - 1000.0)
        slope = FIG14_SLOPE[-1] + (FIG14_SLOPE[-1] - FIG14_SLOPE[-2]) / 100.0 * (T_F - 1000.0)
    elif T_F < 800.0:
        stall = FIG14_STALL[0] + (FIG14_STALL[1] - FIG14_STALL[0]) / 100.0 * (T_F - 800.0)
        slope = FIG14_SLOPE[0] + (FIG14_SLOPE[1] - FIG14_SLOPE[0]) / 100.0 * (T_F - 800.0)
    return float(stall), float(slope)


def q_from_mdot(mdot, rho):
    return mdot / rho


def pump_head(Q, T_K, head_factor=1.0):
    """Developed pump head [Pa] at volumetric flow Q [m3/s] and NaK temperature T_K [K],
    from the digitized Figure 14 curve for that temperature (clipped at zero). head_factor
    < 1 models end-of-life thermoelectric degradation (use EOL_HEAD_FACTOR)."""
    stall, slope = _stall_slope(T_K)
    Q_gpm = np.asarray(Q, float) / GPM
    return np.maximum((stall - slope * Q_gpm), 0.0) * head_factor * PSI


def loop_head(Q, K=K_LOOP_DESIGN):
    """System (loop) pressure drop [Pa] = K Q^2."""
    return K * np.asarray(Q, float) ** 2


def operating_point(T_K, K=K_LOOP_DESIGN, head_factor=1.0):
    """Flow [m3/s] where the pump curve at T_K meets the loop curve K Q^2. Solve in
    psi/gpm (the curve's native units) then convert."""
    stall, slope = _stall_slope(T_K)
    stall *= head_factor
    slope *= head_factor
    K_psi_per_gpm2 = K * GPM ** 2 / PSI                 # K in psi/(gpm)^2
    # K_psi*Qg^2 + slope*Qg - stall = 0
    a, b, c = K_psi_per_gpm2, slope, -stall
    Qg = (-b + np.sqrt(b * b - 4 * a * c)) / (2 * a)
    Q = Qg * GPM
    return dict(Q=Q, Q_gpm=Qg, dP=float(loop_head(Q, K)),
                head=float(pump_head(Q, T_K, head_factor)), stall_psi=stall)


def headroom(Q_required, T_K, K=K_LOOP_DESIGN, head_factor=1.0):
    """At a required flow against the loop curve, the pump head available at NaK
    temperature T_K vs the loop demand. margin < 0 means the pump cannot reach that flow."""
    avail = float(pump_head(Q_required, T_K, head_factor))
    demand = float(loop_head(Q_required, K))
    return dict(Q_required=Q_required, head_available=avail, head_demand=demand,
                margin=avail - demand, pump_limited=avail < demand)


def validate():
    print("SNAP-10A EM pump H-Q model from NAA-SR-11879 Figure 14 -- validation\n")
    print(f"design point: Q = {Q_DESIGN:.4e} m3/s ({Q_DESIGN/GPM:.1f} gpm), "
          f"dP = {DP_DESIGN/1e3:.2f} kPa ({DP_DESIGN/PSI:.2f} psi)\n")

    print("digitized pump curves (stall head and short-circuit flow per NaK temp):")
    print(f"{'NaK F':>7} {'NaK K':>7} {'stall psi':>10} {'stall kPa':>10} {'Qmax gpm':>9}")
    for T_F, st, sl in zip(FIG14_T_F, FIG14_STALL, FIG14_SLOPE):
        T_K = (T_F - 32) * 5 / 9 + 273.15
        print(f"{T_F:>7.0f} {T_K:>7.1f} {st:>10.2f} {st*PSI/1e3:>10.2f} {st/sl:>9.1f}")

    print("\noperating point (pump curve meets the loop K Q^2) vs NaK temperature:")
    print(f"{'NaK K':>7} {'flow gpm':>9} {'flow kg/s':>10} {'head kPa':>9}")
    for T_K in (755.4, 783.15, 810.9, 850.0, 922.0):     # 900 F, design avg, 1000 F, hotter
        op = operating_point(T_K)
        mdot = op["Q"] * 755.92
        flag = "  (extrapolated > 1000 F)" if _T_K_to_F(T_K) > 1000 else ""
        print(f"{T_K:>7.1f} {op['Q_gpm']:>9.1f} {mdot:>10.3f} {op['dP']/1e3:>9.2f}{flag}")

    # validate the above-1000 F extrapolation against the FS-4 flight operating point
    T_flight_K = (FLIGHT_T_F - 32) * 5 / 9 + 273.15
    op_f = operating_point(T_flight_K)
    print(f"\nextrapolation check vs FS-4 flight point ({FLIGHT_T_F:.0f} F NaK):")
    print(f"  model operating flow {op_f['Q_gpm']:.1f} gpm vs measured {FLIGHT_GPM:.1f} gpm "
          f"({100*(op_f['Q_gpm']-FLIGHT_GPM)/FLIGHT_GPM:+.0f}%, model mildly optimistic)")

    # end-of-life degradation (Figure 33: ~14.3 -> ~12.5 gpm over the mission)
    op_bol = operating_point(810.9)
    op_eol = operating_point(810.9, head_factor=EOL_HEAD_FACTOR)
    print(f"\nlife degradation at 1000 F (EOL_HEAD_FACTOR={EOL_HEAD_FACTOR}):")
    print(f"  begin-of-life {op_bol['Q_gpm']:.1f} gpm -> end-of-life {op_eol['Q_gpm']:.1f} gpm "
          f"(target ~12.5 gpm from Figure 33)")

    print("\n  reading: at the design ~810 K (1000 F) the pump settles near 14-15 gpm")
    print("  (~0.70 kg/s), close to the 0.62 kg/s design flow. As the core runs hotter the")
    print("  operating flow climbs, because the TE-driven pump curve lifts with temperature.")
    print("  Two caveats the report adds: 1000 F is the qualification ceiling of the measured")
    print("  curves (the uprate runs hotter, so the high end is extrapolated, validated to")
    print("  1056 F within ~5%); and the TE drive degrades over the mission, dropping the")
    print("  delivered flow ~13% by one year, which lowers the SUSTAINED uprate ceiling.")


if __name__ == "__main__":
    validate()

"""
SNAP-10A thermoelectric converter model (lumped-couple, design point).

Built from the converter-level equations in NAA-SR-11955, "Power Conversion
System Design and Test" (Atomics International, June 1966), as transcribed in
SNAP-10A_Model_Equations.md section 5.2a. This is step one of the project's
validation policy for energy conversion: reproduce the NAA-SR-11955 Table 2
design point with effective lumped constants, before moving to
temperature-dependent SiGe properties.

The converter is N N-P couples wired in n parallel electrical paths. Each
couple carries three lumped constants:
    S   sum Seebeck of the N and P legs (Thomson folded in)   [V/K]
    R0  electrical resistance of the couple                   [ohm]
    K   thermal conductance of the couple                     [W/K]

Units are SI throughout: temperatures in kelvin, voltage in volts, current in
amps, power in watts, resistance in ohms, conductance in W/K.

Sign convention for the junction heats follows 5.2a, with the element current
i = I/n and the Peltier term taken at the absolute junction temperature:

    Q_hot  = N K dT + N i S T_hj - 1/2 N i^2 R0
    Q_cold = N K dT + N i S T_cj + 1/2 N i^2 R0
    P      = Q_hot - Q_cold = N i S dT - N i^2 R0
"""

from dataclasses import dataclass


def f_to_k(t_f: float) -> float:
    """Fahrenheit to kelvin."""
    return (t_f - 32.0) * 5.0 / 9.0 + 273.15


@dataclass
class Converter:
    """A thermoelectric converter described by per-couple lumped constants."""

    N: int      # number of N-P couples
    n: int      # number of parallel electrical paths
    S: float    # sum Seebeck per couple, V/K
    R0: float   # electrical resistance per couple, ohm
    K: float    # thermal conductance per couple, W/K

    @property
    def R(self) -> float:
        """Converter internal resistance, ohm.  R = N R0 / n^2."""
        return self.N * self.R0 / self.n ** 2

    def open_circuit_voltage(self, T_hj: float, T_cj: float) -> float:
        """E_oc = (N/n) S (T_hj - T_cj), at the given junction temperatures."""
        return (self.N / self.n) * self.S * (T_hj - T_cj)

    def matched_load_power(self, T_hj: float, T_cj: float) -> float:
        """Maximum (matched-load) power, P_m = N S^2 dT^2 / (4 R0)."""
        dT = T_hj - T_cj
        return self.N * self.S ** 2 * dT ** 2 / (4.0 * self.R0)

    def figure_of_merit(self, T_hj: float, T_cj: float):
        """Return (Z, Z*Tbar) for the couple.  Z = S^2 / (R0 K)."""
        Z = self.S ** 2 / (self.R0 * self.K)
        Tbar = 0.5 * (T_hj + T_cj)
        return Z, Z * Tbar

    def operate(self, T_hj: float, T_cj: float, M: float = None,
                R_load: float = None) -> dict:
        """
        Solve the operating point at junction temperatures (T_hj, T_cj).

        Load is set by either the load ratio M = R_load / R, or by R_load
        directly. Returns a dict of converter quantities.
        """
        if R_load is not None:
            M = R_load / self.R
        if M is None:
            raise ValueError("specify the load by M or R_load")

        dT = T_hj - T_cj
        R = self.R
        E_oc = self.open_circuit_voltage(T_hj, T_cj)
        I = E_oc / ((M + 1.0) * R)      # converter current
        E = (M / (M + 1.0)) * E_oc      # terminal (closed-circuit) voltage
        i = I / self.n                  # element / per-path current
        P = E * I                       # load power

        Q_hot = self.N * self.K * dT + self.N * i * self.S * T_hj \
            - 0.5 * self.N * i ** 2 * self.R0
        Q_cold = self.N * self.K * dT + self.N * i * self.S * T_cj \
            + 0.5 * self.N * i ** 2 * self.R0

        return {
            "T_hj": T_hj, "T_cj": T_cj, "dT": dT,
            "M": M, "R_internal": R, "R_load": M * R,
            "E_oc": E_oc, "I": I, "i": i, "E_terminal": E,
            "P": P, "Q_hot": Q_hot, "Q_cold": Q_cold,
            "eta_overall": P / Q_hot,
        }


def carnot_efficiency(T_hot: float, T_cold: float) -> float:
    """1 - T_cold / T_hot.  In SNAP-10A's Table 2 the reference temperatures
    are the average NaK and average radiator temperatures, not the junctions."""
    return 1.0 - T_cold / T_hot


def fit_design_point(N: int, n: int, T_hj: float, T_cj: float,
                     V_terminal: float, I: float, R_internal: float,
                     Q_hot: float) -> "Converter":
    """
    Back-solve the per-couple constants (S, R0, K) from the Table 2 operating
    point, treating the loaded electrical point as ground truth.

    R0 comes from the stated internal resistance. S comes from the loaded
    open-circuit voltage E_oc = V_terminal + I R_internal, NOT from the stated
    61.7 V open-circuit reading, which belongs to the wider open-circuit dT.
    K closes the hot-junction heat balance against the stated heat input.
    """
    dT = T_hj - T_cj
    R0 = R_internal * n ** 2 / N
    E_oc_loaded = V_terminal + I * R_internal
    S = E_oc_loaded * n / (N * dT)
    i = I / n
    K = (Q_hot - N * i * S * T_hj + 0.5 * N * i ** 2 * R0) / (N * dT)
    return Converter(N=N, n=n, S=S, R0=R0, K=K)

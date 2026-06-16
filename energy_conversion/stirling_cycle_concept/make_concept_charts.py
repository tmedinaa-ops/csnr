"""
Charts for the Stirling concept branch. Two panels:
  left  - where the efficiency comes from as the hot side heats up
  right - electrical output vs hot-side temperature for several reactor powers,
          with the 14 kWe requirement line

Writes stirling_concept_charts.png into this folder.
Run:  python make_concept_charts.py
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from stirling_converter import carnot_efficiency, relative_efficiency

T_COLD = 590.0          # radiator, SNAP baseline
HEAT_FRAC = 31.9 / 34.0
TARGET = 14.0
TEAL = "#1b9e9e"; RED = "#cc3333"; GREY = "#9aa3ab"

T = np.linspace(700, 1300, 400)
carnot = np.array([carnot_efficiency(t, T_COLD) for t in T])
rel = np.array([relative_efficiency(t, T_COLD) for t in T])
overall = carnot * rel

fig, (a1, a2) = plt.subplots(1, 2, figsize=(13, 5.5))
fig.suptitle("Stirling concept: raising the reactor hot side (radiator fixed at 590 K)",
             fontsize=13, fontweight="bold")

# ---- panel 1: efficiency mechanism --------------------------------------
a1.plot(T, carnot * 100, color=GREY, ls="--", lw=2, label="Carnot ceiling")
a1.plot(T, rel * 100, color="#e6781e", lw=2, label="relative eff (% of Carnot)")
a1.plot(T, overall * 100, color=TEAL, lw=2.5, label="overall efficiency")
a1.axvline(775, color="#444", ls=":", lw=1.3)
a1.text(780, 5, "SNAP 775 K", fontsize=8.5, color="#444")
a1.set_xlabel("hot-side temperature (K)"); a1.set_ylabel("percent")
a1.set_title("Both Carnot and the captured fraction rise with temperature", fontsize=10.5)
a1.legend(fontsize=9); a1.grid(alpha=0.25); a1.set_ylim(0, 70)

# ---- panel 2: kWe vs temperature for several reactor powers -------------
for Q, c in [(34, "#9ecae1"), (56, "#4292c6"), (80, "#08519c"), (120, "#08306b")]:
    P = Q * 1000 * HEAT_FRAC * overall / 1000.0
    a2.plot(T, P, color=c, lw=2, label=f"{Q} kWt reactor")
    cross = np.where(P >= TARGET)[0]
    if len(cross):
        a2.plot(T[cross[0]], TARGET, "o", color=c, ms=7, zorder=5)
a2.axhline(TARGET, color=RED, lw=2)
a2.text(705, TARGET + 0.4, "14 kWe requirement", color=RED, fontsize=11, fontweight="bold")
a2.axvline(775, color="#444", ls=":", lw=1.3)
a2.text(780, 0.4, "SNAP 775 K", fontsize=8.5, color="#444")
a2.set_xlabel("hot-side temperature (K)"); a2.set_ylabel("electrical output (kWe)")
a2.set_title("Need both a hotter hot side and a bigger reactor", fontsize=10.5)
a2.legend(fontsize=9, title="reactor thermal power"); a2.grid(alpha=0.25)
a2.set_ylim(0, 22); a2.set_xlim(700, 1300)

fig.tight_layout(rect=[0, 0, 1, 0.95])
fig.savefig("stirling_concept_charts.png", dpi=150)
print("wrote stirling_concept_charts.png")

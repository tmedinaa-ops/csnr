"""
Charts for the SNAP-10A thermoelectric vs Stirling comparison and the path to a
14 kWe requirement. Writes two PNGs into this folder.

Run:  python make_comparison_charts.py
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

# ---- design-point numbers (from compare_te_stirling.py) -----------------
Q_SNAP = 31.9            # kWt into the converter
CARNOT = 0.2387          # SNAP hot/cold
CARNOT_KRUSTY = 0.534    # ~1073 K hot / 500 K cold

te = dict(eta=1.82, P=0.581, sp=8.3, rad=5.8)
st_lo = dict(eta=7.1, P=2.278, sp=43, rad=5.4)
st_hi = dict(eta=11.0, P=3.493, sp=59, rad=5.1)

TEAL = "#1b9e9e"; ORANGE = "#e6781e"; GREY = "#9aa3ab"; RED = "#cc3333"

# =========================================================================
# Figure 1: design-point comparison, four panels
# =========================================================================
fig, ax = plt.subplots(2, 2, figsize=(11, 8))
fig.suptitle("SNAP-10A converter vs Stirling, same 31.9 kWt reactor and temperatures",
             fontsize=14, fontweight="bold")


def paired(a, title, ylabel, te_v, lo, hi, ceiling=None, ceiling_label=None):
    vmin, vmax = min(lo, hi), max(lo, hi)
    mid = 0.5 * (vmin + vmax)
    x = [0, 1]
    a.bar(0, te_v, width=0.55, color=ORANGE, label="Thermoelectric")
    a.bar(1, mid, width=0.55, color=TEAL,
          yerr=[[mid - vmin], [vmax - mid]], capsize=6,
          error_kw=dict(ecolor="#0d5c5c", lw=1.5), label="Stirling (band)")
    a.text(0, te_v, f"{te_v:g}", ha="center", va="bottom", fontsize=10, fontweight="bold")
    a.text(1, vmax, f"{vmin:g}–{vmax:g}", ha="center", va="bottom", fontsize=10, fontweight="bold")
    if ceiling is not None:
        a.axhline(ceiling, ls="--", color=GREY, lw=1.3)
        a.text(1.45, ceiling, ceiling_label, ha="right", va="bottom",
               fontsize=8.5, color="#555")
    a.set_xticks(x); a.set_xticklabels(["Thermoelectric", "Stirling"])
    a.set_title(title, fontsize=11); a.set_ylabel(ylabel)
    a.margins(y=0.18)

paired(ax[0, 0], "Overall efficiency", "percent", te["eta"], st_lo["eta"], st_hi["eta"],
       ceiling=CARNOT * 100, ceiling_label="Carnot ceiling 23.8%")
paired(ax[0, 1], "Electrical output", "kWe", te["P"], st_lo["P"], st_hi["P"],
       ceiling=Q_SNAP * CARNOT, ceiling_label="Carnot max 7.6 kWe")
paired(ax[1, 0], "Specific power", "W/kg", te["sp"], st_lo["sp"], st_hi["sp"])
paired(ax[1, 1], "Radiator area", "m^2", te["rad"], st_lo["rad"], st_hi["rad"])
ax[1, 1].text(0.5, 0.5, "barely changes:\nboth still reject ~30 kW",
              transform=ax[1, 1].transAxes, ha="center", fontsize=9,
              color="#555", style="italic")
ax[0, 0].legend(loc="upper left", fontsize=9)
fig.tight_layout(rect=[0, 0, 1, 0.96])
fig.savefig("te_vs_stirling_comparison.png", dpi=150)
print("wrote te_vs_stirling_comparison.png")

# =========================================================================
# Figure 2: path to 14 kWe, electrical power vs reactor thermal power
# =========================================================================
fig2, a = plt.subplots(figsize=(11, 7))
Q = np.linspace(0, 150, 400)

a.fill_between(Q, 0.25 * Q, 0.30 * Q, color=TEAL, alpha=0.30,
               label="Stirling, KRUSTY temps (25–30%)")
a.plot(Q, 0.275 * Q, color=TEAL, lw=2)
a.fill_between(Q, 0.0716 * Q, 0.110 * Q, color="#7fcf7f", alpha=0.40,
               label="Stirling, SNAP temps (7–11%)")
a.plot(Q, 0.0182 * Q, color=ORANGE, lw=2.5, label="Thermoelectric (1.82%)")
a.plot(Q, CARNOT * Q, color=GREY, ls="--", lw=1.5,
       label="Carnot ceiling at SNAP temps (23.8%)")

a.axhline(14, color=RED, lw=2.2)
a.text(2, 14.5, "14 kWe requirement", color=RED, fontsize=12, fontweight="bold")
a.axvline(31.9, color="#444", ls=":", lw=1.6)
a.text(33, 1.0, "SNAP reactor\n31.9 kWt", fontsize=9, color="#444")

# crossings of 14 kWe
def mark(eta, color, dy=0.0):
    q = 14 / eta
    if q <= 150:
        a.plot(q, 14, "o", color=color, ms=8, zorder=5)
        a.annotate(f"{q:.0f} kWt", (q, 14), textcoords="offset points",
                   xytext=(4, 8 + dy), fontsize=9, color=color, fontweight="bold")

mark(0.30, "#0d5c5c"); mark(0.25, "#0d5c5c", dy=-18)
mark(0.110, "#3a8a3a"); mark(0.0716, "#3a8a3a", dy=-18)

# SNAP reactor Carnot max marker
a.plot(31.9, 31.9 * CARNOT, "s", color=GREY, ms=8, zorder=5)
a.annotate("max 7.6 kWe here\n(even a perfect converter)", (31.9, 31.9 * CARNOT),
           textcoords="offset points", xytext=(8, -2), fontsize=8.5, color="#555")

a.set_xlabel("Reactor thermal power (kWt)", fontsize=11)
a.set_ylabel("Electrical output (kWe)", fontsize=11)
a.set_title("Reaching 14 kWe: converter, temperature, and reactor power",
            fontsize=13, fontweight="bold")
a.set_xlim(0, 150); a.set_ylim(0, 22)
a.legend(loc="upper right", fontsize=9.5, framealpha=0.95)
a.grid(alpha=0.25)
a.text(150, -2.6, "Thermoelectric needs ~770 kWt for 14 kWe, off the chart.",
       ha="right", fontsize=8.5, color=ORANGE, style="italic")
fig2.tight_layout()
fig2.savefig("path_to_14kwe.png", dpi=150)
print("wrote path_to_14kwe.png")

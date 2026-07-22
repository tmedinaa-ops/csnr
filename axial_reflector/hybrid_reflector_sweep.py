#!/usr/bin/env python3
"""
hybrid_reflector_sweep.py -- how little beryllium buys back a target reactivity, once
you spend it the way the leakage split says to.

Companion to reflector_sweep.py. That script answered "worth vs beryllium thickness."
This one answers the question the leakage split reframed: given a reactivity target you
must recover (on the HALEU route, the gap the ~65 kg all-beryllium plan was closing),
what is the LEAST beryllium that reaches it, and how much does a hydride liner save.

Findings this implements (see Leakage_Split_Prediction.md, measured 70.4% radial / 29.6%
axial, July 22 2026):
  1. Spend beryllium radially. All configs here are radial-only; no axial caps, because
     the ends carry the minority 30% at low yield.
  2. Layer a hydride liner inside the beryllium. The liner thermalizes leaking neutrons
     over a short distance and returns them; hydrogen is light, so it does the cheap part
     per kilo, and the beryllium behind only has to supply (n,2n) plus bulk albedo.
  3. Stay on the steep part of the worth curve. The target-crossing interpolation reports
     where each config reaches the target, so you never buy saturated beryllium.

Configs compared, each swept over added radial beryllium thickness:
  A  be_only        beryllium shell against the core (the reflector_sweep baseline case)
  B  liner_be       fixed hydride liner (LINER_CM) against the core, beryllium behind it
  C  ring_be        one added fuel ring THEN beryllium  -- NEEDS the snap.py hook
                    (Option A below); the generic wrap cannot grow the core, so C is
                    skipped with a message unless snap.py is wired. This is the "not sure
                    about the ring" fork: run A and B first, and only wire C if A/B do not
                    reach target on reflector mass alone.

Deliverable: for each config, the beryllium thickness and MASS at the target worth, and
the beryllium saved versus be_only. Also prints total added mass (Be + liner), because the
liner is denser than beryllium and is not free -- the goal is to cut the CONSTRAINED
material (beryllium), which can be worth a small total-mass penalty.

Two ways to build the variants, same as reflector_sweep.py:
  OPTION A (preferred): wire build_variant() to snap.py so it thickens the real reflector
    and, for config C, adds the outer fuel ring parametrically.
  OPTION B (generic, no snap.py): _layered_wrap() places hydride + beryllium shells in the
    void inside the vacuum sphere, hugging the core. Verify with a plots.xml (color_by
    material) that the layers landed where you expect before trusting k.

Run in openmc-env with OPENMC_CROSS_SECTIONS set. On the HALEU route point MODEL_XML at the
haleu_test model (de-enriched + TRIGA loading) and set EXPECT_KBASE to that core's value:
  MODEL_XML=~/snap/model_haleu.xml EXPECT_KBASE=0.93 TARGET_WORTH_PCM=7500 \
      LINER_CM=2 OMP_NUM_THREADS=20 PARTICLES=200000 BATCHES=150 python hybrid_reflector_sweep.py

Self-check (rule 6): baseline k must land within EXPECT_KBASE +/- KBASE_TOL, or the wrong
model is loaded and the run aborts before writing anything.
"""
import os
from pathlib import Path

import numpy as np
import openmc
import warnings
warnings.filterwarnings("ignore", message="Another")  # benign cross-load ID reuse in one process


def _env(name, default):
    v = os.environ.get(name)
    return v if v not in (None, "") else default


MODEL_XML = Path(_env("MODEL_XML", str(Path.home() / "snap" / "model.xml"))).expanduser()
BE_DENSITY = 1.85  # g/cc
LINER_MAT = _env("LINER_MAT", "zrh").lower()      # zrh (default, matches fuel) or yh2
LINER_CM = float(_env("LINER_CM", "2.0"))          # hydride liner thickness for config B
TARGET_WORTH_PCM = float(_env("TARGET_WORTH_PCM", "7500"))  # reactivity to recover
BE_CM = [float(x) for x in _env("BE_CM", "0,3,6,9,12,16,20,24").split(",")]
EXPECT_KBASE = float(_env("EXPECT_KBASE", "1.0005"))  # 1.0005 fig12 HEU; ~0.93 HALEU-loaded
KBASE_TOL = float(_env("KBASE_TOL", "0.02"))
WIRE_RING = _env("WIRE_RING", "0") == "1"          # set 1 only after snap.py hook is added
PARTICLES = int(_env("PARTICLES", "40000"))
BATCHES = int(_env("BATCHES", "100"))
INACTIVE = int(_env("INACTIVE", "30"))
if BATCHES <= INACTIVE:
    INACTIVE = max(5, BATCHES // 3)
    print(f"note: BATCHES ({BATCHES}) <= INACTIVE, lowering inactive to {INACTIVE}")

if not MODEL_XML.exists():
    raise SystemExit(f"missing {MODEL_XML}; set MODEL_XML to the snap model.xml")


# ----------------------------------------------------------------------------- materials
def beryllium():
    be = openmc.Material(name="reflector_be_added")
    be.add_element("Be", 1.0)
    be.set_density("g/cm3", BE_DENSITY)
    be.add_s_alpha_beta("c_Be")
    return be


def hydride():
    """Moderating liner. ZrH1.7 by default (same H carrier as the fuel, S(a,b) certain to
    be present). YH2 is the temperature-stable swap for the hot reflector radius; confirm
    the c_H_in_YH2 thermal-scattering name is in your ENDF/B-VIII.0 install before trusting
    a YH2 run -- if it is missing the liner runs without S(a,b) and over-predicts leakage."""
    m = openmc.Material(name=f"reflector_liner_{LINER_MAT}")
    if LINER_MAT == "yh2":
        m.add_element("Y", 1.0)
        m.add_nuclide("H1", 1.8)          # YH1.8
        m.set_density("g/cm3", 4.30)
        try:
            m.add_s_alpha_beta("c_H_in_YH2")
        except Exception:
            print("WARN: c_H_in_YH2 S(a,b) not added; liner spectrum will be wrong")
    else:                                  # ZrH1.7
        m.add_element("Zr", 1.0)
        m.add_nuclide("H1", 1.7)
        m.set_density("g/cm3", 5.66)
        m.add_s_alpha_beta("c_H_in_ZrH")
    return m


LINER_DENSITY = 4.30 if LINER_MAT == "yh2" else 5.66


# ------------------------------------------------------------------------------ geometry
def _reactor_dims(model):
    surfs = model.geometry.get_all_surfaces().values()
    radii = [s.r for s in surfs if isinstance(s, openmc.ZCylinder)]
    zs = [s.z0 for s in surfs if isinstance(s, openmc.ZPlane)]
    if not radii or not zs:
        raise SystemExit("no ZCylinder/ZPlane surfaces to size the core; wire the snap.py "
                         "hook in build_variant()")
    return max(radii), min(zs), max(zs)


def _vacuum_sphere(model):
    for s in model.geometry.get_all_surfaces().values():
        if isinstance(s, openmc.Sphere) and getattr(s, "boundary_type", "") == "vacuum":
            return s
    return None


def _layered_wrap(be_cm, liner_cm):
    """Radial hydride liner [Rc, Rc+liner] then beryllium [Rc+liner, Rc+liner+be], over the
    core height, placed in the void inside the vacuum sphere and carved out of the void."""
    model = openmc.Model.from_model_xml(str(MODEL_XML))
    model.tallies = openmc.Tallies()   # k-eff only; drop the model's heat mesh so variants run fast
    if be_cm == 0 and liner_cm == 0:
        return model  # baseline

    Rc, zlo, zhi = _reactor_dims(model)
    r0, r1, r2 = Rc, Rc + liner_cm, Rc + liner_cm + be_cm

    s0 = openmc.ZCylinder(r=r0)
    zbot, ztop = openmc.ZPlane(z0=zlo), openmc.ZPlane(z0=zhi)

    add_cells, new_mats, footprint = [], [], None
    if liner_cm > 0:
        s1 = openmc.ZCylinder(r=r1)
        reg = +s0 & -s1 & +zbot & -ztop
        m = hydride(); m.id = 90002
        add_cells.append(openmc.Cell(cell_id=90002, fill=m, region=reg))
        new_mats.append(m)
        footprint = reg
        r_be_in = s1
    else:
        r_be_in = s0
    if be_cm > 0:
        s2 = openmc.ZCylinder(r=r2)
        reg = +r_be_in & -s2 & +zbot & -ztop
        m = beryllium(); m.id = 90001
        add_cells.append(openmc.Cell(cell_id=90001, fill=m, region=reg))
        new_mats.append(m)
        footprint = reg if footprint is None else (footprint | reg)

    sph = _vacuum_sphere(model)
    if sph is not None:
        need = np.hypot(r2, max(abs(zhi), abs(zlo)))
        if sph.r < need + 0.5:
            sph.r = need + 1.0

    for c in model.geometry.get_all_cells().values():
        if c.fill is None and c.region is not None:
            c.region = c.region & ~footprint
    for c in add_cells:
        model.geometry.root_universe.add_cell(c)
    for m in new_mats:                 # THE FIX: register the added materials on the model
        model.materials.append(m)
    return model


def build_variant(be_cm, liner_cm, ring=False):
    # OPTION A: replace with a snap.py call that thickens the real reflector and, for the
    # ring config, adds the outer fuel ring parametrically, e.g.
    #   import sys; sys.path.insert(0, str(Path.home()/"snap")); import snap
    #   return snap.build_model(case="fig12_test", add_fuel_ring=ring,
    #                           liner_cm=liner_cm, liner_mat=LINER_MAT,
    #                           extra_radial_be_cm=be_cm)
    if ring:
        raise SystemExit("config C (ring) needs the snap.py hook in build_variant(); "
                         "the generic wrap cannot grow the core. Wire Option A, set "
                         "WIRE_RING=1, and rerun.")
    return _layered_wrap(be_cm, liner_cm)


# --------------------------------------------------------------------------------- runs
def run_k(model):
    model.settings.particles = PARTICLES
    model.settings.batches = BATCHES
    model.settings.inactive = INACTIVE
    model.settings.run_mode = "eigenvalue"
    sp = model.run(output=False)
    with openmc.StatePoint(sp) as s:
        k = s.keff
    return k.nominal_value, k.std_dev


_DIMS = None


def _dims():
    global _DIMS
    if _DIMS is None:
        _DIMS = _reactor_dims(openmc.Model.from_model_xml(str(MODEL_XML)))
    return _DIMS


def be_mass_kg(be_cm, liner_cm):
    R, zlo, zhi = _dims()
    H = zhi - zlo
    r1 = R + liner_cm
    r2 = r1 + be_cm
    v_be = np.pi * (r2**2 - r1**2) * H if be_cm > 0 else 0.0
    return v_be * BE_DENSITY / 1000.0


def liner_mass_kg(liner_cm):
    R, zlo, zhi = _dims()
    H = zhi - zlo
    v = np.pi * ((R + liner_cm) ** 2 - R**2) * H if liner_cm > 0 else 0.0
    return v * LINER_DENSITY / 1000.0


def sweep(liner_cm, k_base):
    """Return arrays of (be_cm, worth_pcm) for a fixed liner thickness."""
    out = []
    for be_cm in BE_CM:
        if be_cm == 0 and liner_cm == 0:
            k, s = k_base, 0.0
        else:
            k, s = run_k(build_variant(be_cm, liner_cm))
        worth = (k - k_base) / (k * k_base) * 1e5
        out.append((be_cm, worth))
        tag = f"liner {liner_cm:.0f}cm {LINER_MAT}" if liner_cm else "be only"
        print(f"  [{tag:16s}] be {be_cm:5.1f} cm  k {k:.5f}  worth {worth:+7.0f} pcm  "
              f"be {be_mass_kg(be_cm, liner_cm):5.1f} kg")
    return np.array(out, float)


def be_at_target(curve, liner_cm):
    """Interpolate the beryllium thickness where worth crosses TARGET_WORTH_PCM, then its
    mass. Returns (be_cm, be_kg, reached: bool)."""
    x, w = curve[:, 0], curve[:, 1]
    o = np.argsort(x)
    x, w = x[o], w[o]
    if w[-1] < TARGET_WORTH_PCM:
        return x[-1], be_mass_kg(x[-1], liner_cm), False   # not reached on the swept range
    i = int(np.argmax(w >= TARGET_WORTH_PCM))
    if i == 0:
        be_cm = x[0]
    else:
        be_cm = x[i - 1] + (TARGET_WORTH_PCM - w[i - 1]) * (x[i] - x[i - 1]) / (w[i] - w[i - 1])
    return be_cm, be_mass_kg(be_cm, liner_cm), True


def main():
    print(f"model: {MODEL_XML}")
    print(f"target worth: {TARGET_WORTH_PCM:.0f} pcm   liner: {LINER_CM:.0f} cm {LINER_MAT}\n")

    k_base, s_base = run_k(build_variant(0, 0))
    print(f"baseline k = {k_base:.5f} +/- {s_base:.5f}")

    # --- self-check (rule 6): right model loaded? ---
    if not np.isfinite(k_base):
        raise SystemExit("baseline k is not finite; model failed to run")
    if abs(k_base - EXPECT_KBASE) > KBASE_TOL:
        raise SystemExit(f"SELF-CHECK FAIL: baseline k {k_base:.5f} is off the expected "
                         f"{EXPECT_KBASE:.4f} +/- {KBASE_TOL:.4f}. Wrong model loaded, or "
                         f"set EXPECT_KBASE for this core (HALEU-loaded ~0.93).")
    print("self-check: baseline k matches expected model. OK\n")

    print("config A: be_only")
    curveA = sweep(0.0, k_base)
    print("\nconfig B: liner_be")
    curveB = sweep(LINER_CM, k_base)

    # monotonic-worth sanity (soft): reflector worth should not fall as beryllium grows
    for name, c in (("A", curveA), ("B", curveB)):
        wv = c[np.argsort(c[:, 0])][:, 1]
        if np.any(np.diff(wv) < -150):  # 150 pcm slack for statistical noise
            print(f"WARN: config {name} worth non-monotonic in beryllium; check geometry/stats")

    beA, kgA, okA = be_at_target(curveA, 0.0)
    beB, kgB, okB = be_at_target(curveB, LINER_CM)
    linerB = liner_mass_kg(LINER_CM)

    print("\n" + "=" * 72)
    print(f"BERYLLIUM AT TARGET ({TARGET_WORTH_PCM:.0f} pcm)")
    print("=" * 72)
    print(f"A be_only : be {beA:5.1f} cm -> {kgA:5.1f} kg Be"
          f"{'' if okA else '   (TARGET NOT REACHED on swept range)'}")
    print(f"B liner+Be: be {beB:5.1f} cm -> {kgB:5.1f} kg Be + {linerB:4.1f} kg {LINER_MAT} liner"
          f"{'' if okB else '   (TARGET NOT REACHED on swept range)'}")
    if okA and okB:
        saved = kgA - kgB
        print(f"\nberyllium saved by the {LINER_CM:.0f} cm {LINER_MAT} liner: {saved:+.1f} kg "
              f"({100*saved/kgA:+.0f}% of the be_only beryllium)")
        print(f"total added mass  A: {kgA:5.1f} kg   B: {kgB + linerB:5.1f} kg  "
              f"(delta {kgB + linerB - kgA:+.1f} kg)")
        print("read: negative beryllium-saved means this liner thickness does not pay; "
              "sweep LINER_CM (1,2,3,4) to find the beryllium-minimising liner.")
    if not (okA and okB):
        print("\nTarget not reached on reflector alone -> this is the signal to wire config C "
              "(add a fuel ring, snap.py hook) and rerun. That is the 'ring' fork.")

    hdr = "be_cm,worthA_pcm,worthB_pcm"
    x = np.union1d(curveA[:, 0], curveB[:, 0])
    def wof(curve, xx):
        d = dict(zip(curve[:, 0], curve[:, 1]))
        return [d.get(v, np.nan) for v in xx]
    out = np.column_stack([x, wof(curveA, x), wof(curveB, x)])
    np.savetxt("hybrid_reflector_sweep.csv", out, delimiter=",", header=hdr, comments="")
    print("\nwrote hybrid_reflector_sweep.csv")

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(7.2, 4.6))
        for c, lab in ((curveA, "A  be only"),
                       (curveB, f"B  {LINER_CM:.0f}cm {LINER_MAT} liner + be")):
            c = c[np.argsort(c[:, 0])]
            ax.plot(c[:, 0], c[:, 1], "o-", label=lab)
        ax.axhline(TARGET_WORTH_PCM, ls="--", color="#b03030", label=f"target {TARGET_WORTH_PCM:.0f} pcm")
        ax.set_xlabel("added radial beryllium [cm]"); ax.set_ylabel("reflector worth [pcm]")
        ax.set_title("beryllium to target: be only vs hydride liner + be")
        ax.legend(fontsize=8); ax.grid(alpha=0.25)
        plt.tight_layout(); plt.savefig("hybrid_reflector_sweep.png", dpi=140)
        print("wrote hybrid_reflector_sweep.png")
    except Exception as e:
        print("plot skipped:", e)


if __name__ == "__main__":
    main()

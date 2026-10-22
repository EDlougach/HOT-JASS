"""Example HOT-JASS workflow: first-wall neutron flux of the PONTE preset against
density and beam power, for both confinement scalings, with operating limits.

    .venv/bin/python workflows/example_scan.py          (from the repository root, ~30 s)

Writes workflows/output/example_scan.csv (one row per point, all inputs and outputs)
and workflows/output/example_scan.png. See workflows/README.md for the functions used.
"""
from __future__ import annotations

import copy
import csv
import sys
import warnings
from pathlib import Path

import numpy as np

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import app  # noqa: E402  -- builds the GUI widgets, starts no server

OUT = Path(__file__).resolve().parent / "output"

# ---- 1. what to scan --------------------------------------------------------------------
PRESET = "PONTE"
N_AVG = np.linspace(0.4e20, 1.4e20, 8)          # volume-average density [m^-3]
P_NB = [6.0, 8.0, 10.0]                          # beam power [MW]
SCALINGS = {"IPB98(y,2)": "iter98y2", "Kaye NSTX H-mode": "kaye_nstx_hmode"}
LIMITS = {"f_GW": 0.8, "beta_N": 5.5, "Ti0_keV": 30.0}   # a point is "allowed" within these


# ---- 2. base model from a preset (once) -------------------------------------------------
app.apply_rail_values(app.DEVICE_PRESETS[PRESET])   # same values the GUI preset sets
BASE = app._build_model()
BASE.beams = [b for b in BASE.beams if b.power_MW > 0.0]   # drop empty beam slots


def point(n_avg: float, p_nb: float, mode: str) -> dict:
    """Solve one operating point and return the quantities of interest."""
    m = copy.deepcopy(BASE)                         # never modify BASE itself
    p = m.plasma
    p.central_density = n_avg * (1.0 + 2.0 * p.density_peaking)   # input is the central n_e
    p.tau_Ee_mode = p.tau_Ei_mode = mode
    m.beams[0].power_MW = p_nb
    op = m.operating_point()
    row = {"n_avg_m3": n_avg, "P_NB_MW": p_nb, "scaling": mode, "feasible": bool(op.feasible),
           "f_GW": app._greenwald(m)[2]}
    if not op.feasible:
        return row
    ip_ma = p.plasma_current / 1e6
    wall = app.wall_neutron_profile(p, op)          # poloidal first-wall flux [n m^-2 s^-1]
    row.update(
        Y_n_s=op.neutron_rate_s,
        beam_share=(op.neutron_rate_beam_s + op.neutron_rate_bb_s) / op.neutron_rate_s,
        P_fus_MW=op.pf_total_w / 1e6,
        flux_avg_cm2s=wall["J_avg"] * 1e-4,
        flux_out_cm2s=wall["J"][0] * 1e-4,          # outboard midplane
        beta_N=op.beta_t * 100.0 * p.minor_radius * p.toroidal_field / ip_ma,
        Ti0_keV=op.Ti0_keV,
        tauE_ms=op.tau_E_s * 1e3,
        P_lost_MW=(op.P_shine_w + op.P_orbit_loss_w + op.P_cx_loss_w + op.P_delayed_loss_w) / 1e6,
    )
    row["allowed"] = all(row[k] <= v for k, v in LIMITS.items())
    return row


def main():
    rows = [point(n, p, mode) for mode in SCALINGS.values() for p in P_NB for n in N_AVG]
    OUT.mkdir(exist_ok=True)
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with open(OUT / "example_scan.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} points, {sum(r.get('allowed', False) for r in rows)} allowed "
          f"-> {OUT / 'example_scan.csv'}")
    plot(rows)


def plot(rows):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axs = plt.subplots(1, 2, figsize=(11, 4.4), sharey=True, constrained_layout=True)
    for ax, (label, mode) in zip(axs, SCALINGS.items()):
        for p_nb, col in zip(P_NB, ("#9ec5f4", "#3987e5", "#0d366b")):
            sel = [r for r in rows if r["scaling"] == mode and r["P_NB_MW"] == p_nb and r["feasible"]]
            x = np.array([r["n_avg_m3"] for r in sel]) / 1e19
            y = np.array([r["flux_avg_cm2s"] for r in sel]) / 1e12
            ok = np.array([r["allowed"] for r in sel])
            ax.plot(x, y, color=col, lw=1.2, alpha=0.4)                       # all points
            ax.plot(x, np.where(ok, y, np.nan), "-o", color=col, lw=2.4, ms=5,  # allowed ones
                    label=f"$P_{{NB}}$ = {p_nb:g} MW")
        ax.set_title(label)
        ax.set_xlabel(r"$\langle n_e\rangle$  [$10^{19}$ m$^{-3}$]")
        ax.grid(alpha=0.3)
    axs[0].set_ylabel(r"average first-wall flux  [$10^{12}$ n cm$^{-2}$ s$^{-1}$]")
    axs[0].legend(frameon=False)
    fig.suptitle(f"{PRESET} preset: thick = within limits {LIMITS}", fontsize=10)
    fig.savefig(OUT / "example_scan.png", dpi=150)
    print(f"-> {OUT / 'example_scan.png'}")


if __name__ == "__main__":
    main()

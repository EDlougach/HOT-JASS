"""Regression check for HOT-Jass web: every preset, both profile modes,
delayed orbit loss off and on.

For each case it solves the operating point and builds everything a user
can produce from it -- all six result tabs (on demand, as in the app), the
Results View, the NBI_OUT preview, the summary PNG/PDF, the ALL_info and
Assumptions PDFs, NBI_OUT, the U-file zip and the particle balance -- and
compares the key results with tests/regress_reference.json.

    .venv/bin/python tests/regress.py            # check (about 10 minutes)
    .venv/bin/python tests/regress.py --update   # store the current results as the reference

Exit status 0 when every case builds and matches the reference (relative
tolerance 1e-6), 1 otherwise. After an intended physics change, review the
reported differences, then run --update and commit the new reference.
"""
from __future__ import annotations

import json
import sys
import traceback
import warnings
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REFERENCE = Path(__file__).resolve().parent / "regress_reference.json"
REL_TOL = 1e-6

warnings.filterwarnings("ignore")
sys.path.insert(0, str(ROOT))
import app  # noqa: E402  (builds the app's widgets without a server session)


def _results(op, cd) -> dict:
    """The numbers compared with the reference."""
    out = {
        "Te_keV": op.Te_keV, "Ti_keV": op.Ti_keV, "nb0_m3": op.nb0_m3, "n_thermal_m3": op.n_thermal_m3,
        "P_e_w": op.P_e_w, "P_i_w": op.P_i_w, "P_delayed_loss_w": op.P_delayed_loss_w,
        "pf_total_w": op.pf_total_w, "neutron_rate_s": op.neutron_rate_s, "beta_t": op.beta_t,
    }
    if cd is not None:
        out.update(I_nb_A=cd.I_nb_A, I_bs_A=cd.I_bs_A)
    return out


def _check_case(name: str, profiles: bool, k: float) -> dict:
    app.apply_rail_values(app.DEVICE_PRESETS[name])
    app.profile_avg_checkbox.value = profiles
    app.delayed_loss_slider.value = k
    model = app._build_model()
    op = model.operating_point()
    if not op.feasible:
        raise RuntimeError(f"infeasible: {op.infeasible_reason}")
    vol = model.plasma_volume()
    cd = model.current_drive(op)
    # Result tabs: the visible one first, the others on demand (as in the app).
    advice = app._result_advisories(op, model)
    app._show_results(op, model, vol, advice, {0: app._build_result_tab(0, op, model, vol, advice)})
    for view in range(1, len(app.PLOT_TABS)):
        app.view_tabs.active = view
    if len(app._result_tabs["built"]) != len(app.RESULT_TAB_NAMES):
        raise RuntimeError(f"only {sorted(app._result_tabs['built'])} result tabs built")
    # Everything exported from the last result.
    app._last_result.update(op=op, model=model, vol=vol)
    app._open_results_view(None)
    if not app.results_view_pane.object:
        raise RuntimeError("Results View is empty")
    app._open_nbi_out_preview(None)
    for render in (app._render_summary_png, app._render_summary_pdf, app._render_all_info_pdf,
                   app._render_assumptions_pdf):
        if not render().getvalue():
            raise RuntimeError(f"{render.__name__} produced nothing")
    app._nbi_out_text(op, model)
    zipfile.ZipFile(app._render_ufiles_zip()).read("README.txt")
    app._particle_balance(op, model, vol)
    return _results(op, cd)


def main() -> int:
    update = "--update" in sys.argv[1:]
    reference = json.loads(REFERENCE.read_text()) if REFERENCE.exists() else {}
    current, failures, diffs = {}, 0, 0
    for name in app.DEVICE_PRESETS:
        for profiles in (True, False):
            for k in (0.0, 1.0):
                case = f"{name} | {'profiles' if profiles else 'flat 0-D'} | k={k:g}"
                try:
                    res = _check_case(name, profiles, k)
                except Exception:
                    failures += 1
                    print(f"FAIL  {case}")
                    traceback.print_exc()
                    continue
                current[case] = res
                ref = reference.get(case)
                bad = [] if ref is None else [
                    f"{key} {ref.get(key)!r} -> {val!r}" for key, val in res.items()
                    if ref.get(key) is None or abs(val - ref[key]) > REL_TOL * max(abs(ref[key]), 1e-30)]
                diffs += bool(bad)
                status = "new " if ref is None else ("DIFF" if bad else "ok  ")
                print(f"{status}  {case}" + ("" if not bad else "\n        " + "\n        ".join(bad)))
    if update:
        REFERENCE.write_text(json.dumps(current, indent=1, sort_keys=True) + "\n")
        print(f"\nReference updated: {REFERENCE.name} ({len(current)} cases).")
    print(f"\n{len(current)} cases built, {failures} failed, {diffs} differ from the reference.")
    return 1 if failures or (diffs and not update) else 0


if __name__ == "__main__":
    sys.exit(main())

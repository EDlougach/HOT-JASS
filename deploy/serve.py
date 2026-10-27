"""Production launcher for HOT-Jass web: preload once, then serve with several processes.

    python deploy/serve.py --num-procs 6 --port 5006 --address 127.0.0.1 \
        --allow-websocket-origin hot.real-nbi.com --liveness

All options after the script name are passed to `panel serve app.py`.

What it adds to a plain `panel serve app.py --num-procs N`: before the server
forks its worker processes it

- imports numpy, pandas, matplotlib, Panel and the hotjass physics (~8 s cold),
- runs the app once and solves every machine preset, which fills the physics
  caches (P_phi orbit tables) and the process-wide cache of geometry images,

so every worker starts with all of that already in memory -- shared between
the workers (copy-on-write) instead of loaded by each one, and the first
visitor of each worker no longer waits for it. Set HOTJASS_NO_WARM=1 to skip
the warm-up solves (imports only).

Linux / macOS only (--num-procs > 1 needs fork).
"""
from __future__ import annotations

import os
import runpy
import sys
import time
import warnings
from pathlib import Path

APP = Path(__file__).resolve().parent.parent / "app.py"


def preload() -> None:
    t0 = time.perf_counter()
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot  # noqa: F401
    import numpy  # noqa: F401
    import pandas  # noqa: F401
    import panel as pn
    import hotjass.core  # noqa: F401
    import hotjass.current  # noqa: F401
    t1 = time.perf_counter()
    print(f"[serve] libraries imported in {t1 - t0:.1f} s", flush=True)
    if os.environ.get("HOTJASS_NO_WARM"):
        return
    sys.path.insert(0, str(APP.parent))
    with warnings.catch_warnings():       # quiet warm-up; the filters are restored afterwards
        warnings.simplefilter("ignore")
        ns = runpy.run_path(str(APP), run_name="hotjass_warmup")
    solved = 0
    for name, cfg in ns["DEVICE_PRESETS"].items():
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                ns["apply_rail_values"](cfg)      # also renders + caches its geometry image
                ns["_build_model"]().operating_point()
            solved += 1
        except Exception as exc:              # a failed warm-up must never stop the server
            print(f"[serve] warm-up of {name} failed: {type(exc).__name__}: {exc}", flush=True)
    # The warm-up instance registered its own session-destroyed callback with
    # Panel (no document yet, so it went to the class-level list that is
    # attached to EVERY future session); drop it.
    for attr in ("_on_session_destroyed",):
        lst = getattr(type(pn.state), attr, None)
        if isinstance(lst, list):
            lst.clear()
    n_geom = len(pn.state.cache.get("hotjass_geometry_png", {}))
    print(f"[serve] warm-up: {solved} presets solved, {n_geom} geometry images cached, "
          f"{time.perf_counter() - t1:.1f} s", flush=True)


def main() -> None:
    preload()
    from panel.command import main as panel_main
    sys.argv = ["panel", "serve", str(APP), *sys.argv[1:]]
    panel_main()


if __name__ == "__main__":
    main()

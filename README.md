# HOT-Jass web

Panel web port of the HI-Jass desktop app: toolbar + input rail + tab view
area, wired to HI-Jass's own `hotjass_core`/`hotjass.physics` solver for
real plasma/beam/power/fusion calculations.

## Requirement: HI-Jass as a sibling folder

`app.py` imports `hotjass_core`/`hotjass.physics` directly from
[HI-Jass](https://github.com/EDlougach/HI-Jass) via a relative
`sys.path.insert` -- HI-Jass must be cloned as a **sibling** directory,
not nested inside this one:

```
some-folder/
├── HOT-Jass_web/   (this repo)
└── HI-Jass/
```

```bash
git clone git@github.com:EDlougach/HI-Jass.git
git clone git@github.com:EDlougach/HOT-JASS.git HOT-Jass_web
```

Without HI-Jass cloned alongside, `panel serve app.py` fails immediately
with `ModuleNotFoundError: No module named 'hotjass_core'` -- on any OS.

## First time setup

**Linux / macOS**
```bash
cd HOT-Jass_web
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

**Windows (PowerShell or cmd)**
```powershell
cd HOT-Jass_web
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

## Run

**Linux / macOS**
```bash
.venv/bin/panel serve app.py --show
```

**Windows**
```powershell
.venv\Scripts\panel serve app.py --show
```

Opens in your browser at `http://localhost:5006/app`. Stop with `Ctrl+C`.

## Run with autoreload (while editing app.py)

**Linux / macOS**
```bash
.venv/bin/panel serve app.py --show --autoreload
```

**Windows**
```powershell
.venv\Scripts\panel serve app.py --show --autoreload
```

Refresh the browser tab after each save -- `panel serve` doesn't push
changes automatically, `--autoreload` just restarts the server for you.

## Regression check

After changing the code, run

```bash
.venv/bin/python tests/regress.py
```

It solves every preset with and without profile-corrected 0-D and with the
delayed orbit loss off and on, builds every result tab and export, and
compares the key results with `tests/regress_reference.json` (about 10
minutes). After an intended physics change, review the reported
differences, then store the new results with `--update` and commit them.

## Serve several users at once

Each user's calculation and figures use one CPU core while they run, and
all sessions of one server process share that process. For a server with
several simultaneous users, start one process per core (Linux / macOS
only; not together with `--autoreload`):

```bash
.venv/bin/panel serve app.py --num-procs 4 --port 5006 --allow-websocket-origin=YOUR_HOST:5006
```

`--num-procs 0` uses all cores. Sessions are spread over the processes;
each process keeps its own caches, so the first calculation in each one is
slightly slower. Measured on 4 cores, 5 users pressing Start together
(2026-10-21): about 3.5 s each from Start to Done (a single user: 2.8 s,
of which 2.4 s is the progress display).

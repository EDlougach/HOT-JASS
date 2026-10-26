# HOT-Jass web

Web app for neutral-beam-driven tokamak plasmas: toolbar + input rail + tab
view area, running the physics of the
[`hotjass`](https://github.com/EDlougach/hotjass) package (power and particle
balance, beam deposition and orbit loss, fusion, current drive).

## The physics package

`hotjass` is installed by `requirements.txt` at a pinned version tag, so
`git clone` + the setup below is all an ordinary run needs. The models are
described in its [User Manual](https://github.com/EDlougach/hotjass/blob/main/User_Manual.md).

To work on the physics and the app together, clone `hotjass` next to this
repository and install it in editable mode -- the app then uses your
working copy:

```bash
git clone https://github.com/EDlougach/hotjass
cd HOT-Jass_web && .venv/bin/pip install -e ../hotjass
```

A physics change goes to the `hotjass` repository as its own pull request;
this app adopts a new version by bumping the tag in `requirements.txt` and
updating `tests/regress_reference.json` (see "Regression check").

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

For a server with several simultaneous users use the launcher in `deploy/`:
it preloads the libraries and warms the caches once, then runs `panel serve`
with one worker process per core (Linux / macOS):

```bash
.venv/bin/python deploy/serve.py --num-procs 6 --port 5006 --allow-websocket-origin YOUR_HOST
```

[`deploy/README.md`](deploy/README.md) has the systemd service, the update
script, sizing numbers and a browser load test.

## Your own workflows (scripting)

Every number the app shows comes from Python functions you can call from your
own scripts: scans, optimisations, coupling to other codes. See
[`workflows/README.md`](workflows/README.md) for the guide and a small
working example (`workflows/example_scan.py`).

## Contributing

Bug reports, presets, physics and app improvements are welcome: see
[CONTRIBUTING.md](CONTRIBUTING.md) and the [Code of Conduct](CODE_OF_CONDUCT.md).
Physics changes go to the [`hotjass`](https://github.com/EDlougach/hotjass)
repository. Every pull request runs the regression check automatically.

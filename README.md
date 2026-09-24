# HOT-Jass web

Standalone Panel layout skeleton (toolbar + input rail + tab view area).
Separate from HI-Jass -- own venv, no cross-folder imports.

## First time setup

```bash
cd /home/eugenia/Documents/VSClaude/HOT-Jass_web
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Run

```bash
.venv/bin/panel serve app.py --show
```

Opens in your browser at `http://localhost:5006/app`. Stop with `Ctrl+C`.

## Run with autoreload (while editing app.py)

```bash
.venv/bin/panel serve app.py --show --autoreload
```

Refresh the browser tab after each save -- `panel serve` doesn't push
changes automatically, `--autoreload` just restarts the server for you.

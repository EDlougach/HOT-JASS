## What does this change?

<!-- One or two sentences; link the issue it addresses, e.g. "Closes #12". -->

## Why?

<!-- The problem, or the physics/feature motivation. For physics: the source (paper, code, measurement). -->

## Effect on results

- [ ] No result changes (`tests/regress.py` passes unchanged)
- [ ] Results change -- explained below, `tests/regress_reference.json` updated with `--update`

<!-- For changed results: before/after numbers for the affected presets, and why the new ones are right.
     Changes above 10 % must be an option, off by default. -->

## Checklist

- [ ] `.venv/bin/python tests/regress.py` passes
- [ ] Tried in the running app (`panel serve app.py`)
- [ ] User-facing texts / Help / Assumptions updated where needed
- [ ] New presets: every value has a public source in `MACHINE_REFERENCES`
- [ ] Physics changes: made in `hotjass` and adopted here by bumping its version in `requirements.txt`

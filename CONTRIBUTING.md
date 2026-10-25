# Contributing to HOT-Jass web

Thank you for helping! Bug reports, questions, new machine presets, physics
improvements and app features are all welcome. Every change is reviewed and
approved by the maintainer ([@EDlougach](https://github.com/EDlougach)) before
it is merged.

## Where does my change go?

| Change | Repository |
|---|---|
| Physics: models, solver, current drive, the User Manual | [`hotjass`](https://github.com/EDlougach/hotjass) (see its CONTRIBUTING.md) |
| The web app: inputs, presets, tabs, plots, exports, texts | this repository |

A change that needs both goes as two pull requests: first the physics to
`hotjass`; after it is released, the app adopts the new version here by
bumping the tag in `requirements.txt` (and updating the regression reference).

## How to contribute

1. **Open an issue first** for anything larger than a small fix, so we can
   agree on the approach before you spend time on it.
2. **Fork** this repository and create a branch for your change.
3. Set up the app as described in [README.md](README.md). To change the
   physics at the same time, clone `hotjass` next to this repository and
   install it in editable mode: `.venv/bin/pip install -e ../hotjass`.
4. Make the change. Keep a pull request to one topic.
5. Run the **regression check** and make sure it passes:

   ```bash
   .venv/bin/python tests/regress.py
   ```

   It builds every preset in both profile modes with every tab and export
   (about 10 minutes) and compares the key results with
   `tests/regress_reference.json`. If your change is *meant* to change
   results, review the differences, run it with `--update`, and commit the
   new reference with your change -- the pull request must explain them.
6. Open a **pull request** and fill in the template. The automatic check
   runs the regression check on GitHub as well.

## Rules for changes

- **Results that change must be explained.** Give before/after numbers for
  the affected presets (the regression output is a good start).
- **Physics changes need a source:** a paper, a validated code, or
  measurements -- cited in the pull request and in the User Manual.
- **Changes that move results by more than 10 %** are added as an option,
  off by default, so existing results stay reproducible.
- **New machine presets need a public source** for every value (paper,
  conference contribution, public machine description). Put the reference
  in the preset's entry in `MACHINE_REFERENCES` in `app.py`.
- **Keep the app responsive for several users:** no slow work on the event
  loop -- matplotlib drawing and long calculations run in worker threads
  (see `_render_async` and `_calc_worker` in `app.py`).
- Match the style of the surrounding code; user-facing text in plain,
  short English.
- Contributions written with AI assistance are welcome -- you are
  responsible for the change being correct and understood.

## Reporting bugs and asking questions

Use the issue templates: describe what you did (the machine preset or your
inputs -- a saved Config JSON helps a lot), what you expected, and what
happened.

## Code of Conduct

Everyone taking part is expected to follow the
[Code of Conduct](CODE_OF_CONDUCT.md).

## License

By contributing you agree that your contribution is licensed under this
repository's [BSD 3-Clause License](LICENSE).

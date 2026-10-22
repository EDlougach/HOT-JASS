# Your own workflows with HOT-JASS

HOT-JASS is a web app, but every number it shows comes from Python functions you can
call from your own script: scans, optimisations, sensitivity studies, coupling to other
codes. This folder explains how, with one small working example.

You need some Python. You do not need to change the app.

## Setup

Install the app as described in the main [README](../README.md) (virtual environment +
`pip install -r requirements.txt`; this also installs the `hotjass` physics package).
Run your scripts **from the repository root** with the app's Python:

```bash
.venv/bin/python workflows/example_scan.py          # Windows: .venv\Scripts\python ...
```

`import app` loads the GUI module (about 6 s): it builds the widgets but starts no server.

## The example

[`example_scan.py`](example_scan.py) scans the PONTE preset over density and beam power,
for the IPB98(y,2) and Kaye NSTX H-mode confinement scalings (48 points, about 30 s), and
for each point records the neutron yield, the average and outboard first-wall flux,
β_N, the Greenwald fraction, T_i0 and the beam losses. It flags the points within
the limits n̄_e ≤ 0.8 n_GW, β_N ≤ 5.5 and T_i0 ≤ 30 keV, and writes

- `workflows/output/example_scan.csv`: one row per point, all inputs and outputs;
- `workflows/output/example_scan.png`: flux against density, thick where allowed.

Copy it and change the scan, the outputs or the limits.

## The five steps of any workflow

```python
import copy, app

# 1. a base model from a device preset (once per process)
app.apply_rail_values(app.DEVICE_PRESETS["PONTE"])   # presets: PONTE, JET, ITER, TCV, ST40, T-15MD, MAST-U, NSTX-U
base = app._build_model()

# 2. a copy per point, with your changes
m = copy.deepcopy(base)
m.plasma.major_radius = 0.7
m.beams[0].beam_energy_keV = 100.0

# 3. solve
op = m.operating_point()
if not op.feasible:            # no steady state: op.infeasible_reason says why
    ...

# 4. derived quantities (same helpers the GUI uses)
f_gw = app._greenwald(m)[2]                          # line-average n_e / n_GW
wall = app.wall_neutron_profile(m.plasma, op)        # first-wall flux, n m^-2 s^-1

# 5. your limits and objective, then save (CSV, pandas, ...)
```

Results are identical to what the app shows for the same inputs.

## Inputs you can change

`m.plasma` (a `hotjass.core.PlasmaParams`) and `m.beams[i]` (`BeamParams`). The most used:

| Field | Unit | Note |
|---|---|---|
| `plasma.major_radius`, `minor_radius` | m | |
| `plasma.elongation`, `triangularity` | – | |
| `plasma.toroidal_field` | T | at R0 |
| `plasma.plasma_current` | **A** | not MA |
| `plasma.central_density` | m⁻³ | **central** n_e; volume average = central / (1 + 2·`density_peaking`) |
| `plasma.deuterium_fraction`, `tritium_fraction`, `hydrogen_fraction` | – | thermal fuel mix, sum 1 |
| `plasma.tau_Ee_mode`, `tau_Ei_mode` | – | `"iter98y2"`, `"kaye_nstx_hmode"`, `"kaye_nstx_lmode"`, `"fixed"` |
| `plasma.tauE_enhancement` | – | h, with τ_E = (1 + h) τ_scaling |
| `plasma.p_ecrh_MW`, `p_icrh_MW` | MW | auxiliary heating |
| `plasma.centrepost_radius` | m | −1 = R0 − a |
| `plasma.profile_averaging` | bool | profile-corrected 0-D (on) or flat 0-D |
| `beams[i].power_MW`, `beam_energy_keV`, `species` | MW, keV, `"D"`/`"T"`/`"H"` | |
| `beams[i].tangent_R_m`, `tangent_Z_m`, `vertical_angle_deg` | m, m, deg | aiming |

Print `dataclasses.fields(m.plasma)` for the full list.

## Outputs

`op` (an `OperatingPoint`). The most used:

| Field | Unit |
|---|---|
| `feasible`, `infeasible_reason` | steady state found? |
| `neutron_rate_s`, `neutron_rate_thermal_s`, `neutron_rate_beam_s`, `neutron_rate_bb_s` | s⁻¹ |
| `pf_total_w`, `pf_thermal_w`, `pf_beam_w` | W |
| `Te_keV`, `Ti_keV` (averages), `Te0_keV`, `Ti0_keV` (central) | keV |
| `tau_E_s`, `tau_Ei_s` | s |
| `beta_t` | toroidal β (β_N = β_t · 100 · a · B_t / I_p[MA]) |
| `P_NB_total_w`, `P_shine_w`, `P_orbit_loss_w`, `P_cx_loss_w`, `P_delayed_loss_w` | W |
| `nb0_m3`, `nD0_m3`, `nT0_m3` | m⁻³ |
| `rho_profile`, `ne_profile_m3`, `Te_profile_keV`, `pf_thermal_profile_wm3`, ... | profiles (profile mode only) |

And from the app helpers:

| Call | Returns |
|---|---|
| `app._greenwald(m)` | (line-average n_e, n_GW, fraction), m⁻³ |
| `app._particle_balance(op, m, m.plasma_volume())` | dict: external fuelling per species `["ext"]`, burn, beam source, ... |
| `app.first_wall_area_m2(m.plasma)` | first-wall area, m² |
| `app.wall_neutron_profile(m.plasma, op)` | dict: `J`, `phi` (n m⁻² s⁻¹), `theta_deg`, `J_avg`, `closure` |

## Tips

- **Speed.** A solve takes 0.1–0.5 s. For big scans, run points in parallel with
  `multiprocessing.Pool` (processes, not threads). Build `base` at module level so every
  worker has it.
- **Never change `base`**: always work on `copy.deepcopy(base)`.
  `apply_rail_values` sets the GUI's global input state, so call it once per process,
  before building `base`.
- **Save every point**, inputs and outputs. Then you can change the limits or the
  objective later without re-running.
- **Reproducibility.** The `app._...` helpers are app internals: they are stable in
  practice, but may change between versions. Record the HOT-JASS commit
  (`git rev-parse --short HEAD`) and the `hotjass` version with your results.
- **Physics documentation**: the User Manual of the
  [`hotjass`](https://github.com/EDlougach/hotjass) package.

# Deploying HOT-Jass web on a server

Files in this folder:

| File | What it is |
|---|---|
| `serve.py` | Production launcher: preloads the libraries, solves every preset once (fills the physics and geometry caches), then runs `panel serve app.py` with the options you give it -- every worker process starts warm. |
| `hotjass-web.service` | systemd unit: runs `serve.py` with 6 processes, restarts it automatically, `MALLOC_ARENA_MAX=2`. Adjust the marked lines. |
| `update.sh` | Updates a running server: `git pull` (fast-forward only), `pip install -r requirements.txt`, restart, wait for the health check. |
| `server_info.sh` | Read-only report of how the app runs on a server (processes, code version, packages, services, proxy, ports). |
| `loadtest.py` | Browser load test: N simulated users (headless Chrome) open the app, pick a preset, press Start; prints the timings. |
| `SERVER_QUESTIONS.md` | Questions for the server admin. |

## First installation

```bash
git clone https://github.com/EDlougach/HOT-JASS.git HOT-Jass_web
cd HOT-Jass_web
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt          # includes the pinned hotjass physics
.venv/bin/python deploy/serve.py --num-procs 2 --port 5006 --allow-websocket-origin localhost:5006
# open http://localhost:5006/app ; Ctrl+C to stop
```

Then install the service (adjust user, path, port, host in the file first):

```bash
sudo cp deploy/hotjass-web.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now hotjass-web
systemctl status hotjass-web          # running?
journalctl -u hotjass-web -f          # its log
curl http://127.0.0.1:5006/liveness   # {"/liveness": true} when the app is up
```

Start-up takes 10-25 s (imports + warm-up) before the port answers.

## Updating

```bash
bash deploy/update.sh
```

## Sizing (measured 2026-10-26)

| | |
|---|---|
| Memory per process | ~190 MB after the warm-up, ~250-300 MB with sessions; ~17 MB per open browser tab |
| Server CPU per new visitor | ~1 s to build the page (one core), then ~0.3 s per calculation plus figure drawing when a result tab is opened |
| One user | Start -> Done 2.8 s (2.4 s of it is the progress display), preset -> geometry 0.5 s |
| 10 users at once, 4 processes on a 4-core laptop that also ran the 10 browsers | Start -> Done 4.2-4.5 s mean, 5.4 s max (one process: 10-11 s) |

Rule of thumb: one process per core you can spare, leaving one or two for
the system; `--num-procs 6` on 8 cores. Each process handles its own users
one calculation at a time; sessions are spread over the processes by the
operating system.

## Options worth knowing (`panel serve`, passed through by `serve.py`)

- `--num-procs N`: worker processes (Linux/macOS).
- `--allow-websocket-origin HOST`: the public host name (`hot.real-nbi.com`);
  without it the browser's live connection is refused (log: "Refusing websocket").
- `--address 127.0.0.1` behind a local proxy or tunnel; `0.0.0.0` if the
  outside connects to the port directly.
- `--liveness`: health check at `/liveness`.
- `--keep-alive 30000`: ping every 30 s (keeps proxies from closing idle connections).
- `--unused-session-lifetime 60000`: a session whose tab disconnected is kept
  60 s (survives a short network drop), then freed.
- `--admin`: Panel's monitoring page at `/admin` (sessions, memory) -- only
  behind a password or from the server itself.

## Load test

```bash
.venv/bin/python deploy/loadtest.py https://hot.real-nbi.com/app --users 5
```

Needs Google Chrome or Chromium on the machine running the test.

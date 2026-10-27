#!/usr/bin/env bash
# Update HOT-Jass web on the server to the latest main and restart it.
#   bash deploy/update.sh            (from anywhere; uses this checkout)
# SERVICE (default hot-jass; user or system unit) and PORT (default 8080) can be overridden:
#   SERVICE=hotjass-web PORT=5006 bash deploy/update.sh
set -euo pipefail
cd "$(dirname "$0")/.."
SERVICE="${SERVICE:-hot-jass}"
# a systemd *user* service (hot-jass.user.service) or a system one (hotjass-web.service)
if systemctl --user cat "$SERVICE" >/dev/null 2>&1; then
  restart() { systemctl --user restart "$SERVICE"; }; LOGCMD="journalctl --user -u $SERVICE -n 50"
else
  restart() { sudo systemctl restart "$SERVICE"; }; LOGCMD="journalctl -u $SERVICE -n 50"
fi
PORT="${PORT:-8080}"

git fetch --quiet origin
echo "Running: $(git log -1 --format='%h %s')"
if [ -z "$(git log --oneline HEAD..origin/main)" ]; then
  echo "Already up to date."; exit 0
fi
echo "New commits:"; git log --oneline HEAD..origin/main
git merge --ff-only origin/main                     # refuses if the checkout was edited locally
.venv/bin/pip install --quiet -r requirements.txt   # e.g. a new hotjass version pin
restart
echo -n "Waiting for the app"
for _ in $(seq 1 60); do
  if curl -fsS "http://127.0.0.1:$PORT/liveness" >/dev/null 2>&1; then
    echo; echo "OK: now running $(git log -1 --format='%h %s')"; exit 0
  fi
  echo -n "."; sleep 2
done
echo; echo "The app did not come back -- see: $LOGCMD"; exit 1

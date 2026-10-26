#!/usr/bin/env bash
# Update HOT-Jass web on the server to the latest main and restart it.
#   bash deploy/update.sh            (from anywhere; uses this checkout)
# SERVICE and PORT can be overridden: SERVICE=hotjass-web PORT=5006 bash deploy/update.sh
set -euo pipefail
cd "$(dirname "$0")/.."
SERVICE="${SERVICE:-hotjass-web}"
PORT="${PORT:-5006}"

git fetch --quiet origin
echo "Running: $(git log -1 --format='%h %s')"
if [ -z "$(git log --oneline HEAD..origin/main)" ]; then
  echo "Already up to date."; exit 0
fi
echo "New commits:"; git log --oneline HEAD..origin/main
git merge --ff-only origin/main                     # refuses if the checkout was edited locally
.venv/bin/pip install --quiet -r requirements.txt   # e.g. a new hotjass version pin
sudo systemctl restart "$SERVICE"
echo -n "Waiting for the app"
for _ in $(seq 1 60); do
  if curl -fsS "http://127.0.0.1:$PORT/liveness" >/dev/null 2>&1; then
    echo; echo "OK: now running $(git log -1 --format='%h %s')"; exit 0
  fi
  echo -n "."; sleep 2
done
echo; echo "The app did not come back -- see: journalctl -u $SERVICE -n 50"; exit 1

#!/usr/bin/env bash
# Read-only report on how HOT-Jass web runs on this server.
# Changes nothing, needs no sudo; anything it may not read is skipped.
#
#   bash server_info.sh > server_info.txt     (then send server_info.txt)
#
# Run it as the user that runs the app (or a user that can see its processes).

section() { printf '\n===== %s =====\n' "$1"; }
have() { command -v "$1" >/dev/null 2>&1; }

section "System"
date -u
uname -a
grep -E '^(PRETTY_NAME|VERSION_ID)=' /etc/os-release 2>/dev/null
echo "cores: $(nproc)"
free -h
df -h / 2>/dev/null | tail -1
uptime
echo "user: $(id -un)  groups: $(id -Gn)"
sudo -n true 2>/dev/null && echo "passwordless sudo: yes" || echo "passwordless sudo: no"

section "Python"
for p in python3 python3.12 python3.11 python3.10; do have "$p" && echo "$p: $($p --version 2>&1) ($(command -v $p))"; done

section "App processes (panel / bokeh / python)"
ps -eo pid,ppid,user,etime,rss,pcpu,args --sort=-rss 2>/dev/null \
  | awk 'NR==1 || /panel serve|bokeh serve|app\.py|hotjass/' | grep -v -E 'awk|server_info' | cut -c1-300

section "Per process: directory, code version, packages"
for pid in $(pgrep -f 'panel serve|bokeh serve|app\.py' 2>/dev/null); do
  cwd=$(readlink "/proc/$pid/cwd" 2>/dev/null) || continue
  exe=$(readlink "/proc/$pid/exe" 2>/dev/null)
  case "$exe" in *python*) ;; *) continue ;; esac      # skip shell wrappers
  echo "--- pid $pid  cwd=$cwd  exe=$exe"
  if [ -d "$cwd/.git" ]; then
    git -C "$cwd" log -1 --format='commit %h %ad %s' --date=short 2>/dev/null
    git -C "$cwd" remote -v 2>/dev/null | head -1
    git -C "$cwd" status --short 2>/dev/null | head -10
  fi
  # the interpreter as started (a venv's python is a symlink to the system one)
  py=$(tr '\0' '\n' < "/proc/$pid/cmdline" 2>/dev/null | head -1)
  case "$py" in /*) ;; *) py="$cwd/$py" ;; esac
  echo "interpreter: $py  ($("$py" -c 'import sys; print(sys.version.split()[0], sys.prefix)' 2>/dev/null))"
  "$py" -m pip list 2>/dev/null | grep -i -E '^(panel|bokeh|hotjass|numpy|matplotlib|pandas|tornado) '
  tr '\0' '\n' < "/proc/$pid/environ" 2>/dev/null | grep -E '^(MALLOC_|BOKEH_|PANEL_|PYTHON)' | head
done

section "systemd services"
systemctl list-units --type=service --all --no-pager 2>/dev/null \
  | grep -i -E 'panel|bokeh|jass|hot|nginx|caddy|apache|cloudflared|docker' | head -20
for u in $(systemctl list-units --type=service --all --no-legend --no-pager 2>/dev/null \
             | awk '{print $1}' | grep -i -E 'panel|bokeh|jass|hot'); do
  echo "--- $u"
  systemctl cat "$u" --no-pager 2>/dev/null
  journalctl -u "$u" -n 20 --no-pager 2>/dev/null
done

section "Docker"
have docker && docker ps --format '{{.Names}}  {{.Image}}  {{.Status}}  {{.Ports}}' 2>/dev/null \
  || echo "docker: not installed or no permission"

section "screen / tmux sessions"
have screen && screen -ls 2>/dev/null | head
have tmux && tmux ls 2>/dev/null | head

section "Web front: proxies and tunnels"
for t in nginx caddy apache2 cloudflared; do
  have "$t" && echo "$t: installed, $(systemctl is-active "$t" 2>/dev/null)"
done
ls /etc/nginx/sites-enabled 2>/dev/null && grep -h -E 'server_name|proxy_pass|listen|Upgrade|proxy_read_timeout' \
  /etc/nginx/sites-enabled/* 2>/dev/null | head -30
ls /etc/cloudflared 2>/dev/null && grep -h -E 'hostname|service' /etc/cloudflared/*.yml 2>/dev/null | head

section "Listening ports"
ss -ltnp 2>/dev/null | head -30

section "Local response time of the app"
for port in $(ss -ltnp 2>/dev/null | grep -E 'python|panel' | grep -oE ':[0-9]+ ' | tr -d ': ' | sort -u); do
  curl -s -o /dev/null -w "port $port /app: HTTP %{http_code} in %{time_total}s\n" "http://127.0.0.1:$port/app"
done

section "End"

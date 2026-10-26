"""Browser load test for HOT-Jass web: N simulated users in headless Chrome.

Each user opens the app, picks a machine preset, presses Start and waits for
"Done"; the test prints per user the page-ready time, preset -> geometry
update and Start -> Done, and (for a local server) the server's memory.

    python deploy/loadtest.py http://127.0.0.1:5006/app --users 5
    python deploy/loadtest.py https://hot.real-nbi.com/app --users 5 --rounds 2
    python deploy/loadtest.py http://127.0.0.1:5006/app --users 10 --hold 60 --server-pid 1234

Needs Google Chrome or Chromium (started headless by this script) and the
app's own venv (tornado comes with Bokeh). --server-pid sums the memory of
that process and its children (--num-procs workers); local servers only.
--hold keeps the sessions open that many seconds after Done (idle-memory check).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import statistics
import subprocess
import tempfile
import time
import urllib.request

from tornado.websocket import websocket_connect

PRESETS = ["MAST-U", "JET", "ITER", "NSTX-U", "ST40", "TCV", "PONTE", "T-15MD"]
CDP_PORT = 9333
JS = r"""
window.__deep = function(sel){const out=[];const walk=r=>{r.querySelectorAll(sel).forEach(e=>out.push(e));
  r.querySelectorAll('*').forEach(e=>{if(e.shadowRoot) walk(e.shadowRoot)});};walk(document);return out;};
window.__click = function(label){const b=__deep('button').find(e=>e.textContent.trim()===label);
  if(!b) return false; b.click(); return true;};
window.__status = function(){const t=__deep('p,em,strong,div').map(e=>e.textContent)
  .find(x=>/^(Step \d+\/\d+|Done|Calculation failed|Cancelled|Idle)/.test(x.trim().replace(/^[_*]+/,'')));
  return t? t.trim() : '';};
window.__geomsig = function(){const im=__deep('img').filter(e=>(e.src||'').startsWith('data:image/png')
  && e.naturalWidth===840 && e.naturalHeight===420); return im.length? im[0].src.length+':'+im[0].src.slice(-60) : '';};
"""


def rss_mb(pid: int) -> float:
    """Resident memory of pid and all its descendants [MB] (Linux)."""
    total, todo = 0, [pid]
    while todo:
        p = todo.pop()
        try:
            total += int(open(f"/proc/{p}/status").read().split("VmRSS:")[1].split()[0])
            todo += [int(c) for c in open(f"/proc/{p}/task/{p}/children").read().split()]
        except (OSError, IndexError, ValueError):
            pass
    return total / 1024.0


class Tab:
    def __init__(self, ws):
        self.ws, self.n, self.pending = ws, 0, {}

    async def call(self, method, **params):
        self.n += 1
        fut = asyncio.get_event_loop().create_future()
        self.pending[self.n] = fut
        await self.ws.write_message(json.dumps({"id": self.n, "method": method, "params": params}))
        return await fut

    async def reader(self):
        while True:
            msg = await self.ws.read_message()
            if msg is None:
                return
            d = json.loads(msg)
            if d.get("id") in self.pending:
                self.pending.pop(d["id"]).set_result(d.get("result"))

    async def js(self, expr):
        r = await self.call("Runtime.evaluate", expression=expr, returnByValue=True)
        return (r or {}).get("result", {}).get("value")

    async def wait_for(self, pred, timeout=300.0):
        t0 = time.perf_counter()
        while time.perf_counter() - t0 < timeout:
            try:
                if await self.js(pred):
                    return time.perf_counter() - t0
            except Exception:
                pass
            await asyncio.sleep(0.05)
        return None


async def open_tab(url):
    req = urllib.request.Request(f"http://127.0.0.1:{CDP_PORT}/json/new?about:blank", method="PUT")
    target = json.loads(urllib.request.urlopen(req).read())
    tab = Tab(await websocket_connect(target["webSocketDebuggerUrl"], max_message_size=1 << 28))
    asyncio.ensure_future(tab.reader())
    await tab.call("Page.enable")
    t0 = time.perf_counter()
    await tab.call("Page.navigate", url=url)
    ready = await tab.wait_for("(()=>{try{" + JS + "; return __deep('button').some(e=>e.textContent.trim()==='Start')}"
                               "catch(e){return false}})()", 60)
    await tab.js(JS)
    return tab, (time.perf_counter() - t0 if ready is not None else None)


async def user(tab, k, go):
    await go.wait()
    sig0 = await tab.js("__geomsig()")
    await tab.js(f"__click('{PRESETS[k % len(PRESETS)]}')")
    t_geom = await tab.wait_for(f"__geomsig() !== {json.dumps(sig0)}", 120)
    await asyncio.sleep(0.5)
    await tab.js("__click('Start')")
    t_done = await tab.wait_for("/Done|failed/.test(__status())", 300)
    return t_geom, t_done, (await tab.js("__status()")) or ""


def start_chrome():
    exe = next((shutil.which(c) for c in ("google-chrome", "chromium", "chromium-browser") if shutil.which(c)), None)
    if exe is None:
        raise SystemExit("Chrome/Chromium not found")
    prof = tempfile.mkdtemp(prefix="hj-loadtest-")
    proc = subprocess.Popen([exe, "--headless=new", f"--remote-debugging-port={CDP_PORT}", f"--user-data-dir={prof}",
                             "--no-first-run", "--disable-gpu", "--disable-renderer-backgrounding",
                             "--disable-background-timer-throttling", "--disable-backgrounding-occluded-windows",
                             "--window-size=1600,1000", "about:blank"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(100):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{CDP_PORT}/json/version")
            return proc
        except OSError:
            time.sleep(0.1)
    raise SystemExit("Chrome did not start")


def fmt(x):
    return f"{x:6.2f}s" if x is not None else "  none"


async def main(args):
    mem = (lambda: rss_mb(args.server_pid)) if args.server_pid else (lambda: float("nan"))
    print(f"server memory at start: {mem():.0f} MB")
    for rnd in range(1, args.rounds + 1):
        tabs, loads = [], []
        for _ in range(args.users):
            tab, t_load = await open_tab(args.url)
            if t_load is None:
                raise SystemExit("the app did not become ready in 60 s -- check the URL, and for a local "
                                 "server --allow-websocket-origin (the server log says 'Refusing websocket')")
            tabs.append(tab)
            loads.append(t_load)
        print(f"\nround {rnd}: {args.users} sessions open, server memory {mem():.0f} MB; page ready "
              + " ".join(fmt(x) for x in loads))
        await asyncio.sleep(2)
        go = asyncio.Event()
        jobs = [asyncio.ensure_future(user(t, k, go)) for k, t in enumerate(tabs)]
        go.set()
        res = await asyncio.gather(*jobs)
        for k, (g, d, st) in enumerate(res):
            print(f"  user {k} {PRESETS[k % len(PRESETS)]:7s} preset->geometry {fmt(g)}  Start->Done {fmt(d)}  [{st[:30]}]")
        done = [r[1] for r in res if r[1] is not None]
        print(f"  Start->Done mean {statistics.mean(done):.2f}s max {max(done):.2f}s; server memory {mem():.0f} MB"
              if done else "  no calculation finished")
        if args.hold:
            await asyncio.sleep(args.hold)
            print(f"  after {args.hold:.0f} s idle: server memory {mem():.0f} MB")
        for t in tabs:
            try:
                await t.call("Page.close")
            except Exception:
                pass
        await asyncio.sleep(5)
        print(f"  sessions closed: server memory {mem():.0f} MB")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("url")
    ap.add_argument("--users", type=int, default=5)
    ap.add_argument("--rounds", type=int, default=1)
    ap.add_argument("--hold", type=float, default=0.0, help="seconds to keep sessions open after Done")
    ap.add_argument("--server-pid", type=int, default=0, help="local server pid for memory (incl. workers)")
    a = ap.parse_args()
    chrome = start_chrome()
    try:
        asyncio.run(main(a))
    finally:
        chrome.terminate()

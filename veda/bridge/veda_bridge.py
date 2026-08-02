"""Vavast... VEDA bridge: lets the Python VAYU desktop join a VEDA device cloud.

Speaks veda/protocol v1 over WebSocket. Registers the desktop as a device,
forwards notify.push to the OS, runs OS-native consent gates, and executes
remote control actions (open_app/lock/sleep/restart/shutdown/set_volume/notify).

Usage:
    python veda/bridge/veda_bridge.py --relay ws://127.0.0.1:8080/ws --token vayu-dev
"""
import argparse
import asyncio
import ctypes
import json
import os
import platform
import socket
import subprocess
import sys
import uuid

import websockets


def audit(action: str, **meta) -> None:
    d = os.path.join(os.path.expanduser("~"), ".veda")
    os.makedirs(d, exist_ok=True)
    from datetime import datetime
    with open(os.path.join(d, "bridge-audit.log"), "a") as f:
        f.write(json.dumps({"ts": datetime.now().isoformat(), "action": action, **meta}) + "\n")


def notify(title: str, body: str) -> None:
    import subprocess
    t = title[:80].replace('"', ' ').replace('\r\n', ' ').replace('\n', ' ')
    b = body[:400].replace('"', ' ').replace('\r\n', ' ').replace('\n', ' ')
    subprocess.Popen(["powershell", "-NoProfile", "-Command",
                      f"$x=New-Object -ComObject WScript.Shell; $x.Popup('{b}',8,'VEDA - {t}',48)"])


def confirm(prompt: str, tag: str) -> bool:
    import subprocess
    clean = prompt.replace('"', ' ').replace('\r', ' ').replace('\n', ' ')[:200]
    r = subprocess.run(["powershell", "-NoProfile", "-Command",
                        f"$a=(New-Object -ComObject WScript.Shell).Popup('{clean}',0,'VEDA - {tag}',52); "
                        f"if($a -eq 6){{exit 0}}else{{exit 1}}"],
                       capture_output=True)
    return r.returncode == 0


async def open_app(path: str, url: str = "") -> str:
    target = url or path
    if platform.system() == "Windows":
        os.startfile(target)  # type: ignore[attr-defined]
    else:
        await asyncio.create_subprocess_shell(f'open -a "{target}"' if platform.system() == "Darwin" else
                                              f'gtk-launch "{target}" 2>/dev/null || xdg-open "{target}"')
    return f"launched {target}"


async def lock() -> str:
    await asyncio.sleep(0.05)
    if platform.system() == "Windows":
        ctypes.windll.user32.LockWorkStation()
    else:
        await asyncio.create_subprocess_shell("loginctl lock-session || true")
    return "locked"


async def sleep_now() -> str:
    await asyncio.sleep(0.05)
    if platform.system() == "Windows":
        ctypes.windll.powrprof.SetSuspendState(0, 1, 0)
    else:
        await asyncio.create_subprocess_shell("loginctl suspend || systemctl suspend")
    return "sleeping"


async def set_volume(v: int) -> str:
    k = max(0, min(100, int(v)))
    if platform.system() == "Windows":
        import subprocess
        subprocess.Popen(["powershell", "-NoProfile", "-Command",
                          f"$w=New-Object -ComObject WScript.Shell; for($i=0;$i -lt {k};$i+=2){{$w.SendKeys([char]175)}}"])
    else:
        await asyncio.create_subprocess_shell(f"pactl set-sink-volume @DEFAULT_SINK@ {k}% 2>/dev/null || amixer set Master {k}%")
    return f"volume {k}"


async def power(action: str, seconds: int) -> str:
    flag = "/r" if action == "restart" else "/s"
    if platform.system() == "Windows":
        await asyncio.create_subprocess_shell(f"shutdown {flag} /t {seconds}")
    else:
        await asyncio.create_subprocess_shell("sudo shutdown -r +1" if action == "restart" else "sudo shutdown -h +1")
    return f"{action} in {seconds}s"


async def run_command(cmd: str) -> str:
    proc = await asyncio.create_subprocess_shell(cmd,
                                                 stdout=asyncio.subprocess.PIPE,
                                                 stderr=asyncio.subprocess.PIPE)
    out, err = await proc.communicate()
    return f"{out.decode(errors='ignore')[:1000]}\n{err.decode(errors='ignore')[:1000]}".strip()


ASYNC_ACTIONS = {
    "open_app": lambda a: open_app(a.get("path", ""), a.get("url", "")),
    "lock": lambda a: lock(),
    "sleep": lambda a: sleep_now(),
    "set_volume": lambda a: set_volume(a.get("volume", 50)),
    "send_notify": lambda a: (notify(a.get("title", "VEDA"), a.get("body", "")), "sent")[1],
    "restart": lambda a: power("restart", int(a.get("seconds", 10))),
    "shutdown": lambda a: power("shutdown", int(a.get("seconds", 10))),
    "run_command": lambda a: run_command(a.get("command", "")),
}

CRITICAL = {"restart", "shutdown", "run_command"}


class Bridge:
    def __init__(self, relay: str, token: str):
        self.relay = relay
        self.token = token
        self.id = f"vayu-desktop-{socket.gethostname().lower().replace(' ','-')}"
        self.device = {
            "id": self.id,
            "name": socket.gethostname(),
            "platform": platform.system().lower(),
            "os": platform.platform(),
            "capabilities": sorted(set(list(ASYNC_ACTIONS.keys()) + ["notify.receive", "system.lock", "media.master"])),
        }

    async def run_forever(self) -> None:
        while True:
            try:
                async with websockets.connect(self.relay, max_size=1 << 20) as ws:
                    env = {"v": 1, "type": "hello", "from": self.id, "to": "relay",
                           "body": {"token": self.token, "device": self.device}}
                    await ws.send(json.dumps(env))
                    print(f"[veda-bridge] connected as {self.id}")
                    async for raw in ws:
                        try:
                            e = json.loads(raw)
                        except json.JSONDecodeError:
                            continue
                        await self.handle(e, ws)
            except Exception as exc:  # noqa: BLE001
                print(f"[veda-bridge] disconnected ({exc}); retrying in 3s")
                await asyncio.sleep(3)

    async def handle(self, e: dict, ws) -> None:
        t = e.get("type")
        if t == "notify.push":
            notify(e["body"].get("title", "VEDA"), e["body"].get("body", ""))
        elif t == "control.consent.request":
            cr = e["body"]
            ok = confirm(f"{cr.get('source','')} wants to {cr['action']} this device. Allow?", cr["action"])
            await ws.send(json.dumps({"v": 1, "type": "control.consent.result", "from": self.id,
                                      "to": cr.get("source", ""), "body": {"controlId": cr["controlId"], "ok": ok}}))
            audit("consent", controlId=cr["controlId"], action=cr["action"], ok=ok)
        elif t == "control.request":
            cr = e["body"]
            action = cr["action"]
            if action in CRITICAL and cr.get("consent") != "granted":
                ok = confirm(f"{e.get('from','')} wants to {action.upper()} {socket.gethostname()}. Permit?", action)
                if not ok:
                    await self.reply(ws, cr.get("source"), cr["controlId"], False, "denied")
                    audit("control.denied", controlId=cr["controlId"], action=action)
                    return
            result = await ASYNC_ACTIONS[action](cr.get("args", {}))
            await self.reply(ws, cr.get("source"), cr["controlId"], True, result)
            audit("control.ok", controlId=cr["controlId"], action=action, result=result)

    async def reply(self, ws, to: str, control_id: str, ok: bool, data: str = "") -> None:
        body = {"controlId": control_id, "ok": ok, "data": data} if ok else {"controlId": control_id, "ok": False, "error": data}
        await ws.send(json.dumps({"v": 1, "type": "control.result", "from": self.id, "to": to, "body": body}))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--relay", default=os.environ.get("VEDA_RELAY", "ws://127.0.0.1:8080/ws"))
    ap.add_argument("--token", default=os.environ.get("VEDA_TOKEN", "vayu-dev"))
    args = ap.parse_args()
    asyncio.run(Bridge(args.relay, args.token).run_forever())


if __name__ == "__main__":
    pass  # run via: python -m asyncio veda_bridge  (see main above)
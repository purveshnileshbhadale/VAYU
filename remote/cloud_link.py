"""CloudLink — control any VAYU device from anywhere (no same-WiFi needed).

Uses the free ntfy.sh pub/sub relay: every device pair shares a "pair code";
the code derives a private topic and an auth hash. The laptop and phone both
subscribe to the topic (SSE on desktop, WebSocket in the phone's browser) and
send each other tool calls + results. Works over the internet, no accounts.

Directions:
    laptop -> phone : send_tool("phone", name, args, ...)  (e.g. open_app, set_alarm)
    phone  -> laptop: the laptop's on_tool handler receives desktop_* tool calls
                      and executes them locally (mapped in main.py).
"""

import hashlib
import json
import secrets
import threading
import time

import requests

NTFY = "https://ntfy.sh"
_SSE_TIMEOUT = 90  # ntfy sends SSE heartbeats; reconnect if the stream dies

_GLOBAL = {"link": None}


def set_global_link(link):
    _GLOBAL["link"] = link


def get_global_link():
    return _GLOBAL["link"]


def topic_for(pair_code: str) -> str:
    h = hashlib.sha256(("vayu-link:" + pair_code.strip()).encode()).hexdigest()
    return "vayu-link-" + h[:16]


def auth_for(pair_code: str) -> str:
    return hashlib.sha256(("vayu-auth:" + pair_code.strip()).encode()).hexdigest()[:16]


class CloudLink:
    """Device side of the relay. Start it, then send_tool()/publish() as needed.

    on_tool(name, args) -> str : called (in a worker thread) for incoming tool
                                 calls targeted at this device.
    """

    def __init__(self, pair_code, me="laptop", on_tool=None):
        self.pair = (pair_code or "").strip()
        self.me = me
        self.on_tool = on_tool
        self.topic = topic_for(self.pair)
        self.auth = auth_for(self.pair)
        self._stop = threading.Event()
        self._thread = None
        self._pending = {}
        self._pending_lock = threading.Lock()

    # ---------- publish ----------

    def publish(self, payload: dict):
        payload.setdefault("auth", self.auth)
        try:
            r = requests.post(f"{NTFY}/{self.topic}", json=payload, timeout=15)
            return None if r.ok else f"relay HTTP {r.status_code}"
        except Exception as e:
            return str(e)

    def send_tool(self, target, name, args=None, callback=None, timeout=30):
        """Fire a tool call at the other device. With callback, the matching
        result is delivered to it; otherwise returns the result (or error)."""
        rid = secrets.token_hex(8)
        payload = {
            "to": target, "from": self.me, "auth": self.auth,
            "type": "tool", "id": rid, "name": name, "args": args or {},
        }
        if callback is None:
            holder = {}
            ev = threading.Event()

            def _cb(res, err):
                holder["res"], holder["err"] = res, err
                ev.set()

            with self._pending_lock:
                self._pending[rid] = _cb
            err = self.publish(payload)
            if err:
                with self._pending_lock:
                    self._pending.pop(rid, None)
                return {"ok": False, "error": err}
            ev.wait(timeout)
            with self._pending_lock:
                self._pending.pop(rid, None)
            if "res" in holder:
                return {"ok": True, "result": holder["res"]}
            return {"ok": False, "error": "Phone did not answer (is its Cloud Link ON?)"}
        else:
            with self._pending_lock:
                self._pending[rid] = callback
            return self.publish(payload)

    # ---------- subscribe ----------

    def _handle(self, msg):
        if not isinstance(msg, dict) or msg.get("auth") != self.auth:
            return
        typ = msg.get("type")
        target = msg.get("to")
        if typ == "tool" and target == self.me and self.on_tool:
            threading.Thread(target=self._run_tool, args=(msg,), daemon=True).start()
        elif typ == "result" and target == self.me:
            rid = msg.get("id")
            cb = None
            with self._pending_lock:
                cb = self._pending.pop(rid, None)
            if cb:
                cb(msg.get("result"), msg.get("error"))

    def _run_tool(self, msg):
        rid = msg.get("id")
        name = msg.get("name")
        args = msg.get("args") or {}
        try:
            result = self.on_tool(name, args)
            if isinstance(result, (dict, list)):
                result = json.dumps(result)
            self.publish({"to": msg.get("from"), "from": self.me, "auth": self.auth,
                          "type": "result", "id": rid, "result": str(result)})
        except Exception as e:
            self.publish({"to": msg.get("from"), "from": self.me, "auth": self.auth,
                          "type": "result", "id": rid, "error": str(e)})

    def _listen(self):
        while not self._stop.is_set():
            try:
                r = requests.get(
                    f"{NTFY}/{self.topic}/sse",
                    headers={"Accept": "text/event-stream"},
                    timeout=_SSE_TIMEOUT,
                    stream=True,
                )
                r.raise_for_status()
                for raw in r.iter_lines(decode_unicode=True):
                    if self._stop.is_set():
                        break
                    if not raw or not raw.startswith("data:"):
                        continue
                    try:
                        event = json.loads(raw[5:].strip())
                    except Exception:
                        continue
                    if event.get("event") == "message":
                        try:
                            self._handle(json.loads(event.get("message", "{}")))
                        except Exception:
                            pass
            except Exception:
                pass
            if not self._stop.is_set():
                time.sleep(3)

    def start(self):
        if self._thread or not self.pair:
            return False
        self._thread = threading.Thread(target=self._listen, daemon=True)
        self._thread.start()
        return True

    def stop(self):
        self._stop.set()
        self._thread = None


def main():
    import sys
    code = sys.argv[1] if len(sys.argv) > 1 else input("Pair code: ")
    link = CloudLink(code, me="laptop", on_tool=lambda n, a: f"echo:{n} {a}")
    link.start()
    print(f"Listening on topic {link.topic}")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        link.stop()


if __name__ == "__main__":
    main()

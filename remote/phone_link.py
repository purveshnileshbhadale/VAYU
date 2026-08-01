"""PhoneLink — lets the VAYU desktop app control a phone running VAYU Android.

The phone app runs a small HTTP server (port 8080) when "Phone link" is ON.
This module is the client that talks to it over LAN.

API:
    send(host, port, pin, tool, args) -> dict   (single tool call)
    status(host, port, pin) -> dict             (phone sysinfo)
"""

import json

import requests

_TIMEOUT = 10


def _base(host, port):
    if "://" not in host:
        host = "http://" + host
    return host.rstrip("/") + (f":{port}" if port else "")


def _auth(base, pin):
    r = requests.get(f"{base}/auth", params={"pin": pin or "8421"}, timeout=_TIMEOUT)
    if r.status_code != 200:
        raise RuntimeError(f"PIN rejected by phone ({r.status_code})")
    return r.json().get("token", "")


def send(host, port=8080, pin="8421", tool="status", args=None):
    """Send a single tool call to the phone. Returns the parsed JSON response."""
    base = _base(host, port)
    token = _auth(base, pin)
    r = requests.post(
        f"{base}/tool",
        params={"token": token},
        headers={"Content-Type": "application/json"},
        json={"name": tool, "args": args or {}},
        timeout=_TIMEOUT,
    )
    if r.status_code == 401:
        raise RuntimeError("Phone rejected the session token")
    return r.json()


def status(host, port=8080, pin="8421"):
    base = _base(host, port)
    token = _auth(base, pin)
    r = requests.get(f"{base}/status", params={"token": token}, timeout=_TIMEOUT)
    return r.json()

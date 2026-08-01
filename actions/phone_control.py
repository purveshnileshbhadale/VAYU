"""VAYU Desktop → phone control action.

Lets the user control their Android phone (running VAYU Android) by voice
from the desktop. Talks to the phone's built-in phone-link server.

Tool name: phone_control
Parameters:
    action: one of the phone's runTool names (open_app, send_sms, make_call,
            open_url, navigate, set_alarm, set_timer, set_volume, media,
            flashlight, set_wifi, set_bluetooth, set_brightness, rotate, dnd,
            vibrate, share, clipboard, battery, device_info, list_apps,
            open_settings, status)
    args:   JSON object of that tool's parameters
"""

import json
import os

from remote.phone_link import send, status

_CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "config", "api_keys.json")

_ACTION_LABELS = {
    "open_app": "opening an app",
    "send_sms": "sending an SMS",
    "make_call": "making a call",
    "open_url": "opening a website",
    "navigate": "starting navigation",
    "set_alarm": "setting an alarm",
    "set_timer": "setting a timer",
    "set_volume": "setting volume",
    "media": "controlling media",
    "flashlight": "toggling the flashlight",
    "set_wifi": "toggling WiFi",
    "set_bluetooth": "toggling Bluetooth",
    "set_brightness": "setting brightness",
    "rotate": "toggling auto-rotate",
    "dnd": "toggling Do Not Disturb",
    "vibrate": "vibrating the phone",
    "share": "sharing text",
    "clipboard": "using the clipboard",
    "battery": "checking battery",
    "device_info": "reading device info",
    "list_apps": "listing apps",
    "open_settings": "opening settings",
}


def _load_config():
    try:
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def phone_control(parameters=None, response=None, player=None, session_memory=None):
    parameters = parameters or {}
    action = str(parameters.get("action", "")).strip().lower()
    if not action:
        return "Please specify a phone action (e.g. open_app, set_alarm, status)."

    cfg = _load_config()
    host = str(cfg.get("phone_ip", "")).strip()
    port = int(cfg.get("phone_port", 8080) or 8080)
    pin = str(cfg.get("phone_pin", "8421")).strip()

    if not host:
        return ("No phone linked yet. Ask the user to open Settings on this app, "
                "enter the Phone IP shown on the phone's VAYU app (Settings → "
                "Remote Link), then set the Phone PIN.")

    args = parameters.get("args") or {}

    try:
        if action == "status":
            data = status(host, port, pin)
            return _describe(data)

        if action not in _ACTION_LABELS and action not in {
                "tool", "command", "shell"}:
            # direct passthrough of any phone tool name
            pass

        result = send(host, port, pin, action, args)
        if not result.get("ok"):
            return f"Phone action failed: {result.get('error', 'unknown error')}"
        label = _ACTION_LABELS.get(action, action)
        return f"{label.capitalize()} — {result.get('result', 'done')}"

    except Exception as e:
        return (f"Could not reach the phone ({e}). Make sure the phone and this "
                "computer are on the same network, the phone's VAYU app has "
                "'Phone link' ON, and Settings → Phone IP is correct.")


def _describe(data):
    if not isinstance(data, dict):
        return f"Phone status: {data}"
    parts = [
        f"Battery {data.get('batteryPct', '--')}%",
        "charging" if data.get("charging") else "not charging",
        f"RAM {data.get('ramPct', '--')}% used",
        f"Network {data.get('network', '--')}",
        f"{data.get('device', 'device')} on Android {data.get('android', '--')}",
        f"uptime {data.get('uptime', '--')}",
    ]
    if data.get("phoneLink"):
        parts.append(f"phone link {data['phoneLink']}")
    return ", ".join(parts) + "."

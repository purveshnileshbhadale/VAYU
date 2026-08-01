import subprocess
import sys
import json
import os
import shutil
from pathlib import Path


def get_base_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE_DIR = get_base_dir()


def _get_gemini_key() -> str | None:
    try:
        p = BASE_DIR / "config" / "api_keys.json"
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8")).get("gemini_api_key")
    except Exception:
        pass
    return None


def _find_opencode() -> str | None:
    for c in [
        shutil.which("opencode"),
        shutil.which("opencode.cmd"),
        shutil.which("opencode.exe"),
        os.path.expanduser("~/AppData/Roaming/npm/opencode.cmd"),
        str(BASE_DIR / "node_modules" / "opencode-ai" / "bin" / "opencode.exe"),
        "C:\\Program Files\\nodejs\\opencode.cmd",
    ]:
        if c and os.path.isfile(c):
            return c
    return None


def opencode_bridge(parameters, response=None, player=None, session_memory=None, speak=None) -> str:
    p = parameters or {}
    action = p.get("action", "run").strip().lower()
    prompt = p.get("prompt", "").strip()
    directory = p.get("directory", str(BASE_DIR)).strip()
    model = p.get("model", "opencode/deepseek-v4-flash-free").strip()

    exe = _find_opencode()
    if action == "check":
        if exe:
            return f"OpenCode ready: {exe}"
        return "OpenCode not installed. Say: install opencode"

    if action == "install":
        try:
            npm = shutil.which("npm") or shutil.which("npm.cmd")
            if not npm:
                return "Node.js not found. Install from https://nodejs.org"
            r = subprocess.run([npm, "install", "-g", "opencode-ai"],
                               capture_output=True, text=True, timeout=120)
            return "OpenCode installed!" if r.returncode == 0 else f"Failed: {r.stderr[:200]}"
        except Exception as e:
            return f"Error: {e}"

    if not exe:
        return "OpenCode not installed. Use action='install'."

    api_key = _get_gemini_key()
    env_str = ""
    if api_key:
        env_str = f"set GOOGLE_GENERATIVE_AI_API_KEY={api_key} && "

    prompt_escaped = prompt.replace('"', "'")
    if action == "run":
        cmd = f'start cmd /k "{env_str}{exe} run --model {model} --dangerously-skip-permissions --format json "{prompt_escaped}""'
        subprocess.Popen(cmd, shell=True, cwd=directory)
        return f"OpenCode opened in new terminal for: {prompt[:100]}"

    if action == "tui":
        cmd = f'start cmd /k "{env_str}cd /d {directory} && {exe}"'
        subprocess.Popen(cmd, shell=True)
        return "OpenCode TUI opened in new terminal."

    return f"Unknown action: '{action}'. Try: run, tui, check, install"

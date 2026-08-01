import json
import sys
from pathlib import Path
from enum import Enum


class Mode(Enum):
    DEFAULT = "default"
    RESEARCH = "research"
    PROFESSIONAL = "professional"


MODE_LABELS = {
    Mode.DEFAULT: "Default",
    Mode.RESEARCH: "Research",
    Mode.PROFESSIONAL: "Professional",
}

MODE_DESCRIPTIONS = {
    Mode.DEFAULT: "Balanced assistant with all tools available",
    Mode.RESEARCH: "Deep research mode — web search, code, vision, file analysis",
    Mode.PROFESSIONAL: "Productivity mode — email, calendar, system, office tools",
}


def get_config_path():
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).parent
    else:
        base = Path(__file__).resolve().parent.parent
    return base / "config" / "api_keys.json"


def get_current_mode() -> Mode:
    try:
        path = get_config_path()
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            mode_str = data.get("current_mode", "default")
            return Mode(mode_str)
    except Exception:
        pass
    return Mode.DEFAULT


def set_current_mode(mode: Mode) -> bool:
    try:
        path = get_config_path()
        data = {}
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
        data["current_mode"] = mode.value
        path.write_text(json.dumps(data, indent=4), encoding="utf-8")
        return True
    except Exception as e:
        print(f"[Modes] Failed to set mode: {e}")
        return False


RESEARCH_TOOLS = {
    "web_search", "browser_control", "code_helper", "code_agent", "opencode_bridge", "dev_agent",
    "file_processor", "screen_process", "qr_tools", "agent_task",
    "system_info", "flight_finder", "clipboard_read", "clipboard_write",
    "open_app", "weather_report", "cmd_control", "youtube_video",
    "game_updater", "save_memory",
}

PROFESSIONAL_TOOLS = {
    "email_client", "calendar_notes", "reminder", "timer_alarm",
    "system_info", "power_mgmt", "window_manager", "clipboard_read",
    "clipboard_write", "auto_start", "computer_settings", "desktop_control",
    "media_keys", "wifi_bt_control", "open_app", "weather_report",
    "file_controller", "send_message", "cmd_control", "audio_recorder",
    "computer_control", "qr_tools", "save_memory", "shutdown_vayu",
}


def get_tool_whitelist(mode: Mode) -> set | None:
    if mode == Mode.RESEARCH:
        return RESEARCH_TOOLS
    if mode == Mode.PROFESSIONAL:
        return PROFESSIONAL_TOOLS
    return None


def get_prompt_path(mode: Mode) -> str:
    base = Path(__file__).resolve().parent
    if mode == Mode.RESEARCH:
        return str(base / "prompt_research.txt")
    if mode == Mode.PROFESSIONAL:
        return str(base / "prompt_professional.txt")
    return str(base / "prompt.txt")

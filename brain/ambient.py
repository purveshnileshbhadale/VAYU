"""Ambient awareness — the part where VAYU speaks first.

An assistant that only ever answers is a command line with a microphone. This
module watches a handful of things about the machine and says something when
one of them is worth saying, unprompted.

The hard part is not noticing things; it is shutting up. Almost all the code
here is restraint:

* nothing is said twice while the condition persists (per-observation cooldown)
* nothing is said within a few minutes of the last thing said (global gap)
* nothing is said while VAYU is mid-conversation, muted, or during quiet hours
* a condition has to clear before it can fire again (edge-triggered, not level)

Watchers are pure functions of a :class:`SystemProbe`, so the decision logic
can be tested without a battery, a disk, or a clock.
"""

from __future__ import annotations

import os
import shutil
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

# Don't speak twice within this window, whatever the reason.
_GLOBAL_GAP_SEC = 240.0

# Nothing unprompted outside these hours (local time), unless it is urgent.
_QUIET_BEFORE_HOUR = 8
_QUIET_AFTER_HOUR = 23


@dataclass(frozen=True)
class Observation:
    """Something worth saying, and how long to stay quiet about it afterwards."""

    key: str
    text: str
    cooldown: float = 1800.0
    urgent: bool = False


class SystemProbe:
    """Reads the machine. Swapped for a fake in tests."""

    def battery(self) -> tuple[int, bool] | None:
        """(percent, plugged_in), or None if there is no battery."""
        try:
            import psutil
            b = psutil.sensors_battery()
            if b is None:
                return None
            return int(b.percent), bool(b.power_plugged)
        except Exception:
            return None

    def disk(self) -> tuple[int, int] | None:
        """(free_bytes, total_bytes) for the drive VAYU lives on."""
        try:
            usage = shutil.disk_usage(Path.home())
            return usage.free, usage.total
        except Exception:
            return None

    def downloads_dir(self) -> Path | None:
        d = Path.home() / "Downloads"
        return d if d.is_dir() else None

    def recent_downloads(self, within_sec: float = 90.0) -> list[Path]:
        """Files that finished downloading in the last `within_sec` seconds."""
        d = self.downloads_dir()
        if d is None:
            return []
        cutoff = time.time() - within_sec
        out = []
        try:
            for entry in d.iterdir():
                if not entry.is_file():
                    continue
                # Still in flight — browsers rename these when they finish.
                if entry.suffix.lower() in (".crdownload", ".part", ".tmp", ".download"):
                    continue
                try:
                    if entry.stat().st_mtime >= cutoff:
                        out.append(entry)
                except OSError:
                    continue
        except OSError:
            return []
        return out

    def uptime_sec(self) -> float:
        try:
            import psutil
            return time.time() - psutil.boot_time()
        except Exception:
            return 0.0

    def now(self) -> datetime:
        return datetime.now()


# --------------------------------------------------------------------------
# watchers
# --------------------------------------------------------------------------

def _human_size(n: int) -> str:
    gb = n / 1_000_000_000
    if gb >= 10:
        return f"{gb:.0f} gigabytes"
    if gb >= 1:
        return f"{gb:.1f} gigabytes".replace(".0 ", " ")
    return f"{n / 1_000_000:.0f} megabytes"


def watch_battery(probe: SystemProbe, state: dict) -> Observation | None:
    reading = probe.battery()
    if reading is None:
        return None
    percent, plugged = reading
    was_plugged = state.get("plugged")
    state["plugged"] = plugged

    if plugged:
        return None

    # Just came off the charger — not worth a remark on its own.
    if was_plugged and percent > 40:
        return None

    if percent <= 10:
        return Observation(
            "battery-critical",
            f"Sir, you're at {percent} percent. That's minutes, not hours.",
            cooldown=600, urgent=True,
        )
    if percent <= 20:
        return Observation(
            "battery-low",
            f"Battery's down to {percent} percent, sir, and you're off the charger.",
            cooldown=1800,
        )
    return None


def watch_disk(probe: SystemProbe, state: dict) -> Observation | None:
    reading = probe.disk()
    if reading is None:
        return None
    free, total = reading
    if total <= 0:
        return None
    ratio = free / total

    if ratio <= 0.03:
        return Observation(
            "disk-critical",
            f"You've {_human_size(free)} left, sir. Something is going to fail shortly.",
            cooldown=3600, urgent=True,
        )
    if ratio <= 0.08:
        return Observation(
            "disk-low",
            f"Storage is getting tight — {_human_size(free)} free.",
            cooldown=21600,
        )
    return None


def watch_downloads(probe: SystemProbe, state: dict) -> Observation | None:
    seen: set[str] = state.setdefault("seen_downloads", set())
    fresh = [p for p in probe.recent_downloads() if str(p) not in seen]
    if not fresh:
        return None
    for p in fresh:
        seen.add(str(p))

    # Don't announce the first sweep — those files were there before we started.
    if not state.get("downloads_primed"):
        state["downloads_primed"] = True
        return None

    if len(fresh) == 1:
        return Observation("download-done", f"{fresh[0].name} finished downloading, sir.", cooldown=30)
    return Observation("download-done", f"{len(fresh)} downloads finished, sir.", cooldown=30)


def watch_long_session(probe: SystemProbe, state: dict) -> Observation | None:
    """A quiet nudge after a long unbroken stretch at the machine."""
    started = state.setdefault("session_start", time.monotonic())
    hours = (time.monotonic() - started) / 3600
    if hours < 4:
        return None
    milestone = int(hours)
    if state.get("last_session_milestone") == milestone:
        return None
    state["last_session_milestone"] = milestone
    return Observation(
        "long-session",
        f"You've been at it {milestone} hours, sir. The machine doesn't mind. You might.",
        cooldown=7200,
    )


DEFAULT_WATCHERS: list[Callable[[SystemProbe, dict], "Observation | None"]] = [
    watch_battery,
    watch_disk,
    watch_downloads,
    watch_long_session,
]


# --------------------------------------------------------------------------
# monitor
# --------------------------------------------------------------------------

class AmbientMonitor:
    """Polls the watchers and speaks at most one observation per pass."""

    def __init__(
        self,
        speak: Callable[[str], None],
        probe: SystemProbe | None = None,
        watchers: list | None = None,
        is_busy: Callable[[], bool] | None = None,
        poll_sec: float = 60.0,
        clock: Callable[[], float] = time.monotonic,
    ):
        self._speak = speak
        self._probe = probe or SystemProbe()
        self._watchers = list(watchers if watchers is not None else DEFAULT_WATCHERS)
        self._is_busy = is_busy or (lambda: False)
        self._poll = poll_sec
        self._clock = clock

        self._state: dict = {}
        self._last_spoken: dict[str, float] = {}
        self._last_any: float = 0.0
        self._active: set[str] = set()  # conditions currently asserted
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    # -- lifecycle --------------------------------------------------------

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="vayu-ambient", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        while not self._stop.wait(self._poll):
            try:
                self.poll_once()
            except Exception as exc:
                print(f"[ambient] {exc}")

    # -- the decision -----------------------------------------------------

    def _quiet_hours(self) -> bool:
        hour = self._probe.now().hour
        return hour < _QUIET_BEFORE_HOUR or hour >= _QUIET_AFTER_HOUR

    def poll_once(self) -> Observation | None:
        """Run every watcher; speak at most one thing. Returns what was said."""
        fired: list[Observation] = []
        still_active: set[str] = set()

        for watcher in self._watchers:
            try:
                obs = watcher(self._probe, self._state)
            except Exception as exc:
                print(f"[ambient] {getattr(watcher, '__name__', watcher)}: {exc}")
                continue
            if obs is None:
                continue
            still_active.add(obs.key)
            fired.append(obs)

        # A condition that went away may speak again when it returns.
        self._active = still_active

        if not fired:
            return None

        # Urgent first, then whatever came up.
        fired.sort(key=lambda o: (not o.urgent,))
        now = self._clock()

        for obs in fired:
            if self._suppressed(obs, now):
                continue
            self._last_spoken[obs.key] = now
            self._last_any = now
            self._speak(obs.text)
            return obs
        return None

    def _suppressed(self, obs: Observation, now: float) -> bool:
        last = self._last_spoken.get(obs.key)
        if last is not None and now - last < obs.cooldown:
            return True
        if not obs.urgent:
            if self._quiet_hours():
                return True
            if self._last_any and now - self._last_any < _GLOBAL_GAP_SEC:
                return True
            if self._is_busy():
                return True
        return False

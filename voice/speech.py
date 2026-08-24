"""Interruptible, streaming speech.

The difference between an assistant that feels alive and one that feels like a
kiosk is mostly this file. Three properties matter:

* **Interruptible.** ``stop()`` cuts the current utterance off mid-word and
  drops anything queued behind it, so talking over VAYU works the way talking
  over a person works.
* **Streaming.** ``feed()`` takes partial text as a model produces it and
  starts speaking at the first complete sentence instead of waiting for the
  whole reply. Perceived latency drops from "however long the reply took" to
  "however long the first sentence took".
* **Non-blocking.** Speech runs on its own worker thread; callers enqueue and
  carry on.

Backends are tried in order of how well they support the above. Anything that
cannot be stopped promptly is a last resort, because an assistant that has to
finish its sentence is the thing we are trying to get rid of.

Usage::

    from voice.speech import speech

    speech.say("Good evening, sir.")        # enqueue
    speech.say("Actually —", interrupt=True) # cut in
    for chunk in model_stream:               # stream as it generates
        speech.feed(chunk)
    speech.end_stream()
    speech.stop()                            # barge-in
"""

from __future__ import annotations

import json
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Callable

IDLE = "idle"
SPEAKING = "speaking"

# Emit a clause early if the model is producing a long run-on; keeps the first
# audio starting quickly instead of waiting for a far-off full stop.
_CLAUSE_FLUSH_CHARS = 140

# Terminator, optional closing quote/bracket, then whitespace or end of buffer.
_TERMINATOR = re.compile(r'[.!?…]+["\'”’)\]]*(\s+|$)')

# Tokens that end in "." without ending a sentence.
_ABBREVIATIONS = {
    "mr", "mrs", "ms", "dr", "prof", "sr", "jr", "st", "vs", "etc", "eg", "ie",
    "approx", "dept", "inc", "ltd", "no", "fig", "al", "cf", "pp", "vol",
}


def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


def _config() -> dict:
    try:
        return json.loads((_base_dir() / "config" / "api_keys.json").read_text(encoding="utf-8"))
    except Exception:
        return {}


# --------------------------------------------------------------------------
# sentence splitting
# --------------------------------------------------------------------------

def _ends_with_abbreviation(text: str) -> bool:
    """True if text ends in something like 'Dr.' or an initial like 'J.'."""
    tail = re.search(r'([A-Za-z.]+)\.$', text.strip())
    if not tail:
        return False
    word = tail.group(1).replace(".", "").lower()
    return word in _ABBREVIATIONS or len(word) == 1


def split_stream(buf: str) -> tuple[list[str], str]:
    """Split a streaming buffer into complete sentences plus a remainder.

    The remainder is text we are not yet confident is a whole thought, and is
    kept back until more arrives (or ``end_stream`` flushes it).
    """
    out: list[str] = []
    pos = 0

    while pos < len(buf):
        chunk = buf[pos:]

        # A newline is always a safe boundary.
        nl = chunk.find("\n")
        match = _TERMINATOR.search(chunk)

        if nl != -1 and (match is None or nl < match.start()):
            piece = chunk[:nl].strip()
            if piece:
                out.append(piece)
            pos += nl + 1
            continue

        if match is None:
            break

        end = match.end()
        candidate = chunk[:end].strip()

        # "3.5" or "Dr. Strange" — not a boundary; keep scanning past it.
        if _ends_with_abbreviation(candidate):
            nxt = _TERMINATOR.search(chunk, end)
            if nxt is None:
                break
            end = nxt.end()
            candidate = chunk[:end].strip()

        if candidate:
            out.append(candidate)
        pos += end

    remainder = buf[pos:]

    # Long run-on with no terminator in sight: break at the last clause mark so
    # speech can start rather than waiting for a full stop that may be far off.
    if not out and len(remainder) >= _CLAUSE_FLUSH_CHARS:
        cut = max(remainder.rfind(", "), remainder.rfind("; "), remainder.rfind(": "))
        if cut > 40:
            out.append(remainder[:cut + 1].strip())
            remainder = remainder[cut + 1:]

    return out, remainder.lstrip() if out else remainder


def clean_for_speech(text: str) -> str:
    """Strip markup that should not be read aloud."""
    text = re.sub(r'```.*?```', ' ', text, flags=re.S)      # code fences
    text = re.sub(r'`([^`]*)`', r'\1', text)                 # inline code
    text = re.sub(r'\*\*([^*]*)\*\*', r'\1', text)           # bold
    text = re.sub(r'(?<!\w)\*([^*]+)\*(?!\w)', r'\1', text)  # italics
    text = re.sub(r'^\s*[-*•]\s+', '', text, flags=re.M)
    text = re.sub(r'https?://\S+', 'the link', text)
    text = re.sub(r'[ \t]+', ' ', text)
    # Removing a block can leave a line holding nothing but its own whitespace.
    text = re.sub(r'\n[ \t]*(?=\n)', '', text)
    return text.strip()


# --------------------------------------------------------------------------
# backends
# --------------------------------------------------------------------------

class _Backend:
    """A way of getting words out of a speaker.

    ``speak`` blocks until the utterance finishes, and must return promptly
    once ``cancel`` is set — that promptness is what barge-in is made of.
    """

    name = "none"

    def available(self) -> bool:
        return False

    def speak(self, text: str, cancel: threading.Event) -> bool:
        return False


class Sapi5Backend(_Backend):
    """Windows SAPI5 over COM. Async speak + purge, so barge-in is immediate."""

    name = "sapi5"
    _SPF_ASYNC = 1
    _SPF_PURGE = 2
    _DONE = 1  # SPRS_DONE

    def __init__(self):
        self._voice = None

    def available(self) -> bool:
        return sys.platform == "win32"

    def _ensure(self):
        if self._voice is not None:
            return
        import pythoncom
        import win32com.client
        pythoncom.CoInitialize()
        voice = win32com.client.Dispatch("SAPI.SpVoice")
        cfg = _config()
        try:
            voice.Rate = int(cfg.get("tts_rate", 1))
        except Exception:
            pass
        wanted = str(cfg.get("tts_voice", "")).lower()
        if wanted:
            try:
                for token in voice.GetVoices():
                    if wanted in token.GetDescription().lower():
                        voice.Voice = token
                        break
            except Exception:
                pass
        self._voice = voice

    def speak(self, text: str, cancel: threading.Event) -> bool:
        self._ensure()
        self._voice.Speak(text, self._SPF_ASYNC)
        while True:
            if cancel.is_set():
                self._voice.Speak("", self._SPF_PURGE | self._SPF_ASYNC)
                return False
            try:
                if self._voice.Status.RunningState == self._DONE:
                    return True
            except Exception:
                return True
            time.sleep(0.02)


class ProcessBackend(_Backend):
    """Speaks by spawning a binary we hold a handle to, so we can kill it.

    Text is passed as an argv element or an environment variable, never
    interpolated into a shell string.
    """

    def __init__(self, name: str, argv: Callable[[str], list[str]],
                 env: Callable[[str], dict] | None = None, probe: str | None = None):
        self.name = name
        self._argv = argv
        self._env = env
        self._probe = probe

    def available(self) -> bool:
        return shutil.which(self._probe or self.name) is not None

    def speak(self, text: str, cancel: threading.Event) -> bool:
        env = None
        if self._env:
            env = {**os.environ, **self._env(text)}
        proc = subprocess.Popen(
            self._argv(text),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
        )
        try:
            while proc.poll() is None:
                if cancel.is_set():
                    proc.terminate()
                    try:
                        proc.wait(timeout=1.5)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                    return False
                time.sleep(0.02)
            return proc.returncode == 0
        finally:
            if proc.poll() is None:
                proc.kill()


_PS_SPEAK = (
    "Add-Type -AssemblyName System.Speech; "
    "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
    "try { $s.Rate = [int]$env:VAYU_TTS_RATE } catch {}; "
    "$s.Speak($env:VAYU_TTS_TEXT)"
)


class Pyttsx3Backend(_Backend):
    """Last resort. Stops between utterances rather than mid-word."""

    name = "pyttsx3"

    def available(self) -> bool:
        try:
            import pyttsx3  # noqa: F401
            return True
        except Exception:
            return False

    def speak(self, text: str, cancel: threading.Event) -> bool:
        import pyttsx3
        engine = pyttsx3.init()
        done = threading.Event()

        def _run():
            try:
                engine.say(text)
                engine.runAndWait()
            except Exception:
                pass
            finally:
                done.set()

        threading.Thread(target=_run, daemon=True).start()
        while not done.is_set():
            if cancel.is_set():
                try:
                    engine.stop()
                except Exception:
                    pass
                return False
            time.sleep(0.03)
        return True


def _build_backends() -> list[_Backend]:
    """Preferred order per platform, best barge-in first."""
    rate = int(_config().get("tts_rate", 1) or 0)

    if sys.platform == "win32":
        return [
            Sapi5Backend(),
            ProcessBackend(
                "powershell",
                lambda _t: ["powershell", "-NoProfile", "-NonInteractive", "-Command", _PS_SPEAK],
                env=lambda t: {"VAYU_TTS_TEXT": t, "VAYU_TTS_RATE": str(rate)},
            ),
            Pyttsx3Backend(),
        ]
    if sys.platform == "darwin":
        wpm = str(max(120, min(320, 180 + rate * 15)))
        return [
            ProcessBackend("say", lambda t: ["say", "-r", wpm, "--", t]),
            Pyttsx3Backend(),
        ]
    wpm = str(max(120, min(320, 175 + rate * 15)))
    return [
        ProcessBackend("spd-say", lambda t: ["spd-say", "-w", "-r", str(rate * 10), "--", t]),
        ProcessBackend("espeak-ng", lambda t: ["espeak-ng", "-s", wpm, "--", t]),
        ProcessBackend("espeak", lambda t: ["espeak", "-s", wpm, "--", t]),
        Pyttsx3Backend(),
    ]


# --------------------------------------------------------------------------
# engine
# --------------------------------------------------------------------------

class SpeechEngine:
    def __init__(self, backends: list[_Backend] | None = None):
        self._q: queue.Queue = queue.Queue()
        self._cancel = threading.Event()
        self._generation = 0
        self._lock = threading.Lock()
        self._buf = ""
        self._state = IDLE
        self._listeners: list[Callable[[str], None]] = []
        self._backends: list[_Backend] | None = backends
        self._backend: _Backend | None = None
        self._worker: threading.Thread | None = None
        self._idle = threading.Event()
        self._idle.set()
        # Set while a backend is mid-utterance, so stop() can wait for real silence.
        self._in_flight = threading.Event()

    # -- state ------------------------------------------------------------

    def on_state(self, callback: Callable[[str], None]) -> None:
        """Register a listener for speaking/idle transitions (for the HUD)."""
        self._listeners.append(callback)

    def _set_state(self, state: str) -> None:
        if state == self._state:
            return
        self._state = state
        if state == IDLE:
            self._idle.set()
        else:
            self._idle.clear()
        for cb in list(self._listeners):
            try:
                cb(state)
            except Exception:
                pass

    @property
    def is_speaking(self) -> bool:
        return self._state == SPEAKING

    @property
    def backend_name(self) -> str:
        return self._backend.name if self._backend else "none"

    def wait_until_idle(self, timeout: float | None = None) -> bool:
        return self._idle.wait(timeout)

    # -- input ------------------------------------------------------------

    def say(self, text: str, interrupt: bool = False) -> None:
        """Queue a whole utterance. With interrupt, cut off whatever is playing."""
        text = clean_for_speech(text or "")
        if not text:
            return
        if interrupt:
            self.stop()
        for sentence, _ in [(s, None) for s in self._sentences(text)]:
            self._enqueue(sentence)

    def feed(self, chunk: str) -> None:
        """Add streaming text; speaks each sentence as soon as it is complete."""
        if not chunk:
            return
        with self._lock:
            self._buf += chunk
            ready, self._buf = split_stream(self._buf)
        for sentence in ready:
            spoken = clean_for_speech(sentence)
            if spoken:
                self._enqueue(spoken)

    def end_stream(self) -> None:
        """Flush whatever partial text is still buffered."""
        with self._lock:
            tail, self._buf = self._buf, ""
        spoken = clean_for_speech(tail)
        if spoken:
            self._enqueue(spoken)

    def stop(self) -> None:
        """Barge-in: kill the current utterance and drop the queue.

        Returns once audio has actually stopped, not merely once the request to
        stop has been filed — callers use this to decide it is safe to listen.
        """
        with self._lock:
            self._generation += 1
            self._buf = ""
        self._cancel.set()
        while True:
            try:
                self._q.get_nowait()
            except queue.Empty:
                break
        # Give the backend a moment to actually tear the utterance down.
        deadline = time.monotonic() + 1.5
        while self._in_flight.is_set() and time.monotonic() < deadline:
            time.sleep(0.01)
        self._set_state(IDLE)

    # -- internals --------------------------------------------------------

    @staticmethod
    def _sentences(text: str) -> list[str]:
        ready, tail = split_stream(text)
        if tail.strip():
            ready.append(tail.strip())
        return ready or ([text] if text.strip() else [])

    def _enqueue(self, text: str) -> None:
        self._ensure_worker()
        with self._lock:
            gen = self._generation
        self._set_state(SPEAKING)
        self._q.put((gen, text))

    def _ensure_worker(self) -> None:
        if self._worker and self._worker.is_alive():
            return
        self._worker = threading.Thread(target=self._run, name="vayu-speech", daemon=True)
        self._worker.start()

    def _pick_backend(self) -> _Backend | None:
        if self._backends is None:
            self._backends = _build_backends()
            preferred = str(_config().get("preferred_tts", "auto")).lower()
            if preferred not in ("", "auto"):
                self._backends.sort(key=lambda b: 0 if b.name == preferred else 1)
        for backend in self._backends:
            try:
                if backend.available():
                    return backend
            except Exception:
                continue
        return None

    def _run(self) -> None:
        while True:
            gen, text = self._q.get()
            with self._lock:
                stale = gen != self._generation
            if stale:
                continue

            self._cancel.clear()
            backend = self._backend or self._pick_backend()
            if backend is None:
                print("[speech] no usable TTS backend")
                self._set_state(IDLE)
                continue

            self._in_flight.set()
            try:
                backend.speak(text, self._cancel)
                self._backend = backend
            except Exception as exc:
                print(f"[speech] {backend.name} failed: {exc}")
                # Drop it for the rest of the session and retry once.
                if self._backends and backend in self._backends:
                    self._backends.remove(backend)
                self._backend = None
                fallback = self._pick_backend()
                if fallback is not None and not self._cancel.is_set():
                    try:
                        fallback.speak(text, self._cancel)
                        self._backend = fallback
                    except Exception:
                        pass
            finally:
                self._in_flight.clear()

            if self._q.empty():
                self._set_state(IDLE)


speech = SpeechEngine()


def say(text: str, interrupt: bool = False) -> None:
    speech.say(text, interrupt=interrupt)


def stop() -> None:
    speech.stop()

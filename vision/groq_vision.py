"""Look at the screen or the camera and answer a question about it.

The existing vision path (actions/screen_processor.py) speaks through a Gemini
live session, so it needs a Gemini key and it answers in its own voice, outside
the persona and outside the streaming speech engine. In Groq mode — the mode
that exists precisely so a Gemini key is not required — it does nothing at all.

This module is the other half: capture an image, ask a multimodal Groq model
about it, and hand plain text back to the caller. The text then flows through
the normal reply path, which means it is spoken in character, streamed
sentence by sentence, and can be interrupted like anything else.
"""

from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

import requests

GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"

# Multimodal models, best first. The list is a fallback chain: a model that is
# retired or unavailable to this key falls through to the next.
VISION_MODELS = [
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "meta-llama/llama-4-maverick-17b-128e-instruct",
    "llama-3.2-90b-vision-preview",
    "llama-3.2-11b-vision-preview",
]

# Groq rejects oversized image payloads; keep the long edge sane.
_MAX_EDGE = 1280
_JPEG_QUALITY = 80


def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


def _config() -> dict:
    try:
        return json.loads((_base_dir() / "config" / "api_keys.json").read_text(encoding="utf-8"))
    except Exception:
        return {}


def _groq_key() -> str:
    cfg = _config()
    return (cfg.get("groq_api_key") or cfg.get("groq_key") or "").strip()


# --------------------------------------------------------------------------
# capture
# --------------------------------------------------------------------------

def _shrink(img_bytes: bytes) -> bytes:
    """Downscale and re-encode as JPEG so the payload stays reasonable."""
    try:
        import io

        from PIL import Image

        img = Image.open(io.BytesIO(img_bytes))
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        longest = max(img.size)
        if longest > _MAX_EDGE:
            scale = _MAX_EDGE / longest
            img = img.resize((int(img.width * scale), int(img.height * scale)), Image.LANCZOS)
        out = io.BytesIO()
        img.save(out, format="JPEG", quality=_JPEG_QUALITY)
        return out.getvalue()
    except Exception:
        return img_bytes


def capture_screen() -> bytes:
    """Grab the primary display as JPEG bytes."""
    try:
        import io

        import mss
        from PIL import Image

        with mss.mss() as sct:
            shot = sct.grab(sct.monitors[1])
        img = Image.frombytes("RGB", shot.size, shot.rgb)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=_JPEG_QUALITY)
        return _shrink(buf.getvalue())
    except Exception as exc:
        raise RuntimeError(f"could not capture the screen: {exc}") from exc


def capture_camera(index: int = 0, warmup_frames: int = 8) -> bytes:
    """Grab a frame from the webcam as JPEG bytes.

    Webcams need a few frames before auto-exposure settles; grabbing the very
    first frame reliably produces a black or badly-lit image.
    """
    try:
        import cv2
    except Exception as exc:
        raise RuntimeError("opencv is not installed, so the camera is unavailable") from exc

    cam = cv2.VideoCapture(index, getattr(cv2, "CAP_DSHOW", 0) if sys.platform == "win32" else 0)
    if not cam.isOpened():
        cam.release()
        raise RuntimeError("no camera available")
    try:
        frame = None
        for _ in range(max(1, warmup_frames)):
            ok, f = cam.read()
            if ok:
                frame = f
        if frame is None:
            raise RuntimeError("the camera returned no frames")
        ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), _JPEG_QUALITY])
        if not ok:
            raise RuntimeError("could not encode the camera frame")
        return _shrink(buf.tobytes())
    finally:
        cam.release()


# --------------------------------------------------------------------------
# ask
# --------------------------------------------------------------------------

def ask(image_bytes: bytes, question: str, timeout: int = 60) -> str:
    """Ask a multimodal model about an image. Returns plain text."""
    key = _groq_key()
    if not key:
        return "I have no Groq key to see with, sir."

    b64 = base64.b64encode(image_bytes).decode("ascii")
    messages = [
        {
            "role": "system",
            "content": (
                "You are VAYU's eyes. Answer in one or two spoken sentences — "
                "dry, precise, no markdown, no preamble. Lead with the thing "
                "that actually answers the question. Address the user as 'sir'."
            ),
        },
        {
            "role": "user",
            "content": [
                {"type": "text", "text": question},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
            ],
        },
    ]

    models = _config().get("vision_models") or VISION_MODELS
    last_error = ""
    for model in models:
        try:
            r = requests.post(
                GROQ_CHAT_URL,
                headers={"Authorization": "Bearer " + key},
                json={"model": model, "messages": messages,
                      "temperature": 0.3, "max_tokens": 300},
                timeout=timeout,
            )
        except Exception as exc:
            last_error = str(exc)
            continue

        if r.status_code == 200:
            try:
                text = (r.json()["choices"][0]["message"]["content"] or "").strip()
            except Exception:
                last_error = "unreadable response"
                continue
            if text:
                return text
            last_error = "empty response"
            continue

        # 404/400 usually means this model is gone or not multimodal — try the
        # next one. Anything else is worth reporting.
        last_error = f"{r.status_code}: {r.text[:120]}"
        if r.status_code not in (400, 404, 422):
            break

    return f"I couldn't make sense of what I saw, sir. ({last_error})"


def look(angle: str = "screen", question: str = "What do you see?",
         camera_index: int = 0) -> str:
    """Capture from `angle` ('screen' or 'camera') and answer `question`."""
    try:
        if (angle or "").lower().strip() == "camera":
            image = capture_camera(camera_index)
        else:
            image = capture_screen()
    except Exception as exc:
        return f"I can't see anything, sir — {exc}."
    return ask(image, question or "What do you see?")


def available() -> bool:
    """True if there is a key to see with."""
    return bool(_groq_key())

import cv2
import mediapipe as mp
import threading
import time
import os
from collections import deque
from enum import Enum
from pathlib import Path


class Gesture(Enum):
    NONE = "none"
    FIST = "fist"
    OPEN_PALM = "open_palm"
    THUMBS_UP = "thumbs_up"
    PEACE = "peace"
    POINT_UP = "point_up"
    PINCH = "pinch"
    SWIPE_LEFT = "swipe_left"
    SWIPE_RIGHT = "swipe_right"
    SHAKE = "shake"
    OK_GESTURE = "ok"
    THREE = "three"
    FOUR = "four"
    ROCK_ON = "rock_on"


GESTURE_ACTIONS = {
    Gesture.FIST: "mute_toggle",
    Gesture.OPEN_PALM: "unmute",
    Gesture.THUMBS_UP: "mode_next",
    Gesture.PEACE: "mode_prev",
    Gesture.POINT_UP: "volume_up",
    Gesture.PINCH: "volume_down",
    Gesture.SWIPE_LEFT: "scroll_down",
    Gesture.SWIPE_RIGHT: "scroll_up",
    Gesture.SHAKE: "alt_tab",
    Gesture.OK_GESTURE: "enter",
    Gesture.THREE: "desktop_show",
    Gesture.FOUR: "task_view",
    Gesture.ROCK_ON: "toggle_play",
}

_MODEL_FILENAME = "hand_landmarker.task"
_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
)


def _find_model() -> str | None:
    candidates = [
        Path(__file__).resolve().parent.parent / _MODEL_FILENAME,
        Path(__file__).resolve().parent / _MODEL_FILENAME,
        Path.cwd() / _MODEL_FILENAME,
    ]
    for p in candidates:
        if p.exists():
            return str(p)
    return None


def _download_model(target: str) -> bool:
    import urllib.request
    try:
        print(f"[Gesture] Downloading model from {_MODEL_URL}...")
        urllib.request.urlretrieve(_MODEL_URL, target)
        print(f"[Gesture] Model saved to {target}")
        return True
    except Exception as e:
        print(f"[Gesture] Failed to download model: {e}")
        return False


def ensure_model() -> str | None:
    path = _find_model()
    if path:
        return path
    target = str(Path(__file__).resolve().parent.parent / _MODEL_FILENAME)
    if _download_model(target):
        return target
    return None


class GestureRecognizer:
    def __init__(self, model_path: str | None = None):
        if model_path is None:
            model_path = ensure_model()
        if model_path is None:
            raise RuntimeError(
                "hand_landmarker.task not found and could not be downloaded. "
                "Place it next to gesture.py or run ensure_model()."
            )

        BaseOptions = mp.tasks.BaseOptions
        HandLandmarker = mp.tasks.vision.HandLandmarker
        HandLandmarkerOptions = mp.tasks.vision.HandLandmarkerOptions
        VisionRunningMode = mp.tasks.vision.RunningMode

        self._landmarker = HandLandmarker.create_from_options(
            HandLandmarkerOptions(
                base_options=BaseOptions(model_asset_path=model_path),
                running_mode=VisionRunningMode.IMAGE,
                num_hands=2,
                min_hand_detection_confidence=0.6,
                min_tracking_confidence=0.5,
            )
        )

        self._last_gesture = Gesture.NONE
        self._gesture_history = deque(maxlen=4)
        self._callback = None
        self._running = False
        self._thread = None
        self._cap = None
        self._frame = None
        self._frame_lock = threading.Lock()
        self._gesture_lock = threading.Lock()

        self._swipe_history = deque(maxlen=8)
        self._prev_center = None

        self._cursor_mode = False
        self._cursor_smooth_x = 0.5
        self._cursor_smooth_y = 0.5
        self._cursor_visible = False
        self._cursor_alpha = 0.55
        self._pinch_closed = False
        self._click_triggered = False
        self._right_click_triggered = False
        self._prev_thumb_index_dist = 0.0
        self._pinch_frames = 0

        self._shake_history = deque(maxlen=12)
        self._shake_cooldown = 0

    def set_callback(self, callback):
        self._callback = callback

    def set_cursor_mode(self, enabled: bool):
        self._cursor_mode = enabled
        if not enabled:
            self._cursor_visible = False
            self._pinch_closed = False
            self._pinch_frames = 0

    def is_cursor_mode(self) -> bool:
        return self._cursor_mode

    def get_cursor_pos(self):
        if not self._cursor_mode:
            return None
        return (self._cursor_smooth_x, self._cursor_smooth_y, self._cursor_visible)

    def consume_click(self) -> bool:
        with self._gesture_lock:
            if self._click_triggered:
                self._click_triggered = False
                return True
            return False

    def consume_right_click(self) -> bool:
        with self._gesture_lock:
            if self._right_click_triggered:
                self._right_click_triggered = False
                return True
            return False

    def _get_landmarks(self, frame):
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result = self._landmarker.detect(mp_img)
        if result and result.hand_landmarks and len(result.hand_landmarks) > 0:
            return result.hand_landmarks[0]
        return None

    def _detect_gesture(self, landmarks) -> Gesture:
        lm = landmarks

        tips = [4, 8, 12, 16, 20]

        def is_finger_up(finger_idx):
            tip = lm[tips[finger_idx]]
            pip = lm[tips[finger_idx] - 2]
            if finger_idx == 0:
                return tip.x < pip.x if tip.x < lm[17].x else tip.x > pip.x
            return tip.y < pip.y

        fingers = [is_finger_up(i) for i in range(5)]

        thumb_tip = lm[4]
        index_tip = lm[8]
        index_pip = lm[6]
        index_mcp = lm[5]

        def dist(a, b):
            return ((a.x - b.x) ** 2 + (a.y - b.y) ** 2) ** 0.5

        thumb_index_dist = dist(thumb_tip, index_tip)

        if fingers[1] and fingers[2] and not fingers[3] and not fingers[4] and not fingers[0]:
            return Gesture.PEACE

        if not any(fingers):
            return Gesture.FIST

        if all(fingers) and thumb_index_dist < 0.08:
            return Gesture.OPEN_PALM

        if fingers[0] and not fingers[1] and not fingers[2] and not fingers[3] and not fingers[4]:
            if thumb_tip.y < index_mcp.y - 0.05:
                return Gesture.THUMBS_UP

        if fingers[1] and not fingers[2] and not fingers[3] and not fingers[4] and not fingers[0]:
            if index_tip.y < index_pip.y - 0.03:
                return Gesture.POINT_UP

        if thumb_index_dist < 0.04 and not fingers[2] and not fingers[3] and not fingers[4]:
            return Gesture.PINCH

        if not fingers[0] and not fingers[1] and not fingers[4] and fingers[2] and fingers[3]:
            return Gesture.THREE

        if fingers[1] and fingers[2] and fingers[3] and fingers[4] and not fingers[0]:
            return Gesture.FOUR

        if fingers[1] and fingers[4] and not fingers[2] and not fingers[3]:
            return Gesture.ROCK_ON

        if thumb_index_dist < 0.04 and all(fingers[2:5]):
            return Gesture.OK_GESTURE

        return Gesture.NONE

    def _detect_swipe(self, landmarks) -> Gesture:
        wrist = landmarks[0]
        cx = wrist.x

        if self._prev_center is not None:
            dx = cx - self._prev_center
            self._swipe_history.append(dx)

        self._prev_center = cx

        if len(self._swipe_history) >= 5:
            total_dx = sum(self._swipe_history)
            if total_dx > 0.12:
                self._swipe_history.clear()
                return Gesture.SWIPE_RIGHT
            elif total_dx < -0.12:
                self._swipe_history.clear()
                return Gesture.SWIPE_LEFT

        return Gesture.NONE

    def _detect_shake(self, landmarks) -> Gesture:
        if self._shake_cooldown > 0:
            self._shake_cooldown -= 1
            return Gesture.NONE
        wrist = landmarks[0]
        self._shake_history.append(wrist.x)
        if len(self._shake_history) < 8:
            return Gesture.NONE
        directions = []
        for i in range(1, len(self._shake_history)):
            diff = self._shake_history[i] - self._shake_history[i-1]
            if abs(diff) > 0.006:
                directions.append(1 if diff > 0 else -1)
        if len(directions) >= 5:
            changes = sum(1 for i in range(1, len(directions)) if directions[i] != directions[i-1])
            if changes >= 4:
                self._shake_history.clear()
                self._shake_cooldown = 15
                return Gesture.SHAKE
        return Gesture.NONE

    def _track_cursor(self, landmarks, img_w, img_h):
        index_tip = landmarks[8]
        raw_x = 1.0 - index_tip.x
        raw_y = index_tip.y

        self._cursor_smooth_x = self._cursor_alpha * raw_x + (1 - self._cursor_alpha) * self._cursor_smooth_x
        self._cursor_smooth_y = self._cursor_alpha * raw_y + (1 - self._cursor_alpha) * self._cursor_smooth_y
        self._cursor_visible = True

        thumb_tip = landmarks[4]
        thumb_index_dist = ((thumb_tip.x - index_tip.x) ** 2 + (thumb_tip.y - index_tip.y) ** 2) ** 0.5

        is_pinched = thumb_index_dist < 0.04
        if is_pinched and not self._pinch_closed:
            self._pinch_closed = True
            self._pinch_frames = 0
        elif is_pinched and self._pinch_closed:
            self._pinch_frames += 1
        elif not is_pinched and self._pinch_closed:
            if self._pinch_frames < 5:
                with self._gesture_lock:
                    self._click_triggered = True
            self._pinch_closed = False
            self._pinch_frames = 0

        self._prev_thumb_index_dist = thumb_index_dist

    def _draw_landmarks(self, frame, landmarks):
        h, w, _ = frame.shape
        connections = [
            (0, 1), (1, 2), (2, 3), (3, 4),
            (0, 5), (5, 6), (6, 7), (7, 8),
            (0, 17), (5, 9), (9, 13), (13, 17),
            (9, 10), (10, 11), (11, 12),
            (13, 14), (14, 15), (15, 16),
            (17, 18), (18, 19), (19, 20),
        ]
        for i, lm in enumerate(landmarks):
            cx, cy = int(lm.x * w), int(lm.y * h)
            cv2.circle(frame, (cx, cy), 3, (0, 255, 255), -1)
            cv2.putText(frame, str(i), (cx + 4, cy - 4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.3, (255, 255, 255), 1)
        for a, b in connections:
            if a < len(landmarks) and b < len(landmarks):
                p1 = (int(landmarks[a].x * w), int(landmarks[a].y * h))
                p2 = (int(landmarks[b].x * w), int(landmarks[b].y * h))
                cv2.line(frame, p1, p2, (255, 0, 255), 1)

    def _draw_cursor(self, frame):
        if not self._cursor_visible:
            return
        h, w, _ = frame.shape
        cx = int(self._cursor_smooth_x * w)
        cy = int(self._cursor_smooth_y * h)
        cx = max(0, min(w - 1, cx))
        cy = max(0, min(h - 1, cy))

        cv2.drawMarker(frame, (cx, cy), (0, 255, 0),
                       markerType=cv2.MARKER_CROSS, markerSize=12, thickness=2)
        cv2.circle(frame, (cx, cy), 4, (0, 255, 0), -1)

    def process_frame(self, frame):
        landmarks = self._get_landmarks(frame)
        gesture = Gesture.NONE
        gesture_raw = Gesture.NONE
        self._cursor_visible = False

        if landmarks is not None:
            h, w, _ = frame.shape

            if self._cursor_mode:
                self._track_cursor(landmarks, w, h)

            gesture_raw = self._detect_gesture(landmarks)

            if self._cursor_mode:
                if gesture_raw == Gesture.POINT_UP:
                    gesture_raw = Gesture.NONE
                elif gesture_raw == Gesture.PINCH:
                    gesture_raw = Gesture.NONE
                elif gesture_raw == Gesture.SHAKE:
                    gesture_raw = Gesture.NONE
                elif gesture_raw == Gesture.PEACE:
                    with self._gesture_lock:
                        self._right_click_triggered = True
                    gesture_raw = Gesture.NONE

            if gesture_raw == Gesture.NONE:
                swipe = self._detect_swipe(landmarks)
                if swipe != Gesture.NONE:
                    gesture_raw = swipe

            if gesture_raw == Gesture.NONE:
                shake = self._detect_shake(landmarks)
                if shake != Gesture.NONE:
                    gesture_raw = shake

            self._draw_landmarks(frame, landmarks)

        if self._cursor_mode:
            self._draw_cursor(frame)

        if gesture_raw != Gesture.NONE:
            self._gesture_history.append(gesture_raw)
        else:
            self._gesture_history.append(Gesture.NONE)

        if len([g for g in self._gesture_history if g != Gesture.NONE]) >= 2:
            valid = [g for g in self._gesture_history if g != Gesture.NONE]
            if valid:
                gesture = valid[-1]

        if gesture != self._last_gesture and gesture != Gesture.NONE:
            self._last_gesture = gesture
            action = GESTURE_ACTIONS.get(gesture)
            if action and self._callback:
                self._callback(gesture, action)

        label = gesture_raw.value if gesture_raw != Gesture.NONE else ""
        if label:
            cv2.putText(frame, f"{label.upper()}", (10, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)

        if self._cursor_mode:
            status = "CURSOR ON" if self._cursor_visible else "CURSOR (no hand)"
            cv2.putText(frame, status, (10, 70),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

        return frame, gesture

    def start(self, callback=None, camera_index=0):
        if self._running:
            return
        if callback:
            self._callback = callback
        self._running = True
        self._thread = threading.Thread(target=self._run, args=(camera_index,), daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._cap:
            self._cap.release()
        if self._thread:
            self._thread.join(timeout=2)

    def _run(self, camera_index):
        self._cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
        self._cap.set(cv2.CAP_PROP_FPS, 15)

        if not self._cap.isOpened():
            print("[Gesture] Camera could not be opened")
            self._running = False
            return

        while self._running:
            ret, frame = self._cap.read()
            if not ret:
                time.sleep(0.1)
                continue

            frame, gesture = self.process_frame(frame)

            with self._frame_lock:
                self._frame = frame.copy()

        self._cap.release()

    def get_frame(self):
        with self._frame_lock:
            if self._frame is not None:
                return self._frame.copy()
            return None

    def is_running(self):
        return self._running

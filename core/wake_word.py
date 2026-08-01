import threading
import time
import queue
import numpy as np
import sounddevice as sd


SAMPLE_RATE = 16000
BLOCK_SIZE  = 800
SILENCE_SEC = 2.0
ENERGY_THRESHOLD = 60


class WakeWordDetector:
    def __init__(self, on_trigger, device=None):
        self._on_trigger = on_trigger
        self._device = device
        self._running = False
        self._thread = None
        self._speaking = False
        self._silence_start = 0.0

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)

    @property
    def active(self) -> bool:
        return self._speaking

    def _loop(self):
        q = queue.Queue()

        def callback(indata, frames, time_info, status):
            q.put(indata.copy())

        try:
            with sd.InputStream(
                samplerate=SAMPLE_RATE, channels=1, dtype="int16",
                blocksize=BLOCK_SIZE, device=self._device, callback=callback,
            ):
                self._silence_start = time.time()
                while self._running:
                    try:
                        data = q.get(timeout=0.5)
                    except queue.Empty:
                        continue

                    rms = np.sqrt(np.mean(data.astype(np.float64) ** 2))

                    if rms > ENERGY_THRESHOLD:
                        if not self._speaking:
                            silence_dur = time.time() - self._silence_start
                            if silence_dur >= SILENCE_SEC:
                                self._speaking = True
                                self._on_trigger(True)
                    else:
                        if self._speaking:
                            self._speaking = False
                            self._silence_start = time.time()
                            self._on_trigger(False)
        except Exception as e:
            print(f"[WakeWord] Error: {e}")

"""Tests for the interruptible streaming speech engine.

Run with:  python -m unittest discover -s tests -v
"""

import sys
import threading
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from voice.speech import (  # noqa: E402
    IDLE,
    SPEAKING,
    SpeechEngine,
    _Backend,
    clean_for_speech,
    split_stream,
)


class FakeBackend(_Backend):
    """Records what it was asked to say and how long it got to say it."""

    name = "fake"

    def __init__(self, duration: float = 0.05):
        self.duration = duration
        self.spoken: list[str] = []
        self.interrupted: list[str] = []
        self.started = threading.Event()
        self._lock = threading.Lock()

    def available(self) -> bool:
        return True

    def speak(self, text: str, cancel: threading.Event) -> bool:
        self.started.set()
        deadline = time.monotonic() + self.duration
        while time.monotonic() < deadline:
            if cancel.is_set():
                with self._lock:
                    self.interrupted.append(text)
                return False
            time.sleep(0.005)
        with self._lock:
            self.spoken.append(text)
        return True

    def snapshot(self) -> list[str]:
        with self._lock:
            return list(self.spoken)


class SplitStreamTest(unittest.TestCase):
    def test_splits_on_sentence_end(self):
        ready, rest = split_stream("Good evening, sir. The door is open.")
        self.assertEqual(ready, ["Good evening, sir.", "The door is open."])
        self.assertEqual(rest, "")

    def test_holds_back_incomplete_sentence(self):
        ready, rest = split_stream("Still thinking about")
        self.assertEqual(ready, [])
        self.assertEqual(rest, "Still thinking about")

    def test_decimal_is_not_a_boundary(self):
        ready, _ = split_stream("Disk is at 3.5 GB free. Tight.")
        self.assertEqual(ready[0], "Disk is at 3.5 GB free.")

    def test_abbreviation_is_not_a_boundary(self):
        ready, _ = split_stream("Dr. Strange called. He seemed upset.")
        self.assertEqual(ready[0], "Dr. Strange called.")

    def test_newline_is_a_boundary(self):
        ready, rest = split_stream("One\nTwo\n")
        self.assertEqual(ready, ["One", "Two"])
        self.assertEqual(rest, "")

    def test_long_run_on_flushes_at_a_clause(self):
        text = (
            "I checked the calendar, the inbox, the download folder, the battery "
            "level, the network status, the disk usage, and the running processes, "
            "and everything looks entirely fine"
        )
        ready, rest = split_stream(text)
        self.assertEqual(len(ready), 1)
        self.assertTrue(ready[0].endswith(","))
        self.assertTrue(rest.startswith("and everything"))


class CleanForSpeechTest(unittest.TestCase):
    def test_strips_markup_and_urls(self):
        got = clean_for_speech("**Done**. See `main.py` or https://example.com/x")
        self.assertEqual(got, "Done. See main.py or the link")

    def test_drops_code_fences(self):
        self.assertEqual(clean_for_speech("Here:\n```\nrm -rf /\n```\nDone."), "Here:\nDone.")


class SpeechEngineTest(unittest.TestCase):
    def setUp(self):
        self.backend = FakeBackend()
        self.engine = SpeechEngine(backends=[self.backend])

    def drain(self, timeout=3.0):
        self.assertTrue(self.engine.wait_until_idle(timeout), "engine never went idle")

    def test_say_speaks_each_sentence(self):
        self.engine.say("First one. Second one.")
        self.drain()
        self.assertEqual(self.backend.snapshot(), ["First one.", "Second one."])

    def test_streaming_speaks_as_sentences_complete(self):
        for chunk in ["Good ", "evening", ", sir. ", "The car is ", "ready."]:
            self.engine.feed(chunk)
        self.engine.end_stream()
        self.drain()
        self.assertEqual(self.backend.snapshot(), ["Good evening, sir.", "The car is ready."])

    def test_first_sentence_starts_before_the_rest_arrives(self):
        # The point of streaming: audio begins while the model is still talking.
        self.engine.feed("Good evening, sir. ")
        self.assertTrue(self.backend.started.wait(2.0), "did not start on the first sentence")
        self.engine.feed("Here is the rest of it.")
        self.engine.end_stream()
        self.drain()
        self.assertEqual(len(self.backend.snapshot()), 2)

    def test_stop_interrupts_the_current_utterance(self):
        slow = FakeBackend(duration=5.0)
        engine = SpeechEngine(backends=[slow])
        engine.say("This is a very long sentence that should be cut off.")
        self.assertTrue(slow.started.wait(2.0))
        engine.stop()
        self.assertTrue(engine.wait_until_idle(3.0))
        self.assertEqual(slow.snapshot(), [], "utterance finished despite stop()")
        self.assertEqual(len(slow.interrupted), 1)

    def test_stop_drops_everything_queued(self):
        slow = FakeBackend(duration=5.0)
        engine = SpeechEngine(backends=[slow])
        engine.say("One. Two. Three. Four.")
        self.assertTrue(slow.started.wait(2.0))
        engine.stop()
        time.sleep(0.3)
        self.assertEqual(slow.snapshot(), [])

    def test_speech_after_stop_still_works(self):
        # A barge-in must not wedge the engine for the next thing said.
        self.engine.say("Interrupted.")
        self.engine.stop()
        self.engine.say("Fresh start.")
        self.drain()
        self.assertIn("Fresh start.", self.backend.snapshot())

    def test_interrupt_flag_cuts_in(self):
        slow = FakeBackend(duration=1.0)
        engine = SpeechEngine(backends=[slow])
        engine.say("The long one that gets cut.")
        self.assertTrue(slow.started.wait(2.0))
        engine.say("Urgent.", interrupt=True)
        self.assertTrue(engine.wait_until_idle(5.0))
        self.assertEqual(slow.snapshot(), ["Urgent."])

    def test_state_transitions_reach_listeners(self):
        seen: list[str] = []
        self.engine.on_state(seen.append)
        self.engine.say("Hello.")
        self.drain()
        self.assertEqual(seen[0], SPEAKING)
        self.assertEqual(seen[-1], IDLE)

    def test_empty_input_is_ignored(self):
        self.engine.say("")
        self.engine.say("   ")
        self.engine.feed("")
        self.engine.end_stream()
        self.assertFalse(self.engine.is_speaking)
        self.assertEqual(self.backend.snapshot(), [])

    def test_falls_back_when_a_backend_raises(self):
        class Broken(_Backend):
            name = "broken"

            def available(self):
                return True

            def speak(self, text, cancel):
                raise RuntimeError("no audio device")

        good = FakeBackend()
        engine = SpeechEngine(backends=[Broken(), good])
        engine.say("Fallback works.")
        self.assertTrue(engine.wait_until_idle(3.0))
        self.assertEqual(good.snapshot(), ["Fallback works."])


if __name__ == "__main__":
    unittest.main()

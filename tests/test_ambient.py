"""Tests for ambient awareness — mostly tests that it stays quiet.

Run with:  python -m unittest discover -s tests -v
"""

import sys
import time
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from brain.ambient import (  # noqa: E402
    AmbientMonitor,
    Observation,
    SystemProbe,
    watch_battery,
    watch_disk,
    watch_downloads,
    watch_long_session,
)


class FakeProbe(SystemProbe):
    def __init__(self, battery=None, disk=None, downloads=None, hour=14):
        self._battery = battery
        self._disk = disk
        self._downloads = downloads or []
        self._hour = hour

    def battery(self):
        return self._battery

    def disk(self):
        return self._disk

    def recent_downloads(self, within_sec=90.0):
        return list(self._downloads)

    def uptime_sec(self):
        return 3600.0

    def now(self):
        return datetime(2026, 1, 1, self._hour, 0, 0)


class FakeClock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t

    def advance(self, seconds):
        self.t += seconds


class BatteryWatcherTest(unittest.TestCase):
    def test_silent_when_plugged_in(self):
        self.assertIsNone(watch_battery(FakeProbe(battery=(5, True)), {}))

    def test_silent_when_healthy(self):
        self.assertIsNone(watch_battery(FakeProbe(battery=(80, False)), {}))

    def test_speaks_when_low(self):
        obs = watch_battery(FakeProbe(battery=(18, False)), {})
        self.assertIsNotNone(obs)
        self.assertEqual(obs.key, "battery-low")
        self.assertIn("18", obs.text)

    def test_critical_is_urgent(self):
        obs = watch_battery(FakeProbe(battery=(7, False)), {})
        self.assertEqual(obs.key, "battery-critical")
        self.assertTrue(obs.urgent)

    def test_no_battery_hardware_is_silent(self):
        self.assertIsNone(watch_battery(FakeProbe(battery=None), {}))

    def test_unplugging_a_full_battery_says_nothing(self):
        state = {"plugged": True}
        self.assertIsNone(watch_battery(FakeProbe(battery=(95, False)), state))


class DiskWatcherTest(unittest.TestCase):
    def test_silent_when_roomy(self):
        self.assertIsNone(watch_disk(FakeProbe(disk=(500_000_000_000, 1_000_000_000_000)), {}))

    def test_speaks_when_tight(self):
        obs = watch_disk(FakeProbe(disk=(40_000_000_000, 1_000_000_000_000)), {})
        self.assertEqual(obs.key, "disk-low")

    def test_critical_is_urgent(self):
        obs = watch_disk(FakeProbe(disk=(10_000_000_000, 1_000_000_000_000)), {})
        self.assertEqual(obs.key, "disk-critical")
        self.assertTrue(obs.urgent)

    def test_zero_total_does_not_divide_by_zero(self):
        self.assertIsNone(watch_disk(FakeProbe(disk=(0, 0)), {}))


class DownloadWatcherTest(unittest.TestCase):
    def test_first_sweep_is_silent(self):
        # Files already sitting in Downloads at startup are not news.
        probe = FakeProbe(downloads=[Path("/tmp/report.pdf")])
        self.assertIsNone(watch_downloads(probe, {}))

    def test_announces_a_new_file_after_priming(self):
        state = {}
        probe = FakeProbe(downloads=[Path("/tmp/old.pdf")])
        watch_downloads(probe, state)  # prime
        probe._downloads.append(Path("/tmp/new.zip"))
        obs = watch_downloads(probe, state)
        self.assertIsNotNone(obs)
        self.assertIn("new.zip", obs.text)

    def test_does_not_repeat_the_same_file(self):
        state = {}
        probe = FakeProbe(downloads=[Path("/tmp/a.pdf")])
        watch_downloads(probe, state)
        probe._downloads.append(Path("/tmp/b.zip"))
        self.assertIsNotNone(watch_downloads(probe, state))
        self.assertIsNone(watch_downloads(probe, state))

    def test_batches_several_at_once(self):
        state = {}
        probe = FakeProbe(downloads=[Path("/tmp/a")])
        watch_downloads(probe, state)
        probe._downloads.extend([Path("/tmp/b"), Path("/tmp/c"), Path("/tmp/d")])
        obs = watch_downloads(probe, state)
        self.assertIn("3 downloads", obs.text)


class LongSessionWatcherTest(unittest.TestCase):
    def test_silent_early(self):
        state = {"session_start": time.monotonic()}
        self.assertIsNone(watch_long_session(FakeProbe(), state))

    def test_speaks_once_per_hour_milestone(self):
        state = {"session_start": time.monotonic() - 4 * 3600}
        self.assertIsNotNone(watch_long_session(FakeProbe(), state))
        self.assertIsNone(watch_long_session(FakeProbe(), state))


class MonitorRestraintTest(unittest.TestCase):
    def setUp(self):
        self.said: list[str] = []
        self.clock = FakeClock()

    def monitor(self, watchers, hour=14, busy=False, probe=None):
        return AmbientMonitor(
            speak=self.said.append,
            probe=probe or FakeProbe(hour=hour),
            watchers=watchers,
            is_busy=lambda: busy,
            clock=self.clock,
        )

    def test_speaks_an_observation(self):
        m = self.monitor([lambda p, s: Observation("k", "Something, sir.")])
        m.poll_once()
        self.assertEqual(self.said, ["Something, sir."])

    def test_does_not_repeat_within_cooldown(self):
        m = self.monitor([lambda p, s: Observation("k", "Again.", cooldown=100)])
        m.poll_once()
        self.clock.advance(50)
        m.poll_once()
        self.assertEqual(len(self.said), 1)

    def test_repeats_after_cooldown_and_global_gap(self):
        m = self.monitor([lambda p, s: Observation("k", "Again.", cooldown=100)])
        m.poll_once()
        self.clock.advance(500)
        m.poll_once()
        self.assertEqual(len(self.said), 2)

    def test_global_gap_holds_back_a_second_topic(self):
        seq = [Observation("a", "First."), Observation("b", "Second.")]
        m = self.monitor([lambda p, s: seq.pop(0) if seq else None])
        m.poll_once()
        self.clock.advance(10)
        m.poll_once()
        self.assertEqual(self.said, ["First."])

    def test_quiet_hours_silence_routine_observations(self):
        m = self.monitor([lambda p, s: Observation("k", "Routine.")], hour=3)
        m.poll_once()
        self.assertEqual(self.said, [])

    def test_urgent_speaks_through_quiet_hours(self):
        m = self.monitor([lambda p, s: Observation("k", "Fire.", urgent=True)], hour=3)
        m.poll_once()
        self.assertEqual(self.said, ["Fire."])

    def test_busy_silences_routine_observations(self):
        m = self.monitor([lambda p, s: Observation("k", "Routine.")], busy=True)
        m.poll_once()
        self.assertEqual(self.said, [])

    def test_urgent_speaks_through_busy(self):
        m = self.monitor([lambda p, s: Observation("k", "Fire.", urgent=True)], busy=True)
        m.poll_once()
        self.assertEqual(self.said, ["Fire."])

    def test_at_most_one_thing_per_pass(self):
        m = self.monitor([
            lambda p, s: Observation("a", "First."),
            lambda p, s: Observation("b", "Second."),
        ])
        m.poll_once()
        self.assertEqual(len(self.said), 1)

    def test_urgent_wins_the_pass(self):
        m = self.monitor([
            lambda p, s: Observation("a", "Routine."),
            lambda p, s: Observation("b", "Fire.", urgent=True),
        ])
        m.poll_once()
        self.assertEqual(self.said, ["Fire."])

    def test_a_broken_watcher_does_not_stop_the_others(self):
        def broken(p, s):
            raise RuntimeError("sensor exploded")

        m = self.monitor([broken, lambda p, s: Observation("k", "Still here.")])
        m.poll_once()
        self.assertEqual(self.said, ["Still here."])

    def test_silence_when_nothing_is_happening(self):
        m = self.monitor([lambda p, s: None])
        self.assertIsNone(m.poll_once())
        self.assertEqual(self.said, [])


if __name__ == "__main__":
    unittest.main()

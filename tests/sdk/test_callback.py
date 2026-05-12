import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock

from freezegun import freeze_time

from dynatrace_extension.sdk.callback import WrappedCallback


class TestCallBack(unittest.TestCase):
    def test_simple_callback(self):
        def callback():
            pass

        cb = WrappedCallback(timedelta(seconds=1), callback, MagicMock(), running_in_sim=True)
        self.assertEqual(cb.executions_total, 0)
        self.assertEqual(cb.interval.total_seconds(), 1)

        self.assertEqual(cb.cluster_time_diff, 0)
        self.assertFalse(cb.running)
        self.assertEqual(cb.name(), "callback")

    def test_minute_callback(self):
        def callback():
            pass

        cb = WrappedCallback(timedelta(minutes=1), callback, MagicMock(), running_in_sim=True)
        self.assertEqual(cb.executions_total, 0)
        self.assertEqual(cb.interval.total_seconds(), 60)

        self.assertEqual(cb.cluster_time_diff, 0)
        self.assertFalse(cb.running)
        self.assertEqual(cb.name(), "callback")

    def test_metric_adjustment(self):
        def callback():
            pass

        cb = WrappedCallback(timedelta(minutes=1), callback, MagicMock(), running_in_sim=True)
        cb.start_timestamp = datetime(2020, 1, 1, 0, 0, 0)

        # In production, __call__ snapshots `iterations` into `current_iteration`
        # at the start of each execution. We set it manually here to simulate
        # that state at the time get_adjusted_metric_timestamp() is called.
        # 1st execution: metric timestamp should match the callback start timestamp
        cb.current_iteration = 1
        self.assertEqual(cb.get_adjusted_metric_timestamp(), datetime(2020, 1, 1, 0, 0, 0))

        # 2nd execution: metric timestamp should be start + 1 interval
        cb.current_iteration = 2
        self.assertEqual(cb.get_adjusted_metric_timestamp(), datetime(2020, 1, 1, 0, 1, 0))

        # 5th execution: metric timestamp should be start + 4 intervals
        cb.current_iteration = 5
        self.assertEqual(cb.get_adjusted_metric_timestamp(), datetime(2020, 1, 1, 0, 4, 0))

    def test_metric_timestamp_does_not_drift_when_execution_exceeds_interval(self):
        """
        Regression test for DAQ-23741 follow-up:

        When a callback execution exceeds its interval, extension._run_callback
        skips the next tick via the `if not callback.running` guard, so the
        callback's __call__ — and thus executions_total — is not incremented
        for the skipped tick.

        get_adjusted_metric_timestamp() must therefore derive its timestamp
        from `iterations` (incremented by the scheduler on every tick) rather
        than `executions_total`, otherwise each skipped tick causes a permanent
        `interval`-sized drift between metric timestamps and wall-clock time.
        """
        interval = timedelta(minutes=1)
        start = datetime(2026, 1, 1, 12, 0, 0)

        with freeze_time(start) as frozen:
            cb = WrappedCallback(interval, lambda: None, MagicMock(), running_in_sim=True)
            cb.start_timestamp = start

            # Tick 1 fires at T=0. Scheduler increments iterations, callback runs
            # (and takes 65s — longer than the interval).
            cb.iterations += 1
            cb()
            frozen.tick(timedelta(seconds=65))

            # Tick 2 fires at T=60 while the previous run is still in-flight.
            # extension._callback_iteration still increments iterations, but
            # extension._run_callback skips invoking the callback because
            # cb.running is True. We mirror that here:
            cb.iterations += 1
            # (no cb() call — execution skipped)

            # Tick 3 fires at T=120 — callback is free, runs again.
            frozen.tick(timedelta(seconds=55))
            cb.iterations += 1
            cb()

            reported = cb.get_adjusted_metric_timestamp()
            wall_clock_now = datetime.now()

            self.assertEqual(
                reported,
                wall_clock_now,
                f"Metric timestamp drifted: reported {reported}, wall clock {wall_clock_now}, "
                f"drift = {(wall_clock_now - reported).total_seconds()}s",
            )

    def test_start_timestamp_anchored_at_first_tick_not_first_execution(self):
        """
        Regression test:

        `start_timestamp` must be anchored when the first scheduler tick fires,
        not when the first execution actually runs in the worker. Otherwise a
        backlogged executor at startup will shift `start_timestamp` forward
        while `iterations` has already advanced, producing metric timestamps
        in the future relative to wall-clock.

        Simulated sequence:
          T=0  : tick 1 fires → anchor start_timestamp, iterations=1, submit #1 (queued)
          T=60 : tick 2 fires → iterations=2, submit #2 (queued)
          T=30 (between): worker finally picks up #1 and runs the callback
        """
        interval = timedelta(minutes=1)
        anchor = datetime(2026, 1, 1, 12, 0, 0)

        with freeze_time(anchor) as frozen:
            cb = WrappedCallback(interval, lambda: None, MagicMock(), running_in_sim=True)

            # Tick 1 at T=0 — scheduler anchors start_timestamp here.
            cb.start_timestamp = cb.get_current_time_with_cluster_diff()
            cb.iterations += 1

            # Tick 2 at T=60 — scheduler increments iterations even though
            # the executor hasn't started run #1 yet.
            frozen.tick(timedelta(seconds=60))
            cb.iterations += 1

            # Executor finally picks up run #1 somewhere in between.
            # Calling cb() here must NOT re-anchor start_timestamp.
            cb()

            # The very first run's metric timestamp must equal the original anchor.
            self.assertEqual(cb.get_adjusted_metric_timestamp(), anchor + timedelta(seconds=60))
            self.assertEqual(cb.start_timestamp, anchor)

    def test_metric_timestamps_within_one_execution_must_share_bucket(self):
        """
        Regression test:

        All metrics reported from a single callback invocation must share one
        timestamp (one "bucket" per run). Otherwise, when a long-running
        callback spans a scheduler tick boundary, two metrics emitted within
        the same `__call__` invocation get different timestamps — one before
        the tick fires and one after — even though they belong to the same
        logical execution.

        Simulated sequence with interval=60s, callback runtime=70s:
          T=0  : scheduler fires tick 1 → iterations=1, callback starts
          T=10 : callback reports metric A
          T=60 : scheduler fires tick 2 mid-execution → iterations=2 (run is skipped)
          T=65 : same callback execution reports metric B
          T=70 : callback finishes
        """
        interval = timedelta(minutes=1)
        anchor = datetime(2026, 1, 1, 12, 0, 0)

        timestamps: list[datetime] = []

        with freeze_time(anchor) as frozen:

            def long_running_callback():
                # T=10: first metric reported within the run
                frozen.tick(timedelta(seconds=10))
                timestamps.append(cb.get_adjusted_metric_timestamp())

                # T=60: scheduler fires the next tick mid-execution.
                # extension._callback_iteration increments `iterations` even
                # though _run_callback will skip the submission (running=True).
                frozen.tick(timedelta(seconds=50))
                cb.iterations += 1

                # T=65: second metric reported within the SAME run
                frozen.tick(timedelta(seconds=5))
                timestamps.append(cb.get_adjusted_metric_timestamp())

            cb = WrappedCallback(interval, long_running_callback, MagicMock(), running_in_sim=True)
            cb.start_timestamp = anchor

            # Scheduler tick 1: anchor + iterations bump, then run.
            cb.iterations += 1
            cb()

        # Both metrics were emitted within run #1; they should share one bucket.
        self.assertEqual(
            timestamps[0],
            timestamps[1],
            f"Metrics from a single execution got different timestamps: "
            f"A={timestamps[0]}, B={timestamps[1]}, "
            f"jump = {(timestamps[1] - timestamps[0]).total_seconds()}s",
        )

    def test_metric_timestamp_synchronization_with_cluster_time(self):
        def callback():
            pass

        callback = WrappedCallback(timedelta(minutes=1), callback, MagicMock(), running_in_sim=True)
        callback.cluster_time_diff = 10000
        callback.start_timestamp = callback.get_current_time_with_cluster_diff()

        self.assertGreater(callback.get_adjusted_metric_timestamp(), datetime.now() + timedelta(milliseconds=9000))

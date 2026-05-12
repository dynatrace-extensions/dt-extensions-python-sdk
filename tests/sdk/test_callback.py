import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock

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

        # In production, __call__ increments executions_total before each execution.
        # We set it manually here to simulate the state at the time get_adjusted_metric_timestamp() is called.
        # 1st execution: metric timestamp should match the callback start timestamp
        cb.executions_total = 1
        self.assertEqual(cb.get_adjusted_metric_timestamp(), datetime(2020, 1, 1, 0, 0, 0))

        # 2nd execution: metric timestamp should be start + 1 interval
        cb.executions_total = 2
        self.assertEqual(cb.get_adjusted_metric_timestamp(), datetime(2020, 1, 1, 0, 1, 0))

        # 5th execution: metric timestamp should be start + 4 intervals
        cb.executions_total = 5
        self.assertEqual(cb.get_adjusted_metric_timestamp(), datetime(2020, 1, 1, 0, 4, 0))

    def test_metric_timestamp_synchronization_with_cluster_time(self):
        def callback():
            pass

        callback = WrappedCallback(timedelta(minutes=1), callback, MagicMock(), running_in_sim=True)
        callback.cluster_time_diff = 10000
        callback.start_timestamp = callback.get_current_time_with_cluster_diff()

        self.assertGreater(callback.get_adjusted_metric_timestamp(), datetime.now() + timedelta(milliseconds=9000))

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

        # 30 seconds later
        cb.get_current_time_with_cluster_diff = MagicMock(return_value=datetime(2020, 1, 1, 0, 0, 30))

        # The metric timestamp should match the callback start timestamp
        self.assertEqual(cb.get_adjusted_metric_timestamp(), datetime(2020, 1, 1, 0, 0, 0))

        # 1 minute 5 seconds later
        cb.get_current_time_with_cluster_diff = MagicMock(return_value=datetime(2020, 1, 1, 0, 1, 5))

        # The metric timestamp should match the callback start timestamp + 1 minute
        self.assertEqual(cb.get_adjusted_metric_timestamp(), datetime(2020, 1, 1, 0, 1, 0))

        # 4 minutes 55 seconds later
        cb.get_current_time_with_cluster_diff = MagicMock(return_value=datetime(2020, 1, 1, 0, 4, 55))

        # The metric timestamp should match the callback start timestamp + 4 minutes
        self.assertEqual(cb.get_adjusted_metric_timestamp(), datetime(2020, 1, 1, 0, 4, 0))

    def test_metric_timestamp_synchronization_with_cluster_time(self):
        def callback():
            pass

        callback = WrappedCallback(timedelta(minutes=1), callback, MagicMock(), running_in_sim=True)
        callback.cluster_time_diff = 10000
        callback.start_timestamp = callback.get_current_time_with_cluster_diff()

        self.assertGreater(callback.get_adjusted_metric_timestamp(), datetime.now() + timedelta(milliseconds=9000))

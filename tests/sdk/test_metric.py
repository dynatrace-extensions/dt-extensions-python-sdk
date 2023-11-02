import unittest
from datetime import datetime

from dynatrace_extension import Metric, MetricType
from dynatrace_extension.sdk.metric import SfmMetric


class TestMetric(unittest.TestCase):
    def test_simple(self):
        metric = Metric("myMetric", 101)
        self.assertEqual(metric.to_mint_line(), "myMetric gauge,101")

    def test_delta(self):
        metric = Metric("myMetric", 101, metric_type=MetricType.DELTA)
        self.assertEqual(metric.to_mint_line(), "myMetric count,delta=101")

    def test_dimensions(self):
        metric = Metric("myMetric", 101, dimensions={"someid": "42", "descr": "Interface73/0/10"})
        self.assertEqual(metric.to_mint_line(), 'myMetric,someid="42",descr="Interface73/0/10" gauge,101')

    def test_timestamp(self):
        timestamp = datetime(2022, 1, 1, 1, 0, 0, 0)
        metric = Metric("myMetric", 101, timestamp=timestamp)
        self.assertEqual(metric.to_mint_line(), f"myMetric gauge,101 {int(timestamp.timestamp() * 1000)}")

    def test_too_many_dimensions(self):
        dimensions = {k: "value" for k in range(0, 51)}
        metric = Metric("myMetric", 101, dimensions=dimensions)
        self.assertRaises(ValueError, metric.validate)

    def test_line_too_large(self):
        metric = Metric("a" * 2000, 101)
        self.assertRaises(ValueError, metric.validate)


class TestSfmMetric(unittest.TestCase):
    def test_sfm_metric_key(self):
        metric = SfmMetric("callback.execution.time", 1, client_facing=True)
        self.assertEqual(metric.key, "dsfm:datasource.python.callback.execution.time")

        metric = SfmMetric("callback.execution.time", 1)
        self.assertEqual(metric.key, "isfm:datasource.python.callback.execution.time")

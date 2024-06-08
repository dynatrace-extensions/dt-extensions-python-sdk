import json
import unittest
from unittest.mock import MagicMock, mock_open, patch

from dynatrace_extension.sdk.communication import (
    MAX_LOG_REQUEST_SIZE,
    MAX_METRIC_REQUEST_SIZE,
    HttpClient,
    divide_into_batches,
)


class TestCommunication(unittest.TestCase):
    @patch("builtins.open", mock_open(read_data="test_token"))
    @patch.object(HttpClient, "_make_request", return_value=MagicMock())
    def test_http_client_metric_report(self, mock_make_request):
        http_client = HttpClient("https://localhost:9999", "1", "token", MagicMock())
        few_metrics = ["metric 1", "metric 2"]
        responses = http_client.send_metrics(few_metrics)
        self.assertEqual(len(responses), 1)

        many_metrics = ['my.metric,dim="dim" 10'] * 500 * 100
        responses = http_client.send_metrics(many_metrics)
        self.assertEqual(len(responses), 2)

        no_metrics = []
        responses = http_client.send_metrics(no_metrics)
        self.assertEqual(len(responses), 0)

    def test_large_log_chunk(self):

        # This is 14_660_000 bytes
        events = []
        for _ in range(5000):
            attributes = {}
            for j in range(150):
                attributes[f"attribute{j}"] = j
            events.append(attributes)

        # it needs to be divided into 4 lists, each with 3_665_000 bytes
        chunks = list(divide_into_batches(events, MAX_LOG_REQUEST_SIZE))
        self.assertEqual(len(chunks), 4)
        self.assertEqual(len(chunks[0]), 3665000)
        self.assertEqual(len(chunks[1]), 3665000)
        self.assertEqual(len(chunks[2]), 3665000)
        self.assertEqual(len(chunks[3]), 3665000)

    def test_small_log_chunk(self):
        events = []
        for _ in range(10):
            attributes = {}
            for j in range(10):
                attributes[f"attribute{j}"] = j
            events.append(attributes)

        chunks = list(divide_into_batches(events, MAX_LOG_REQUEST_SIZE))
        self.assertEqual(len(chunks), 1)
        self.assertEqual(len(chunks[0]), 1720)

    def test_large_metric_chunk(self):

        metrics = ['my.metric,dim="dim" 10'] * 500 * 100

        # it needs to be divided into 2 lists, each with 650_000 bytes
        chunks = list(divide_into_batches(metrics, MAX_METRIC_REQUEST_SIZE, "\n"))
        self.assertEqual(len(chunks), 2)
        self.assertEqual(len(chunks[0]), 574999)
        self.assertEqual(len(chunks[1]), 574999)

    def test_small_metric_chunk(self):
        metrics = ['my.metric,dim="dim" 10'] * 100

        chunks = list(divide_into_batches(metrics, MAX_METRIC_REQUEST_SIZE, "\n"))
        self.assertEqual(len(chunks), 1)
        self.assertEqual(len(chunks[0]), 2299)

    def test_no_metrics(self):
        metrics = []

        chunks = list(divide_into_batches(metrics, MAX_METRIC_REQUEST_SIZE, "\n"))
        self.assertEqual(len(chunks), 0)

    def test_large_log_chunk_valid_json(self):

        events = []
        for _ in range(5000):
            attributes = {}
            for j in range(150):
                attributes[f"attribute{j}"] = j
            events.append(attributes)

        # it needs to be divided into 4 lists, each with 3_665_000 bytes
        chunks = list(divide_into_batches(events, MAX_LOG_REQUEST_SIZE))
        self.assertEqual(len(chunks), 4)

        for chunk in chunks:
            json.loads(chunk)

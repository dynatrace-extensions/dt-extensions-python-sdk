import unittest
from unittest.mock import MagicMock, mock_open, patch

from dynatrace_extension.sdk.communication import HttpClient, divide_into_chunks


class TestCommunication(unittest.TestCase):
    def test_large_chunk(self):
        large_list = ["metric 1"] * 1400
        chunks = list(divide_into_chunks(large_list, 1000))
        self.assertEqual(len(chunks), 2)
        self.assertEqual(len(chunks[0]), 1000)
        self.assertEqual(len(chunks[1]), 400)

    def test_small_chunk(self):
        small_list = ["metric 1"] * 10
        chunks = list(divide_into_chunks(small_list, 1000))
        self.assertEqual(len(chunks), 1)
        self.assertEqual(len(chunks[0]), 10)

    @patch("builtins.open", mock_open(read_data="test_token"))
    @patch.object(HttpClient, "_make_request", return_value=MagicMock())
    def test_http_client_metric_report(self, mock_make_request):
        http_client = HttpClient("https://localhost:9999", "1", "token", MagicMock())
        few_metrics = ["metric 1", "metric 2"]
        responses = http_client.send_metrics(few_metrics)
        self.assertEqual(len(responses), 1)

        many_metrics = ["metric 1"] * 1400
        responses = http_client.send_metrics(many_metrics)
        self.assertEqual(len(responses), 2)

        no_metrics = []
        responses = http_client.send_metrics(no_metrics)
        self.assertEqual(len(responses), 0)

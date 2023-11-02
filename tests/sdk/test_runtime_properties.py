import logging
import unittest
from typing import Any, Dict

from dynatrace_extension import Extension
from dynatrace_extension.sdk.runtime import RuntimeProperties


class TestRuntimeProperties(unittest.TestCase):
    def tearDown(self) -> None:
        Extension._instance = None

    def test_api_log_level(self) -> None:
        response_json: Dict[str, Any] = {"runtime": {}}
        response_json["runtime"]["debuglevel.extension1.api"] = "debug"  # converted to debug
        response_json["runtime"]["debuglevel.extension2.api"] = "WARNING"  # wrong value - default to info

        runtime = RuntimeProperties(response_json)

        self.assertEqual(logging.DEBUG, runtime.get_api_log_level("extension1"))
        self.assertEqual(logging.INFO, runtime.get_api_log_level("extension2"))
        self.assertEqual(logging.INFO, runtime.get_api_log_level("extension3"))

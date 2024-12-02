import time
import unittest
from datetime import timedelta
from unittest.mock import MagicMock

from dynatrace_extension import Extension
from dynatrace_extension.sdk.communication import DebugClient
from dynatrace_extension.sdk.extension import Status, StatusValue


class TestStatus(unittest.TestCase):
    def tearDown(self) -> None:
        Extension._instance = None

    def test_status(self):
        status = Status(StatusValue.OK, "status message")
        self.assertEqual(status.status, StatusValue.OK)
        self.assertEqual(status.message, "status message")
        self.assertEqual(status.status.value, "OK")

    def test_overall_status(self):
        def callback():
            return 1

        ext = Extension()
        ext.logger = MagicMock()
        ext._running_in_sim = True
        ext._client = DebugClient("", "", MagicMock())
        ext._is_fastcheck = False
        ext.schedule(callback, timedelta(seconds=1))
        status = ext._build_current_status()

        self.assertEqual(status.status, StatusValue.OK)
        self.assertEqual(status.message, "")

    def test_bad_status(self):
        ext = Extension()
        ext.logger = MagicMock()
        ext._running_in_sim = True
        ext._client = DebugClient("", "", MagicMock())
        ext._is_fastcheck = False

        def bad_method():
            msg = "something went wrong"
            raise Exception(msg)

        ext.schedule(bad_method, timedelta(seconds=1))
        ext._scheduler.run(blocking=False)
        time.sleep(0.01)

        status = ext._build_current_status()
        self.assertEqual(status.status, StatusValue.GENERIC_ERROR)
        self.assertIn("something went wrong", status.message)

    def test_mutiple_bad_status(self):
        ext = Extension()
        ext.logger = MagicMock()
        ext._running_in_sim = True
        ext._client = DebugClient("", "", MagicMock())
        ext._is_fastcheck = False

        def bad_method_1():
            msg = "something went wrong"
            raise Exception(msg)

        def bad_method_2():
            msg = "something broke"
            raise Exception(msg)

        ext.schedule(bad_method_1, timedelta(seconds=1))
        ext.schedule(bad_method_2, timedelta(seconds=1))
        ext._scheduler.run(blocking=False)
        time.sleep(0.01)

        status = ext._build_current_status()
        self.assertEqual(status.status, StatusValue.GENERIC_ERROR)
        self.assertIn("something went wrong", status.message)
        self.assertIn("something broke", status.message)

    def test_callback_taking_too_long_sets_status(self):
        extension = Extension()
        extension.logger = MagicMock()
        extension._running_in_sim = True
        extension._is_fastcheck = False
        extension._client = MagicMock()

        def callback():
            time.sleep(1)

        extension.schedule(callback, timedelta(seconds=1))
        extension._scheduler.run(blocking=False)
        time.sleep(2)

        self.assertTrue(extension._scheduled_callbacks[1].status.is_error())
        self.assertIn("longer than the interval", extension._scheduled_callbacks[1].status.message)

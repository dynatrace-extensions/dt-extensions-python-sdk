import threading
import time
import unittest
from datetime import timedelta
from unittest.mock import MagicMock

from dynatrace_extension import EndpointStatus, EndpointStatuses, Extension, MultiStatus, Status, StatusValue
from dynatrace_extension.sdk.communication import DebugClient


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

    def test_multiple_bad_status(self):
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
        time.sleep(1)

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

    def test_direct_status_return(self):
        ext = Extension()
        ext.logger = MagicMock()
        ext._running_in_sim = True
        ext._client = DebugClient("", "", MagicMock())
        ext._is_fastcheck = False

        def callback():
            return Status(StatusValue.OK, "foo1")

        ext.schedule(callback, timedelta(seconds=1))
        ext._scheduler.run(blocking=False)
        time.sleep(0.01)

        status = ext._build_current_status()
        self.assertEqual(status.status, StatusValue.OK)
        self.assertIn("foo1", status.message)

    def test_direct_statuses_return(self):
        def callback():
            return Status(StatusValue.OK, "foo1")

        def custom_query():
            return Status(StatusValue.EMPTY, "foo2")

        ext = Extension()
        ext.logger = MagicMock()
        ext._running_in_sim = True
        ext._client = DebugClient("", "", MagicMock())
        ext._is_fastcheck = False

        ext.schedule(callback, timedelta(seconds=1))
        ext.schedule(custom_query, timedelta(seconds=1))
        ext._scheduler.run(blocking=False)
        time.sleep(0.01)

        status = ext._build_current_status()
        self.assertEqual(status.status, StatusValue.OK)
        self.assertIn("foo1", status.message)
        self.assertIn("foo2", status.message)

    def test_multistatus_empty(self):
        ext = Extension()
        ext.logger = MagicMock()
        ext._running_in_sim = True
        ext._client = DebugClient("", "", MagicMock())
        ext._is_fastcheck = False

        def callback():
            ret = MultiStatus()
            return ret

        ext.schedule(callback, timedelta(seconds=1))
        ext._scheduler.run(blocking=False)
        time.sleep(1)

        status = ext._build_current_status()
        self.assertEqual(status.status, StatusValue.OK)

    def test_multistatus_ok(self):
        ext = Extension()
        ext.logger = MagicMock()
        ext._running_in_sim = True
        ext._client = DebugClient("", "", MagicMock())
        ext._is_fastcheck = False

        def callback():
            ret = MultiStatus()
            ret.add_status(StatusValue.OK, "foo1")
            ret.add_status(StatusValue.OK, "foo2")
            return ret

        ext.schedule(callback, timedelta(seconds=1))
        ext._scheduler.run(blocking=False)
        time.sleep(1)

        status = ext._build_current_status()
        self.assertEqual(status.status, StatusValue.OK)
        self.assertIn("foo1", status.message)
        self.assertIn("foo2", status.message)

    def test_multistatus_warning_1(self):
        ext = Extension()
        ext.logger = MagicMock()
        ext._running_in_sim = True
        ext._client = DebugClient("", "", MagicMock())
        ext._is_fastcheck = False

        def callback():
            ret = MultiStatus()
            ret.add_status(StatusValue.OK, "foo1")
            ret.add_status(StatusValue.GENERIC_ERROR, "foo2")
            return ret

        ext.schedule(callback, timedelta(seconds=1))
        ext._scheduler.run(blocking=False)
        time.sleep(1)

        status = ext._build_current_status()
        self.assertEqual(status.status, StatusValue.WARNING)
        self.assertIn("foo1", status.message)
        self.assertIn("foo2", status.message)

    def test_multistatus_warning_2(self):
        ext = Extension()
        ext.logger = MagicMock()
        ext._running_in_sim = True
        ext._client = DebugClient("", "", MagicMock())
        ext._is_fastcheck = False

        def callback():
            ret = MultiStatus()
            ret.add_status(StatusValue.OK, "foo1")
            ret.add_status(StatusValue.WARNING, "foo2")
            return ret

        ext.schedule(callback, timedelta(seconds=1))
        ext._scheduler.run(blocking=False)
        time.sleep(1)

        status = ext._build_current_status()
        self.assertEqual(status.status, StatusValue.WARNING)
        self.assertIn("foo1", status.message)
        self.assertIn("foo2", status.message)

    def test_multistatus_warning_3(self):
        ext = Extension()
        ext.logger = MagicMock()
        ext._running_in_sim = True
        ext._client = DebugClient("", "", MagicMock())
        ext._is_fastcheck = False

        def callback():
            ret = MultiStatus()
            ret.add_status(StatusValue.GENERIC_ERROR, "foo1")
            ret.add_status(StatusValue.WARNING, "foo2")
            return ret

        ext.schedule(callback, timedelta(seconds=1))
        ext._scheduler.run(blocking=False)
        time.sleep(1)

        status = ext._build_current_status()
        self.assertEqual(status.status, StatusValue.WARNING)
        self.assertIn("foo1", status.message)
        self.assertIn("foo2", status.message)

    def test_multistatus_single_warning(self):
        ext = Extension()
        ext.logger = MagicMock()
        ext._running_in_sim = True
        ext._client = DebugClient("", "", MagicMock())
        ext._is_fastcheck = False

        def callback():
            ret = MultiStatus()
            ret.add_status(StatusValue.WARNING, "foo1")
            return ret

        ext.schedule(callback, timedelta(seconds=1))
        ext._scheduler.run(blocking=False)
        time.sleep(1)

        status = ext._build_current_status()
        self.assertEqual(status.status, StatusValue.WARNING)
        self.assertIn("foo1", status.message)

    def test_multistatus_error(self):
        ext = Extension()
        ext.logger = MagicMock()
        ext._running_in_sim = True
        ext._client = DebugClient("", "", MagicMock())
        ext._is_fastcheck = False

        def callback():
            ret = MultiStatus()
            ret.add_status(StatusValue.AUTHENTICATION_ERROR, "foo1")
            ret.add_status(StatusValue.DEVICE_CONNECTION_ERROR, "foo2")
            return ret

        ext.schedule(callback, timedelta(seconds=1))
        ext._scheduler.run(blocking=False)
        time.sleep(1)

        status = ext._build_current_status()
        self.assertEqual(status.status, StatusValue.GENERIC_ERROR)
        self.assertIn("foo1", status.message)
        self.assertIn("foo2", status.message)

    def test_endpoint_status_all_ok(self):
        ext = Extension()
        ext.logger = MagicMock()
        ext._running_in_sim = True
        ext._client = DebugClient("", "", MagicMock())
        ext._is_fastcheck = False

        def callback():
            statuses = EndpointStatuses()
            statuses.add_endpoint_status(EndpointStatus("1.2.3.4:80", StatusValue.OK, "All good 1"))
            statuses.add_endpoint_status(EndpointStatus("4.5.6.7:80", StatusValue.OK, "All good 2"))

            statuses.add_endpoint_status(EndpointStatus("6.7.8.9:80", StatusValue.OK, "All good 3"))

            return statuses

        ext.schedule(callback, timedelta(seconds=1))
        ext._scheduler.run(blocking=False)
        time.sleep(0.01)

        status = ext._build_current_status()
        self.assertEqual(status.status, StatusValue.OK)
        self.assertIn("OK: 3 WARNING: 0 ERROR: 0", status.message)

    def test_endpoint_status_some_faulty_endpoints(self):
        ext = Extension()
        ext.logger = MagicMock()
        ext._running_in_sim = True
        ext._client = DebugClient("", "", MagicMock())
        ext._is_fastcheck = False

        def callback():
            statuses = EndpointStatuses()
            statuses.add_endpoint_status(EndpointStatus("1.2.3.4:80", StatusValue.OK, "Invalid authorization scheme 1"))
            statuses.add_endpoint_status(
                EndpointStatus("4.5.6.7:80", StatusValue.DEVICE_CONNECTION_ERROR, "Invalid authorization scheme 2")
            )

            statuses.add_endpoint_status(
                EndpointStatus("6.7.8.9:80", StatusValue.DEVICE_CONNECTION_ERROR, "Invalid authorization scheme 3")
            )

            return statuses

        ext.schedule(callback, timedelta(seconds=1))
        ext._scheduler.run(blocking=False)
        time.sleep(0.01)

        status = ext._build_current_status()
        self.assertEqual(status.status, StatusValue.WARNING)
        self.assertIn(
            "Endpoints OK: 1 WARNING: 0 ERROR: 2 Unhealthy endpoints: "
            "4.5.6.7:80 - DEVICE_CONNECTION_ERROR Invalid authorization scheme 2, 6.7.8.9:80 - DEVICE_CONNECTION_ERROR Invalid authorization scheme 3",
            status.message,
        )

    def test_endpoint_status_all_faulty_endpoints(self):
        ext = Extension()
        ext.logger = MagicMock()
        ext._running_in_sim = True
        ext._client = DebugClient("", "", MagicMock())
        ext._is_fastcheck = False

        def callback():
            statuses = EndpointStatuses()
            statuses.add_endpoint_status(
                EndpointStatus("1.2.3.4:80", StatusValue.AUTHENTICATION_ERROR, "Invalid authorization scheme 4")
            )
            statuses.add_endpoint_status(
                EndpointStatus("4.5.6.7:80", StatusValue.DEVICE_CONNECTION_ERROR, "Invalid authorization scheme 5")
            )

            statuses.add_endpoint_status(
                EndpointStatus("6.7.8.9:80", StatusValue.DEVICE_CONNECTION_ERROR, "Invalid authorization scheme 6")
            )

            return statuses

        ext.schedule(callback, timedelta(seconds=1))
        ext._scheduler.run(blocking=False)
        time.sleep(0.01)

        status = ext._build_current_status()
        self.assertEqual(status.status, StatusValue.GENERIC_ERROR)
        self.assertIn(
            "Endpoints OK: 0 WARNING: 0 ERROR: 3 Unhealthy endpoints: 1.2.3.4:80 - AUTHENTICATION_ERROR Invalid authorization scheme 4, "
            "4.5.6.7:80 - DEVICE_CONNECTION_ERROR Invalid authorization scheme 5, 6.7.8.9:80 - DEVICE_CONNECTION_ERROR Invalid authorization scheme 6",
            status.message,
        )

    def test_endpoint_empty(self):
        ext = Extension()
        ext.logger = MagicMock()
        ext._running_in_sim = True
        ext._client = DebugClient("", "", MagicMock())
        ext._is_fastcheck = False

        def callback():
            statuses = EndpointStatuses()
            return statuses

        ext.schedule(callback, timedelta(seconds=1))
        ext._scheduler.run(blocking=False)
        time.sleep(0.01)

        status = ext._build_current_status()
        self.assertEqual(status.status, StatusValue.OK)
        self.assertNotIn("Endpoints", status.message)

    def test_endpoint_status_single_warning(self):
        ext = Extension()
        ext.logger = MagicMock()
        ext._running_in_sim = True
        ext._client = DebugClient("", "", MagicMock())
        ext._is_fastcheck = False

        def callback():
            statuses = EndpointStatuses()
            statuses.add_endpoint_status(
                EndpointStatus("1.2.3.4:80", StatusValue.WARNING, "Invalid authorization scheme A")
            )
            return statuses

        ext.schedule(callback, timedelta(seconds=1))
        ext._scheduler.run(blocking=False)
        time.sleep(0.01)

        status = ext._build_current_status()
        self.assertEqual(status.status, StatusValue.WARNING)
        self.assertIn(
            "Endpoints OK: 0 WARNING: 1 ERROR: 0 Unhealthy endpoints: 1.2.3.4:80 - WARNING Invalid authorization scheme A",
            status.message,
        )

    def test_endpoint_status_single_error(self):
        ext = Extension()
        ext.logger = MagicMock()
        ext._running_in_sim = True
        ext._client = DebugClient("", "", MagicMock())
        ext._is_fastcheck = False

        def callback():
            statuses = EndpointStatuses()
            statuses.add_endpoint_status(
                EndpointStatus("1.2.3.4:80", StatusValue.AUTHENTICATION_ERROR, "Invalid authorization scheme")
            )
            return statuses

        ext.schedule(callback, timedelta(seconds=1))
        ext._scheduler.run(blocking=False)
        time.sleep(0.01)

        status = ext._build_current_status()
        self.assertEqual(status.status, StatusValue.GENERIC_ERROR)
        self.assertIn(
            "OK: 0 WARNING: 0 ERROR: 1 Unhealthy endpoints: 1.2.3.4:80 - AUTHENTICATION_ERROR Invalid authorization scheme",
            status.message,
        )

    def test_endpoint_merge_ok(self):
        def callback_ep_status_1():
            status = EndpointStatuses()
            status.add_endpoint_status(EndpointStatus("1.2.3.4:80", StatusValue.OK, "All good 1"))
            return status

        def callback_ep_status_2():
            status = EndpointStatuses()
            status.add_endpoint_status(EndpointStatus("5.6.7.8:90", StatusValue.OK, "All good 2"))
            status.add_endpoint_status(EndpointStatus("10.11.12.13:100", StatusValue.OK, "All good 3"))
            return status

        ext = Extension()
        ext.logger = MagicMock()
        ext._running_in_sim = True
        ext._client = DebugClient("", "", MagicMock())
        ext._is_fastcheck = False

        ext.schedule(callback_ep_status_1, timedelta(seconds=1))
        ext.schedule(callback_ep_status_2, timedelta(seconds=1))
        ext._scheduler.run(blocking=False)
        time.sleep(0.01)

        status = ext._build_current_status()
        self.assertEqual(status.status, StatusValue.OK)
        self.assertIn("OK: 3 WARNING: 0 ERROR: 0", status.message)

    def test_endpoint_merge_error(self):
        def callback_ep_status_1():
            status = EndpointStatuses()
            status.add_endpoint_status(EndpointStatus("EP_HINT_1", StatusValue.AUTHENTICATION_ERROR, "EP1 MSG"))
            return status

        def callback_ep_status_2():
            status = EndpointStatuses()
            status.add_endpoint_status(EndpointStatus("EP_HINT_2", StatusValue.INVALID_CONFIG_ERROR, "EP2 MSG"))
            return status

        ext = Extension()
        ext.logger = MagicMock()
        ext._running_in_sim = True
        ext._client = DebugClient("", "", MagicMock())
        ext._is_fastcheck = False

        ext.schedule(callback_ep_status_1, timedelta(seconds=1))
        ext.schedule(callback_ep_status_2, timedelta(seconds=1))
        ext._scheduler.run(blocking=False)
        time.sleep(0.01)

        status = ext._build_current_status()
        self.assertEqual(status.status, StatusValue.GENERIC_ERROR)
        self.assertIn(
            "OK: 0 WARNING: 0 ERROR: 2 Unhealthy endpoints: EP_HINT_1 - AUTHENTICATION_ERROR EP1 MSG, EP_HINT_2 - INVALID_CONFIG_ERROR EP2 MSG",
            status.message,
        )

    def test_endpoint_merge_warning(self):
        def callback_ep_status_1():
            status = EndpointStatuses()
            status.add_endpoint_status(EndpointStatus("EP_HINT_1", StatusValue.OK, "EP1 MSG"))
            return status

        def callback_ep_status_2():
            status = EndpointStatuses()
            status.add_endpoint_status(EndpointStatus("EP_HINT_2", StatusValue.WARNING, "EP2 MSG"))
            return status

        ext = Extension()
        ext.logger = MagicMock()
        ext._running_in_sim = True
        ext._client = DebugClient("", "", MagicMock())
        ext._is_fastcheck = False

        ext.schedule(callback_ep_status_1, timedelta(seconds=1))
        ext.schedule(callback_ep_status_2, timedelta(seconds=1))
        ext._scheduler.run(blocking=False)
        time.sleep(0.01)

        status = ext._build_current_status()
        self.assertEqual(status.status, StatusValue.WARNING)
        self.assertIn("OK: 1 WARNING: 1 ERROR: 0 Unhealthy endpoints: EP_HINT_2 - WARNING EP2 MSG", status.message)

    def test_overall_status_error(self):
        def callback_ep_status():
            status = EndpointStatuses()
            status.add_endpoint_status(EndpointStatus("EP_HINT", StatusValue.UNKNOWN_ERROR, "EP MSG"))
            return status

        def callback_multistatus():
            status = MultiStatus()
            status.add_status(StatusValue.INVALID_ARGS_ERROR, "MULTI MSG")
            return status

        def callback_status():
            status = Status(StatusValue.EEC_CONNECTION_ERROR, "STATUS MSG")
            return status

        ext = Extension()
        ext.logger = MagicMock()
        ext._running_in_sim = True
        ext._client = DebugClient("", "", MagicMock())
        ext._is_fastcheck = False

        ext.schedule(callback_ep_status, timedelta(seconds=1))
        ext.schedule(callback_multistatus, timedelta(seconds=1))
        ext.schedule(callback_status, timedelta(seconds=1))
        ext._scheduler.run(blocking=False)
        time.sleep(0.01)

        status = ext._build_current_status()
        self.assertEqual(status.status, StatusValue.GENERIC_ERROR)
        self.assertIn(
            "Endpoints OK: 0 WARNING: 0 ERROR: 1 Unhealthy endpoints: EP_HINT - UNKNOWN_ERROR EP MSG"
            "\ncallback_multistatus: GENERIC_ERROR - MULTI MSG\ncallback_status: EEC_CONNECTION_ERROR - STATUS MSG",
            status.message,
        )

    def test_overall_status_ok(self):
        def callback_ep_status():
            status = EndpointStatuses()
            status.add_endpoint_status(EndpointStatus("EP_HINT", StatusValue.OK, "EP MSG"))
            return status

        def callback_multistatus():
            status = MultiStatus()
            status.add_status(StatusValue.OK, "")
            return status

        def callback_status():
            status = Status(StatusValue.OK, "STATUS MSG")
            return status

        ext = Extension()
        ext.logger = MagicMock()
        ext._running_in_sim = True
        ext._client = DebugClient("", "", MagicMock())
        ext._is_fastcheck = False

        ext.schedule(callback_ep_status, timedelta(seconds=1))
        ext.schedule(callback_multistatus, timedelta(seconds=1))
        ext.schedule(callback_status, timedelta(seconds=1))
        ext._scheduler.run(blocking=False)
        time.sleep(0.01)

        status = ext._build_current_status()
        self.assertEqual(status.status, StatusValue.OK)
        self.assertIn("Endpoints OK: 1 WARNING: 0 ERROR: 0\ncallback_status: OK - STATUS MSG", status.message)

    def test_overall_status_warning_1(self):
        def callback_ep_status():
            status = EndpointStatuses()
            status.add_endpoint_status(EndpointStatus("EP_HINT", StatusValue.WARNING, "EP MSG"))
            return status

        def callback_multistatus():
            status = MultiStatus()
            status.add_status(StatusValue.OK, "MULTI MSG")
            return status

        def callback_status():
            status = Status(StatusValue.OK, "")
            return status

        ext = Extension()
        ext.logger = MagicMock()
        ext._running_in_sim = True
        ext._client = DebugClient("", "", MagicMock())
        ext._is_fastcheck = False

        ext.schedule(callback_ep_status, timedelta(seconds=1))
        ext.schedule(callback_multistatus, timedelta(seconds=1))
        ext.schedule(callback_status, timedelta(seconds=1))
        ext._scheduler.run(blocking=False)
        time.sleep(0.01)

        status = ext._build_current_status()
        self.assertEqual(status.status, StatusValue.WARNING)
        self.assertIn(
            "Endpoints OK: 0 WARNING: 1 ERROR: 0 Unhealthy endpoints: EP_HINT - WARNING EP MSG\ncallback_multistatus: OK - MULTI MSG",
            status.message,
        )

    def test_overall_status_warning_2(self):
        def callback_ep_status():
            status = EndpointStatuses()
            status.add_endpoint_status(EndpointStatus("EP_HINT", StatusValue.INVALID_CONFIG_ERROR, ""))
            return status

        def callback_multistatus():
            status = MultiStatus()
            status.add_status(StatusValue.INVALID_ARGS_ERROR, "")
            return status

        def callback_status():
            status = Status(StatusValue.WARNING, "")
            return status

        ext = Extension()
        ext.logger = MagicMock()
        ext._running_in_sim = True
        ext._client = DebugClient("", "", MagicMock())
        ext._is_fastcheck = False

        ext.schedule(callback_ep_status, timedelta(seconds=1))
        ext.schedule(callback_multistatus, timedelta(seconds=1))
        ext.schedule(callback_status, timedelta(seconds=1))
        ext._scheduler.run(blocking=False)
        time.sleep(0.01)

        status = ext._build_current_status()
        self.assertEqual(status.status, StatusValue.WARNING)
        self.assertIn(
            "Endpoints OK: 0 WARNING: 0 ERROR: 1 Unhealthy endpoints: EP_HINT - INVALID_CONFIG_ERROR "
            "\ncallback_multistatus: GENERIC_ERROR - "
            "\ncallback_status: WARNING - ",
            status.message,
        )

    def test_endpoint_status_skipped_interval(self):
        ext = Extension()
        ext.logger = MagicMock()
        ext._running_in_sim = True
        ext._client = DebugClient("", "", MagicMock())
        ext._is_fastcheck = False

        skipped_callback_call_counter = 0
        regular_callback_call_counter = 0

        def skipped_callback():
            nonlocal skipped_callback_call_counter
            skipped_callback_call_counter += 1

            statuses = EndpointStatuses()
            statuses.add_endpoint_status(
                EndpointStatus("skipped_callback", StatusValue.GENERIC_ERROR, "skipped_callback_msg")
            )
            return statuses

        def regular_callback():
            nonlocal regular_callback_call_counter
            regular_callback_call_counter += 1
            statuses = EndpointStatuses()
            statuses.add_endpoint_status(
                EndpointStatus("regular_callback", StatusValue.UNKNOWN_ERROR, "regular_callback_msg")
            )
            return statuses

        ext.schedule(skipped_callback, timedelta(seconds=10))  # called only once during test
        ext.schedule(regular_callback, timedelta(seconds=1))

        # Runngin scheduler in another thread as we need it to run in parallel in this test
        class KillSchedulerError(Exception):
            pass

        def scheduler_thread_impl(ext: Extension):
            try:
                ext._scheduler.run(blocking=True)
            except KillSchedulerError:
                pass

        scheduler_thread = threading.Thread(target=scheduler_thread_impl, args=(ext,))
        scheduler_thread.start()
        time.sleep(0.01)

        # 5 second of test
        for _ in range(5):
            status = ext._build_current_status()
            self.assertEqual(status.status, StatusValue.GENERIC_ERROR)
            self.assertIn(
                (
                    "Endpoints OK: 0 WARNING: 0 ERROR: 2 Unhealthy endpoints: "
                    "skipped_callback - GENERIC_ERROR skipped_callback_msg, regular_callback - UNKNOWN_ERROR regular_callback_msg"
                ),
                status.message,
            )
            time.sleep(1)

        ext._scheduler.enter(delay=0, priority=1, action=lambda: (_ for _ in ()).throw(KillSchedulerError()))
        scheduler_thread.join()

        # Confirm schedulered called callbacks as requested
        self.assertEqual(skipped_callback_call_counter, 1)
        self.assertEqual(regular_callback_call_counter, 6)

import time
import unittest
from datetime import timedelta
from unittest.mock import MagicMock

from dynatrace_extension import EndpointStatus, EndpointStatuses, Extension, Status, StatusValue
from dynatrace_extension.sdk.communication import DebugClient, MultiStatus


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
            return EndpointStatuses(10)

        ext.schedule(callback, timedelta(seconds=1))
        ext._scheduler.run(blocking=False)
        time.sleep(0.01)

        status = ext._build_current_status()
        self.assertEqual(status.status, StatusValue.OK)
        self.assertIn("OK: 10 NOK: 0", status.message)

    def test_endpoint_status_some_faulty_endpoints(self):
        ext = Extension()
        ext.logger = MagicMock()
        ext._running_in_sim = True
        ext._client = DebugClient("", "", MagicMock())
        ext._is_fastcheck = False

        def callback():
            statuses = EndpointStatuses(10)
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
            "OK: 8 NOK: 2 NOK_reported_errors: 4.5.6.7:80 - DEVICE_CONNECTION_ERROR "
            "Invalid authorization scheme 2, 6.7.8.9:80 - DEVICE_CONNECTION_ERROR Invalid authorization scheme 3",
            status.message,
        )

    def test_endpoint_status_all_faulty_endpoints(self):
        ext = Extension()
        ext.logger = MagicMock()
        ext._running_in_sim = True
        ext._client = DebugClient("", "", MagicMock())
        ext._is_fastcheck = False

        def callback():
            statuses = EndpointStatuses(3)
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
            "OK: 0 NOK: 3 NOK_reported_errors: 1.2.3.4:80 - AUTHENTICATION_ERROR "
            "Invalid authorization scheme 4, 4.5.6.7:80 - DEVICE_CONNECTION_ERROR "
            "Invalid authorization scheme 5, 6.7.8.9:80 - DEVICE_CONNECTION_ERROR Invalid authorization scheme 6",
            status.message,
        )

    def test_endpoint_status_clearing_the_status(self):
        ext = Extension()
        ext.logger = MagicMock()
        ext._running_in_sim = True
        ext._client = DebugClient("", "", MagicMock())
        ext._is_fastcheck = False

        def callback():
            statuses = EndpointStatuses(10)
            statuses.add_endpoint_status(
                EndpointStatus("1.2.3.4:80", StatusValue.AUTHENTICATION_ERROR, "Invalid authorization scheme 7")
            )

            statuses.add_endpoint_status(
                EndpointStatus("4.5.6.7:80", StatusValue.DEVICE_CONNECTION_ERROR, "Invalid authorization scheme 8")
            )

            statuses.add_endpoint_status(
                EndpointStatus("6.7.8.9:80", StatusValue.DEVICE_CONNECTION_ERROR, "Invalid authorization scheme 9")
            )

            statuses.add_endpoint_status(
                EndpointStatus("4.5.6.7:80", StatusValue.OK, "Invalid authorization scheme 10")
            )

            statuses.clear_endpoint_error("6.7.8.9:80")

            return statuses

        ext.schedule(callback, timedelta(seconds=1))
        ext._scheduler.run(blocking=False)
        time.sleep(0.01)

        status = ext._build_current_status()
        self.assertEqual(status.status, StatusValue.WARNING)
        self.assertIn(
            "OK: 9 NOK: 1 NOK_reported_errors: 1.2.3.4:80 - AUTHENTICATION_ERROR Invalid authorization scheme 7",
            status.message,
        )

    def test_endpoint_status_max(self):
        ext = Extension()
        ext.logger = MagicMock()
        ext._running_in_sim = True
        ext._client = DebugClient("", "", MagicMock())
        ext._is_fastcheck = False

        def callback():
            statuses = EndpointStatuses(2)
            statuses.add_endpoint_status(
                EndpointStatus("1.2.3.4:80", StatusValue.AUTHENTICATION_ERROR, "Invalid authorization scheme A")
            )

            statuses.add_endpoint_status(
                EndpointStatus("4.5.6.7:80", StatusValue.DEVICE_CONNECTION_ERROR, "Invalid authorization scheme B")
            )

            with self.assertRaises(EndpointStatuses.TooManyEndpointStatusesError):
                statuses.add_endpoint_status(
                    EndpointStatus("6.7.8.9:80", StatusValue.DEVICE_CONNECTION_ERROR, "Invalid authorization scheme C")
                )
            return statuses

        ext.schedule(callback, timedelta(seconds=1))
        ext._scheduler.run(blocking=False)
        time.sleep(0.01)

        status = ext._build_current_status()
        self.assertEqual(status.status, StatusValue.GENERIC_ERROR)
        self.assertIn(
            "OK: 0 NOK: 2 NOK_reported_errors: 1.2.3.4:80 - AUTHENTICATION_ERROR "
            "Invalid authorization scheme A, 4.5.6.7:80 - DEVICE_CONNECTION_ERROR Invalid authorization scheme B",
            status.message,
        )

    def test_endpoint_empty(self):
        ext = Extension()
        ext.logger = MagicMock()
        ext._running_in_sim = True
        ext._client = DebugClient("", "", MagicMock())
        ext._is_fastcheck = False

        def callback():
            statuses = EndpointStatuses(3)
            return statuses

        ext.schedule(callback, timedelta(seconds=1))
        ext._scheduler.run(blocking=False)
        time.sleep(0.01)

        status = ext._build_current_status()
        self.assertEqual(status.status, StatusValue.OK)
        self.assertIn("OK: 3 NOK: 0", status.message)

    def test_endpoint_status_single_warning(self):
        ext = Extension()
        ext.logger = MagicMock()
        ext._running_in_sim = True
        ext._client = DebugClient("", "", MagicMock())
        ext._is_fastcheck = False

        def callback():
            statuses = EndpointStatuses(1)
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
            "OK: 0 NOK: 1 NOK_reported_errors: 1.2.3.4:80 - WARNING Invalid authorization scheme A", status.message
        )

    def test_endpoint_status_single_error(self):
        ext = Extension()
        ext.logger = MagicMock()
        ext._running_in_sim = True
        ext._client = DebugClient("", "", MagicMock())
        ext._is_fastcheck = False

        def callback():
            statuses = EndpointStatuses(1)
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
            "OK: 0 NOK: 1 NOK_reported_errors: 1.2.3.4:80 - AUTHENTICATION_ERROR Invalid authorization scheme",
            status.message,
        )

    def test_endpoint_merge_ok(self):
        def callback_ep_status_1():
            status = EndpointStatuses(1)
            return status

        def callback_ep_status_2():
            status = EndpointStatuses(2)
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
        self.assertIn("OK: 3 NOK: 0", status.message)

    def test_endpoint_merge_error(self):
        def callback_ep_status_1():
            status = EndpointStatuses(1)
            status.add_endpoint_status(EndpointStatus("EP_HINT_1", StatusValue.AUTHENTICATION_ERROR, "EP1 MSG"))
            return status

        def callback_ep_status_2():
            status = EndpointStatuses(1)
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
            "OK: 0 NOK: 2 NOK_reported_errors: EP_HINT_1 - AUTHENTICATION_ERROR EP1 MSG, EP_HINT_2 - INVALID_CONFIG_ERROR EP2 MSG",
            status.message,
        )

    def test_endpoint_merge_warning(self):
        def callback_ep_status_1():
            status = EndpointStatuses(1)
            status.add_endpoint_status(EndpointStatus("EP_HINT_1", StatusValue.OK, "EP1 MSG"))
            return status

        def callback_ep_status_2():
            status = EndpointStatuses(1)
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
        self.assertIn("OK: 1 NOK: 1 NOK_reported_errors: EP_HINT_2 - WARNING EP2 MSG", status.message)

    def test_overall_status_error(self):
        def callback_ep_status():
            status = EndpointStatuses(1)
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
            "Endpoints OK: 0 NOK: 1 NOK_reported_errors: EP_HINT - UNKNOWN_ERROR EP MSG"
            "\ncallback_multistatus: GENERIC_ERROR - MULTI MSG\ncallback_status: EEC_CONNECTION_ERROR - STATUS MSG",
            status.message,
        )

    def test_overall_status_ok(self):
        def callback_ep_status():
            status = EndpointStatuses(1)
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
        self.assertIn("Endpoints OK: 1 NOK: 0\ncallback_status: OK - STATUS MSG", status.message)

    def test_overall_status_warning_1(self):
        def callback_ep_status():
            status = EndpointStatuses(1)
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
            "Endpoints OK: 0 NOK: 1 NOK_reported_errors: EP_HINT - WARNING EP MSG\ncallback_multistatus: OK - MULTI MSG",
            status.message,
        )

    def test_overall_status_warning_2(self):
        def callback_ep_status():
            status = EndpointStatuses(1)
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
            "Endpoints OK: 0 NOK: 1 NOK_reported_errors: EP_HINT - INVALID_CONFIG_ERROR "
            "\ncallback_multistatus: GENERIC_ERROR - \ncallback_status: WARNING - ",
            status.message,
        )

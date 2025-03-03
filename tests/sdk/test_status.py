import time
import unittest
from datetime import timedelta
from unittest.mock import MagicMock

from dynatrace_extension import Extension

from dynatrace_extension.sdk.communication import DebugClient, MultiStatus
from dynatrace_extension.sdk.extension import Status, StatusValue, EndpointStatuses, EndpointStatus, EndpointSeverity


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

    def test_multistatus(self):
        ext = Extension()
        ext.logger = MagicMock()
        ext._running_in_sim = True
        ext._client = DebugClient("", "", MagicMock())
        ext._is_fastcheck = False

        def callback():
            ret = MultiStatus()
            ret.add_status(StatusValue.OK, "foo1")
            ret.add_status(StatusValue.UNKNOWN_ERROR, "foo2")
            return ret

        ext.schedule(callback, timedelta(seconds=1))
        ext._scheduler.run(blocking=False)
        time.sleep(1)

        status = ext._build_current_status()
        self.assertEqual(status.status, StatusValue.UNKNOWN_ERROR)
        self.assertIn("foo1", status.message)

    def test_endpoint_status_all_ok(self):
        ext = Extension()
        ext.logger = MagicMock()
        ext._running_in_sim = True
        ext._client = DebugClient("", "", MagicMock())
        ext._is_fastcheck = False

        def callback():
            statuses = EndpointStatuses(10)
            assert statuses.get_summarized_severity() == EndpointSeverity.INFO
            return statuses

        ext.schedule(callback, timedelta(seconds=1))
        ext._scheduler.run(blocking=False)
        time.sleep(0.01)

        status = ext._build_current_status()
        self.assertEqual(status.status, StatusValue.OK)
        self.assertIn("All 10 endpoints are OK and returned 0 metrics.", status.message)

    def test_endpoint_status_all_ok_metrics(self):
        ext = Extension()
        ext.logger = MagicMock()
        ext._running_in_sim = True
        ext._client = DebugClient("", "", MagicMock())
        ext._is_fastcheck = False

        def callback():
            statuses = EndpointStatuses(10)
            statuses.add_reported_metrics(20)
            statuses.add_reported_metrics(40)            
            statuses.add_reported_metrics(40)
            statuses.add_reported_metrics(-1)
            statuses.add_reported_metrics(0)

            assert statuses.get_summarized_severity() == EndpointSeverity.INFO

            return statuses

        ext.schedule(callback, timedelta(seconds=1))
        ext._scheduler.run(blocking=False)
        time.sleep(0.01)

        status = ext._build_current_status()
        self.assertEqual(status.status, StatusValue.OK)
        self.assertIn("All 10 endpoints are OK and returned 100 metrics", status.message)

    def test_endpoint_status_faulty_endpoints(self):
        ext = Extension()
        ext.logger = MagicMock()
        ext._running_in_sim = True
        ext._client = DebugClient("", "", MagicMock())
        ext._is_fastcheck = False

        def callback():
            statuses = EndpointStatuses(10)
            statuses.add_endpoint_status(
                EndpointStatus("1.2.3.4:80",
                               EndpointSeverity.INFO,
                               StatusValue.AUTHENTICATION_ERROR,
                               "Invalid authorization scheme"))
            statuses.add_endpoint_status(
                EndpointStatus("4.5.6.7:80",
                               EndpointSeverity.ERROR,
                               StatusValue.DEVICE_CONNECTION_ERROR,
                               "Invalid authorization scheme"))
                        
            statuses.add_reported_metrics(20)

            statuses.add_endpoint_status(
                EndpointStatus("6.7.8.9:80",
                               EndpointSeverity.WARNING,
                               StatusValue.DEVICE_CONNECTION_ERROR,
                               "Invalid authorization scheme"))
            
            assert statuses.get_summarized_severity() == EndpointSeverity.ERROR

            return statuses

        ext.schedule(callback, timedelta(seconds=1))
        ext._scheduler.run(blocking=False)
        time.sleep(0.01)

        status = ext._build_current_status()
        self.assertEqual(status.status, StatusValue.GENERIC_ERROR)
        self.assertIn("3 out of 10 endpoints work incorrectly. Returned 20 metrics. Malfunctioning endpoints: 1.2.3.4:80: AUTHENTICATION_ERROR, 4.5.6.7:80: DEVICE_CONNECTION_ERROR, 6.7.8.9:80: DEVICE_CONNECTION_ERROR", status.message)

    def test_endpoint_status_clearing_the_status(self):
        ext = Extension()
        ext.logger = MagicMock()
        ext._running_in_sim = True
        ext._client = DebugClient("", "", MagicMock())
        ext._is_fastcheck = False

        def callback():
            statuses = EndpointStatuses(10)
            statuses.add_endpoint_status(
                EndpointStatus("1.2.3.4:80",
                               EndpointSeverity.INFO,
                               StatusValue.AUTHENTICATION_ERROR,
                               "Invalid authorization scheme"))
            
            statuses.add_endpoint_status(
                EndpointStatus("4.5.6.7:80",
                               EndpointSeverity.WARNING,
                               StatusValue.DEVICE_CONNECTION_ERROR,
                               "Invalid authorization scheme"))

            statuses.add_endpoint_status(
                EndpointStatus("6.7.8.9:80",
                               EndpointSeverity.ERROR,
                               StatusValue.DEVICE_CONNECTION_ERROR,
                               "Invalid authorization scheme"))
                       
            statuses.add_endpoint_status(
                EndpointStatus("4.5.6.7:80",
                               EndpointSeverity.ERROR,
                               StatusValue.OK,
                               "Invalid authorization scheme"))
            
            statuses.clear_endpoint_error("6.7.8.9:80")

            assert statuses.get_summarized_severity() == EndpointSeverity.INFO

            return statuses

        ext.schedule(callback, timedelta(seconds=1))
        ext._scheduler.run(blocking=False)
        time.sleep(0.01)

        status = ext._build_current_status()
        self.assertEqual(status.status, StatusValue.GENERIC_ERROR)
        self.assertIn("1 out of 10 endpoints work incorrectly. Returned 0 metrics. Malfunctioning endpoints: 1.2.3.4:80: AUTHENTICATION_ERROR", status.message)


    def test_endpoint_status_corrupted(self):
        ext = Extension()
        ext.logger = MagicMock()
        ext._running_in_sim = True
        ext._client = DebugClient("", "", MagicMock())
        ext._is_fastcheck = False

        def callback():
            statuses = EndpointStatuses(10)
            statuses.add_endpoint_status(
                EndpointStatus("1.2.3.4:80",
                               EndpointSeverity.WARNING,
                               StatusValue.AUTHENTICATION_ERROR,
                               "Invalid authorization scheme"))
            statuses._faulty_endpoints["4.5.6.7:80"] = EndpointStatus("4.5.6.7:80",
                                                            EndpointSeverity.ERROR,
                                                            StatusValue.OK, "")
            
            assert statuses.get_summarized_severity() == EndpointSeverity.WARNING

            return statuses

        ext.schedule(callback, timedelta(seconds=1))
        ext._scheduler.run(blocking=False)
        time.sleep(0.01)

        status = ext._build_current_status()
        self.assertEqual(status.status, StatusValue.GENERIC_ERROR)
        self.assertIn("1 out of 10 endpoints work incorrectly. Returned 0 metrics. Malfunctioning endpoints: 1.2.3.4:80: AUTHENTICATION_ERROR", status.message)


    def test_endpoint_status_max(self):
        ext = Extension()
        ext.logger = MagicMock()
        ext._running_in_sim = True
        ext._client = DebugClient("", "", MagicMock())
        ext._is_fastcheck = False

        def callback():
            statuses = EndpointStatuses(2)
            statuses.add_endpoint_status(
                EndpointStatus("1.2.3.4:80",
                               EndpointSeverity.INFO,
                               StatusValue.AUTHENTICATION_ERROR,
                               "Invalid authorization scheme"))
            
            statuses.add_endpoint_status(
                EndpointStatus("4.5.6.7:80",
                               EndpointSeverity.WARNING,
                               StatusValue.DEVICE_CONNECTION_ERROR,
                               "Invalid authorization scheme"))

            with self.assertRaises(EndpointStatuses.TooManyEndpointStatuses):
                statuses.add_endpoint_status(
                    EndpointStatus("6.7.8.9:80",
                                   EndpointSeverity.ERROR,
                                   StatusValue.DEVICE_CONNECTION_ERROR,
                                   "Invalid authorization scheme"))
            
            assert statuses.get_summarized_severity() == EndpointSeverity.WARNING
            return statuses

        ext.schedule(callback, timedelta(seconds=1))
        ext._scheduler.run(blocking=False)
        time.sleep(0.01)

        status = ext._build_current_status()
        self.assertEqual(status.status, StatusValue.GENERIC_ERROR)
        self.assertIn("2 out of 2 endpoints work incorrectly. Returned 0 metrics. Malfunctioning endpoints: 1.2.3.4:80: AUTHENTICATION_ERROR, 4.5.6.7:80: DEVICE_CONNECTION_ERROR", status.message)


    def test_endpoint_severity_order(self):
        assert max([EndpointSeverity.WARNING, EndpointSeverity.INFO, EndpointSeverity.ERROR]) == EndpointSeverity.ERROR
        
        assert max(EndpointSeverity.INFO, EndpointSeverity.INFO) == EndpointSeverity.INFO
        assert max(EndpointSeverity.WARNING, EndpointSeverity.WARNING) == EndpointSeverity.WARNING
        assert max(EndpointSeverity.ERROR, EndpointSeverity.ERROR) == EndpointSeverity.ERROR

        assert max(EndpointSeverity.INFO, EndpointSeverity.WARNING) == EndpointSeverity.WARNING
        assert max(EndpointSeverity.INFO, EndpointSeverity.ERROR) == EndpointSeverity.ERROR

        assert max(EndpointSeverity.WARNING, EndpointSeverity.INFO) == EndpointSeverity.WARNING
        assert max(EndpointSeverity.WARNING, EndpointSeverity.ERROR) == EndpointSeverity.ERROR
        
        assert max(EndpointSeverity.ERROR, EndpointSeverity.INFO) == EndpointSeverity.ERROR
        assert max(EndpointSeverity.ERROR, EndpointSeverity.WARNING) == EndpointSeverity.ERROR
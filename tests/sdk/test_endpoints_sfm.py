import threading
import time
import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock

from freezegun import freeze_time

from dynatrace_extension import EndpointStatus, EndpointStatuses, Extension, Severity, StatusValue


class KillSchedulerError(Exception):
    pass


class TestSfmPerEndpont(unittest.TestCase):
    def setUp(self, extension_name=""):
        self.ext = Extension(name=extension_name)
        self.ext.logger = MagicMock()
        self.ext._running_in_sim = True
        self.ext._client = MagicMock()
        self.ext._is_fastcheck = False
        self.i = 0
        self.test_cases = None
        self.time_machine_idx = None

        self.ext.schedule(self.callback, timedelta(seconds=1))
        self.scheduler_thread = threading.Thread(target=self.scheduler_thread_fun)

    def scheduler_thread_fun(self):
        with self.assertRaises(KillSchedulerError):
            self.ext._scheduler.run()

    def tearDown(self) -> None:
        self.ext._scheduler.enter(delay=0, priority=1, action=lambda: (_ for _ in ()).throw(KillSchedulerError()))
        self.scheduler_thread.join()
        Extension._instance = None

    def run_test(self):
        self.scheduler_thread.start()
        time.sleep(0.1)

        for case in self.test_cases[: self.time_machine_idx]:
            self.single_test_iteration(case)

        if self.time_machine_idx:
            with freeze_time(datetime.now() + timedelta(hours=2), tick=True):
                for case in self.test_cases[self.time_machine_idx :]:
                    self.single_test_iteration(case)

    def single_test_iteration(self, case):
        self.ext._client.send_sfm_logs.reset_mock()
        self.ext._build_current_status()
        time.sleep(0.05)  # sleep required becuase mocked method is called in a different thread

        if case["expected"]:
            if not isinstance(case["expected"], list):
                case["expected"] = [case["expected"]]
            self.ext._client.send_sfm_logs.assert_called_once_with(case["expected"])
        else:
            self.ext._client.send_sfm_logs.assert_not_called()

        time.sleep(1)

    def callback(self):
        assert self.test_cases

        ep_status = EndpointStatuses()
        if self.i < len(self.test_cases):
            if self.test_cases[self.i]["status"]:
                ep_status.add_endpoint_status(self.test_cases[self.i]["status"])
            self.i += 1

        return ep_status

    def expected_sfm_dict(
        self,
        device_address,
        level,
        status,
        status_msg,
        status_state,
        dt_extension_config_id="",
        dt_extension_ds="python",
        dt_extension_version="",
        dt_extension_name="",
        dt_extension_config_label="",
    ):

        return {
            "device.address": device_address,
            "level": level,
            "message": f"{device_address}: [{status_state}] - {status} {status_msg}",
            "dt.extension.config.id": dt_extension_config_id,
            "dt.extension.ds": dt_extension_ds,
            "dt.extension.version": dt_extension_version,
            "dt.extension.name": dt_extension_name,
            "dt.extension.config.label": dt_extension_config_label,
        }

    def test_endpoint_sfm_ok(self):
        self.time_machine_idx = 5
        self.test_cases = [
            {"status": EndpointStatus("1.2.3.4:80", StatusValue.OK, "All good 1"), "expected": None},
            {"status": EndpointStatus("1.2.3.4:80", StatusValue.OK, "All good 1"), "expected": None},
            {"status": None, "expected": None},
            {
                "status": EndpointStatus("1.2.3.4:80", StatusValue.OK, "All good 2"),
                "expected": self.expected_sfm_dict(
                    device_address="1.2.3.4:80", level="INFO", status="OK", status_msg="All good 2", status_state="NEW"
                ),
            },
            {"status": EndpointStatus("1.2.3.4:80", StatusValue.OK, "All good 2"), "expected": None},
            # Time machine applied
            {"status": None, "expected": None},
            {
                "status": EndpointStatus("1.2.3.4:80", StatusValue.OK, "All good 3"),
                "expected": self.expected_sfm_dict(
                    device_address="1.2.3.4:80", level="INFO", status="OK", status_msg="All good 3", status_state="NEW"
                ),
            },
        ]

        self.run_test()

    def test_endpoint_sfm_nok(self):
        self.time_machine_idx = 2
        self.test_cases = [
            {
                "status": EndpointStatus("1.2.3.4:80", StatusValue.WARNING, "Warning 1"),
                "expected": self.expected_sfm_dict(
                    device_address="1.2.3.4:80",
                    level="WARN",
                    status="WARNING",
                    status_msg="Warning 1",
                    status_state="INITIAL",
                ),
            },
            {"status": EndpointStatus("1.2.3.4:80", StatusValue.WARNING, "Warning 1"), "expected": None},
            # Time machine applied
            {
                "status": None,
                "expected": self.expected_sfm_dict(
                    device_address="1.2.3.4:80",
                    level="WARN",
                    status="WARNING",
                    status_msg="Warning 1",
                    status_state="ONGOING",
                ),
            },
            {
                "status": EndpointStatus("1.2.3.4:80", StatusValue.GENERIC_ERROR, "Generic error 1"),
                "expected": self.expected_sfm_dict(
                    device_address="1.2.3.4:80",
                    level="ERROR",
                    status="GENERIC_ERROR",
                    status_msg="Generic error 1",
                    status_state="NEW",
                ),
            },
            {
                "status": EndpointStatus("1.2.3.4:80", StatusValue.WARNING, "Warning 1"),
                "expected": self.expected_sfm_dict(
                    device_address="1.2.3.4:80",
                    level="WARN",
                    status="WARNING",
                    status_msg="Warning 1",
                    status_state="NEW",
                ),
            },
            {
                "status": EndpointStatus("1.2.3.4:80", StatusValue.OK, "All good 1"),
                "expected": self.expected_sfm_dict(
                    device_address="1.2.3.4:80", level="INFO", status="OK", status_msg="All good 1", status_state="NEW"
                ),
            },
        ]

        self.run_test()

    def test_endpoint_sfm_severity(self):
        def expected_severtity(status: StatusValue):
            requirements = {
                StatusValue.EMPTY: Severity.INFO,
                StatusValue.OK: Severity.INFO,
                StatusValue.GENERIC_ERROR: Severity.ERROR,
                StatusValue.INVALID_ARGS_ERROR: Severity.ERROR,
                StatusValue.EEC_CONNECTION_ERROR: Severity.ERROR,
                StatusValue.INVALID_CONFIG_ERROR: Severity.ERROR,
                StatusValue.AUTHENTICATION_ERROR: Severity.ERROR,
                StatusValue.DEVICE_CONNECTION_ERROR: Severity.ERROR,
                StatusValue.WARNING: Severity.WARN,
                StatusValue.UNKNOWN_ERROR: Severity.ERROR,
            }

            for s in StatusValue:
                assert s in requirements.keys()

            return requirements[status].value

        self.test_cases = [
            {
                "status": EndpointStatus("1.2.3.4:123", status, f"Status {i}"),
                "expected": self.expected_sfm_dict(
                    device_address="1.2.3.4:123",
                    level=expected_severtity(status),
                    status=status.value,
                    status_msg=f"Status {i}",
                    status_state="INITIAL" if i == 0 else "NEW",
                ),
            }
            for i, status in enumerate(StatusValue)
        ]

        self.run_test()

    def test_endpoint_custom_blocked(self):
        self.ext = None
        Extension._instance = None
        self.setUp(extension_name="custom:custom_ext_unit_test")
        self.test_cases = [
            {"status": EndpointStatus("1.2.3.4:80", StatusValue.GENERIC_ERROR, "Generic error 1"), "expected": None}
        ]

        self.run_test()

    def test_endpoint_independent_ongoing(self):
        self.test_cases = [
            {
                "status": EndpointStatus("1.2.3.4:1", StatusValue.WARNING, "Warning 1"),
                "expected": self.expected_sfm_dict(
                    device_address="1.2.3.4:1",
                    level="WARN",
                    status="WARNING",
                    status_msg="Warning 1",
                    status_state="INITIAL",
                ),
            },
            {
                "status": EndpointStatus("1.2.3.4:2", StatusValue.WARNING, "Warning 2"),
                "expected": self.expected_sfm_dict(
                    device_address="1.2.3.4:2",
                    level="WARN",
                    status="WARNING",
                    status_msg="Warning 2",
                    status_state="INITIAL",
                ),
            },
            {
                "status": EndpointStatus("1.2.3.4:1", StatusValue.WARNING, "Warning 1"),
                "expected": self.expected_sfm_dict(
                    device_address="1.2.3.4:1",
                    level="WARN",
                    status="WARNING",
                    status_msg="Warning 1",
                    status_state="ONGOING",
                ),
            },
            {
                "status": EndpointStatus("1.2.3.4:2", StatusValue.WARNING, "Warning 2"),
                "expected": self.expected_sfm_dict(
                    device_address="1.2.3.4:2",
                    level="WARN",
                    status="WARNING",
                    status_msg="Warning 2",
                    status_state="ONGOING",
                ),
            },
            {
                "status": None,
                "expected": [
                    self.expected_sfm_dict(
                        device_address="1.2.3.4:1",
                        level="WARN",
                        status="WARNING",
                        status_msg="Warning 1",
                        status_state="ONGOING",
                    ),
                    self.expected_sfm_dict(
                        device_address="1.2.3.4:2",
                        level="WARN",
                        status="WARNING",
                        status_msg="Warning 2",
                        status_state="ONGOING",
                    ),
                ],
            },
        ]

        self.scheduler_thread.start()
        time.sleep(0.1)

        self.single_test_iteration(self.test_cases[0])

        with freeze_time(datetime.now() + timedelta(hours=1), tick=True):
            self.single_test_iteration(self.test_cases[1])

            with freeze_time(datetime.now() + timedelta(hours=1), tick=True):
                self.single_test_iteration(self.test_cases[2])

                with freeze_time(datetime.now() + timedelta(hours=1), tick=True):
                    self.single_test_iteration(self.test_cases[3])

                    with freeze_time(datetime.now() + timedelta(hours=2), tick=True):
                        self.single_test_iteration(self.test_cases[4])

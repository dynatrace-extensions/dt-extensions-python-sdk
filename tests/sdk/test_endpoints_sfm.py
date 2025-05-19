import time
import unittest
from datetime import timedelta, datetime
from unittest.mock import MagicMock
import threading
from freezegun import freeze_time

from dynatrace_extension import EndpointStatus, EndpointStatuses, Extension, StatusValue, Severity


class KillScheduler(Exception):
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
        self.scheduler_thread = threading.Thread(target=self.schedulerThreadFun)

    def schedulerThreadFun(self):
        with self.assertRaises(KillScheduler):
            self.ext._scheduler.run()

    def tearDown(self) -> None:
        self.ext._scheduler.enter(delay=0, priority=1, action=lambda: (_ for _ in ()).throw(KillScheduler()))
        self.scheduler_thread.join()
        Extension._instance = None

    def runTest(self):
        self.scheduler_thread.start()
        time.sleep(0.1)        

        for case in self.test_cases[:self.time_machine_idx]:
            self.single_test_iteration(case)

        if self.time_machine_idx:
            with freeze_time(datetime.now() + timedelta(hours=2), tick=True):
                for case in self.test_cases[self.time_machine_idx:]:
                    self.single_test_iteration(case)        

    def single_test_iteration(self, case):
        print(f"Test case: {case}")
        self.ext._client.send_sfm_logs.reset_mock()
        self.ext._build_current_status()
        time.sleep(0.05) # sleep required becuase mocked method is called in a different thread
        
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

    def test_endpoint_sfm_ok(self):
        self.time_machine_idx = 5
        self.test_cases = [
            {"status": EndpointStatus("1.2.3.4:80", StatusValue.OK, "All good 1"), "expected": None},   # Initial OK status
            {"status": EndpointStatus("1.2.3.4:80", StatusValue.OK, "All good 1"), "expected": None},   # Same OK status reported
            {"status": None,                                                       "expected": None},   # Nothing reported
            {"status": EndpointStatus("1.2.3.4:80", StatusValue.OK, "All good 2"), "expected": {'device.address': '1.2.3.4:80', 'level': 'INFO', 'message': '1.2.3.4:80: [NEW] - OK All good 2'}},   # New OK status
            {"status": EndpointStatus("1.2.3.4:80", StatusValue.OK, "All good 2"), "expected": None},   # Same OK status reported
            # Time machine applied
            {"status": None,                                                       "expected": None},   # Check if ONGOING skipped (+2h ahead)
            {"status": EndpointStatus("1.2.3.4:80", StatusValue.OK, "All good 3"), "expected": {'device.address': '1.2.3.4:80', 'level': 'INFO', 'message': '1.2.3.4:80: [NEW] - OK All good 3'}}   # New OK status
        ]
        
        self.runTest()

    def test_endpoint_sfm_nok(self):
        self.time_machine_idx = 2
        self.test_cases = [
            {"status": EndpointStatus("1.2.3.4:80", StatusValue.WARNING, "Warning 1"), "expected": {'device.address': '1.2.3.4:80', 'level': 'WARN', 'message': '1.2.3.4:80: [INITIAL] - WARNING Warning 1'}},
            {"status": EndpointStatus("1.2.3.4:80", StatusValue.WARNING, "Warning 1"), "expected": None},
            # Time machine applied
            {"status": None, "expected": {'device.address': '1.2.3.4:80', 'level': 'WARN', 'message': '1.2.3.4:80: [ONGOING] - WARNING Warning 1'}},
            {"status": EndpointStatus("1.2.3.4:80", StatusValue.GENERIC_ERROR, "Generic error 1"), "expected": {'device.address': '1.2.3.4:80', 'level': 'ERROR', 'message': '1.2.3.4:80: [NEW] - GENERIC_ERROR Generic error 1'}},
            {"status": EndpointStatus("1.2.3.4:80", StatusValue.WARNING, "Warning 1"), "expected": {'device.address': '1.2.3.4:80', 'level': 'WARN', 'message': '1.2.3.4:80: [NEW] - WARNING Warning 1'}},
            {"status": EndpointStatus("1.2.3.4:80", StatusValue.OK, "All good 1"), "expected": {'device.address': '1.2.3.4:80', 'level': 'INFO', 'message': '1.2.3.4:80: [NEW] - OK All good 1'}}
        ]
        
        self.runTest()

    def test_endpoint_sfm_severity(self):
        def expectedSevertity(status: StatusValue):
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
                StatusValue.UNKNOWN_ERROR: Severity.ERROR
            }

            for s in StatusValue:
                assert s in requirements.keys()

            return requirements[status].value

        self.test_cases = [
            {"status": EndpointStatus(f"1.2.3.4:123", status, f"Status {i}"), "expected": {'device.address': f'1.2.3.4:123', 'level': f'{expectedSevertity(status)}', 'message': f'1.2.3.4:123: [{"INITIAL" if i == 0 else "NEW"}] - {status.value} Status {i}'}} for i, status in enumerate(StatusValue)
        ]

        self.runTest()

    def test_endpoint_custom_blocked(self):
        self.ext = None
        Extension._instance = None
        self.setUp(extension_name="custom:custom_ext_unit_test")
        self.test_cases = [
            {"status": EndpointStatus("1.2.3.4:80", StatusValue.GENERIC_ERROR, "Generic error 1"), "expected": None}
        ]
        
        self.runTest()

    def test_endpoint_independent_ongoing(self):
        self.test_cases = [
            {"status": EndpointStatus("1.2.3.4:1", StatusValue.WARNING, "Warning 1"), "expected": {'device.address': '1.2.3.4:1', 'level': 'WARN', 'message': '1.2.3.4:1: [INITIAL] - WARNING Warning 1'}},
            {"status": EndpointStatus("1.2.3.4:2", StatusValue.WARNING, "Warning 2"), "expected": {'device.address': '1.2.3.4:2', 'level': 'WARN', 'message': '1.2.3.4:2: [INITIAL] - WARNING Warning 2'}},
            {"status": EndpointStatus("1.2.3.4:1", StatusValue.WARNING, "Warning 1"), "expected": {'device.address': '1.2.3.4:1', 'level': 'WARN', 'message': '1.2.3.4:1: [ONGOING] - WARNING Warning 1'}},
            {"status": EndpointStatus("1.2.3.4:2", StatusValue.WARNING, "Warning 2"), "expected": {'device.address': '1.2.3.4:2', 'level': 'WARN', 'message': '1.2.3.4:2: [ONGOING] - WARNING Warning 2'}},
            {"status": None, "expected": [{'device.address': '1.2.3.4:1', 'level': 'WARN', 'message': '1.2.3.4:1: [ONGOING] - WARNING Warning 1'}, {'device.address': '1.2.3.4:2', 'level': 'WARN', 'message': '1.2.3.4:2: [ONGOING] - WARNING Warning 2'}]}
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

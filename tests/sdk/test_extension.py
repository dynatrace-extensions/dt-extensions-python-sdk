import threading
import time
import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, mock_open, patch

import pytest

from dynatrace_extension import Status, StatusValue, get_helper_extension
from dynatrace_extension.sdk.activation import ActivationConfig
from dynatrace_extension.sdk.communication import HttpClient, MintResponse
from dynatrace_extension.sdk.extension import (
    CountMetricRegistrationEntry,
    DtEventType,
    Extension,
)
from dynatrace_extension.sdk.helper import _HelperExtension, dt_fastcheck, schedule_function, schedule_method


class TestExtension(unittest.TestCase):
    def tearDown(self) -> None:
        Extension._instance = None
        Extension.schedule_decorators = []

    @patch("dynatrace_extension.Extension._heartbeat")
    def test_heartbeat_called(self, mock_extension):
        extension = Extension()
        extension.logger = MagicMock()
        extension._running_in_sim = True
        extension._next_heartbeat = datetime.now()
        extension._heartbeat_iteration()
        extension._heartbeat.assert_called_once()

    def test_loglevel(self):
        pass
        # TODO - this should set the log level of the framework itself, not of the python extension
        # extension = Extension()
        # extension._client = MagicMock()
        # extension._client.send_status.return_value = {"runtime":{"debuglevel":"debug"}}
        # extension._heartbeat()
        # self.assertEqual(logging.DEBUG, extension.logger.level)

    def test_add_metric(self):
        extension = Extension()
        extension.logger = MagicMock()
        extension._running_in_sim = True
        extension.report_metric("my_metric", 1)
        self.assertEqual(len(extension._metrics), 1)
        self.assertTrue(extension._metrics[0].startswith("my_metric gauge,1"))

    def test_metrics_flushed(self):
        extension = Extension()
        extension._running_in_sim = True
        extension._client = MagicMock()
        extension.report_metric("my_metric", 1)

        self.assertEqual(len(extension._metrics), 1)
        extension._metrics_iteration()
        time.sleep(0.01)
        with extension._metrics_lock:
            self.assertEqual(len(extension._metrics), 0)

    def test_callback(self):
        extension = Extension()
        extension.logger = MagicMock()
        extension._running_in_sim = True
        extension._is_fastcheck = False
        extension._client = MagicMock()
        extension._run_callback = MagicMock()

        def callback():
            return 1

        self.assertEqual(len(extension._scheduled_callbacks), 1)
        extension.schedule(callback, timedelta(seconds=1))
        self.assertEqual(len(extension._scheduled_callbacks), 2)

        extension.schedule(callback, timedelta(seconds=1))
        self.assertEqual(len(extension._scheduled_callbacks), 3)
        extension._scheduler.run(blocking=False)
        time.sleep(0.01)
        self.assertEqual(extension._run_callback.call_count, 3)

    def test_callback_scheduled_multiple_times(self):
        extension = Extension()
        extension.logger = MagicMock()
        extension._running_in_sim = True
        extension._is_fastcheck = False
        extension._client = MagicMock()

        callback_call_count = 0

        def callback():
            nonlocal callback_call_count
            callback_call_count += 1

        extension.schedule(callback, timedelta(seconds=1))
        extension.schedule(callback, timedelta(seconds=1))
        extension._scheduler.run(blocking=False)
        time.sleep(1)

        self.assertEqual(extension._scheduled_callbacks[0].executions_total, 1)
        self.assertEqual(extension._scheduled_callbacks[1].executions_total, 1)
        self.assertEqual(callback_call_count, 2)

    def test_big_number_callbacks_scheduled(self):
        extension = Extension()
        extension.logger = MagicMock()
        extension._running_in_sim = True
        extension._is_fastcheck = False
        extension._client = MagicMock()

        for i in range(200):
            extension.schedule(
                callback=lambda x: extension.report_metric("scheduled_callback_executed", 1, {"index": f"{x}"}),
                interval=timedelta(seconds=10),
                args=(i,),
            )
        # run scheduler once and flush metrics
        extension._scheduler.run(blocking=False)
        time.sleep(0.1)
        extension._metrics_iteration()

        # assert metrics sent
        arguments = extension._client.send_metrics.call_args.args[0]
        self.assertEqual(len(arguments), 200)

    def test_callback_from_init(self):
        class MyExt(Extension):
            def callback(self):
                self.callback_call_count += 1

            def initialize(self):
                self.callback_call_count = 0
                self.schedule(self.callback, timedelta(seconds=1))

        extension = MyExt()
        extension.logger = MagicMock()
        extension._running_in_sim = True
        extension._is_fastcheck = False
        extension._client = MagicMock()

        extension._scheduler.run(blocking=False)
        time.sleep(1)

        self.assertEqual(len(extension._scheduled_callbacks), 2)
        self.assertEqual(extension._scheduled_callbacks[0].executions_total, 1)
        self.assertEqual(extension.callback_call_count, 1)

    def test_schedule_callback_from_callback(self):
        class MyExt(Extension):
            def __init__(self) -> None:
                super().__init__()

                self.callback_that_schedules_another_callback_call_count = 0
                self.another_callback_scheduled = False
                self.another_callback_call_count = 0

            def callback_that_schedules_another_callback(self):
                self.callback_that_schedules_another_callback_call_count += 1
                if not self.another_callback_scheduled:
                    self.another_callback_scheduled = True
                    self.schedule(self.another_callback, timedelta(seconds=1))

            def another_callback(self):
                self.another_callback_call_count += 1

        extension = MyExt()
        extension.logger = MagicMock()
        extension._running_in_sim = True
        extension._is_fastcheck = False
        extension._client = MagicMock()

        extension.schedule(extension.callback_that_schedules_another_callback, timedelta(seconds=1))
        self.assertEqual(len(extension._scheduled_callbacks), 2)

        extension._scheduler.run(blocking=False)
        time.sleep(1)

        self.assertEqual(len(extension._scheduled_callbacks), 3)
        self.assertEqual(extension._scheduled_callbacks[1].executions_total, 1)
        self.assertEqual(extension.callback_that_schedules_another_callback_call_count, 1)
        extension._scheduler.run(blocking=False)
        time.sleep(1)

        self.assertEqual(len(extension._scheduled_callbacks), 3)
        self.assertEqual(extension._scheduled_callbacks[1].executions_total, 2)
        self.assertEqual(extension.callback_that_schedules_another_callback_call_count, 2)
        self.assertGreaterEqual(extension._scheduled_callbacks[1].executions_total, 1)
        self.assertGreaterEqual(extension.callback_that_schedules_another_callback_call_count, 1)

        extension._scheduler.run(blocking=False)
        time.sleep(1)
        assert len(extension._scheduled_callbacks) == 3

    def test_callback_scheduled_exception(self):
        extension = Extension()
        extension.logger = MagicMock()
        extension._running_in_sim = True
        extension._is_fastcheck = False
        extension._client = MagicMock()
        callback_call_count = 0
        callback_wait = threading.Condition()
        callback_wait.acquire()

        def callback():
            nonlocal callback_call_count, callback_wait
            callback_call_count += 1
            if callback_call_count == 2:
                with callback_wait:
                    callback_wait.notify()

            msg = "test exception"
            raise RuntimeError(msg)

        def run_scheduler():
            nonlocal extension, callback, callback_wait, callback_call_count
            extension.schedule(callback, timedelta(seconds=1))
            extension._scheduler.run(blocking=False)
            time.sleep(1)
            extension._scheduler.run(blocking=False)
            time.sleep(1)
            if callback_call_count < 2:
                callback_wait.notify()

        with callback_wait:
            t = threading.Thread(target=run_scheduler)
            t.start()
            callback_wait.wait(timeout=5)
        self.assertEqual(callback_call_count, 2)

    def test_schedule_method_decorator(self):
        class MyExt(Extension):
            def __init__(self) -> None:
                super().__init__()
                self.called_callback = False

            @schedule_method(timedelta(seconds=1))
            def callback(self):
                self.called_callback = True

        extension = MyExt()

        extension._scheduler.run(blocking=False)
        time.sleep(0.01)

        self.assertEqual(len(extension._scheduled_callbacks), 2)
        self.assertTrue(extension.called_callback)

    def test_schedule_function_decorator(self):
        callback_done = False

        @schedule_function(timedelta(seconds=1))
        def callback():
            nonlocal callback_done
            callback_done = True

        extension = _HelperExtension()
        extension._scheduler.run(blocking=False)
        time.sleep(1)

        self.assertEqual(len(extension._scheduled_callbacks), 1)
        self.assertTrue(callback_done)

    def test_query_status(self):
        extension = Extension()
        extension.logger = MagicMock()
        extension._running_in_sim = True
        extension._is_fastcheck = False
        extension._client = MagicMock()
        callback_call_count = 0

        def callback():
            nonlocal callback_call_count
            callback_call_count += 1
            if callback_call_count == 1:
                msg = "test exception"
                raise RuntimeError(msg)

        extension.schedule(callback, timedelta(seconds=1))
        extension._scheduler.run(blocking=False)
        time.sleep(1)
        self.assertEqual(extension._build_current_status().status, StatusValue.GENERIC_ERROR)
        extension._scheduler.run(blocking=False)
        time.sleep(1)
        self.assertEqual(extension._build_current_status().status, StatusValue.OK)

    def test_register_fastcheck(self):
        extension = Extension()
        extension.logger = MagicMock()
        extension._client = MagicMock()
        extension.activation_config = ActivationConfig({"pythonRemote": "config"})
        extension.extension_config = "extension_config"

        fastcheck = MagicMock()
        fastcheck.return_value = Status(StatusValue.OK)
        extension.register_fastcheck(fastcheck)
        extension._run_fastcheck()

        fastcheck.assert_called_once_with(extension.activation_config, "extension_config")
        extension._client.send_status.assert_called_once_with(fastcheck.return_value)

    def test_register_fastcheck_decorator(self):
        extension = Extension()
        extension._client = MagicMock()
        extension.activation_config = ActivationConfig({"pythonRemote": "config"})
        extension.extension_config = "extension_config"

        @dt_fastcheck()
        def test(activation_config: ActivationConfig, extension_config: str) -> StatusValue:
            return StatusValue.UNKNOWN_ERROR

        extension._run_fastcheck()
        extension._client.send_status.assert_called_once_with(StatusValue.UNKNOWN_ERROR)

    def test_implemented_fastcheck(self):
        class MyExt(Extension):
            def __init__(self) -> None:
                super().__init__()
                self.fastcheck_mock = MagicMock()
                self.fastcheck_mock.return_value = Status(StatusValue.OK, "SomeMessage")

            def fastcheck(self) -> Status:
                return self.fastcheck_mock(self.activation_config, self.extension_config)

        extension = MyExt()
        extension.logger = MagicMock()
        extension._client = MagicMock()
        extension.activation_config = ActivationConfig({"pythonRemote": "config"})
        extension.extension_config = "extension_config"
        extension._run_fastcheck()

        extension.fastcheck_mock.assert_called_once_with(extension.activation_config, "extension_config")
        extension._client.send_status.assert_called_once_with(extension.fastcheck_mock.return_value)

    def test_fastcheck_exception(self):
        extension = Extension()
        extension.logger = MagicMock()
        extension._client = MagicMock()

        fastcheck = MagicMock()
        fastcheck.side_effect = Exception("SomeException")
        extension.register_fastcheck(fastcheck)
        self.assertRaises(Exception, extension._run_fastcheck)

        fastcheck.assert_called_once()
        extension._client.send_status.assert_called_once()
        self.assertEqual(extension._client.send_status.call_args[0][0].status, StatusValue.GENERIC_ERROR)
        self.assertIn(
            "Python datasource fastcheck error: Exception('SomeException')",
            extension._client.send_status.call_args[0][0].message,
        )

    def test_fastcheck_python_error(self):
        extension = Extension()
        extension.logger = MagicMock()
        extension._client = MagicMock()

        def custom_fastcheck(activation_config) -> Status:
            return Status(StatusValue.OK)

        extension.register_fastcheck(custom_fastcheck)
        self.assertRaises(TypeError, extension._run_fastcheck)

        extension._client.send_status.assert_called_once()
        self.assertEqual(extension._client.send_status.call_args[0][0].status, StatusValue.GENERIC_ERROR)
        self.assertTrue(
            extension._client.send_status.call_args[0][0].message.startswith(
                "Python datasource fastcheck error: TypeError"
            )
        )

    def test_fastcheck_more_than_one_assigned(self):
        extension = Extension()
        extension.logger = MagicMock()
        extension._client = MagicMock()

        @dt_fastcheck()
        def fastcheck1(activation_config: ActivationConfig, extension_config: str) -> StatusValue:
            return StatusValue.OK

        @dt_fastcheck()
        def fastcheck2(activation_config: ActivationConfig, extension_config: str) -> StatusValue:
            return StatusValue.UNKNOWN_ERROR

        extension._run_fastcheck()
        extension._client.send_status.assert_called_once_with(StatusValue.UNKNOWN_ERROR)

    def test_singleton(self):
        class UserExtension(Extension):
            def query(self):
                self.queried = True

        extension1 = UserExtension()
        extension2 = Extension()
        self.assertIsInstance(extension1, UserExtension)
        self.assertIsInstance(extension2, UserExtension)
        self.assertIs(extension1, extension2)
        extension2.query()
        self.assertTrue(extension1.queried)

    @patch("sys.argv", ["dummy_exe", "--dsid", "test_id"])
    @patch("builtins.open", mock_open(read_data="test_token"))
    @patch.object(HttpClient, "get_activation_config", return_value={})
    @patch.object(HttpClient, "get_extension_config", return_value="")
    @patch.object(HttpClient, "get_feature_sets", return_value={})
    def test_arguments(self, activation_mock, extension_mock, feature_sets_mock):
        ext = Extension()
        self.assertEqual(ext.task_id, "test_id")
        self.assertEqual(ext.activation_config, ActivationConfig({}))
        self.assertEqual(ext._feature_sets, {})

    @patch("sys.argv", ["dummy_exe", "--activationconfig", "activation.json"])
    def test_arguments_developer(self):
        ext = Extension()
        self.assertEqual(ext.task_id, "development_task_id")
        self.assertEqual(ext.monitoring_config_id, "development_config_id")

    def parse_sfm(self, line):
        tokens = line.split(",")
        name = tokens[0]
        last_token = tokens[-1]
        tokens = last_token.split("=")
        value = tokens[-1]
        return (name, value)

    def verify_sfm_value(self, sfm, expected_values):
        found = False
        for line in sfm:
            name, value = self.parse_sfm(line)
            if name == "dsfm:datasource.python.threads":
                self.assertIsNotNone(expected_values.get(name))
                found = True
            if name == "dsfm:datasource.python.execution.time":
                self.assertAlmostEqual(float(value), expected_values[name], delta=0.1)
                found = True
            if name == "dsfm:datasource.python.execution.total.count":
                self.assertEqual(int(value), expected_values[name])
                found = True
            if name == "dsfm:datasource.python.execution.count":
                self.assertEqual(int(value), expected_values[name])
                found = True
            if name == "dsfm:datasource.python.execution.ok.count":
                self.assertEqual(int(value), expected_values[name])
                found = True
            if name == "dsfm:datasource.python.execution.timeout.count":
                self.assertEqual(int(value), expected_values[name])
                found = True
            if name == "dsfm:datasource.python.execution.exception.count":
                self.assertEqual(int(value), expected_values[name])
                found = True
            self.assertTrue(found, f"No SFM metrics found: {line}")

    def test_sfm_ok(self):
        extension = get_helper_extension()
        extension.extension_logger = MagicMock()
        extension._running_in_sim = True
        extension._is_fastcheck = False
        extension._client = MagicMock()
        # extension._run_callback = MagicMock()

        def callback():
            time.sleep(0.01)
            return 1

        extension.schedule(callback, timedelta(seconds=1))
        extension._scheduler.run(blocking=False)
        time.sleep(0.1)
        sfm = extension._prepare_sfm_metrics()
        expected_values = {
            "dsfm:datasource.python.threads": 0,
            "dsfm:datasource.python.execution.time": 0.01,
            "dsfm:datasource.python.execution.total.count": 1,
            "dsfm:datasource.python.execution.count": 1,
            "dsfm:datasource.python.execution.ok.count": 1,
            "dsfm:datasource.python.execution.timeout.count": 0,
            "dsfm:datasource.python.execution.exception.count": 0,
        }
        self.verify_sfm_value(sfm, expected_values)

    def test_sfm_timeout(self):
        extension = get_helper_extension()
        extension.extension_logger = MagicMock()
        extension._running_in_sim = True
        extension._is_fastcheck = False
        extension._client = MagicMock()

        def callback():
            time.sleep(1.1)
            return 1

        extension.schedule(callback, timedelta(seconds=1))
        extension._scheduler.run(blocking=False)
        time.sleep(2)
        sfm = extension._prepare_sfm_metrics()
        expected_values = {
            "dsfm:datasource.python.threads": 0,
            "dsfm:datasource.python.execution.time": 1.1,
            "dsfm:datasource.python.execution.total.count": 1,
            "dsfm:datasource.python.execution.count": 1,
            "dsfm:datasource.python.execution.ok.count": 0,
            "dsfm:datasource.python.execution.timeout.count": 1,
            "dsfm:datasource.python.execution.exception.count": 0,
        }
        self.verify_sfm_value(sfm, expected_values)

    def test_sfm_exception(self):
        extension = get_helper_extension()
        extension.extension_logger = MagicMock()
        extension._running_in_sim = True
        extension._is_fastcheck = False
        extension._client = MagicMock()

        def callback():
            msg = "Ups ..."
            raise Exception(msg)

        extension.schedule(callback, timedelta(seconds=1))
        extension._scheduler.run(blocking=False)
        time.sleep(1)
        sfm = extension._prepare_sfm_metrics()
        expected_values = {
            "dsfm:datasource.python.threads": 0,
            "dsfm:datasource.python.execution.time": 0.1,
            "dsfm:datasource.python.execution.total.count": 1,
            "dsfm:datasource.python.execution.count": 1,
            "dsfm:datasource.python.execution.ok.count": 0,
            "dsfm:datasource.python.execution.timeout.count": 0,
            "dsfm:datasource.python.execution.exception.count": 1,
        }
        self.verify_sfm_value(sfm, expected_values)

    def test_count_metric_registration(self):
        extension = get_helper_extension()
        extension.extension_logger = MagicMock()
        extension._running_in_sim = True
        extension._is_fastcheck = False
        extension._client = MagicMock()

        metric_entry1 = CountMetricRegistrationEntry.make_list("metric_correct1", ["dim1", "dim2", "dim3"])
        metric_entry2 = CountMetricRegistrationEntry.make_all("metric_correct2")
        pattern1 = {
            "metric_correct1": {"aggregation_mode": "include_list", "dimensions_list": ["dim1", "dim2", "dim3"]}
        }
        pattern2 = {"metric_correct2": {"aggregation_mode": "include_all"}}
        extension._register_count_metrics(metric_entry1)
        extension._client.register_count_metrics.assert_called_with(pattern1)
        extension._register_count_metrics(metric_entry2)
        extension._client.register_count_metrics.assert_called_with(pattern2)

    def test_send_dt_event(self):
        extension = get_helper_extension()
        extension.logger = MagicMock()
        extension._running_in_sim = True
        extension._is_fastcheck = False
        extension._client = MagicMock()

        extension.report_dt_event(
            DtEventType.CUSTOM_INFO, "test_event", 123456789, 123456789, 5, 'type("value")', {"prop1": "val1"}
        )
        pattern = {
            "eventType": "CUSTOM_INFO",
            "title": "test_event",
            "startTime": 123456789,
            "endTime": 123456789,
            "timeout": 5,
            "entitySelector": 'type("value")',
            "properties": {"prop1": "val1"},
        }
        extension._client.send_dt_event.assert_called_with(pattern)

    def test_send_dt_event_dict(self):
        extension = get_helper_extension()
        extension.logger = MagicMock()
        extension._running_in_sim = True
        extension._is_fastcheck = False
        extension._client = MagicMock()

        valid_pattern = {
            "eventType": "CUSTOM_INFO",
            "title": "test_event",
            "startTime": 123456789,
            "endTime": 123456789,
            "timeout": 5,
            "entitySelector": 'type("value")',
            "properties": {"prop1": "val1"},
        }
        invalid_pattern = {
            "eventType": 134814814,
            "title": "test_event",
            "startTime": 123456789,
            "endTime": 123456789,
            "timeout": 5,
            "entitySelector": 'type("value")',
            "properties": {"prop1": 1},
        }
        extension.report_dt_event_dict(valid_pattern)

        try:
            extension.report_dt_event_dict(invalid_pattern)
        except Exception as e:
            expected = "Event type must be a DtEventType enum value, got: 134814814"
            self.assertEqual(str(e), expected)
        extension._client.send_dt_event.assert_called_once_with(valid_pattern)

    def test_send_count_delta_signal_force_true(self):
        extension = get_helper_extension()
        extension.extension_logger = MagicMock()
        extension._running_in_sim = True
        extension._is_fastcheck = False
        extension._client = MagicMock()

        metric_keys = ["metric1", "metric2", "metric3"]
        extension._send_count_delta_signal(metric_keys, force=True)
        extension._client.send_count_delta_signal.assert_called_once_with(metric_keys)

    def test_send_count_delta_signal_force_false(self):
        extension = get_helper_extension()
        extension.extension_logger = MagicMock()
        extension._running_in_sim = True
        extension._is_fastcheck = False
        extension._client = MagicMock()

        metric_keys = {"metric1", "metric2", "metric3"}
        extension._send_count_delta_signal(metric_keys, force=False)
        self.assertEqual(metric_keys, extension._delta_signal_buffer)

    def test_send_count_delta_signal_force_true_and_false(self):
        extension = get_helper_extension()
        extension.extension_logger = MagicMock()
        extension._running_in_sim = True
        extension._is_fastcheck = False
        extension._client = MagicMock()

        metric_keys = {"metric1", "metric2", "metric3"}
        extension._send_count_delta_signal(metric_keys, force=False)
        self.assertEqual(metric_keys, extension._delta_signal_buffer)

        extension._send_count_delta_signal(metric_keys, force=True)
        extension._client.send_count_delta_signal.assert_called_once_with(metric_keys)

    @patch("sys.argv", ["dummy_exe", "--local-ingest"])
    def test_local_ingest(self):
        ext = Extension()
        assert ext._client.local_ingest
        assert ext._client.local_ingest_port == 14499

    def test_feature_set_properties(self):
        ext = Extension()
        feature_sets = {
            "set1": ["metric1set1", "metric2set1"],
            "set2": ["metric1set2"],
            "set3": ["metric1set3", "metric2set3", "metric3set3"],
            "default": ["metric1default", "metric2default"],
        }

        activation_config_dict = {
            "enabled": True,
            "description": "feature set request test",
            "version": "0.0.12",
            "featureSets": ["set2", "set1"],
            "pythonRemote": {
                "endpoints": [{"url": "http:\\\\localhost:9090\\metrics", "user": "test", "password": "*********"}]
            },
        }

        activation_config = ActivationConfig(activation_config_dict)

        correct_enabled_feature_sets_names = ["set1", "set2", "default"]

        correct_enabled_feature_sets = {
            "set1": ["metric1set1", "metric2set1"],
            "set2": ["metric1set2"],
            "default": ["metric1default", "metric2default"],
        }

        correct_enabled_feature_sets_metrics = [
            "metric1set1",
            "metric2set1",
            "metric1set2",
            "metric1default",
            "metric2default",
        ]

        ext._feature_sets = feature_sets
        ext.activation_config = activation_config

        assert ext.enabled_feature_sets_names == correct_enabled_feature_sets_names
        assert ext.enabled_feature_sets == correct_enabled_feature_sets
        assert ext.enabled_feature_sets_metrics == correct_enabled_feature_sets_metrics

    def test_initialize_error_handling(self):
        class MyExtension(Extension):
            def initialize(self):
                raise AttributeError

        with pytest.raises(AttributeError):
            MyExtension()

    def test_report_mint_and_log_sending_failure(self):
        extension = get_helper_extension()
        extension.extension_logger = MagicMock()
        extension._running_in_sim = True
        extension._is_fastcheck = False
        extension._client = MagicMock()

        extension._client.send_metrics.return_value = [
            MintResponse(lines_invalid=1, lines_ok=0, error=None, warnings=None),
            MintResponse(lines_invalid=2, lines_ok=0, error=None, warnings=None),
        ]
        extension._client.send_sfm_metrics.return_value = MintResponse(
            lines_invalid=2, lines_ok=0, error=None, warnings=None
        )
        extension._client.send_events.return_value = {"error": {"message": "invalid log data"}}

        extension.report_metric("my:invalidmetric", 1)
        extension._prepare_sfm_metrics()
        extension.report_event("my:invalidevent", "RabbitMQ cluster is available")

        extension._send_metrics()
        extension._send_sfm_metrics()
        extension._heartbeat()

        extension._client.send_status.assert_called_once()
        self.assertEqual(extension._client.send_status.call_args[0][0].status, StatusValue.GENERIC_ERROR)
        self.assertTrue("3 invalid metric lines found" in extension._client.send_status.call_args[0][0].message)

    def test_feature_set_debug_mode(self):
        extension_yaml = """
        python:
          featureSets:
            - featureSet: basic
              metrics:
                - key: messages
                - key: inflight_messages
            - featureSet: advanced
              metrics:
                - key: messages_visible
                - key: messages_sent
        """
        activation = {
            "enabled": True,
            "description": "Description",
            "version": "0.0.1",
            "featureSets": ["basic", "advanced"],
        }

        extension = Extension()
        extension.logger = MagicMock()
        extension._running_in_sim = True
        extension.extension_config = extension_yaml
        extension.activation_config = ActivationConfig(activation)
        extension._client.extension_config = extension.extension_config
        extension._client.activation_config = activation
        extension._feature_sets = extension._client.get_feature_sets()

        assert extension.enabled_feature_sets_names == ["basic", "advanced"]
        assert extension.enabled_feature_sets_metrics == [
            "messages",
            "inflight_messages",
            "messages_visible",
            "messages_sent",
        ]

        activation_single_feature_set = {
            "enabled": True,
            "description": "Description",
            "version": "0.0.1",
            "featureSets": ["basic"],
        }
        extension.activation_config = ActivationConfig(activation_single_feature_set)
        extension._client.activation_config = extension.activation_config

        assert extension.enabled_feature_sets_names == ["basic"]
        assert extension.enabled_feature_sets_metrics == ["messages", "inflight_messages"]

        activation_no_feature_sets = {
            "enabled": True,
            "description": "Description",
            "version": "0.0.1",
            "featureSets": [],
        }
        extension.activation_config = ActivationConfig(activation_no_feature_sets)
        extension._client.activation_config = extension.activation_config

        assert not extension.enabled_feature_sets_names
        assert not extension.enabled_feature_sets_metrics

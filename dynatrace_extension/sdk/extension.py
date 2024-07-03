# SPDX-FileCopyrightText: 2023-present Dynatrace LLC
#
# SPDX-License-Identifier: MIT

import logging
import sched
import signal
import sys
import threading
import time
from argparse import ArgumentParser
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from enum import Enum
from itertools import chain
from pathlib import Path
from threading import Lock, RLock, active_count
from typing import Any, Callable, ClassVar, Dict, List, NamedTuple, Optional, Union

from .activation import ActivationConfig, ActivationType
from .callback import WrappedCallback
from .communication import CommunicationClient, DebugClient, HttpClient, Status, StatusValue
from .event import Severity
from .metric import Metric, MetricType, SfmMetric, SummaryStat
from .runtime import RuntimeProperties
from .snapshot import Snapshot

HEARTBEAT_INTERVAL = timedelta(seconds=60)
METRIC_SENDING_INTERVAL = timedelta(seconds=30)
SFM_METRIC_SENDING_INTERVAL = timedelta(seconds=60)
TIME_DIFF_INTERVAL = timedelta(seconds=60)

CALLBACKS_THREAD_POOL_SIZE = 100
INTERNAL_THREAD_POOL_SIZE = 20

RFC_3339_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
DATASOURCE_TYPE = "python"

logging.raiseExceptions = False
formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s (%(threadName)s): %(message)s")
error_handler = logging.StreamHandler()
error_handler.addFilter(lambda record: record.levelno >= logging.ERROR)
error_handler.setFormatter(formatter)
std_handler = logging.StreamHandler(sys.stdout)
std_handler.addFilter(lambda record: record.levelno < logging.ERROR)
std_handler.setFormatter(formatter)
extension_logger = logging.getLogger(__name__)
extension_logger.setLevel(logging.INFO)
extension_logger.addHandler(error_handler)
extension_logger.addHandler(std_handler)

api_logger = logging.getLogger("api")
api_logger.setLevel(logging.INFO)
api_logger.addHandler(error_handler)
api_logger.addHandler(std_handler)

DT_EVENT_SCHEMA = {
    "eventType": str,
    "title": str,
    "startTime": int,
    "endTime": int,
    "timeout": int,
    "entitySelector": str,
    "properties": dict,
}


class AggregationMode(Enum):
    ALL = "include_all"
    NONE = "include_none"
    LIST = "include_list"


class DtEventType(str, Enum):
    """Event type.

    Note:
        Official API v2 documentation:

        https://docs.dynatrace.com/docs/dynatrace-api/environment-api/events-v2/post-event
    """

    AVAILABILITY_EVENT = "AVAILABILITY_EVENT"
    CUSTOM_INFO = "CUSTOM_INFO"
    CUSTOM_ALERT = "CUSTOM_ALERT"
    CUSTOM_ANNOTATION = "CUSTOM_ANNOTATION"
    CUSTOM_CONFIGURATION = "CUSTOM_CONFIGURATION"
    CUSTOM_DEPLOYMENT = "CUSTOM_DEPLOYMENT"
    ERROR_EVENT = "ERROR_EVENT"
    MARKED_FOR_TERMINATION = "MARKED_FOR_TERMINATION"
    PERFORMANCE_EVENT = "PERFORMANCE_EVENT"
    RESOURCE_CONTENTION_EVENT = "RESOURCE_CONTENTION_EVENT"


class CountMetricRegistrationEntry(NamedTuple):
    metric_key: str
    aggregation_mode: AggregationMode
    dimensions_list: list[str]

    @staticmethod
    def make_list(metric_key: str, dimensions_list: List[str]):
        """Build an entry that uses defined list of dimensions for aggregation.

        Args:
            metric_key: Metric key in string.
            dimensions_list: List of dimensions.
        """
        return CountMetricRegistrationEntry(metric_key, AggregationMode.LIST, dimensions_list)

    @staticmethod
    def make_all(metric_key: str):
        """Build an entry that uses all mint dimensions for aggregation.

        Args:
            metric_key: Metric key in string.
        """
        return CountMetricRegistrationEntry(metric_key, AggregationMode.ALL, [])

    @staticmethod
    def make_none(metric_key: str):
        """Build an entry that uses none of mint dimensions for aggregation.

        Args:
            metric_key: Metric key in string.
        """
        return CountMetricRegistrationEntry(metric_key, AggregationMode.NONE, [])

    def registration_items_dict(self):
        result = {"aggregation_mode": self.aggregation_mode.value}
        if self.aggregation_mode == AggregationMode.LIST:
            result["dimensions_list"] = self.dimensions_list
            return result
        else:
            return result


def _add_sfm_metric(metric: Metric, sfm_metrics: Optional[List[Metric]] = None):
    if sfm_metrics is None:
        sfm_metrics = []
    metric.validate()
    sfm_metrics.append(metric)


class Extension:
    """Base class for Python extensions.

    Attributes:
        logger: Embedded logger object for the extension.
    """

    _instance: ClassVar = None
    schedule_decorators: ClassVar = []

    def __new__(cls):
        if Extension._instance is None:
            Extension._instance = super(__class__, cls).__new__(cls)
        return Extension._instance

    def __init__(self, name: str = "") -> None:
        # do not initialize already created singleton
        if hasattr(self, "logger"):
            return

        self.logger = extension_logger
        self.logger.name = name

        self.extension_config: str = ""
        self._feature_sets: dict[str, list[str]] = {}

        # Useful metadata, populated once the extension is started
        self.extension_name = name
        self.extension_version = ""
        self.monitoring_config_name = ""
        self._task_id = "development_task_id"
        self._monitoring_config_id = "development_config_id"

        # The user can override default EEC enrichment for logs
        self.log_event_enrichment = True

        # The Communication client
        self._client: CommunicationClient = None  # type: ignore

        # Set to true when --fastcheck is passed as a parameter
        self._is_fastcheck: bool = True

        # If this is true, we are running locally during development
        self._running_in_sim: bool = False

        # Response from EEC to /alive/ requests
        self._runtime_properties: RuntimeProperties = RuntimeProperties({})

        # The time difference between the local machine and the cluster time, used to sync callbacks with cluster
        self._cluster_time_diff: int = 0

        # Optional callback to be invoked during the fastcheck
        self._fast_check_callback: Optional[Callable[[ActivationConfig, str], Status]] = None

        # List of all scheduled callbacks we must run
        self._scheduled_callbacks: List[WrappedCallback] = []
        self._scheduled_callbacks_before_run: List[WrappedCallback] = []

        # Internal callbacks results, used to report statuses
        self._internal_callbacks_results: Dict[str, Status] = {}
        self._internal_callbacks_results_lock: Lock = Lock()

        # Running callbacks, used to get the callback info when reporting metrics
        self._running_callbacks: Dict[int, WrappedCallback] = {}
        self._running_callbacks_lock: Lock = Lock()

        self._scheduler = sched.scheduler(time.time, time.sleep)

        # Executors for the callbacks and internal methods
        self._callbacks_executor = ThreadPoolExecutor(max_workers=CALLBACKS_THREAD_POOL_SIZE)
        self._internal_executor = ThreadPoolExecutor(max_workers=INTERNAL_THREAD_POOL_SIZE)

        # Extension metrics
        self._metrics_lock = RLock()
        self._metrics: List[str] = []

        # Self monitoring metrics
        self._sfm_metrics_lock = Lock()
        self._callbackSfmReport: Dict[str, WrappedCallback] = {}

        # Count metric delta signals
        self._delta_signal_buffer: set[str] = set()
        self._registered_count_metrics: set[str] = set()

        # Self tech rule
        self._techrule = ""

        # Error message from caught exception in self.initialize()
        self._initialization_error: str = ""

        self._parse_args()

        for function, interval, args, activation_type in Extension.schedule_decorators:
            params = (self,)
            if args is not None:
                params = params + args
            self.schedule(function, interval, params, activation_type)

        starting_message = f"Starting {self}"
        api_logger.info("-" * len(starting_message))
        api_logger.info(starting_message)
        api_logger.info("-" * len(starting_message))

    def __repr__(self):
        return f"{self.__class__.__name__}(name={self.extension_name}, version={self.extension_version})"

    @property
    def is_helper(self) -> bool:
        """Internal property used by the EEC."""

        return False

    @property
    def task_id(self) -> str:
        """Internal property used by the EEC."""

        return self._task_id

    @property
    def monitoring_config_id(self) -> str:
        """Internal property used by the EEC.

        Represents a unique identifier of the monitoring configuration.
        that is assigned to this particular extension instance.
        """

        return self._monitoring_config_id

    def run(self):
        """Launch the extension instance.

        Calling this method starts the main loop of the extension.

        This method must be invoked once to start the extension,

        if `--fastcheck` is set, the extension will run in fastcheck mode,
        otherwise the main loop is started, which periodically runs:

        * The scheduled callbacks
        * The heartbeat method
        * The metrics publisher method
        """

        self._setup_signal_handlers()
        if self._is_fastcheck:
            return self._run_fastcheck()
        self._start_extension_loop()

    def _setup_signal_handlers(self):
        if sys.platform == "win32":
            signal.signal(signal.SIGBREAK, self._shutdown_signal_handler)
        signal.signal(signal.SIGINT, self._shutdown_signal_handler)

    def _shutdown_signal_handler(self, sig, frame):  # noqa: ARG002
        api_logger.info(f"{signal.Signals(sig).name} captured. Flushing metrics and exiting...")
        self.on_shutdown()
        self._send_metrics()
        self._send_sfm_metrics()
        sys.exit(0)

    def on_shutdown(self):
        """Callback method to be invoked when the extension is shutting down.

        Called when extension exits after it has received shutdown signal from EEC
        This is executed before metrics are flushed to EEC
        """
        pass

    def _schedule_callback(self, callback: WrappedCallback):
        if callback.activation_type is not None and callback.activation_type != self.activation_config.type:
            api_logger.info(
                f"Skipping {callback} with activation type {callback.activation_type} because it is not {self.activation_config.type}"
            )
            return

        api_logger.debug(f"Scheduling callback {callback}")

        # These properties are updated after the extension starts
        callback.cluster_time_diff = self._cluster_time_diff
        callback.running_in_sim = self._running_in_sim
        self._scheduled_callbacks.append(callback)
        self._scheduler.enter(callback.initial_wait_time(), 1, self._callback_iteration, (callback,))

    def schedule(
        self,
        callback: Callable,
        interval: Union[timedelta, int],
        args: Optional[tuple] = None,
        activation_type: Optional[ActivationType] = None,
    ) -> None:
        """Schedule a method to be executed periodically.

        The callback method will be periodically invoked in a separate thread.
        The callback method is always immediately scheduled for execution.

        Args:
            callback: The callback method to be invoked
            interval: The time interval between invocations, can be a timedelta object,
                or an int representing the number of seconds
            args: Arguments to the callback, if any
            activation_type: Optional activation type when this callback should run,
                can be 'ActivationType.LOCAL' or 'ActivationType.REMOTE'
        """

        if isinstance(interval, int):
            interval = timedelta(seconds=interval)

        if interval.total_seconds() < 1:
            msg = f"Interval must be at least 1 second, got {interval.total_seconds()} seconds"
            raise ValueError(msg)

        callback = WrappedCallback(interval, callback, api_logger, args, activation_type=activation_type)
        if self._is_fastcheck:
            self._scheduled_callbacks_before_run.append(callback)
        else:
            self._schedule_callback(callback)

    def query(self):
        """Callback to be executed every minute by default.

        Optional method that can be implemented by subclasses.
        The query method is always scheduled to run every minute.
        """
        pass

    def initialize(self):
        """Callback to be executed when the extension starts.

        Called once after the extension starts and the processes arguments are parsed.
        Sometimes there are tasks the user needs to do that must happen before runtime,
        but after the activation config has been received, example: Setting the schedule frequency
        based on the user input on the monitoring configuration, this can be done on this method
        """
        pass

    def fastcheck(self) -> Status:
        """Callback executed when extension is launched.

        Called if the extension is run in the `fastcheck` mode. Only invoked for remote
        extensions.
        This method is not called if fastcheck callback was already registered with
        Extension.register_fastcheck().

        Returns:
            Status with optional message whether the fastcheck succeed or failed.
        """
        return Status(StatusValue.OK)

    def register_fastcheck(self, fast_check_callback: Callable[[ActivationConfig, str], Status]):
        """Registers fastcheck callback that is executed in the `fastcheck` mode.

        Extension.fastcheck() is not called if fastcheck callback is registered with this method

        Args:
            fast_check_callback: callable called with ActivationConfig and
            extension_config arguments. Must return the Status with optional message
            whether the fastcheck succeed or failed.
        """
        if self._fast_check_callback:
            api_logger.error("More than one function assigned to fastcheck, last registered one was kept.")

        self._fast_check_callback = fast_check_callback

    def _register_count_metrics(self, *count_metric_entries: CountMetricRegistrationEntry) -> None:
        """Send a count metric registration request to EEC.

        Args:
            count_metric_entries: CountMetricRegistrationEntry objects for each count metric to register
        """
        json_pattern = {
            metric_entry.metric_key: metric_entry.registration_items_dict() for metric_entry in count_metric_entries
        }
        self._client.register_count_metrics(json_pattern)

    def _send_count_delta_signal(self, metric_keys: set[str], force: bool = True) -> None:
        """Send calculate-delta signal to EEC monotonic converter.

        Args:
            metric_keys: List with metrics for which we want to calculate deltas
            force: If true, it forces the metrics from cache to be pushed into EEC and then delta signal request is
                sent. Otherwise, it puts delta signal request in cache and request is sent after nearest (in time) sending
                metrics to EEC event
        """

        with self._metrics_lock:
            if not force:
                for key in metric_keys:
                    self._delta_signal_buffer.add(key)
                return

            self._send_metrics()
            self._client.send_count_delta_signal(metric_keys)
            self._delta_signal_buffer = {
                metric_key for metric_key in self._delta_signal_buffer if metric_key not in metric_keys
            }

    def report_metric(
        self,
        key: str,
        value: Union[float, str, int, SummaryStat],
        dimensions: Optional[Dict[str, str]] = None,
        techrule: Optional[str] = None,
        timestamp: Optional[datetime] = None,
        metric_type: MetricType = MetricType.GAUGE,
    ) -> None:
        """Report a metric.

        Metric is sent to EEC using an HTTP request and MINT protocol. EEC then
        sends the metrics to the tenant.

        By default, it reports a gauge metric.

        Args:
            key: The metric key, must follow the MINT specification
            value: The metric value, can be a simple value or a SummaryStat
            dimensions: A dictionary of dimensions
            techrule: The technology rule string set by self.techrule setter.
            timestamp: The timestamp of the metric, defaults to the current time
            metric_type: The type of the metric, defaults to MetricType.GAUGE
        """

        if techrule:
            if not dimensions:
                dimensions = {}
            if "dt.techrule.id" not in dimensions:
                dimensions["dt.techrule.id"] = techrule

        if metric_type == MetricType.COUNT and timestamp is None:
            # We must report a timestamp for count metrics
            timestamp = datetime.now()

        metric = Metric(key=key, value=value, dimensions=dimensions, metric_type=metric_type, timestamp=timestamp)
        self._add_metric(metric)

    def report_mint_lines(self, lines: List[str]) -> None:
        """Report mint lines using the MINT protocol

        Examples:
            Metric lines must comply with the MINT format.

            >>> self.report_mint_lines(["my_metric 1", "my_other_metric 2"])

        Args:
            lines: A list of mint lines
        """
        self._add_mint_lines(lines)

    def report_event(
        self,
        title: str,
        description: str,
        properties: Optional[dict] = None,
        timestamp: Optional[datetime] = None,
        severity: Union[Severity, str] = Severity.INFO,
    ) -> None:
        """Report an event using log ingest.

        Args:
            title: The title of the event
            description: The description of the event
            properties: A dictionary of extra event properties
            timestamp: The timestamp of the event, defaults to the current time
            severity: The severity of the event, defaults to Severity.INFO
        """
        if timestamp is None:
            timestamp = datetime.now(tz=timezone.utc)

        if properties is None:
            properties = {}

        event = {
            "content": f"{title}\n{description}",
            "title": title,
            "description": description,
            "timestamp": timestamp.strftime(RFC_3339_FORMAT),
            "severity": severity.value if isinstance(severity, Severity) else severity,
            **self._metadata,
            **properties,
        }
        self._send_events(event)

    def report_dt_event(
        self,
        event_type: DtEventType,
        title: str,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        timeout: Optional[int] = None,
        entity_selector: Optional[str] = None,
        properties: Optional[dict[str, str]] = None,
    ) -> None:
        """
        Reports an event using the v2 event ingest API.

        Unlike ``report_event``, this directly raises an event or even a problem
        based on the specified ``event_type``.

        Note:
            For reference see: https://www.dynatrace.com/support/help/dynatrace-api/environment-api/events-v2/post-event

        Args:
            event_type: The event type chosen from type Enum (required)
            title: The title of the event (required)
            start_time: The start time of event in UTC ms, if not set, current timestamp (optional)
            end_time: The end time of event in UTC ms, if not set, current timestamp + timeout (optional)
            timeout: The timeout of event in minutes, if not set, 15 (optional)
            entity_selector: The entity selector, if not set, the event is associated with environment entity (optional)
            properties: A map of event properties (optional)
        """
        event: Dict[str, Any] = {"eventType": event_type, "title": title}
        if start_time:
            event["startTime"] = start_time
        if end_time:
            event["endTime"] = end_time
        if timeout:
            event["timeout"] = timeout
        if entity_selector:
            event["entitySelector"] = entity_selector
        if properties:
            event["properties"] = properties

        self._send_dt_event(event)

    def report_dt_event_dict(self, event: dict):
        """Report an event using event ingest API with provided dictionary.

        Note:
            For reference see: https://www.dynatrace.com/support/help/dynatrace-api/environment-api/events-v2/post-event

        Format of the event dictionary::

            {
                "type": "object",
                "required": ["eventType", "title"],
                "properties": {
                    "eventType": {
                        "type": "string",
                        "enum": [
                            "CUSTOM_INFO",
                            "CUSTOM_ANNOTATION",
                            "CUSTOM_CONFIGURATION",
                            "CUSTOM_DEPLOYMENT",
                            "MARKED_FOR_TERMINATION",
                            "ERROR_EVENT",
                            "AVAILABILITY_EVENT",
                            "PERFORMANCE_EVENT",
                            "RESOURCE_CONTENTION_EVENT",
                            "CUSTOM_ALERT"
                        ]
                    },
                    "title": {
                        "type": "string",
                        "minLength": 1
                    },
                    "startTime": {"type": "integer"},
                    "endTime": {"type": "integer"},
                    "timeout": {"type": "integer"},
                    "entitySelector": {"type": "string"},
                    "properties": {
                        "type": "object",
                        "patternProperties": {
                            "^.*$": {"type": "string"}
                        }
                    }
                }
            }
        """

        if "eventType" not in event or "title" not in event:
            raise ValueError('"eventType" not present' if "eventType" not in event else '"title" not present in event')
        for key, value in event.items():
            if DT_EVENT_SCHEMA[key] is None:
                msg = f'invalid member: "{key}"'
                raise ValueError(msg)
            if key == "eventType" and value not in list(DtEventType):
                msg = f"Event type must be a DtEventType enum value, got: {value}"
                raise ValueError(msg)
            if key == "properties":
                for prop_key, prop_val in event[key].items():
                    if not isinstance(prop_key, str) or not isinstance(prop_val, str):
                        msg = f'invalid "properties" member: {prop_key}: {prop_val}, required: "str": str'
                        raise ValueError(msg)
        self._send_dt_event(event)

    def report_log_event(self, log_event: dict):
        """Report a custom log event using log ingest.

        Note:
            See reference: https://www.dynatrace.com/support/help/shortlink/log-monitoring-log-data-ingestion

        Args:
            log_event: The log event dictionary.
        """
        self._send_events(log_event)

    def report_log_events(self, log_events: List[dict]):
        """Report a list of custom log events using log ingest.

        Args:
            log_events: The list of log events
        """
        self._send_events(log_events)

    def report_log_lines(self, log_lines: List[Union[str, bytes]]):
        """Report a list of log lines using log ingest

        Args:
            log_lines: The list of log lines
        """
        events = [{"content": line} for line in log_lines]
        self._send_events(events)

    @property
    def enabled_feature_sets(self) -> dict[str, list[str]]:
        """Map of enabled feautre sets and corresponding metrics.

        Returns:
            Dictionary containing enabled feature sets with corresponding
            metrics defined in ``extension.yaml``.
        """
        return {
            feature_set_name: metric_keys
            for feature_set_name, metric_keys in self._feature_sets.items()
            if feature_set_name in self.activation_config.feature_sets or feature_set_name == "default"
        }

    @property
    def enabled_feature_sets_names(self) -> list[str]:
        """Names of enabled feature sets.

        Returns:
            List containing names of enabled feature sets.
        """
        return list(self.enabled_feature_sets.keys())

    @property
    def enabled_feature_sets_metrics(self) -> list[str]:
        """Enabled metrics.

        Returns:
            List of all metric keys from enabled feature sets
        """
        return list(chain(*self.enabled_feature_sets.values()))

    def _parse_args(self):
        parser = ArgumentParser(description="Python extension parameters")

        # Production parameters, these are passed by the EEC
        parser.add_argument("--dsid", required=False, default=None)
        parser.add_argument("--url", required=False)
        parser.add_argument("--idtoken", required=False)
        parser.add_argument(
            "--loglevel",
            help="Set extension log level. Info is default.",
            type=str,
            choices=["debug", "info"],
            default="info",
        )
        parser.add_argument("--fastcheck", action="store_true", default=False)
        parser.add_argument("--monitoring_config_id", required=False, default=None)
        parser.add_argument("--local-ingest", action="store_true", default=False)
        parser.add_argument("--local-ingest-port", required=False, default=14499)

        # Debug parameters, these are used when running the extension locally
        parser.add_argument("--extensionconfig", required=False, default=None)
        parser.add_argument("--activationconfig", required=False, default="activation.json")
        parser.add_argument("--no-print-metrics", required=False, action="store_true")

        args, unknown = parser.parse_known_args()
        self._is_fastcheck = args.fastcheck
        if args.dsid is None:
            # DEV mode
            self._running_in_sim = True
            print_metrics = not args.no_print_metrics
            self._client = DebugClient(
                activation_config_path=args.activationconfig,
                extension_config_path=args.extensionconfig,
                logger=api_logger,
                local_ingest=args.local_ingest,
                local_ingest_port=args.local_ingest_port,
                print_metrics=print_metrics,
            )
            RuntimeProperties.set_default_log_level(args.loglevel)
        else:
            # EEC mode
            self._client = HttpClient(args.url, args.dsid, args.idtoken, api_logger)
            self._task_id = args.dsid
            self._monitoring_config_id = args.monitoring_config_id
            api_logger.info(f"DSID = {self.task_id}, monitoring config id = {self._monitoring_config_id}")

        self.activation_config = ActivationConfig(self._client.get_activation_config())
        self.extension_config = self._client.get_extension_config()
        self._feature_sets = self._client.get_feature_sets()

        self.monitoring_config_name = self.activation_config.description
        self.extension_version = self.activation_config.version

        if not self._is_fastcheck:
            try:
                self.initialize()
                if not self.is_helper:
                    self.schedule(self.query, timedelta(minutes=1))
            except Exception as e:
                msg = f"Error running self.initialize {self}: {e!r}"
                api_logger.exception(msg)
                self._client.send_status(Status(StatusValue.GENERIC_ERROR, msg))
                self._initialization_error = msg
                raise e

    @property
    def _metadata(self) -> dict:
        return {
            "dt.extension.config.id": self._runtime_properties.extconfig,
            "dt.extension.ds": DATASOURCE_TYPE,
            "dt.extension.version": self.extension_version,
            "dt.extension.name": self.extension_name,
            "monitoring.configuration": self.monitoring_config_name,
        }

    def _run_fastcheck(self):
        api_logger.info(f"Running fastcheck for monitoring configuration '{self.monitoring_config_name}'")
        try:
            if self._fast_check_callback:
                status = self._fast_check_callback(self.activation_config, self.extension_config)
                api_logger.info(f"Sending fastcheck status: {status}")
                self._client.send_status(status)
                return

            status = self.fastcheck()
            api_logger.info(f"Sending fastcheck status: {status}")
            self._client.send_status(status)
        except Exception as e:
            status = Status(StatusValue.GENERIC_ERROR, f"Python datasource fastcheck error: {e!r}")
            api_logger.error(f"Error running fastcheck {self}: {e!r}")
            self._client.send_status(status)
            raise

    def _run_callback(self, callback: WrappedCallback):
        if not callback.running:
            # Add the callback to the list of running callbacks
            with self._running_callbacks_lock:
                current_thread_id = threading.get_ident()
                self._running_callbacks[current_thread_id] = callback

            callback()

            with self._sfm_metrics_lock:
                self._callbackSfmReport[callback.name()] = callback
            # Remove the callback from the list of running callbacks
            with self._running_callbacks_lock:
                self._running_callbacks.pop(current_thread_id, None)

    def _callback_iteration(self, callback: WrappedCallback):
        self._callbacks_executor.submit(self._run_callback, callback)
        callback.iterations += 1
        next_timestamp = callback.get_next_execution_timestamp()
        self._scheduler.enterabs(next_timestamp, 1, self._callback_iteration, (callback,))

    def _start_extension_loop(self):
        api_logger.debug(f"Starting main loop for monitoring configuration: '{self.monitoring_config_name}'")

        # These were scheduled before the extension started, schedule them now
        for callback in self._scheduled_callbacks_before_run:
            self._schedule_callback(callback)
        self._heartbeat_iteration()
        self._metrics_iteration()
        self._sfm_metrics_iteration()
        self._timediff_iteration()
        self._scheduler.run()

    def _timediff_iteration(self):
        self._internal_executor.submit(self._update_cluster_time_diff)
        self._scheduler.enter(TIME_DIFF_INTERVAL.total_seconds(), 1, self._timediff_iteration)

    def _heartbeat_iteration(self):
        self._internal_executor.submit(self._heartbeat)
        self._scheduler.enter(HEARTBEAT_INTERVAL.total_seconds(), 1, self._heartbeat_iteration)

    def _metrics_iteration(self):
        self._internal_executor.submit(self._send_metrics)
        self._scheduler.enter(METRIC_SENDING_INTERVAL.total_seconds(), 1, self._metrics_iteration)

    def _sfm_metrics_iteration(self):
        self._internal_executor.submit(self._send_sfm_metrics)
        self._scheduler.enter(SFM_METRIC_SENDING_INTERVAL.total_seconds(), 1, self._sfm_metrics_iteration)

    def _send_metrics(self):
        with self._metrics_lock:
            with self._internal_callbacks_results_lock:
                if self._metrics:
                    number_of_metrics = len(self._metrics)
                    responses = self._client.send_metrics(self._metrics)

                    self._internal_callbacks_results[self._send_metrics.__name__] = Status(StatusValue.OK)
                    lines_invalid = sum(response.lines_invalid for response in responses)
                    if lines_invalid > 0:
                        message = f"{lines_invalid} invalid metric lines found"
                        self._internal_callbacks_results[self._send_metrics.__name__] = Status(
                            StatusValue.GENERIC_ERROR, message
                        )

                    api_logger.info(f"Sent {number_of_metrics} metric lines to EEC: {responses}")
                    self._metrics = []

    def _prepare_sfm_metrics(self) -> List[str]:
        """Prepare self monitoring metrics.

        Builds the list of mint metric lines to send as self monitoring metrics.
        """

        sfm_metrics: List[Metric] = []
        sfm_dimensions = {"dt.extension.config.id": self.monitoring_config_id}
        _add_sfm_metric(
            SfmMetric("threads", active_count(), sfm_dimensions, client_facing=True, metric_type=MetricType.DELTA),
            sfm_metrics,
        )

        for name, callback in self._callbackSfmReport.items():
            sfm_dimensions = {"callback": name, "dt.extension.config.id": self.monitoring_config_id}
            _add_sfm_metric(
                SfmMetric(
                    "execution.time",
                    f"{callback.duration_interval_total:.4f}",
                    sfm_dimensions,
                    client_facing=True,
                    metric_type=MetricType.GAUGE,
                ),
                sfm_metrics,
            )
            _add_sfm_metric(
                SfmMetric(
                    "execution.total.count",
                    callback.executions_total,
                    sfm_dimensions,
                    client_facing=True,
                    metric_type=MetricType.DELTA,
                ),
                sfm_metrics,
            )
            _add_sfm_metric(
                SfmMetric(
                    "execution.count",
                    callback.executions_per_interval,
                    sfm_dimensions,
                    client_facing=True,
                    metric_type=MetricType.DELTA,
                ),
                sfm_metrics,
            )
            _add_sfm_metric(
                SfmMetric(
                    "execution.ok.count",
                    callback.ok_count,
                    sfm_dimensions,
                    client_facing=True,
                    metric_type=MetricType.DELTA,
                ),
                sfm_metrics,
            )
            _add_sfm_metric(
                SfmMetric(
                    "execution.timeout.count",
                    callback.timeouts_count,
                    sfm_dimensions,
                    client_facing=True,
                    metric_type=MetricType.DELTA,
                ),
                sfm_metrics,
            )
            _add_sfm_metric(
                SfmMetric(
                    "execution.exception.count",
                    callback.exception_count,
                    sfm_dimensions,
                    client_facing=True,
                    metric_type=MetricType.DELTA,
                ),
                sfm_metrics,
            )
            callback.clear_sfm_metrics()
        return [metric.to_mint_line() for metric in sfm_metrics]

    def _send_sfm_metrics(self):
        with self._sfm_metrics_lock:
            lines = self._prepare_sfm_metrics()
            # Flushes the cache of metrics, maybe we should only flush if they were successfully sent
            self._callbackSfmReport.clear()
        response = self._client.send_sfm_metrics(lines)

        with self._internal_callbacks_results_lock:
            self._internal_callbacks_results[self._send_sfm_metrics.__name__] = Status(StatusValue.OK)
            if response.lines_invalid > 0:
                message = f"{response.lines_invalid} invalid metric lines found"
                self._internal_callbacks_results[self._send_sfm_metrics.__name__] = Status(
                    StatusValue.GENERIC_ERROR, message
                )

    def _build_current_status(self):
        overall_status = Status(StatusValue.OK)

        if self._initialization_error:
            overall_status.status = StatusValue.GENERIC_ERROR
            overall_status.message = self._initialization_error
            return overall_status

        internal_callback_error = False
        messages = []
        with self._internal_callbacks_results_lock:
            for callback, result in self._internal_callbacks_results.items():
                if result.is_error():
                    internal_callback_error = True
                    overall_status.status = result.status
                    messages.append(f"{callback}: {result.message}")
            if internal_callback_error:
                overall_status.message = "\n".join(messages)
                return overall_status

        for callback in self._scheduled_callbacks:
            if callback.status.is_error():
                overall_status.status = callback.status.status
                messages.append(f"{callback}: {callback.status.message}")

        overall_status.message = "\n".join(messages)
        return overall_status

    def _update_cluster_time_diff(self):
        self._cluster_time_diff = self._client.get_cluster_time_diff()
        for callback in self._scheduled_callbacks:
            callback.cluster_time_diff = self._cluster_time_diff

    def _heartbeat(self):
        response = bytes("not set", "utf-8")
        try:
            overall_status = self._build_current_status()
            response = self._client.send_status(overall_status)
            self._runtime_properties = RuntimeProperties(response)
        except Exception as e:
            api_logger.error(f"Heartbeat failed because {e}, response {response}", exc_info=True)

    def __del__(self):
        self._callbacks_executor.shutdown()
        self._internal_executor.shutdown()

    def _add_metric(self, metric: Metric):
        metric.validate()

        with self._running_callbacks_lock:
            current_thread_id = threading.get_ident()
            current_callback = self._running_callbacks.get(current_thread_id)

        if current_callback is not None and metric.timestamp is None:
            # Adjust the metric timestamp according to the callback start time
            # If the user manually set a metric timestamp, don't adjust it
            metric.timestamp = current_callback.get_adjusted_metric_timestamp()
        elif current_callback is None and metric.timestamp is None:
            api_logger.debug(
                f"Metric {metric} was added by unknown thread {current_thread_id}, cannot adjust the timestamp"
            )

        with self._metrics_lock:
            self._metrics.append(metric.to_mint_line())

    def _add_mint_lines(self, lines: List[str]):
        with self._metrics_lock:
            self._metrics.extend(lines)

    def _send_events_internal(self, events: Union[dict, List[dict]]):
        try:
            responses = self._client.send_events(events, self.log_event_enrichment)

            for response in responses:
                with self._internal_callbacks_results_lock:
                    self._internal_callbacks_results[self._send_events.__name__] = Status(StatusValue.OK)
                    if not response or "error" not in response or "message" not in response["error"]:
                        return
                    self._internal_callbacks_results[self._send_events.__name__] = Status(
                        StatusValue.GENERIC_ERROR, response["error"]["message"]
                    )
        except Exception as e:
            api_logger.error(f"Error sending events: {e!r}", exc_info=True)
            with self._internal_callbacks_results_lock:
                self._internal_callbacks_results[self._send_events.__name__] = Status(StatusValue.GENERIC_ERROR, str(e))

    def _send_events(self, events: Union[dict, List[dict]]):
        self._internal_executor.submit(self._send_events_internal, events)

    def _send_dt_event(self, event: dict[str, str | int | dict[str, str]]):
        self._client.send_dt_event(event)

    def get_version(self) -> str:
        """Return the extension version."""
        return self.activation_config.version

    @property
    def techrule(self) -> str:
        """Internal property used by the EEC."""

        return self._techrule

    @techrule.setter
    def techrule(self, value):
        self._techrule = value

    def get_activation_config(self) -> ActivationConfig:
        """Retrieve the activation config.

        Represents activation configuration assigned to this particular
        extension instance.

        Returns:
            ActivationConfig object.
        """
        return self.activation_config

    def get_snapshot(self, snapshot_file: Path | str | None = None) -> Snapshot:
        """Retrieves an oneagent snapshot.

        Args:
            snapshot_file: Optional path to the snapshot file, only used when running from dt-sdk run

        Returns:
            Snapshot object.
        """
        if self._running_in_sim:
            if snapshot_file is None:
                snapshot_file = Path("snapshot.json")
            if isinstance(snapshot_file, str):
                snapshot_file = Path(snapshot_file)
            if not snapshot_file.exists():
                msg = f"snapshot file '{snapshot_file}' not found"
                raise FileNotFoundError(msg)

        return Snapshot.parse_from_file(snapshot_file)

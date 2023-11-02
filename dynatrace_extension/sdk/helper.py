# SPDX-FileCopyrightText: 2023-present Dynatrace LLC
#
# SPDX-License-Identifier: MIT

from datetime import datetime, timedelta
from typing import Callable, Dict, List, Optional, Union

from .activation import ActivationConfig, ActivationType
from .communication import Status
from .event import Severity
from .extension import DtEventType, Extension
from .metric import MetricType, SummaryStat


class _HelperExtension(Extension):
    @property
    def is_helper(self) -> bool:
        return True


def report_metric(
    key: str,
    value: Union[float, str, int, SummaryStat],
    dimensions: Optional[Dict[str, str]] = None,
    techrule: Optional[str] = None,
    timestamp: Optional[datetime] = None,
    metric_type: MetricType = MetricType.GAUGE,
) -> None:
    """Reports a metric using the MINT protocol
    By default, it reports a gauge metric


    :param key: The metric key, must follow the MINT specification
    :param value: The metric value, can be a simple value or a SummaryStat
    :param dimensions: A dictionary of dimensions
    :param techrule: The techrule of the metric, defaults to None
    :param timestamp: The timestamp of the metric, defaults to the current time
    :param metric_type: The type of the metric, defaults to MetricType.GAUGE
    """
    _HelperExtension().report_metric(key, value, dimensions, techrule, timestamp, metric_type)


def report_mint_lines(lines: List[str]) -> None:
    """Reports mint lines using the MINT protocol.
    These lines are not validated before being sent.

    :param lines: A list of mint lines, example: ["my_metric 1", "my_other_metric 2"]
    """
    _HelperExtension().report_mint_lines(lines)


def report_dt_event(
    event_type: DtEventType,
    title: str,
    start_time: Optional[int] = None,
    end_time: Optional[int] = None,
    timeout: Optional[int] = None,
    entity_selector: Optional[str] = None,
    properties: Optional[dict[str, str]] = None,
) -> None:
    """
    Reports a custom event v2 using event ingest

    For reference see: https://www.dynatrace.com/support/help/dynatrace-api/environment-api/events-v2/post-event

    :param event_type: The event type chosen from type Enum (required)
    :param title: The title of the event (required)
    :param start_time: The start time of event in UTC ms, if not set, current timestamp (optional)
    :param end_time: The end time of event in UTC ms, if not set, current timestamp + timeout (optional)
    :param timeout: The timeout of event in minutes, if not set, 15 (optional)
    :param entity_selector: The entity selector, if not set, the event is associated with environment entity (optional)
    :param properties: A map of event properties (optional)
    """
    _HelperExtension().report_dt_event(event_type, title, start_time, end_time, timeout, entity_selector, properties)


def report_dt_event_dict(event: dict):
    """
    Reports a custom event v2 using event ingest using provided dictionary resembling required json

    For reference see: https://www.dynatrace.com/support/help/dynatrace-api/environment-api/events-v2/post-event
    """
    _HelperExtension().report_dt_event_dict(event)


def schedule(
    callback: Callable,
    interval: Union[timedelta, int],
    args: Optional[tuple] = None,
    activation_type: Optional[ActivationType] = None,
) -> None:
    """Schedules a callback to be called periodically

    :param callback: The callback to be called
    :param interval: The time interval between invocations, can be a timedelta object, or an int representing the number of seconds
    :param args: Arguments to the callback, if any
    :param activation_type: Optional activation type when this callback should run, can be 'ActivationType.LOCAL' or 'ActivationType.REMOTE'

    """
    _HelperExtension().schedule(callback, interval, args, activation_type)


def schedule_function(
    interval: Union[timedelta, int], args: Optional[tuple] = None, activation_type: Optional[ActivationType] = None
):
    def decorator(function):
        schedule(function, interval, args=args, activation_type=activation_type)

    return decorator


def schedule_method(
    interval: Union[timedelta, int], args: Optional[tuple] = None, activation_type: Optional[ActivationType] = None
):
    def decorator(function):
        Extension.schedule_decorators.append((function, interval, args, activation_type))

    return decorator


def report_event(
    title: str,
    description: str,
    properties: Optional[dict] = None,
    timestamp: Optional[datetime] = None,
    severity: Union[Severity, str] = Severity.INFO,
) -> None:
    """Reports an event using the MINT protocol

    :param title: The title of the event
    :param description: The description of the event
    :param properties: A dictionary of properties
    :param timestamp: The timestamp of the event, defaults to the current time
    :param severity: The severity of the event, defaults to Severity.INFO
    """
    _HelperExtension().report_event(title, description, properties, timestamp, severity)


def report_log_event(log_event: dict):
    """Reports a custom log event using log ingest

    :param log_event: The log event dictionary, reference: https://www.dynatrace.com/support/help/shortlink/log-monitoring-log-data-ingestion
    """
    _HelperExtension().report_log_event(log_event)


def report_log_events(log_events: List[dict]):
    """Reports a list of custom log events using log ingest

    :param log_events: The list of log events
    """
    _HelperExtension().report_log_events(log_events)


def report_log_lines(log_lines: List[Union[str, bytes]]):
    """Reports a list of log lines using log ingest

    :param log_lines: The list of log lines
    """
    _HelperExtension().report_log_lines(log_lines)


def run_extension():
    """Starts the extension loop"""
    _HelperExtension().run()


def get_activation_config():
    return _HelperExtension().get_activation_config()


def get_helper_extension():
    return _HelperExtension()


def dt_fastcheck():
    def wrapper(fast_check_callback: Callable[[ActivationConfig, str], Status]):
        _HelperExtension().register_fastcheck(fast_check_callback=fast_check_callback)

    return wrapper


def log(message: str, severity: Severity):
    """
    Logs provided message into the extension's log file.
    Only two severities are supported: INFO and ERROR
    """
    if severity == Severity.INFO:
        _HelperExtension().logger.info(message)
    elif severity == Severity.ERROR:
        _HelperExtension().logger.error(message)

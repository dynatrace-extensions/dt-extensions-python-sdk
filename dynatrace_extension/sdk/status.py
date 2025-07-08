import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from threading import Lock

from .event import Severity


class DynatraceDeprecatedError(Exception):
    pass


class StatusValue(Enum):
    EMPTY = ""
    OK = "OK"
    GENERIC_ERROR = "GENERIC_ERROR"
    INVALID_ARGS_ERROR = "INVALID_ARGS_ERROR"
    EEC_CONNECTION_ERROR = "EEC_CONNECTION_ERROR"
    INVALID_CONFIG_ERROR = "INVALID_CONFIG_ERROR"
    AUTHENTICATION_ERROR = "AUTHENTICATION_ERROR"
    DEVICE_CONNECTION_ERROR = "DEVICE_CONNECTION_ERROR"
    WARNING = "WARNING"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"

    def is_error(self) -> bool:
        # WARNING is treated as an error
        return self not in (StatusValue.OK, StatusValue.EMPTY)

    def is_warning(self) -> bool:
        return self == StatusValue.WARNING


class IgnoreStatus:
    pass


class Status:
    def __init__(self, status: StatusValue = StatusValue.EMPTY, message: str = "", timestamp: int | None = None):
        self.status = status
        self.message = message
        self.timestamp = timestamp

    def to_json(self) -> dict:
        status = {"status": self.status.value, "message": self.message}
        if self.timestamp:
            status["timestamp"] = self.timestamp  # type: ignore
        return status

    def __repr__(self):
        return json.dumps(self.to_json())

    def is_error(self) -> bool:
        # WARNING is treated as an error
        return self.status.is_error()

    def is_warning(self) -> bool:
        return self.status.is_warning()


class MultiStatus:
    def __init__(self) -> None:
        self.statuses: list[Status] = []

    def add_status(self, status: StatusValue, message):
        self.statuses.append(Status(status, message))

    def build(self) -> Status:
        ret = Status(StatusValue.OK)
        if len(self.statuses) == 0:
            return ret

        messages = []
        all_ok = True
        all_err = True
        any_warning = False

        for stored_status in self.statuses:
            if stored_status.message != "":
                messages.append(stored_status.message)

            if stored_status.is_warning():
                any_warning = True

            if stored_status.is_error():
                all_ok = False
            else:
                all_err = False

        ret.message = ", ".join(messages)

        if any_warning:
            ret.status = StatusValue.WARNING
        elif all_ok:
            ret.status = StatusValue.OK
        elif all_err:
            ret.status = StatusValue.GENERIC_ERROR
        else:
            ret.status = StatusValue.WARNING

        return ret


class EndpointStatus:
    def __init__(self, endpoint_hint: str, short_status: StatusValue, message: str | None = None):
        self.endpoint = endpoint_hint
        self.status: StatusValue = short_status
        self.message = message

    def __repr__(self):
        return str(self.__dict__)

    def __eq__(self, other):
        return isinstance(other, EndpointStatus) and self.__dict__ == other.__dict__

    def __hash__(self):
        return hash(tuple(sorted(self.__dict__.items())))


class EndpointStatuses:
    def __init__(self, total_endpoints_number=None) -> None:
        if total_endpoints_number is not None:
            msg = (
                "EndpointStatuses.__init__: usage of `total_endpoints_number` parameter is abandoned. "
                "Use other class methods to explicitly report all status changes for any endpoint."
            )
            raise DynatraceDeprecatedError(msg)

        self._lock = Lock()
        self._endpoints_statuses: dict[str, EndpointStatus] = {}

    def add_endpoint_status(self, status: EndpointStatus):
        with self._lock:
            self._endpoints_statuses[status.endpoint] = status


class StatusState(Enum):
    INITIAL = "INITIAL"
    NEW = "NEW"
    ONGOING = "ONGOING"


@dataclass
class EndpointStatusRecord:
    ep_status: EndpointStatus
    last_sent: datetime | None
    state: StatusState

    def __repr__(self):
        return str(self.__dict__)


class EndpointStatusesMap:
    RESENDING_INTERVAL = timedelta(hours=2)

    def __init__(self, send_sfm_logs_function: Callable) -> None:
        self._lock = Lock()
        self._ep_records: dict[str, EndpointStatusRecord] = {}
        self._send_sfm_logs_function = send_sfm_logs_function
        self._logs_to_send: list[str] = []

    def contains_any_status(self) -> bool:
        return len(self._ep_records) > 0

    def update_ep_statuses(self, new_ep_statuses: EndpointStatuses):
        with self._lock:
            with new_ep_statuses._lock:
                for endpoint, ep_status in new_ep_statuses._endpoints_statuses.items():
                    if endpoint not in self._ep_records.keys():
                        self._ep_records[endpoint] = EndpointStatusRecord(
                            ep_status=ep_status, last_sent=None, state=StatusState.INITIAL
                        )
                    elif ep_status != self._ep_records[endpoint].ep_status:
                        self._ep_records[endpoint] = EndpointStatusRecord(
                            ep_status=ep_status, last_sent=None, state=StatusState.NEW
                        )

    def send_ep_logs(self):
        logs_to_send = []

        with self._lock:
            for ep_record in self._ep_records.values():
                if self._should_be_reported(ep_record):
                    logs_to_send.append(
                        self._prepare_ep_status_log(
                            ep_record.ep_status.endpoint,
                            ep_record.state,
                            ep_record.ep_status.status,
                            ep_record.ep_status.message,
                        )
                    )
                    ep_record.last_sent = datetime.now()
                    ep_record.state = StatusState.ONGOING

        if logs_to_send:
            self._send_sfm_logs_function(logs_to_send)

    def _should_be_reported(self, ep_record: EndpointStatusRecord):
        if ep_record.ep_status.status == StatusValue.OK:
            return ep_record.state == StatusState.NEW
        elif ep_record.state in (StatusState.INITIAL, StatusState.NEW):
            return True
        elif ep_record.state == StatusState.ONGOING and (
            ep_record.last_sent is None or datetime.now() - ep_record.last_sent >= self.RESENDING_INTERVAL
        ):
            return True
        else:
            return False

    def _prepare_ep_status_log(
        self, endpoint_name: str, prefix: StatusState, status_value: StatusValue, status_message: str
    ) -> dict:
        level = Severity.ERROR.value

        if status_value.is_error() is False:
            level = Severity.INFO.value
        elif status_value.is_warning():
            level = Severity.WARN.value

        ep_status_log = {
            "device.address": endpoint_name,
            "level": level,
            "message": f"{endpoint_name}: [{prefix.value}] - {status_value.value} {status_message}",
        }

        return ep_status_log

    def build_common_status(self) -> Status:
        with self._lock:
            # Summarize all statuses
            ok_count = 0
            warning_count = 0
            error_count = 0
            messages_to_report = []

            for ep_record in self._ep_records.values():
                ep_status = ep_record.ep_status

                if ep_status.status.is_warning():
                    warning_count += 1
                    messages_to_report.append(f"{ep_status.endpoint} - {ep_status.status.value} {ep_status.message}")
                elif ep_status.status.is_error():
                    error_count += 1
                    messages_to_report.append(f"{ep_status.endpoint} - {ep_status.status.value} {ep_status.message}")
                else:
                    ok_count += 1

            status_msg = f"Endpoints OK: {ok_count} WARNING: {warning_count} ERROR: {error_count}"

            # Early return if all OK
            if error_count == 0 and warning_count == 0:
                return Status(StatusValue.OK, status_msg)

            # Build final status if some errors present
            status_msg += f" Unhealthy endpoints: {', '.join(messages_to_report)}"

            if ok_count == 0 and warning_count == 0:
                status_value = StatusValue.GENERIC_ERROR
            else:
                status_value = StatusValue.WARNING

            return Status(status=status_value, message=status_msg)

# SPDX-FileCopyrightText: 2023-present Dynatrace LLC
#
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import logging
import sys
from abc import ABC, abstractmethod
from collections.abc import Generator, Sequence
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Generator, List, Sequence, TypeVar, Dict
from threading import RLock

from .vendor.mureq.mureq import HTTPException, Response, request

CONTENT_TYPE_JSON = "application/json;charset=utf-8"
CONTENT_TYPE_PLAIN = "text/plain;charset=utf-8"
COUNT_METRIC_ITEMS_DICT = TypeVar("COUNT_METRIC_ITEMS_DICT", str, list[str])

# TODO - I believe these can be adjusted via RuntimeConfig, they can't be constants
MAX_MINT_LINES_PER_REQUEST = 1000
MAX_LOG_EVENTS_PER_REQUEST = 50_000
MAX_LOG_REQUEST_SIZE = 5_000_000  # actually 5_242_880
MAX_METRIC_REQUEST_SIZE = 1_000_000  # actually 1_048_576

HTTP_BAD_REQUEST = 400


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
        return self.status not in (StatusValue.OK, StatusValue.EMPTY)
    
    def is_warning(self) -> bool:
        return self.status == StatusValue.WARNING


class MultiStatus:
    def __init__(self):
        self.statuses: List[StatusValue] = []

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

        ret.message = "\n".join(messages)

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
    def __init__(self, endpoint_hint: str, short_status: StatusValue, message: str):
        self.endpoint = endpoint_hint
        self.short_status: StatusValue = short_status
        self.message = message

    def __str__(self):
        return str(self.__dict__)


class EndpointStatuses:
    class TooManyEndpointStatuses(Exception):
        pass

    class MergeConflict(Exception):
        def __init__(self, first: EndpointStatus, second: EndpointStatus):
            super().__init__(f"Endpoint Statuses conflict while merging - first: {first}; second: {second}")

    def __init__(self, total_endpoints_number: int):
        self._lock = RLock()
        self._faulty_endpoints: Dict[str, EndpointStatus] = {}
        self._num_endpoints = total_endpoints_number

    def add_endpoint_status(self, status: EndpointStatus):
        with self._lock:
            if status.short_status == StatusValue.OK:
                self.clear_endpoint_error(status.endpoint)
            else:
                if len(self._faulty_endpoints) == self._num_endpoints:
                    raise EndpointStatuses.TooManyEndpointStatuses(f"Cannot add another endpoint status. The number of reported statuses already has reached preconfigured maximum of {self._num_endpoints} endpoints.")
                
                self._faulty_endpoints[status.endpoint] = status

    def clear_endpoint_error(self, endpoint_hint: str):
        with self._lock:
            try:
                del self._faulty_endpoints[endpoint_hint]
            except KeyError:
                pass
        
    def merge(self, other: EndpointStatuses):
        with self._lock:
            with other._lock:
                self._num_endpoints += other._num_endpoints

                for endpoint, status in other._faulty_endpoints.items():
                    if endpoint not in self._faulty_endpoints.keys():
                        self._faulty_endpoints[endpoint] = status
                    else:
                        self._num_endpoints -= 1
                        raise EndpointStatuses.MergeConflict(self._faulty_endpoints[endpoint], other._faulty_endpoints[endpoint])
                    
    def build_common_status(self) -> Status:
        with self._lock:
            if len(self._faulty_endpoints) == 0:
                status = Status(StatusValue.OK, f"Endpoints OK: {self._num_endpoints} NOK: 0")
            else:
                common_msg = ", ".join([f"{ep_status.endpoint} - {ep_status.short_status.value} {ep_status.message}" for ep_status in self._faulty_endpoints.values()])
                
                status = Status(
                    status = StatusValue.GENERIC_ERROR if len(self._faulty_endpoints) == self._num_endpoints and StatusValue.WARNING not in [ep_status.short_status for ep_status in self._faulty_endpoints.values()] else StatusValue.WARNING,
                    message = f"Endpoints OK: {self._num_endpoints - len(self._faulty_endpoints)} NOK: {len(self._faulty_endpoints)} NOK_reported_errors: {common_msg}"
                )

            return status


class CommunicationClient(ABC):
    """
    Abstract class for extension communication
    """

    @abstractmethod
    def get_activation_config(self) -> dict:
        pass

    @abstractmethod
    def get_extension_config(self) -> str:
        pass

    @abstractmethod
    def get_feature_sets(self) -> dict[str, list[str]]:
        pass

    @abstractmethod
    def register_count_metrics(self, pattern: dict[str, dict[str, COUNT_METRIC_ITEMS_DICT]]) -> None:
        pass

    @abstractmethod
    def send_count_delta_signal(self, metric_keys: set[str]) -> None:
        pass

    @abstractmethod
    def send_status(self, status: Status) -> dict:
        pass

    @abstractmethod
    def send_keep_alive(self) -> str:
        pass

    @abstractmethod
    def send_metrics(self, mint_lines: list[str]) -> list[MintResponse]:
        pass

    @abstractmethod
    def send_events(self, event: dict | list[dict], eec_enrichment: bool) -> list[dict | None]:
        pass

    @abstractmethod
    def send_sfm_metrics(self, metrics: list[str]) -> MintResponse:
        pass

    @abstractmethod
    def get_cluster_time_diff(self) -> int:
        pass

    @abstractmethod
    def send_dt_event(self, event: dict) -> None:
        pass


class HttpClient(CommunicationClient):
    """
    Concrete implementation of the client, this one handles the communication with the EEC
    """

    def __init__(self, base_url: str, datasource_id: str, id_token_file_path: str, logger: logging.Logger):
        self._activation_config_url = f"{base_url}/userconfig/{datasource_id}"
        self._extension_config_url = f"{base_url}/extconfig/{datasource_id}"
        self._metric_url = f"{base_url}/mint/{datasource_id}"
        self._sfm_url = f"{base_url}/sfm/{datasource_id}"
        self._keep_alive_url = f"{base_url}/alive/{datasource_id}"
        self._timediff_url = f"{base_url}/timediffms"
        self._events_url = f"{base_url}/logs/{datasource_id}"
        self._count_metric_register_url = f"{base_url}/countmetricregister/{datasource_id}"
        self._count_delta_signal_url = f"{base_url}/countmetricdeltasignal/{datasource_id}"
        self._feature_sets_query = "?feature_sets_json"
        self._event_ingest_url = f"{base_url}/events/{datasource_id}"

        with open(id_token_file_path) as f:
            id_token = f.read()
            self._headers = {"Authorization": f"Api-Token {id_token}"}

        self.logger = logger

    def _make_request(
        self,
        url: str,
        method: str = "GET",
        body: Any = None,
        extra_headers: dict | None = None,
        is_delta_signal: bool = False,
    ) -> Response:
        if extra_headers is None:
            extra_headers = {}
        headers = {**self._headers, **extra_headers}

        response = request(method, url, body=body, headers=headers)
        self.logger.debug(f"Response from {url}: {response}")
        if response.status_code >= HTTP_BAD_REQUEST:
            if not is_delta_signal:
                self.logger.warning(f"Error HTTP {response.status_code} from {url}: {response.content}")
        return response

    def get_activation_config(self) -> dict:
        try:
            response = self._make_request(self._activation_config_url, "GET")
        except HTTPException as err:
            self.logger.error(f"HTTP exception: {err}")
            return {}

        if response.status_code < HTTP_BAD_REQUEST:
            try:
                return response.json()
            except Exception as err:
                self.logger.error(f"JSON parse failure: {err}")
            return {}
        else:
            self.logger.error(f"Can't get activation configuration ({response.content}). Extension is stopped.")
            sys.exit(1)

    def get_extension_config(self) -> str:
        try:
            response = self._make_request(self._extension_config_url, "GET")
            return response.content.decode("utf-8")
        except HTTPException as err:
            self.logger.error(f"HTTP exception: {err}")
            return ""

    def get_feature_sets(self) -> dict[str, list[str]]:
        try:
            response = self._make_request(self._extension_config_url + self._feature_sets_query, "GET")
        except HTTPException as err:
            self.logger.error(f"HTTP exception: {err}")
            return {}

        if response.status_code < HTTP_BAD_REQUEST:
            try:
                return response.json()
            except Exception as err:
                self.logger.error(f"JSON parse failure: {err}")
                return {}

        return {}

    def register_count_metrics(self, json_pattern: dict[str, dict[str, COUNT_METRIC_ITEMS_DICT]]) -> None:
        register_data = json.dumps(json_pattern).encode("utf-8")
        try:
            response = self._make_request(
                self._count_metric_register_url,
                "POST",
                register_data,
                extra_headers={"Content-Type": CONTENT_TYPE_JSON},
            )
            if response.ok:
                self.logger.debug(
                    f"Monotonic cache converter successful registration for metric {list(json_pattern.keys())}."
                )
        except HTTPException:
            self.logger.error(
                f"Monotonic cache converter registration request error for metric {list(json_pattern.keys())}."
            )

    def send_count_delta_signal(self, metric_keys: set[str]) -> None:
        json_data = {"metric_keys": list(metric_keys), "filter_dimensions": {}}
        delta_signal_data = json.dumps(json_data).encode("utf-8")
        try:
            response = self._make_request(
                self._count_delta_signal_url,
                "POST",
                delta_signal_data,
                extra_headers={"Content-Type": CONTENT_TYPE_JSON},
                is_delta_signal=True,
            )
            if response.ok:
                self.logger.debug(
                    f"Monotonic converter cache delta calculation signal success for metric {metric_keys}."
                )
            else:
                self.logger.debug(
                    f"Not enough metrics of type {metric_keys} cached in monotonic cache converter to calculate delta."
                )
        except HTTPException:
            self.logger.error(
                f"Monotonic cache converter delta calculation signal request error for metric {metric_keys}."
            )

    def send_dt_event(self, event: dict[str, str | int | dict[str, str]]):
        json_data = json.dumps(event).encode("utf-8")
        try:
            response = self._make_request(
                self._event_ingest_url, "POST", json_data, extra_headers={"Content-Type": CONTENT_TYPE_JSON}
            )
            if response.ok:
                self.logger.debug(f"DT Event sent to EEC, content: {json_data.decode('utf-8')}")
            else:
                self.logger.debug(f"DT Event request failed: {response.content}")
        except HTTPException:
            self.logger.error(f"DT Event request HTTP exception, request body: {json_data.decode('utf-8')}")

    def send_status(self, status: Status) -> dict:
        encoded_data = json.dumps(status.to_json()).encode("utf-8")
        self.logger.debug(f"Sending status to EEC: {status}")
        response = self._make_request(
            self._keep_alive_url, "POST", encoded_data, extra_headers={"Content-Type": CONTENT_TYPE_JSON}
        ).content
        return json.loads(response.decode("utf-8"))

    def send_keep_alive(self):
        return self.send_status(Status())

    def send_metrics(self, mint_lines: list[str]) -> list[MintResponse]:
        responses = []

        # We divide into batches of MAX_METRIC_REQUEST_SIZE bytes to avoid hitting the body size limit
        batches = divide_into_batches(mint_lines, MAX_METRIC_REQUEST_SIZE, "\n")
        for batch in batches:
            response = self._make_request(
                self._metric_url, "POST", batch, extra_headers={"Content-Type": CONTENT_TYPE_PLAIN}
            ).json()
            self.logger.debug(f"{self._metric_url}: {response}")
            mint_response = MintResponse.from_json(response)
            responses.append(mint_response)
        return responses

    def send_events(self, events: dict | list[dict], eec_enrichment: bool = True) -> list[dict | None]:
        self.logger.debug(f"Sending log events: {events}")

        responses = []
        if isinstance(events, dict):
            events = [events]
        batches = divide_into_batches(events, MAX_LOG_REQUEST_SIZE)

        for batch in batches:
            try:
                eec_response = self._make_request(
                    self._events_url,
                    "POST",
                    batch,
                    extra_headers={"Content-Type": CONTENT_TYPE_JSON, "eec-enrichment": str(eec_enrichment).lower()},
                ).json()
                responses.append(eec_response)
            except json.JSONDecodeError:
                responses.append(None)

        return responses

    def send_sfm_metrics(self, mint_lines: list[str]) -> MintResponse:
        mint_data = "\n".join(mint_lines).encode("utf-8")
        return MintResponse.from_json(
            self._make_request(
                self._sfm_url, "POST", mint_data, extra_headers={"Content-Type": CONTENT_TYPE_PLAIN}
            ).json()
        )

    def get_cluster_time_diff(self) -> int:
        response = self._make_request(self._timediff_url, "GET")
        time_diff = response.json()["clusterDiffMs"]
        return time_diff


class DebugClient(CommunicationClient):
    """
    This client is used for debugging purposes
    It does not send metrics to Dynatrace, but prints them to the console
    """

    def __init__(
        self,
        activation_config_path: str,
        extension_config_path: str,
        logger: logging.Logger,
        secrets_path: str = "secrets.json",
        local_ingest: bool = False,
        local_ingest_port: int = 14499,
        print_metrics: bool = True,
    ):
        self.secrets = {}
        if secrets_path and Path(secrets_path).exists():
            with open(secrets_path) as f:
                self.secrets = json.load(f)

        self.activation_config = {}
        if activation_config_path and Path(activation_config_path).exists():
            with open(activation_config_path) as f:
                raw_activation_config = f.read()
                self.activation_config = json.loads(
                    self.replace_secrets_in_activation_config(self.secrets, raw_activation_config)
                )

        self.extension_config = ""
        if not extension_config_path:
            extension_config_path = "extension/extension.yaml"
        if Path(extension_config_path).exists():
            with open(extension_config_path) as f:
                self.extension_config = f.read()
        self.logger = logger
        self.local_ingest = local_ingest
        self.local_ingest_port = local_ingest_port
        self.print_metrics = print_metrics

    def get_activation_config(self) -> dict:
        return self.activation_config

    def get_extension_config(self) -> str:
        return self.extension_config

    def get_feature_sets(self) -> dict[str, list[str]]:
        # This is only called from dt-sdk run, where PyYaml is installed because of dt-cli
        # Do NOT move this to the top of the file
        import yaml  # type: ignore

        # Grab the feature sets from the extension.yaml file
        extension_yaml = yaml.safe_load(self.extension_config)
        if not extension_yaml:
            return {}

        yaml_feature_sets = extension_yaml.get("python", {}).get("featureSets", [])
        if not yaml_feature_sets:
            return {}

        # Construct the object that the SDK expects
        feature_sets = {}
        for feature_set in yaml_feature_sets:
            feature_set_name = feature_set["featureSet"]
            if feature_set_name in self.activation_config.get("featureSets", []):
                feature_sets[feature_set_name] = [metric["key"] for metric in feature_set["metrics"]]

        return feature_sets

    def register_count_metrics(self, pattern: dict[str, dict[str, COUNT_METRIC_ITEMS_DICT]]) -> None:
        self.logger.info(f"Registering metrics in converter: {pattern}")

    def send_count_delta_signal(self, metric_keys: set[str]) -> None:
        self.logger.info(f"Sending delta signal for: {metric_keys}")

    def send_dt_event(self, event: dict) -> None:
        self.logger.info(f"Sending DT Event: {event}")

    def send_status(self, status: Status) -> dict:
        self.logger.info(f"send_status: '{status}'")
        return {}

    def send_keep_alive(self):
        return self.send_status(Status())

    def send_metrics(self, mint_lines: list[str]) -> list[MintResponse]:
        total_lines = len(mint_lines)
        self.logger.info(f"Start sending {total_lines} metrics to the EEC")

        responses = []

        batches = divide_into_batches(mint_lines, MAX_METRIC_REQUEST_SIZE)
        for batch in batches:
            lines = json.loads(batch)
            if self.local_ingest:
                response = request(
                    "POST",
                    f"http://localhost:{self.local_ingest_port}/metrics/ingest",
                    body="\n".join(lines).encode(),
                    headers={"Content-Type": CONTENT_TYPE_PLAIN},
                ).json()
                mint_response = MintResponse.from_json(response)
                responses.append(mint_response)
            elif self.print_metrics:
                for line in lines:
                    self.logger.info(f"send_metric: {line}")

        return responses

    def send_events(self, events: dict | list[dict], eec_enrichment: bool = True) -> list[dict | None]:
        self.logger.info(f"send_events (enrichment = {eec_enrichment}): {len(events)} events")
        if isinstance(events, dict):
            events = [events]
        if self.print_metrics:
            for event in events:
                self.logger.info(f"send_event: {event}")
        return []

    def send_sfm_metrics(self, mint_lines: list[str]) -> MintResponse:
        for line in mint_lines:
            self.logger.info(f"send_sfm_metric: {line}")
        return MintResponse(lines_invalid=0, lines_ok=len(mint_lines), error=None, warnings=None)

    def get_cluster_time_diff(self) -> int:
        return 0

    def replace_secrets_in_activation_config(self, secrets: dict, activation_config_string: str) -> str:
        for secret_name, secret_value in secrets.items():
            activation_config_string = activation_config_string.replace(f"{{{{{secret_name}}}}}", str(secret_value))

        return activation_config_string


def divide_into_batches(
    items: Sequence[dict | str], max_size_bytes: int, join_with: str | None = None
) -> Generator[bytes, None, None]:
    """
    Yield successive batches from a list, according to sizing limitations

    :param items: The list items to divide, they myst be encodable to bytes
    :param max_size_bytes: The maximum size of the payload in bytes
    :param join_with: A string to join the items with before encoding
    :return: A generator of batches of log events already encoded
    """

    if not items:
        return

    if join_with is not None:
        joined = join_with.join(items)  # type: ignore
        encoded = f"{joined}".encode(errors="replace")
    else:
        encoded = json.dumps(items).encode(errors="replace")
    size = len(encoded)
    if size <= max_size_bytes:
        yield encoded
        return

    # if we get here, the payload is too large, split it in half until we have chunks that are small enough
    half = len(items) // 2
    first_half = items[:half]
    second_half = items[half:]
    yield from divide_into_batches(first_half, max_size_bytes, join_with)
    yield from divide_into_batches(second_half, max_size_bytes, join_with)


@dataclass
class MintResponse:
    lines_ok: int
    lines_invalid: int
    error: dict | None
    warnings: dict | None

    @staticmethod
    def from_json(json_data: dict) -> MintResponse:
        return MintResponse(
            lines_ok=json_data.get("linesOk", 0),
            lines_invalid=json_data.get("linesInvalid", 0),
            error=json_data.get("error"),
            warnings=json_data.get("warnings"),
        )

    def __str__(self) -> str:
        return f"MintResponse(lines_ok={self.lines_ok}, lines_invalid={self.lines_invalid}, error={self.error}, warnings={self.warnings})"

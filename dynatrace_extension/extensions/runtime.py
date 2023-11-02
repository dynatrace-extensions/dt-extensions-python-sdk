# SPDX-FileCopyrightText: 2023-present Dynatrace LLC
#
# SPDX-License-Identifier: MIT

import logging
from typing import ClassVar, List, NamedTuple


class DefaultLogLevel(NamedTuple):
    string_value: str
    int_value: int


class RuntimeProperties:
    _default_log_level = DefaultLogLevel("info", logging.INFO)
    _log_level_converter: ClassVar = {"debug": logging.DEBUG, "info": logging.INFO}

    def __init__(self, json_response: dict):
        """
        This is the response from EEC when a status (heartbeat) is sent
        Example:
        {'extconfig': 'b2520a74-88e8-3e03-bc01-e1116fec4a98', 'userconfig': '1645918226657', 'debugmode': '0', 'runtime': {}, 'tasks': []}
        """
        self.extconfig: str = json_response.get("extconfig", "")
        self.userconfig: str = json_response.get("userconfig", "")
        self.debugmode: bool = json_response.get("debugmode", "0") == "1"
        self.runtime: dict = json_response.get("runtime", {})
        self.tasks: List[str] = json_response.get("tasks", [])

    @classmethod
    def set_default_log_level(cls, value: str):
        RuntimeProperties._default_log_level = DefaultLogLevel(value, RuntimeProperties._to_log_level(value))

    @classmethod
    def _to_log_level(cls, value: str) -> int:
        """
        The method convert LogLevel string value into Python log level (loggin package).
        loggin.INFO is a default.
        :param value: string log lever
        :return: Python log level
        """
        return RuntimeProperties._log_level_converter.get(value, RuntimeProperties._default_log_level.int_value)

    def log_level(self, extension_name: str) -> int:
        """
        The method check python.debuglevel (lower priority)
        and python.debuglevel.extension_name (higher priority) string debug flags.
        loggin.INFO is a default.
        :param extension_name: extension name
        :return: log level for Python log system (loggin)
        """
        value = self.runtime.get("debuglevel", RuntimeProperties._default_log_level.string_value)
        value = self.runtime.get(f"debuglevel.{extension_name}", value)
        return RuntimeProperties._to_log_level(value)

    def get_api_log_level(self, extension_name: str) -> int:
        """
        The method check python.debuglevel.api (lower priority)
        python.debuglevel.extension_name.api (higher priority) string debug flags.
        loggin.INFO is a default.
        :param extension_name: extension name
        :return: log level for Python log system (loggin)
        """
        value = self.runtime.get("debuglevel.api", RuntimeProperties._default_log_level.string_value)
        value = self.runtime.get(f"debuglevel.{extension_name}.api", value)
        return RuntimeProperties._to_log_level(value)
        pass

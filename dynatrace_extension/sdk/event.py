# SPDX-FileCopyrightText: 2023-present Dynatrace LLC
#
# SPDX-License-Identifier: MIT

from enum import Enum


class Severity(Enum):
    """Severity of an event ingested through log ingest."""

    EMERGENCY = "EMERGENCY"
    ERROR = "ERROR"
    ALERT = "ALERT"
    CRITICAL = "CRITICAL"
    SEVERE = "SEVERE"
    WARN = "WARN"
    NOTICE = "NOTICE"
    INFO = "INFO"
    DEBUG = "DEBUG"

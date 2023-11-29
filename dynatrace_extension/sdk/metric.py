# SPDX-FileCopyrightText: 2023-present Dynatrace LLC
#
# SPDX-License-Identifier: MIT

from datetime import datetime
from enum import Enum
from typing import Dict, Optional, Union

# https://bitbucket.lab.dynatrace.org/projects/ONE/repos/schemaless-metrics-spec/browse/limits.md
LIMIT_DIMENSIONS_COUNT = 50
LIMIT_LINE_LENGTH = 2000

CLIENT_FACING_SFM_NAMESPACE = "dsfm"
INTERNAL_SFM_NAMESPACE = "isfm"


class SummaryStat:
    def __init__(
        self,
        value_min: float,
        value_max: float,
        value_sum: float,
        value_count: float,
    ):
        self.value_min = value_min
        self.value_max = value_max
        self.value_sum = value_sum
        self.value_count = value_count

    def __str__(self):
        return f"min={self.value_min},max={self.value_max},sum={self.value_sum},count={self.value_count}"


class MetricType(Enum):
    GAUGE = "gauge"
    COUNT = "count"
    DELTA = "count,delta"


class Metric:
    def __init__(
        self,
        key: str,
        value: Union[float, int, str, SummaryStat],
        dimensions: Optional[Dict[str, str]] = None,
        metric_type: MetricType = MetricType.GAUGE,
        timestamp: Optional[datetime] = None,
    ):
        self.key: str = key
        self.value: Union[float, int, str, SummaryStat] = value
        if dimensions is None:
            dimensions = {}
        self.dimensions: Dict[str, str] = dimensions
        self.metric_type: MetricType = metric_type
        self.timestamp: Optional[datetime] = timestamp

    def __hash__(self):
        return hash(self._key_and_dimensions())

    def __eq__(self, other):
        return self._key_and_dimensions() == other._key_and_dimensions()

    def to_mint_line(self) -> str:
        # Add key and dimensions
        line = f"{self._key_and_dimensions()}"

        # Add value
        if self.metric_type == MetricType.DELTA:
            line = f"{line} {self.metric_type.value}={self.value}"
        else:
            line = f"{line} {self.metric_type.value},{self.value}"

        # Add timestamp
        if self.timestamp is not None:
            timestamp = int(self.timestamp.timestamp() * 1000)
            line = f"{line} {timestamp}"

        return line

    def __repr__(self):
        return self.to_mint_line()

    def _key_and_dimensions(self):
        if not self.dimensions:
            return f"{self.key}"

        dimensions_string = ",".join([f'{k}="{v}"' for k, v in self.dimensions.items()])
        return f"{self.key},{dimensions_string}"

    def validate(self) -> bool:
        if len(self.dimensions) > LIMIT_DIMENSIONS_COUNT:
            msg = f"Metric dimension count of {len(self.dimensions)} exceeds limit of {LIMIT_DIMENSIONS_COUNT} for {self.key}"
            raise ValueError(msg)

        line_length = len(self.to_mint_line())
        if line_length > LIMIT_LINE_LENGTH:
            msg = f"Metric line length {line_length} exceeds limit of {LIMIT_LINE_LENGTH} for {self.key}"
            raise ValueError(msg)
        return True


class SfmMetric(Metric):
    def __init__(
        self,
        key: str,
        value: Union[float, int, str, SummaryStat],
        dimensions: Optional[Dict[str, str]] = None,
        metric_type: MetricType = MetricType.GAUGE,
        timestamp: Optional[datetime] = None,
        client_facing: bool = False,
    ):
        key = create_sfm_metric_key(key, client_facing)
        super().__init__(key, value, dimensions, metric_type, timestamp)


def create_sfm_metric_key(key: str, client_facing: bool = False) -> str:
    namespace = CLIENT_FACING_SFM_NAMESPACE if client_facing else INTERNAL_SFM_NAMESPACE
    return f"{namespace}:datasource.python.{key}"

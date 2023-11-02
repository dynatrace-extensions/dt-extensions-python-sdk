# SPDX-FileCopyrightText: 2023-present Dynatrace LLC
#
# SPDX-License-Identifier: MIT

from enum import Enum
from typing import List


class ActivationType(Enum):
    REMOTE = "remote"
    LOCAL = "local"


class ActivationConfig(dict):
    def __init__(self, activation_context_json: dict):
        self._activation_context_json = activation_context_json
        self.version: str = self._activation_context_json.get("version", "")
        self.enabled: bool = self._activation_context_json.get("enabled", True)
        self.description: str = self._activation_context_json.get("description", "")
        self.feature_sets: List[str] = self._activation_context_json.get("featureSets", [])
        self.type: ActivationType = ActivationType.REMOTE if self.remote else ActivationType.LOCAL
        super().__init__()

    @property
    def config(self) -> dict:
        return self.remote if self.remote else self.local

    @property
    def remote(self) -> dict:
        return self._activation_context_json.get("pythonRemote", {})

    @property
    def local(self) -> dict:
        return self._activation_context_json.get("pythonLocal", {})

    def __getitem__(self, item):
        return self.config[item]

    def get(self, key, default=None):
        return self.config.get(key, default)

    def __repr__(self):
        return f"ActivationConfig(version='{self.version}', enabled={self.enabled}, description='{self.description}', type={self.type}, config={self.config})"

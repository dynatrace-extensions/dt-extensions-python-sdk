from __future__ import annotations

import json
from pathlib import Path

import yaml


class ExtensionYaml:
    def __init__(self, yaml_file: Path):
        self._file = yaml_file
        self._data = yaml.safe_load(yaml_file.read_text())

    @property
    def name(self) -> str:
        return self._data.get("name", "")

    @property
    def version(self) -> str:
        return self._data.get("version", "")

    @property
    def min_dynatrace_version(self) -> str:
        return self._data.get("minDynatraceVersion", "")

    @property
    def author(self) -> Author:
        return Author(self._data.get("author", {}))

    @property
    def python(self) -> Python:
        return Python(self._data.get("python", {}))

    def validate(self):
        """
        Checks that the files under 'python.activation' exist and are valid json files
        """
        if self.python.activation.remote and self.python.activation.remote.path:
            self._validate_json_file(self.python.activation.remote.path)

        if self.python.activation.local and self.python.activation.local.path:
            self._validate_json_file(self.python.activation.local.path)

    def _validate_json_file(self, raw_path: str):
        path = Path(Path(self._file).parent / raw_path)
        if not path.exists():
            msg = f"Extension yaml validation failed, file {path} does not exist"
            raise ValueError(msg)

        # Parse the file to make sure it is valid json
        with path.open() as f:
            json.load(f)

    def zip_file_name(self) -> str:
        return f"{self.name.replace(':', '_')}-{self.version}.zip"


class Python:
    def __init__(self, data: dict):
        self._data = data

    @property
    def runtime(self) -> Runtime:
        return Runtime(self._data.get("runtime", {}))

    @property
    def activation(self):
        return Activation(self._data.get("activation", {}))


class Runtime:
    def __init__(self, data: dict):
        self._data = data

    @property
    def module(self) -> str:
        return self._data.get("module", "datasourcepy")

    @property
    def version(self) -> Version:
        return Version(self._data.get("version", {}))


class Version:
    def __init__(self, data: dict):
        self._data = data

    @property
    def min_version(self) -> str:
        return self._data.get("min", "")

    @property
    def max_version(self) -> str:
        return self._data.get("max", "")


class Activation:
    def __init__(self, data: dict):
        self._data = data

    @property
    def remote(self) -> ActivationInstance | None:
        if data := self._data.get("remote"):
            return ActivationInstance(data)
        return None

    @property
    def local(self) -> ActivationInstance | None:
        if data := self._data.get("local"):
            return ActivationInstance(data)
        return None


class ActivationInstance:
    def __init__(self, data: dict):
        self._data = data

    @property
    def path(self) -> str:
        return self._data.get("path", "")


class Author:
    def __init__(self, _data: dict):
        self._data = _data

    @property
    def name(self) -> str:
        return self._data.get("name", "")

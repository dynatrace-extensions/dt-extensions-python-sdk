from io import StringIO
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from dynatrace_extension.cli.schema import ExtensionYaml

VALID_YAML = """
name: custom:mulesoft-cloudhub
version: 0.0.1
minDynatraceVersion: "1.285"
author:
  name: "Dynatrace"

python:
  runtime:
    module: mulesoft_cloudhub
    version:
      min: "3.10"

  activation:
    remote:
      path: activationSchema.json
    local: null
"""


def mock_open(*args, **kwargs):
    return StringIO(VALID_YAML)


class TestTypes(TestCase):
    @patch("pathlib.Path.open", mock_open)
    def test_valid_yaml(self):
        extension = ExtensionYaml(Path("extension.yaml"))
        assert extension.name == "custom:mulesoft-cloudhub"
        assert extension.version == "0.0.1"
        assert extension.min_dynatrace_version == "1.285"
        assert extension.author.name == "Dynatrace"
        assert extension.python.runtime.module == "mulesoft_cloudhub"
        assert extension.python.runtime.version.min_version == "3.10"
        assert extension.python.activation.remote.path == "activationSchema.json"
        assert extension.python.activation.local is None

    def test_invalid_yaml(self):
        with self.assertRaises(FileNotFoundError):
            ExtensionYaml(Path("non_existent_file"))

    @patch("pathlib.Path.open", mock_open)
    def test_validate(self):
        extension = ExtensionYaml(Path("extension.yaml"))

        with self.assertRaises(ValueError):
            extension.validate()

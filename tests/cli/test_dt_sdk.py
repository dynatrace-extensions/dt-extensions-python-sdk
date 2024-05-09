import shutil
from pathlib import Path
from unittest import TestCase
from unittest.mock import NonCallableMock, call, mock_open, patch

import dynatrace_extension.cli.main as dt_sdk

SAMPLE_EXTENSION_DATA = """
name: test_extension
version: 1.0.0
"""


class TestDtSdk(TestCase):
    def setUp(self):
        self.temp_dir = Path("test_temp")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        pass

    @patch("dynatrace_extension.cli.main.dt_cli_upload")
    @patch("dynatrace_extension.cli.main.dt_cli_validate")
    @patch("builtins.open", mock_open(read_data=SAMPLE_EXTENSION_DATA))
    def test_dt_sdk_upload(self, mock_upload, mock_validate):
        extension_path = Path("test_extension_dir")
        tenant_url = "test_tenant_url"
        api_token = "test_api_token"

        dt_sdk.upload(extension_path, tenant_url, api_token, validate=False)

    @patch("dynatrace_extension.cli.main.subprocess.run")
    def test_dt_sdk_gen_certs(self, mock_subprocess_run: NonCallableMock):
        output = Path("certificates")

        dt_sdk.gencerts(output, force=True)
        mock_subprocess_run.assert_has_calls(
            [
                call(
                    [
                        "dt",
                        "ext",
                        "genca",
                        "--ca-cert",
                        f"{output / 'ca.pem'}",
                        "--ca-key",
                        f"{output / 'ca.key'}",
                        "--no-ca-passphrase",
                    ],
                    cwd=None,
                    env=None,
                    check=True,
                ),
                call(
                    [
                        "dt",
                        "ext",
                        "generate-developer-pem",
                        "--output",
                        f"{output / 'developer.pem'}",
                        "--name",
                        "Acme",
                        "--ca-crt",
                        f"{output / 'ca.pem'}",
                        "--ca-key",
                        f"{output / 'ca.key'}",
                    ],
                    cwd=None,
                    env=None,
                    check=True,
                ),
            ]
        )

    def test_dt_sdk_workflow(self):
        # Generate real certificates
        dt_sdk.gencerts(self.temp_dir / "certificates", force=True)

        # Check that the certificate files were created
        self.assertTrue((self.temp_dir / "certificates" / "ca.key").exists())
        self.assertTrue((self.temp_dir / "certificates" / "ca.pem").exists())
        self.assertTrue((self.temp_dir / "certificates" / "developer.pem").exists())

        # Create a real extension
        dt_sdk.create("test_extension", self.temp_dir)

        # Check that the extension files exist
        self.assertTrue((self.temp_dir / "test_extension" / "test_extension" / "__main__.py").exists())
        self.assertTrue((self.temp_dir / "test_extension" / "setup.py").exists())
        self.assertTrue((self.temp_dir / "test_extension" / "activation.json").exists())
        self.assertTrue((self.temp_dir / "test_extension" / "extension" / "extension.yaml").exists())

        # Build the extension
        dt_sdk.build(
            self.temp_dir / "test_extension",
            self.temp_dir / "certificates" / "developer.pem",
            target_directory=None,
            extra_platforms=None,
            extra_index_url=None,
            find_links=None,
        )

        # Check that the built extension file exists
        self.assertTrue((self.temp_dir / "test_extension" / "extension" / "lib").exists())
        self.assertTrue((self.temp_dir / "test_extension" / "dist" / "custom_test-extension-0.0.1.zip").exists())

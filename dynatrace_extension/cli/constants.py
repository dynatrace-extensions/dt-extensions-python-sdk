import stat
from pathlib import Path

# Extension file system related constants
DIST_DIR = "dist"
EXTENSION_DIR = "extension"
EXTENSION_YAML = "extension.yaml"
EXTENSION_ZIP = "extension.zip"
EXTENSION_ZIP_SIG = "extension.zip.sig"

# Certificate related constants
CA_KEY = "ca.key"
CA_PEM = "ca.pem"
DEFAULT_CA_SUBJECT = "/CN=Extension CA/O=Some Company/OU=Extension CA"
DEFAULT_DEV_SUBJECT = "/CN=Some Developer/O=Some Company/OU=Extension Development"
DEFAULT_VALIDITY_PERIOD = 365 * 3
DEV_PEM = "developer.pem"
CERT_DIR_ENVIRONMENT_VAR = "DT_CERTIFICATES_FOLDER"
CERTIFICATE_DEFAULT_PATH = Path.home() / ".dynatrace" / "certificates"
REQUIRED_PERMISSIONS = stat.S_IREAD + stat.S_IWRITE

# Python related constants
SUPPORTED_PYTHON_VERSIONS = ["3.10", "3.14"]

# Environment related constants
DT_API_TOKEN = "DT_API_TOKEN"
DT_API_URL = "DT_API_URL"
DT_PLATFORM_TOKEN = "DT_PLATFORM_TOKEN"

# API related constants
CLASSIC_ENV_CONFIG_ENDPOINT = "/api/v2/extensions/{extension_id}/environmentConfiguration"
CLASSIC_UPLOAD_ENDPOINT = "/api/v2/extensions"
CLASSIC_VALIDATE_ENDPOINT = "/api/v2/extensions?validateOnly=true"
PLATFORM_ENV_CONFIG_ENDPOINT = "/platform/extensions/v2/extensions/{extension_id}/environment-configuration"
PLATFORM_UPLOAD_ENDPOINT = "/platform/extensions/v2/extensions"
PLATFORM_VALIDATE_ENDPOINT = "/platform/extensions/v2/extensions:validate"

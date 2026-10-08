from pathlib import Path
import stat

#Extension file system related constants
DIST_DIR = "dist"
EXTENSION_DIR = "extension"
EXTENSION_YAML = "extension.yaml"
EXTENSION_ZIP = "extension.zip"
EXTENSION_ZIP_SIG = "extension.zip.sig"

#Certificate related constants
CA_KEY = "ca.key"
CA_PEM = "ca.pem"
DEFAULT_CA_SUBJECT = "/CN=Extension CA/O=Some Company/OU=Extension CA"
DEFAULT_DEV_SUBJECT = "/CN=Some Developer/O=Some Company/OU=Extension Development"
DEFAULT_VALIDITY_PERIOD = 365 * 3
DEV_PEM = "developer.pem"
CERT_DIR_ENVIRONMENT_VAR = "DT_CERTIFICATES_FOLDER"
CERTIFICATE_DEFAULT_PATH = Path.home() / ".dynatrace" / "certificates"
REQUIRED_PRIVATE_KEY_PERMISSIONS = stat.S_IREAD

#Python related constants
SUPPORTED_PYTHON_VERSIONS = ["3.10", "3.14"]
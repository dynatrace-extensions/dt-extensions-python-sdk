import ast
import re
import typer

from cryptography import x509
from cryptography.x509.oid import NameOID
from pathlib import Path
from rich.console import Console

X509NameAttributes = {
    "CN": NameOID.COMMON_NAME,
    "O": NameOID.ORGANIZATION_NAME,
    "OU": NameOID.ORGANIZATIONAL_UNIT_NAME,
    "L": NameOID.LOCALITY_NAME,
    "S": NameOID.STATE_OR_PROVINCE_NAME,
    "C": NameOID.COUNTRY_NAME,
}

def _generate_x509_name(attributes: dict) -> x509.Name:
    names_attributes = []
    for name, oid in X509NameAttributes.items():
        if name in attributes and attributes[name]:
            names_attributes.append(x509.NameAttribute(oid, attributes[name]))

    return x509.Name(names_attributes)

def _version_to_pip_version(version: str) -> str:
    """Convert a version string like '3.10' to pip format '310'."""
    return version.replace(".", "")

def _parse_x509_subject(subject: str) -> dict[str, str]:
    """Parse a subject like '/CN=name/O=org/OU=unit' into a dict for _generate_x509_name.

    A literal '/' inside a value can be escaped as '\\/'. 'ST' is accepted as an alias for 'S'.
    """
    attributes: dict[str, str] = {}
    for part in re.split(r"(?<!\\)/", subject.strip()):
        if not part:
            continue
        key, sep, value = part.partition("=")
        key = key.strip().upper()
        if key == "ST":
            key = "S"
        if not sep or key not in X509NameAttributes:
            raise typer.BadParameter(
                f"Invalid subject component '{part}'. Expected /key=value with key in {', '.join(X509NameAttributes)}."
            )
        attributes[key] = value.strip().replace("\\/", "/")
    return attributes

def _get_windows_dependencies(extension_dir: Path) -> list[str]:
    """Parse setup.py and return package names that are Windows-only (platform_system=='Windows')."""
    setup_py = extension_dir / "setup.py"
    if not setup_py.exists():
        return []

    tree = ast.parse(setup_py.read_text())
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        is_setup_call = (isinstance(func, ast.Name) and func.id == "setup") or (
            isinstance(func, ast.Attribute) and func.attr == "setup"
        )
        if not is_setup_call:
            continue
        for keyword in node.keywords:
            if keyword.arg != "install_requires":
                continue
            if not isinstance(keyword.value, ast.List):
                continue
            windows_deps = []
            for elt in keyword.value.elts:
                if not isinstance(elt, ast.Constant) or not isinstance(elt.value, str):
                    continue
                dep = elt.value
                if "platform_system=='Windows'" in dep or 'platform_system=="Windows"' in dep:
                    windows_deps.append(dep.split(";")[0].strip())
            return windows_deps
    return []

def require_file_existence(console: Console, file: Path):
    if not file.exists():
        console.print(f"{file.as_posix()} doesn't exist, aborting!", style="bold red")
        raise typer.Exit(1)

def check_file_existence(console: Console, file: Path):
    if file.exists():
        console.print(f"{file} already exists, it will be overwritten!", style="yellow")
        return True
    return False
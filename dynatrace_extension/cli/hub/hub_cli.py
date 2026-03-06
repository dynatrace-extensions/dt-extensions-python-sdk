import io
import logging
import zipfile
from pathlib import Path

import typer
import yaml
from rich.console import Console

from ..schema import ExtensionYaml
from .hub_client import HubConsole

hub_app = typer.Typer(help="Hub commands")
console = Console()
logger = logging.getLogger(__name__)


def _get_extension_id_from_zip(zip_path: Path) -> str:
    """Extract the extension name from a signed extension zip file.

    The signed zip contains an inner zip, which in turn contains
    ``extension.yaml`` with the extension metadata.
    """
    with zipfile.ZipFile(zip_path) as outer_zip:
        inner_names = [n for n in outer_zip.namelist() if n.endswith(".zip")]
        if not inner_names:
            msg = f"No inner zip file found in {zip_path}"
            raise typer.BadParameter(msg)

        with outer_zip.open(inner_names[0]) as inner_file:
            with zipfile.ZipFile(io.BytesIO(inner_file.read())) as inner_zip:
                with inner_zip.open("extension.yaml") as yaml_file:
                    data = yaml.safe_load(yaml_file.read())
                    name = data.get("name")
                    if not name:
                        msg = f"Could not find 'name' in extension.yaml inside {zip_path}"
                        raise typer.BadParameter(msg)
                    return name


@hub_app.command(help="Publish the extension to the Dynatrace Hub")
def publish(
    extension_path: Path = typer.Argument(Path("."), help="Path to the extension folder or built zip file"),
    changelog: Path = typer.Option(Path("CHANGELOG.md"), "--changelog", "-c", help="Path to the changelog file"),
):
    """
    Publishes the extension to the Dynatrace Hub

    :param extension_path: The path to the extension folder or built zip file
    :param changelog: The path to the changelog file (CHANGELOG.md by default)
    """
    zip_file_path = extension_path
    if extension_path.is_dir():
        yaml_path = extension_path / "extension" / "extension.yaml"
        extension_yaml = ExtensionYaml(yaml_path)
        extension_id = extension_yaml.name
        zip_file_path = extension_path / "dist" / extension_yaml.zip_file_name()
    else:
        extension_id = _get_extension_id_from_zip(zip_file_path)

    if not zip_file_path.exists():
        msg = f"Extension zip file not found: {zip_file_path}"
        logger.error(msg)
        raise FileNotFoundError(msg)

    changelog_path: Path | None = changelog
    if not changelog.exists():
        logger.warning("Changelog file not found at %s, publishing without release notes", changelog)
        changelog_path = None

    client = HubConsole()
    result = client.post_extension_release(extension_id, zip_file_path, changelog_path)
    console.print(f"Published extension {extension_id} to the Hub: {result}", style="bold green")

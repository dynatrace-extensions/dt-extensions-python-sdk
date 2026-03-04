import logging
from pathlib import Path

import typer
from rich.console import Console

from ..schema import ExtensionYaml
from .hub_client import HubConsole

hub_app = typer.Typer(help="Hub commands")
console = Console()
logger = logging.getLogger(__name__)


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
        extension_id = None

    if not zip_file_path.exists():
        msg = f"Extension zip file not found: {zip_file_path}"
        logger.error(msg)
        raise FileNotFoundError(msg)

    changelog_path: Path | None = changelog
    if not changelog.exists():
        logger.warning("Changelog file not found at %s, publishing without release notes", changelog)
        changelog_path = None

    if extension_id is None:
        raise typer.BadParameter("Could not determine extension ID. Provide a directory with extension.yaml.")

    client = HubConsole()
    result = client.post_extension_release(extension_id, zip_file_path, changelog_path)
    console.print(f"Published extension {extension_id} to the Hub: {result}", style="bold green")

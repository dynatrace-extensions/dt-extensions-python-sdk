from pathlib import Path
from zipfile import ZipFile

import typer
from rich.console import Console

from ..constants import EXTENSION_ZIP, EXTENSION_ZIP_SIG


def build_signed_bundle(console: Console, extension_zip: Path, signature: bytes, output_path: Path, force: bool = False):
    if not extension_zip.exists():
        console.print(f"Failed to build signed bundle, {extension_zip.as_posix()} doesn't exist, aborting!", style="bold red")
        raise typer.Exit(1)

    if output_path.exists() and not force:
        console.print(f"Failed to build signed bundle, {output_path} already exists, aborting! Use --force to overwrite the existing bundle.", style="bold red")
        raise typer.Exit(1)

    with ZipFile(output_path, "w") as zf:
        zf.write(extension_zip, arcname=EXTENSION_ZIP)
        zf.writestr(EXTENSION_ZIP_SIG, signature)

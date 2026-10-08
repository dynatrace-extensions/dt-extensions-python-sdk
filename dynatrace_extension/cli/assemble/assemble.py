from pathlib import Path
from zipfile import ZipFile

from rich.console import Console

from ..constants import EXTENSION_YAML
from ..utils import check_file_existence, require_file_existence


def assemble_extension(console: Console, source: Path, output: Path):
    require_file_existence(console, Path(source / EXTENSION_YAML))
    check_file_existence(console, output)

    with ZipFile(output, "w") as zf:
        for entry in source.rglob("*"):

            if entry.is_dir():
                continue

            rel_path = entry.relative_to(source)
            if rel_path == output:
                continue

            zf.write(entry, arcname=rel_path)
            console.print(f"Adding file: {entry.as_posix()} as {rel_path.as_posix()}", style="bold green")

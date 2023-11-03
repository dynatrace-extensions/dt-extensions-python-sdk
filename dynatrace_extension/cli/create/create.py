import os
import re
import shutil
from pathlib import Path
from typing import Final, List, NamedTuple, Tuple

output_mode_folder: Final = 0o755
output_mode_file: Final = 0o644
template_base_folder: Final = Path(__file__).parent


class ReplaceString(NamedTuple):
    what: str
    replace: str


def replace_placeholders(file: Path, replaces: List[Tuple[str, str]]):
    with open(file) as f:
        contents = f.read()
    for replace in replaces:
        old_text, new_text = replace
        contents = contents.replace(old_text, new_text)
    with open(file, "w") as f:
        f.write(contents)


def copy_templates(source: Path, destination: Path, extension_name: str):
    extension_name_lower = extension_name.lower()
    extension_name_capitalize = extension_name.capitalize()
    extension_name_dash = extension_name_lower.replace("_", "-")
    extension_prefix = "custom:"
    replaces = [
        ("%Extension_Name%", extension_name_capitalize),
        ("%extension_name%", extension_name_lower),
        ("%extension-name%", extension_name_dash),
        ("%extension-prefix%", extension_prefix),
    ]
    for file in source.iterdir():
        if file.is_dir() and file.name != "__pycache__":
            # If it is a folder, recursively copy and process the template files
            dir_name = file.name
            if dir_name == "extension_name":
                dir_name = extension_name
            dest_dir = Path(destination, dir_name)
            dest_dir.mkdir(mode=output_mode_folder, exist_ok=True)
            copy_templates(file, dest_dir, extension_name)

        elif file.is_file() and file.name.endswith(".template"):
            # If it is a file, copy and process it
            file_name = file.name.removesuffix(".template")
            dest_file = Path(destination, file_name)
            shutil.copy(file, dest_file)
            os.chmod(dest_file, output_mode_file)
            replace_placeholders(dest_file, replaces)


def is_pep8_compliant(extension_name: str) -> bool:
    """
    Check if extension name is valid according to PEP-8
    https://peps.python.org/pep-0008/#package-and-module-names
    :param extension_name: extension name to check
    :return: True if extension name is valid, False otherwise
    """
    if not re.match("[a-z][a-z0-9]*(_[a-z0-9]+)*$", extension_name):
        return False
    return True


def generate_extension(extension_name: str, output: Path) -> Path:
    output.mkdir(mode=output_mode_folder, exist_ok=True, parents=True)
    try:
        copy_templates(template_base_folder / "extension_template", output, extension_name)
        return output.resolve()
    except Exception:
        shutil.rmtree(output)
        raise

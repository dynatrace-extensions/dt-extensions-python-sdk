import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

import typer
from dtcli.server_api import upload as dt_cli_upload  # type: ignore
from dtcli.server_api import validate as dt_cli_validate
from rich.console import Console

from ..__about__ import __version__
from .create import generate_extension, is_pep8_compliant
from .schema import ExtensionYaml

app = typer.Typer(pretty_exceptions_show_locals=False, pretty_exceptions_enable=False)
console = Console()

# if we are not python 3.10.X, exit with an error
if sys.version_info < (3, 10) or sys.version_info >= (3, 11):
    console.print(f"Python 3.10.X is required to build extensions, you are using {sys.version_info}", style="bold red")
    sys.exit(1)

CERT_DIR_ENVIRONMENT_VAR = "DT_CERTIFICATES_FOLDER"
CERTIFICATE_DEFAULT_PATH = Path.home() / ".dynatrace" / "certificates"


# show version
@app.command()
def version():
    """
    Show the version of the CLI
    """
    console.print(f"dt-extensions-sdk version {__version__}", style="bold green")


@app.command()
def run(
    extension_dir: Path = typer.Argument("."),
    activation_config: str = "activation.json",
    fast_check: bool = typer.Option(False, "--fastcheck"),
    local_ingest: bool = typer.Option(False, "--local-ingest"),
    local_ingest_port: int = typer.Option(14499, "--local-ingest-port"),
    print_metrics: bool = typer.Option(True),
):
    """
    Runs an extension, this is used during development to locally run and test an extension

    :param extension_dir: The directory of the extension, by default this is the current directory
    :param activation_config: The activation config file, by default this is activation.json
    :param fast_check: If true, run a fastcheck and exits
    :param local_ingest: If true, send metrics to localhost:14499 on top of printing them
    :param local_ingest_port: The port to send metrics to, by default this is 14499
    :param print_metrics: If true, print metrics to the console
    """

    # This parses the yaml, which validates it before running
    extension_yaml = ExtensionYaml(extension_dir / "extension/extension.yaml")
    try:
        command = [sys.executable, "-m", extension_yaml.python.runtime.module, "--activationconfig", activation_config]
        if fast_check:
            command.append("--fastcheck")
        if local_ingest:
            command.append("--local-ingest")
            command.append(f"--local-ingest-port={local_ingest_port}")
        if not print_metrics:
            command.append("--no-print-metrics")
        run_process(command, cwd=extension_dir)
    except KeyboardInterrupt:
        console.print("\nRun interrupted with a KeyboardInterrupt, stopping", style="bold yellow")


@app.command(help="Runs wheel, assemble and sign. Downloads dependencies, creates and signs the extension zip file")
def build(
    extension_dir: Path = typer.Argument(Path("."), help="Path to the python extension"),
    private_key: Path = typer.Option(
        Path(CERTIFICATE_DEFAULT_PATH) / "developer.pem",
        "--private-key",
        "-k",
        help="Path to the dev fused key-certificate",
    ),
    target_directory: Optional[Path] = typer.Option(None, "--target-directory", "-t"),
    extra_platforms: Optional[list[str]] = typer.Option(
        None, "--extra-platform", "-e", help="Download wheels for an extra platform"
    ),
    extra_index_url: Optional[str] = typer.Option(
        None, "--extra-index-url", "-i", help="Extra index url to use when downloading dependencies"
    ),
    find_links: Optional[str] = typer.Option(
        None, "--find-links", "-f", help="Extra index url to use when downloading dependencies"
    ),
):
    """
    Builds and signs an extension using the developer fused key-certificate

    :param extension_dir: The directory of the extension, by default this is the current directory
    :param private_key: The path to the developer fused key-certificate, if not specified, we try to locate the file developer.pem under the environment
    variable DT_CERTIFICATES_FOLDER
    :param target_directory: The directory to put the extension zip file in, if not specified, we put it in the dist
    folder
    :param extra_platforms: Attempt to also download wheels for an extra platform (e.g. manylinux1_x86_64 or win_amd64)
    :param extra_index_url: Extra index url to use when downloading dependencies
    :param find_links: Extra index url to use when downloading dependencies
    """
    console.print(f"Building and signing extension from {extension_dir} to {target_directory}", style="cyan")
    if target_directory is None:
        target_directory = extension_dir / "dist"
    if not target_directory.exists():
        target_directory.mkdir()

    console.print("Stage 1 - Download and build dependencies", style="bold blue")
    wheel(extension_dir, extra_platforms, extra_index_url, find_links)

    console.print("Stage 2 - Create the extension zip file", style="bold blue")
    built_zip = assemble(extension_dir, target_directory)

    console.print("Stage 3 - Sign the extension", style="bold blue")
    extension_yaml = ExtensionYaml(Path(extension_dir) / "extension" / "extension.yaml")
    output = target_directory / extension_yaml.zip_file_name()
    sign(built_zip, private_key, output)

    console.print(f"Stage 4 - Delete {built_zip}", style="bold blue")
    built_zip.unlink()


@app.command(help="Creates the extension zip file, without signing it yet")
def assemble(
    extension_dir: Path = typer.Argument(".", help="Path to the python extension"),
    output: Path = typer.Option(None, "--output", "-o"),
    force: bool = typer.Option(True, "--force", "-f", help="Force overwriting the output zip file"),
) -> Path:
    """
    Creates the extension zip file (not yet signed)

    :param extension_dir: The directory of the extension, by default this is the current directory
    :param output: The path to the output zip file, if not specified, we put it in the dist folder
    :param force: If true, overwrite the output zip file if it exists
    """

    # This checks if the yaml is valid, because it parses it
    # Also validates that the schema files are valid and exist
    extension_yaml = ExtensionYaml(Path(extension_dir) / "extension" / "extension.yaml")
    extension_yaml.validate()

    # Checks that the module name is valid and exists in the filesystem
    module_folder = Path(extension_dir) / extension_yaml.python.runtime.module
    if not module_folder.exists():
        msg = f"Extension module folder {module_folder} not found"
        raise FileNotFoundError(msg)

    # This is the zip file that will contain the extension
    if output is None:
        dist_dir = Path(extension_dir) / "dist"
        if not dist_dir.exists():
            dist_dir.mkdir()
        output = dist_dir / "extension.zip"
    elif output.exists() and output.is_dir():
        output = output / "extension.zip"

    command = ["dt", "ext", "assemble", "--source", f"{Path(extension_dir) / 'extension'}", "--output", f"{output}"]
    if force:
        command.append("--force")
    run_process(command)
    console.print(f"Built the extension zip file to {output}", style="bold green")
    return output


@app.command(help="Downloads the dependencies of the extension to the lib folder")
def wheel(
    extension_dir: Path = typer.Argument(".", help="Path to the python extension"),
    extra_platforms: Optional[list[str]] = typer.Option(
        None, "--extra-platform", "-e", help="Download wheels for an extra platform"
    ),
    extra_index_url: Optional[str] = typer.Option(
        None, "--extra-index-url", "-i", help="Extra index url to use when downloading dependencies"
    ),
    find_links: Optional[str] = typer.Option(
        None, "--find-links", "-f", help="Extra index url to use when downloading dependencies"
    ),
):
    """
    Builds the extension and it's dependencies into wheel files
    Places these files in the lib folder

    :param extension_dir: The directory of the extension, by default this is the current directory
    :param extra_platforms: Attempt to also download wheels for an extra platform (e.g. manylinux1_x86_64 or win_amd64)
    :param extra_index_url: Extra index url to use when downloading dependencies
    :param find_links: Extra index url to use when downloading dependencies
    """
    relative_lib_folder_dir = "extension/lib"
    lib_folder: Path = extension_dir / relative_lib_folder_dir
    _clean_directory(lib_folder)

    console.print(f"Downloading dependencies to {lib_folder}", style="cyan")

    # Downloads the dependencies and places them in the lib folder
    command = [sys.executable, "-m", "pip", "wheel", "-w", relative_lib_folder_dir]
    if extra_index_url is not None:
        command.extend(["--extra-index-url", extra_index_url])
    if find_links is not None:
        command.extend(["--find-links", find_links])
    command.append(".")
    run_process(command, cwd=extension_dir)

    if extra_platforms:
        for extra_platform in extra_platforms:
            console.print(f"Downloading wheels for platform {extra_platform}", style="cyan")
            command = [
                sys.executable,
                "-m",
                "pip",
                "download",
                "-d",
                relative_lib_folder_dir,
                "--only-binary=:all:",
                "--platform",
                extra_platform,
            ]
            if extra_index_url:
                command.extend(["--extra-index-url", extra_index_url])
            if find_links:
                command.extend(["--find-links", find_links])
            command.append(".")

            run_process(command, cwd=extension_dir)

    console.print(f"Installed dependencies to {lib_folder}", style="bold green")


@app.command()
def sign(
    zip_file: Path = typer.Argument(Path("dist/extension.zip"), help="Path to the extension zip file"),
    certificate: Path = typer.Option(
        Path(CERTIFICATE_DEFAULT_PATH) / "developer.pem",
        "--certificate",
        "-c",
        help="Path to the dev fused key-certificate",
    ),
    output: Path = typer.Option(None, "--output", "-o"),
    force: bool = typer.Option(True, "--force", "-f", help="Force overwriting the output zip file"),
):
    """
    Signs the extension zip file using the provided fused key-certificate

    :param zip_file: The path to the extension zip file to sign
    :param certificate: The developer fused key-certificate to use for signing
    :param output: The path to the output zip file, if not specified, we put it in the dist folder
    :param force: If true, overwrite the output zip file if it exists
    """
    if not certificate:
        # If the user doesn't specify a certificate, we try to find it in the default directory
        # This directory can be set by the environment variable DT_CERTIFICATES_FOLDER
        if CERT_DIR_ENVIRONMENT_VAR not in os.environ:
            console.print(
                f"{CERT_DIR_ENVIRONMENT_VAR} not found in environment variables. Using {CERTIFICATE_DEFAULT_PATH} instead.",
                style="yellow",
            )
        certificate = _find_certificate(CERTIFICATE_DEFAULT_PATH)
    else:
        certificate = _find_certificate(Path(certificate))

    combined_cert_and_key = certificate

    if output is None:
        output = zip_file.parent / f"signed_{zip_file.name}"

    console.print(f"Signing file {zip_file} to {output} with certificate {certificate}", style="cyan")
    command = [
        "dt",
        "ext",
        "sign",
        "--src",
        f"{zip_file}",
        "--output",
        f"{output}",
        "--key",
        f"{combined_cert_and_key}",
    ]

    if force:
        command.append("--force")
    run_process(command)
    console.print(f"Created signed extension file {output}", style="bold green")


@app.command(help="Upload the extension to a Dynatrace environment")
def upload(
    extension_path: Path = typer.Argument(None, help="Path to the extension folder or built zip file"),
    tenant_url: str = typer.Option(None, "--tenant-url", "-u", help="Dynatrace tenant URL"),
    api_token: str = typer.Option(None, "--api-token", "-t", help="Dynatrace API token"),
    validate: bool = typer.Option(None, "--validate", "-v", help="Validate only"),
):
    """
    Uploads the extension to a Dynatrace environment

    :param extension_path: The path to the extension folder or built zip file
    :param tenant_url: The Dynatrace tenant URL
    :param api_token: The Dynatrace API token
    :param validate: If true, only validate the extension and exit
    """

    zip_file_path = extension_path
    if extension_path is None:
        extension_path = Path(".")
    else:
        extension_path = Path(extension_path)
    if extension_path.is_dir():
        yaml_path = Path(extension_path, "extension", "extension.yaml")
        extension_yaml = ExtensionYaml(yaml_path)
        zip_file_name = extension_yaml.zip_file_name()
        zip_file_path = Path(extension_path, "dist", zip_file_name)

    api_url = tenant_url or os.environ.get("DT_API_URL", "")
    api_url = api_url.rstrip("/")

    if not api_url:
        console.print("Set the --tenant-url parameter or the DT_API_URL environment variable", style="bold red")
        sys.exit(1)

    api_token = api_token or os.environ.get("DT_API_TOKEN", "")
    if not api_token:
        console.print("Set the --api-token parameter or the DT_API_TOKEN environment variable", style="bold red")
        sys.exit(1)

    if validate:
        dt_cli_validate(f"{zip_file_path}", api_url, api_token)
    else:
        dt_cli_upload(f"{zip_file_path}", api_url, api_token)
        console.print(f"Extension {zip_file_path} uploaded to {api_url}", style="bold green")


@app.command(help="Generate root and developer certificates and key")
def gencerts(
    output: Path = typer.Option(CERTIFICATE_DEFAULT_PATH, "--output", "-o", help="Path to the output directory"),
    force: bool = typer.Option(False, "--force", "-f", help="Force overwriting the certificates"),
):
    developer_pem = output / "developer.pem"
    command_gen_ca = [
        "dt",
        "ext",
        "genca",
        "--ca-cert",
        f"{output / 'ca.pem'}",
        "--ca-key",
        f"{output / 'ca.key'}",
        "--no-ca-passphrase",
    ]

    command_gen_dev_pem = [
        "dt",
        "ext",
        "generate-developer-pem",
        "--output",
        f"{developer_pem}",
        "--name",
        "Acme",
        "--ca-crt",
        f"{output / 'ca.pem'}",
        "--ca-key",
        f"{output / 'ca.key'}",
    ]

    if output.exists():
        if developer_pem.exists() and force:
            command_gen_ca.append("--force")
            developer_pem.chmod(stat.S_IREAD | stat.S_IWRITE)
            developer_pem.unlink(missing_ok=True)
        elif developer_pem.exists() and not force:
            msg = f"Certificates were NOT generated! {developer_pem} already exists. Use --force option to overwrite the certificates"
            console.print(msg, style="bold red")
            sys.exit(1)
    else:
        output.mkdir(parents=True)

    run_process(command_gen_ca)
    run_process(command_gen_dev_pem)


@app.command(help="Creates a new python extension")
def create(extension_name: str, output: Path = typer.Option(None, "--output", "-o")):
    """
    Creates a new python extension

    :param extension_name: The name of the extension
    :param output: The path to the output directory, if not specified, we will use the extension name
    """

    if not is_pep8_compliant(extension_name):
        msg = f"Extension name {extension_name} is not valid, should be short, all-lowercase and underscores can be used if it improves readability"
        raise Exception(msg)

    if output is None:
        output = Path.cwd() / extension_name
    else:
        output = output / extension_name
    extension_path = generate_extension(extension_name, output)
    console.print(f"Extension created at {extension_path}", style="bold green")


def run_process(
    command: List[str], cwd: Optional[Path] = None, env: Optional[dict] = None, print_message: Optional[str] = None
):
    friendly_command = " ".join(command)
    if print_message is not None:
        console.print(print_message, style="cyan")
    else:
        console.print(f"Running: {friendly_command}", style="cyan")
    return subprocess.run(command, cwd=cwd, env=env, check=True)  # noqa: S603


def _clean_directory(directory: Path):
    if directory.exists():
        console.print(f"Cleaning {directory}", style="cyan")
        shutil.rmtree(directory)


def _find_certificate(path: Path) -> Path:
    """
    Verifies the existence of the file in given path or returns the default file
    """

    # If the user specified the path as a directory, we try to find developer.pem in this directory
    if path.is_dir():
        certificate = path / "developer.pem"
    else:
        certificate = path

    if not certificate.exists():
        msg = f"Certificate {certificate} not found"
        raise FileNotFoundError(msg)
    return certificate


if __name__ == "__main__":
    app()

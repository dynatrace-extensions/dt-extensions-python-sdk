from pathlib import Path

import requests
import typer
from rich.console import Console

from ..constants import (
    CLASSIC_ENV_CONFIG_ENDPOINT,
    CLASSIC_UPLOAD_ENDPOINT,
    CLASSIC_VALIDATE_ENDPOINT,
    PLATFORM_ENV_CONFIG_ENDPOINT,
    PLATFORM_UPLOAD_ENDPOINT,
    PLATFORM_VALIDATE_ENDPOINT,
)
from ..utils import detect_dt_platform


def upload_extension(console: Console, api_url: str, extension_package: Path, token: str):
    platform = detect_dt_platform(api_url)

    headers = {
        "Accept": "application/json; charset=utf-8",
        "Content-Type": "application/octet-stream",
    }

    if platform:
        url = f"{api_url}{PLATFORM_UPLOAD_ENDPOINT}"
        headers["Authorization"] = f"Bearer {token}"
    else:
        url = f"{api_url}{CLASSIC_UPLOAD_ENDPOINT}"
        headers["Authorization"] = f"Api-Token {token}"

    try:
        response = requests.post(url, headers=headers, data=extension_package.read_bytes(), timeout=10)
        response.raise_for_status()
        console.print("Extension upload successful!", style="bold green")
    except requests.exceptions.HTTPError as err:
        console.print(f"Extension upload failed! {response.text}", style="bold red")
        raise typer.Exit(1) from err


def validate_extension(console: Console, api_url: str, extension_package: Path, token: str):
    platform = detect_dt_platform(api_url)

    headers = {
        "Accept": "application/json; charset=utf-8",
        "Content-Type": "application/octet-stream",
    }

    if platform:
        url = f"{api_url}{PLATFORM_VALIDATE_ENDPOINT}"
        headers["Authorization"] = f"Bearer {token}"
    else:
        url = f"{api_url}{CLASSIC_VALIDATE_ENDPOINT}"
        headers["Authorization"] = f"Api-Token {token}"

    try:
        response = requests.post(url, headers=headers, data=extension_package.read_bytes(), timeout=10)
        response.raise_for_status()
        console.print("Extension validation successful!", style="bold green")
    except requests.exceptions.HTTPError as err:
        console.print(f"Extension validation failed! {response.text}", style="bold red")
        raise typer.Exit(1) from err


def set_active_version(console: Console, api_url: str, extension_id: str, version: str, token: str):
    platform = detect_dt_platform(api_url)

    headers = {
        "Accept": "application/json; charset=utf-8",
        "Content-Type": "application/json",
    }

    if platform:
        url = f"{api_url}{PLATFORM_ENV_CONFIG_ENDPOINT.format(extension_id=extension_id)}"
        headers["Authorization"] = f"Bearer {token}"
    else:
        url = f"{api_url}{CLASSIC_ENV_CONFIG_ENDPOINT.format(extension_id=extension_id)}"
        headers["Authorization"] = f"Api-Token {token}"

    try:
        response = requests.put(url, headers=headers, json={"version": version}, timeout=10)
        response.raise_for_status()
        console.print(f"Extension version {version} set as active!", style="bold green")
    except requests.exceptions.HTTPError as err:
        console.print(f"Setting active extension version failed! {response.text}", style="bold red")
        raise typer.Exit(1) from err

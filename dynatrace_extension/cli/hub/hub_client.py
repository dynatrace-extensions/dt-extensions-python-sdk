import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import requests


@dataclass
class Token:
    access_token: str
    expires_in: int
    token_type: str
    scope: str
    _issued_at: float = 0.0

    def __post_init__(self):
        self._issued_at = time.monotonic()

    @property
    def is_expired(self) -> bool:
        # Refresh 30 seconds before actual expiry
        return time.monotonic() >= self._issued_at + self.expires_in - 30


class HubConsole:
    def __init__(self):
        self.base_url = os.getenv("HUB_BASE_URL")
        self.sso_url = os.getenv("HUB_SSO_URL")
        self.client_id = os.getenv("HUB_CLIENT_ID")
        self._client_secret = os.getenv("HUB_CLIENT_SECRET")
        self._token: Optional[Token] = None


    def _check_env(self):
        if not self.base_url:
            raise ValueError("HUB_BASE_URL is not set")
        if not self.sso_url:
            raise ValueError("HUB_SSO_URL is not set")
        if not self.client_id:
            raise ValueError("HUB_CLIENT_ID is not set")
        if not self._client_secret:
            raise ValueError("HUB_CLIENT_SECRET is not set")

    def _get_token(self) -> str:
        if self._token is not None and not self._token.is_expired:
            return self._token.access_token

        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        params = {
            "client_id": self.client_id,
            "client_secret": self._client_secret,
            "grant_type": "client_credentials",
            "scope": "hub-console:projects:read hub-console:projects.releases:read hub-console:projects.releases:write"
        }
        resp = requests.post(self.sso_url, data=params, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        self._token = Token(
            access_token=data["access_token"],
            expires_in=data["expires_in"],
            token_type=data["token_type"],
            scope=data["scope"],
        )
        return self._token.access_token
    
    def make_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        self._check_env()
        headers = {"Authorization": f"Bearer {self._get_token()}", "accept": "application/json"}
        resp = requests.request(method, f"{self.base_url}/{endpoint}", headers=headers, **kwargs)
        try:
            resp.raise_for_status()
        except requests.exceptions.HTTPError as e:
            raise requests.exceptions.HTTPError(
                f"{e}\nResponse body: {resp.text}", response=resp
            ) from e
        return resp

    def get_extension(self, id: str):
        resp = self.make_request("GET", f"projects/extensions/{id}")
        return resp.json()
    
    def get_extension_releases(self, id: str):
        resp = self.make_request("GET", f"projects/extensions/{id}/releases")
        return resp.json()

    def post_extension_release(self, id: str, zip_file: Path, release_notes: Path | None = None) -> dict:
        files: list[tuple[str, tuple[str, Any, str]]] = [
            ("artifact", (zip_file.name, open(zip_file, "rb"), "application/x-zip-compressed")),
        ]
        if release_notes is not None:
            files.append(
                ("releaseNotes", (release_notes.name, open(release_notes, "rb"), "text/markdown")),
            )
        resp = self.make_request("POST", f"projects/extensions/{id}/releases", files=files)
        return resp.json()
"""Module containing the HashiCorp Vault source used throughout the confiq package."""

from __future__ import annotations

import importlib
import os
from typing import Any

from confiq.exceptions import SourceUnavailableError


_VAULT_TOKEN_ENV_VAR: str = "VAULT_TOKEN"


def _require(package: str, extra: str) -> None:
    try:
        importlib.import_module(package)
    except ImportError:
        raise ImportError(
            f"confiq[{extra}] extra is required. Install it with: pip install confiq[{extra}]"
        ) from None


class VaultSource:
    """Source that reads a KV v2 secret path from HashiCorp Vault as a config dict."""

    def __init__(
        self,
        addr: str,
        path: str,
        *,
        token: str | None = None,
        name: str = "vault",
    ) -> None:
        _require("hvac", "vault")
        self.name: str = name
        self._addr: str = addr
        self._path: str = path
        self._token: str | None = token if token is not None else os.environ.get(_VAULT_TOKEN_ENV_VAR)

    def fetch(self) -> dict[str, Any]:
        """Read the KV v2 secret at the configured path and return its data dict."""
        import hvac
        import hvac.exceptions

        client: Any = hvac.Client(url=self._addr, token=self._token)
        try:
            response: dict[str, Any] = client.secrets.kv.v2.read_secret_version(
                path=self._path
            )
        except hvac.exceptions.VaultError as exc:
            raise SourceUnavailableError(
                f"Vault request failed for path {self._path!r} at {self._addr!r}: {exc}"
            ) from exc

        return response["data"]["data"]

from __future__ import annotations

import os
from typing import Any

from confiq._registry import MissingDependencyError
from confiq.sources.base import PRIORITY_CLOUD
from confiq.sources.base import AbstractConfigSource


class VaultSource(AbstractConfigSource):
    """Reads a KV v2 secret from HashiCorp Vault.

    Authentication uses the provided `token`, falling back to the ``VAULT_TOKEN``
    environment variable. The secret's ``data.data`` dict is returned directly.
    """

    protocol = "vault"
    priority = PRIORITY_CLOUD

    def __init__(
        self,
        addr: str,
        path: str,
        *,
        token: str | None = None,
        mount_point: str = "secret",
        priority: int | None = None,
    ) -> None:
        super().__init__(priority=priority)
        self.addr = addr
        self.vault_path = path
        self.token = token
        self.mount_point = mount_point

    def load(self) -> dict[str, Any]:
        """Read the KV v2 secret and return its data dict."""
        try:
            import hvac
        except ImportError as exc:
            raise MissingDependencyError(
                "Install confiq[vault] to use HashiCorp Vault (requires hvac>=2.0)."
            ) from exc

        token: str | None = self.token or os.environ.get("VAULT_TOKEN")
        client = hvac.Client(url=self.addr, token=token)
        response = client.secrets.kv.v2.read_secret_version(
            path=self.vault_path,
            mount_point=self.mount_point,
        )
        return dict(response["data"]["data"])

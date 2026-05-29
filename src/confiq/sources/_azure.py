"""Module containing the Azure Key Vault source used throughout the confiq package."""

from __future__ import annotations

import importlib
import json
from typing import Any

from confiq.exceptions import SourceUnavailableError


def _require(package: str, extra: str) -> None:
    try:
        importlib.import_module(package)
    except ImportError:
        raise ImportError(
            f"confiq[{extra}] extra is required. Install it with: pip install confiq[{extra}]"
        ) from None


class AzureKeyVaultSource:
    """Source that reads all secrets from an Azure Key Vault instance as a config dict."""

    def __init__(
        self,
        vault_url: str,
        *,
        name: str = "azure_keyvault",
    ) -> None:
        _require("azure.identity", "azure")
        _require("azure.keyvault.secrets", "azure")
        self.name: str = name
        self._vault_url: str = vault_url

    def fetch(self) -> dict[str, Any]:
        """List and retrieve all secrets from the vault, returning a flat config dict.

        Each secret value is JSON-parsed if possible; kept as a raw string otherwise.
        """
        from azure.core.exceptions import AzureError
        from azure.identity import DefaultAzureCredential
        from azure.keyvault.secrets import SecretClient

        credential: Any = DefaultAzureCredential()
        client: Any = SecretClient(vault_url=self._vault_url, credential=credential)

        result: dict[str, Any] = {}
        try:
            for secret_properties in client.list_properties_of_secrets():
                secret_name: str = secret_properties.name
                secret: Any = client.get_secret(secret_name)
                raw_value: str = secret.value or ""
                try:
                    result[secret_name] = json.loads(raw_value)
                except (json.JSONDecodeError, ValueError):
                    result[secret_name] = raw_value
        except AzureError as exc:
            raise SourceUnavailableError(
                f"Azure Key Vault request failed for {self._vault_url!r}: {exc}"
            ) from exc

        return result

from __future__ import annotations

import json
from typing import Any

from confiq._registry import MissingDependencyError
from confiq.sources.base import PRIORITY_CLOUD
from confiq.sources.base import AbstractConfigSource


class AzureKeyVaultSource(AbstractConfigSource):
    """Reads a secret from Azure Key Vault and JSON-decodes it.

    Uses ``DefaultAzureCredential`` for authentication (environment variables,
    managed identity, Azure CLI, etc.). The secret value must be a JSON object.
    Plain-string secrets are wrapped as ``{"value": "<string>"}``.
    """

    protocol = "azure-kv"
    priority = PRIORITY_CLOUD

    def __init__(
        self,
        vault_url: str,
        secret_name: str,
        *,
        priority: int | None = None,
    ) -> None:
        super().__init__(priority=priority)
        self.vault_url = vault_url
        self.secret_name = secret_name

    def load(self) -> dict[str, Any]:
        """Fetch the Key Vault secret and return its value as a dict."""
        try:
            from azure.identity import DefaultAzureCredential
            from azure.keyvault.secrets import SecretClient
        except ImportError as exc:
            raise MissingDependencyError(
                "Install confiq[azure] to use Azure Key Vault."
            ) from exc

        credential = DefaultAzureCredential()
        client = SecretClient(vault_url=self.vault_url, credential=credential)
        secret = client.get_secret(self.secret_name)

        try:
            result = json.loads(secret.value or "")
            if isinstance(result, dict):
                return result
            return {"value": result}
        except (json.JSONDecodeError, TypeError):
            return {"value": secret.value}

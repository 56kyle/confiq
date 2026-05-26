from __future__ import annotations

from typing import Any

from confiq._registry import MissingDependencyError
from confiq.sources._coerce import _decode_json
from confiq.sources.base import PRIORITY_CLOUD
from confiq.sources.base import AbstractConfigSource


class GcpSecretManagerSource(AbstractConfigSource):
    """Reads a secret from Google Cloud Secret Manager and JSON-decodes it.

    The secret payload must be a JSON object. Plain-string secrets are wrapped as
    ``{"value": "<string>"}`` so confiq always receives a dict.
    """

    protocol = "gcp-secrets"
    priority = PRIORITY_CLOUD

    def __init__(
        self,
        project_id: str,
        secret_id: str,
        *,
        version: str = "latest",
        priority: int | None = None,
    ) -> None:
        super().__init__(priority=priority)
        self.project_id = project_id
        self.secret_id = secret_id
        self.version = version

    def load(self) -> dict[str, Any]:
        """Access the secret version and return its payload as a dict."""
        try:
            from google.cloud import secretmanager
        except ImportError as exc:
            raise MissingDependencyError(
                "Install confiq[gcp] to use GCP Secret Manager."
            ) from exc

        client = secretmanager.SecretManagerServiceClient()
        name: str = (
            f"projects/{self.project_id}"
            f"/secrets/{self.secret_id}"
            f"/versions/{self.version}"
        )
        response = client.access_secret_version(request={"name": name})
        payload = response.payload.data.decode("utf-8")
        return _decode_json(payload)

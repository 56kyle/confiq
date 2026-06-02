"""Module containing the GCP Secret Manager source used throughout the confiq cloud subpackage."""

from __future__ import annotations

import json
from typing import Any

from confiq.cloud._require import _require
from confiq.exceptions import SourceParseError
from confiq.exceptions import SourceUnavailableError


class GcpSecretManagerSource:
    """Source that reads a single GCP Secret Manager secret version as a config dict."""

    def __init__(
        self,
        project_id: str,
        secret_id: str,
        *,
        version: str = "latest",
        name: str = "gcp_secrets",
    ) -> None:
        _require("google.cloud.secretmanager", "gcp")
        self.name: str = name
        self._project_id: str = project_id
        self._secret_id: str = secret_id
        self._version: str = version

    def fetch(self) -> dict[str, Any]:
        """Fetch the secret version from GCP Secret Manager and return it as a parsed dict."""
        from google.api_core import exceptions as gcp_exceptions
        from google.cloud import secretmanager

        client: Any = secretmanager.SecretManagerServiceClient()
        secret_path: str = (
            f"projects/{self._project_id}/secrets/{self._secret_id}/versions/{self._version}"
        )
        try:
            response: Any = client.access_secret_version(request={"name": secret_path})
        except gcp_exceptions.GoogleAPICallError as exc:
            raise SourceUnavailableError(
                f"GCP Secret Manager request failed for {secret_path!r}: {exc}"
            ) from exc

        payload: str = response.payload.data.decode("utf-8")
        try:
            result: dict[str, Any] = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise SourceParseError(
                f"GCP secret {secret_path!r} is not valid JSON: {exc}"
            ) from exc

        return result

"""Config source that reads a secret from AWS Secrets Manager."""

from __future__ import annotations

import base64
import binascii
from typing import Any

from confiq._registry import MissingDependencyError
from confiq.sources._coerce import _decode_json
from confiq.sources.base import PRIORITY_CLOUD
from confiq.sources.base import AbstractConfigSource


class AwsSecretsManagerSource(AbstractConfigSource):
    """Reads a secret from AWS Secrets Manager and JSON-decodes it.

    The secret value must be a JSON object. Plain-string secrets are wrapped as
    ``{"value": "<string>"}`` so confiq always receives a dict.
    """

    protocol = "aws-secrets"
    priority = PRIORITY_CLOUD

    def __init__(
        self,
        secret_id: str,
        *,
        region: str | None = None,
        priority: int | None = None,
    ) -> None:
        super().__init__(priority=priority)
        self.secret_id = secret_id
        self.region = region

    def load(self) -> dict[str, Any]:
        """Fetch the secret value and return it as a dict."""
        try:
            import boto3
        except ImportError as exc:
            raise MissingDependencyError("Install confiq[aws] to use AWS Secrets Manager.") from exc

        client = boto3.client("secretsmanager", region_name=self.region)
        response = client.get_secret_value(SecretId=self.secret_id)

        secret_str: str | None = response.get("SecretString")
        if secret_str is not None:
            return _decode_json(secret_str)

        secret_binary: bytes | None = response.get("SecretBinary")
        if secret_binary is None:
            raise ValueError("Secret has neither SecretString nor SecretBinary")
        try:
            decoded: str = base64.b64decode(secret_binary).decode("utf-8")
        except (binascii.Error, UnicodeDecodeError) as exc:
            raise ValueError(
                f"Secret binary value could not be decoded as base64 UTF-8: {exc}"
            ) from exc
        return _decode_json(decoded)

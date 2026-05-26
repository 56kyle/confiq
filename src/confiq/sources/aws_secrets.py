from __future__ import annotations

import json
from typing import Any

from confiq._registry import MissingDependencyError
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

        secret_str = response.get("SecretString")
        if secret_str is not None:
            return _decode_json(secret_str)

        secret_binary = response.get("SecretBinary", b"")
        import base64
        return _decode_json(base64.b64decode(secret_binary).decode("utf-8"))


def _decode_json(text: str) -> dict[str, Any]:
    try:
        result = json.loads(text)
        if isinstance(result, dict):
            return result
        return {"value": result}
    except json.JSONDecodeError:
        return {"value": text}

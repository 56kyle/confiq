"""Module containing the AWS Secrets Manager source used throughout the confiq package."""

from __future__ import annotations

import importlib
import json
from typing import Any

from confiq.exceptions import SourceParseError
from confiq.exceptions import SourceUnavailableError


def _require(package: str, extra: str) -> None:
    try:
        importlib.import_module(package)
    except ImportError:
        raise ImportError(
            f"confiq[{extra}] extra is required. Install it with: pip install confiq[{extra}]"
        ) from None


class AwsSecretsManagerSource:
    """Source that reads a single secret from AWS Secrets Manager as a config dict."""

    def __init__(
        self,
        secret_name: str,
        *,
        region: str,
        name: str = "aws_secrets",
    ) -> None:
        _require("boto3", "aws")
        self.name: str = name
        self._secret_name: str = secret_name
        self._region: str = region

    def fetch(self) -> dict[str, Any]:
        """Fetch the secret from AWS Secrets Manager and return it as a parsed dict."""
        import boto3
        import botocore.exceptions

        client: Any = boto3.client("secretsmanager", region_name=self._region)
        try:
            response: dict[str, Any] = client.get_secret_value(SecretId=self._secret_name)
        except botocore.exceptions.ClientError as exc:
            raise SourceUnavailableError(
                f"AWS Secrets Manager request failed for secret {self._secret_name!r}: {exc}"
            ) from exc

        secret_string: str = response["SecretString"]
        try:
            result: dict[str, Any] = json.loads(secret_string)
        except json.JSONDecodeError as exc:
            raise SourceParseError(
                f"Secret {self._secret_name!r} is not valid JSON: {exc}"
            ) from exc

        return result

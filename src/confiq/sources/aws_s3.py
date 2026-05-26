from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from confiq._registry import MissingDependencyError
from confiq.sources.base import PRIORITY_CLOUD
from confiq.sources.base import AbstractConfigSource


class AwsS3Source(AbstractConfigSource):
    """Downloads a config file from AWS S3 and parses it.

    Format is inferred from the S3 key's extension, or overridden via `file_format`.
    Supports JSON natively; YAML and TOML require the respective confiq extras.
    """

    protocol = "aws-s3"
    priority = PRIORITY_CLOUD

    def __init__(
        self,
        bucket: str,
        key: str,
        *,
        region: str | None = None,
        file_format: str | None = None,
        priority: int | None = None,
    ) -> None:
        super().__init__(priority=priority)
        self.bucket = bucket
        self.key = key
        self.region = region
        self.file_format = file_format

    def load(self) -> dict[str, Any]:
        """Download the S3 object and return its contents as a dict."""
        try:
            import boto3
        except ImportError as exc:
            raise MissingDependencyError("Install confiq[aws] to use AWS S3.") from exc

        client = boto3.client("s3", region_name=self.region)
        response = client.get_object(Bucket=self.bucket, Key=self.key)
        raw_bytes: bytes = response["Body"].read()
        try:
            content: str = raw_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError(
                f"S3 object s3://{self.bucket}/{self.key} is not UTF-8: {exc}"
            ) from exc

        suffix: str = (self.file_format or Path(self.key).suffix).lower()
        if not suffix.startswith("."):
            suffix = "." + suffix

        return _parse(content, suffix)


def _parse(content: str, suffix: str) -> dict[str, Any]:
    if suffix == ".json":
        result: Any = json.loads(content)
        if not isinstance(result, dict):
            raise ValueError(
                f"Expected a mapping from {suffix} content, got {type(result).__name__}"
            )
        return result
    if suffix in (".yaml", ".yml"):
        try:
            import yaml
        except ImportError as exc:
            raise MissingDependencyError("Install confiq[yaml] for YAML support.") from exc
        yaml_result: Any = yaml.safe_load(content)
        if yaml_result is None:
            return {}
        if not isinstance(yaml_result, dict):
            raise ValueError(
                f"Expected a mapping from {suffix} content, got {type(yaml_result).__name__}"
            )
        return yaml_result
    if suffix == ".toml":
        try:
            try:
                import tomllib
            except ImportError:
                import tomli as tomllib  # type: ignore[no-redef]
        except ImportError as exc:
            raise MissingDependencyError("Install confiq[toml] for TOML support.") from exc
        toml_result: Any = tomllib.loads(content)
        if not isinstance(toml_result, dict):
            raise ValueError(
                f"Expected a mapping from {suffix} content, got {type(toml_result).__name__}"
            )
        return toml_result
    raise ValueError(
        f"Unsupported format {suffix!r} for S3 source. "
        f"Use file_format='json' / 'yaml' / 'toml' to override."
    )

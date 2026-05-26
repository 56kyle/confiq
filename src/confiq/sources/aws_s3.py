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
        content = response["Body"].read().decode("utf-8")

        suffix = (self.file_format or Path(self.key).suffix).lower()
        if not suffix.startswith("."):
            suffix = "." + suffix

        return _parse(content, suffix)


def _parse(content: str, suffix: str) -> dict[str, Any]:
    if suffix == ".json":
        return json.loads(content)
    if suffix in (".yaml", ".yml"):
        try:
            import yaml
        except ImportError as exc:
            raise MissingDependencyError("Install confiq[yaml] for YAML support.") from exc
        return yaml.safe_load(content) or {}
    if suffix == ".toml":
        try:
            try:
                import tomllib
            except ImportError:
                import tomli as tomllib  # type: ignore[no-redef]
        except ImportError as exc:
            raise MissingDependencyError("Install confiq[toml] for TOML support.") from exc
        return tomllib.loads(content)
    raise ValueError(
        f"Unsupported format {suffix!r} for S3 source. "
        f"Use file_format='json' / 'yaml' / 'toml' to override."
    )

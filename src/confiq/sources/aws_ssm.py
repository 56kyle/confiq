from __future__ import annotations

from typing import Any

from confiq._registry import MissingDependencyError
from confiq.sources._coerce import parse_env_value
from confiq.sources._coerce import set_nested_path
from confiq.sources.base import PRIORITY_CLOUD
from confiq.sources.base import AbstractConfigSource


class AwsSsmSource(AbstractConfigSource):
    """Reads parameters from AWS Systems Manager Parameter Store under a key path.

    All parameters at or below `path` are fetched (recursive by default). The
    path prefix is stripped and slashes become nested dict keys, so
    ``/myapp/database/host`` under path ``/myapp/`` becomes
    ``{"database": {"host": value}}``.
    SecureString parameters are decrypted automatically.
    """

    protocol = "aws-ssm"
    priority = PRIORITY_CLOUD

    def __init__(
        self,
        path: str,
        *,
        region: str | None = None,
        recursive: bool = True,
        priority: int | None = None,
    ) -> None:
        super().__init__(priority=priority)
        self.ssm_path = "/" + path.strip("/") + "/"
        self.region = region
        self.recursive = recursive

    def load(self) -> dict[str, Any]:
        """Fetch all SSM parameters under the configured path and return them as a nested dict."""
        try:
            import boto3
        except ImportError as exc:
            raise MissingDependencyError("Install confiq[aws] to use AWS SSM.") from exc

        client = boto3.client("ssm", region_name=self.region)
        paginator = client.get_paginator("get_parameters_by_path")
        out: dict[str, Any] = {}
        for page in paginator.paginate(
            Path=self.ssm_path,
            Recursive=self.recursive,
            WithDecryption=True,
        ):
            for param in page["Parameters"]:
                rel = param["Name"][len(self.ssm_path):]
                parts = [p for p in rel.split("/") if p]
                if not parts:
                    continue
                raw = param["Value"]
                if param["Type"] == "StringList":
                    value: Any = [parse_env_value(v.strip()) for v in raw.split(",")]
                else:
                    value = parse_env_value(raw)
                set_nested_path(out, parts, value)
        return out

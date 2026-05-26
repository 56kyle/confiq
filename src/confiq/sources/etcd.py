from __future__ import annotations

import json
from typing import Any

from confiq._registry import MissingDependencyError
from confiq.sources._coerce import parse_env_value
from confiq.sources._coerce import set_nested_path
from confiq.sources.base import PRIORITY_CLOUD
from confiq.sources.base import AbstractConfigSource


class EtcdSource(AbstractConfigSource):
    """Reads key-value pairs from an etcd3 prefix path.

    All keys under `path` are fetched. The prefix is stripped and slashes
    become nested dict keys. Values are JSON-decoded when possible, otherwise
    coerced via ``parse_env_value``.
    """

    protocol = "etcd"
    priority = PRIORITY_CLOUD

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 2379,
        path: str = "/",
        *,
        priority: int | None = None,
    ) -> None:
        super().__init__(priority=priority)
        self.host = host
        self.port = port
        self.etcd_path = "/" + path.strip("/") + "/"

    def load(self) -> dict[str, Any]:
        """Fetch all keys under the configured path and return them as a nested dict."""
        try:
            import etcd3
        except ImportError as exc:
            raise MissingDependencyError(
                "Install confiq[etcd] to use etcd (requires etcd3>=0.12)."
            ) from exc

        client = etcd3.client(host=self.host, port=self.port)
        out: dict[str, Any] = {}
        for value_bytes, metadata in client.get_prefix(self.etcd_path):
            key: str = metadata.key.decode("utf-8")
            rel: str = key[len(self.etcd_path):]
            parts: list[str] = [p for p in rel.split("/") if p]
            if not parts or value_bytes is None:
                continue
            value_str: str = value_bytes.decode("utf-8")
            try:
                value: Any = json.loads(value_str)
            except json.JSONDecodeError:
                value = parse_env_value(value_str)
            set_nested_path(out, parts, value)
        return out

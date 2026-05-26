from __future__ import annotations

import json
from typing import Any

from confiq._registry import MissingDependencyError
from confiq.sources._coerce import parse_env_value
from confiq.sources._coerce import set_nested_path
from confiq.sources.base import PRIORITY_CLOUD
from confiq.sources.base import AbstractConfigSource


class ConsulSource(AbstractConfigSource):
    """Reads key-value pairs from a Consul prefix path.

    All keys under `path` are fetched recursively. The prefix is stripped and
    slashes become nested dict keys, so ``myapp/database/host`` under
    ``myapp/`` becomes ``{"database": {"host": value}}``.
    Values are JSON-decoded when possible, otherwise coerced via ``parse_env_value``.
    """

    protocol = "consul"
    priority = PRIORITY_CLOUD

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8500,
        path: str = "",
        *,
        token: str | None = None,
        scheme: str = "http",
        priority: int | None = None,
    ) -> None:
        super().__init__(priority=priority)
        self.host = host
        self.port = port
        self.consul_path = path.strip("/") + "/" if path else ""
        self.token = token
        self.scheme = scheme

    def load(self) -> dict[str, Any]:
        """Fetch all keys under the configured path and return them as a nested dict."""
        try:
            import consul
        except ImportError as exc:
            raise MissingDependencyError(
                "Install confiq[consul] to use Consul."
            ) from exc

        client = consul.Consul(
            host=self.host, port=self.port, token=self.token, scheme=self.scheme
        )
        _, pairs = client.kv.get(self.consul_path, recurse=True)

        out: dict[str, Any] = {}
        if not pairs:
            return out
        for pair in pairs:
            rel = pair["Key"][len(self.consul_path):]
            parts = [p for p in rel.split("/") if p]
            if not parts or pair["Value"] is None:
                continue
            value_str = pair["Value"].decode("utf-8")
            try:
                value: Any = json.loads(value_str)
            except json.JSONDecodeError:
                value = parse_env_value(value_str)
            set_nested_path(out, parts, value)
        return out

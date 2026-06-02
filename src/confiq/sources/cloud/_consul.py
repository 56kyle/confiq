"""Module containing the Consul KV source used throughout the confiq cloud subpackage."""

from __future__ import annotations

import base64
import json
from typing import Any

from confiq.exceptions import SourceUnavailableError
from confiq.sources.cloud._require import _require


_DEFAULT_HOST: str = "127.0.0.1"
_DEFAULT_PORT: int = 8500


def _set_nested(d: dict[str, Any], parts: list[str], value: Any) -> None:
    for part in parts[:-1]:
        if part not in d or not isinstance(d[part], dict):
            d[part] = {}
        d = d[part]
    d[parts[-1]] = value


class ConsulSource:
    """Source that reads all keys under a Consul KV prefix as a nested config dict."""

    def __init__(
        self,
        host: str = _DEFAULT_HOST,
        prefix: str = "",
        *,
        port: int = _DEFAULT_PORT,
        name: str = "consul",
    ) -> None:
        _require("consul", "consul")
        self.name: str = name
        self._host: str = host
        self._prefix: str = prefix
        self._port: int = port

    def fetch(self) -> dict[str, Any]:
        """Fetch all keys under the configured prefix from Consul KV.

        Keys are split on '/' to produce a nested dict. Values are JSON-parsed
        where possible; raw UTF-8 strings otherwise.
        """
        import consul

        client: Any = consul.Consul(host=self._host, port=self._port)
        try:
            items: list[dict[str, Any]] | None
            _index, items = client.kv.get(self._prefix, recurse=True)
        except Exception as exc:
            raise SourceUnavailableError(
                f"Consul KV request failed for prefix {self._prefix!r} "
                f"at {self._host}:{self._port}: {exc}"
            ) from exc

        result: dict[str, Any] = {}
        if not items:
            return result

        prefix_strip: str = self._prefix.rstrip("/") + "/" if self._prefix else ""

        item: dict[str, Any]
        for item in items:
            raw_key: str = item["Key"]
            key: str = raw_key[len(prefix_strip):] if prefix_strip and raw_key.startswith(prefix_strip) else raw_key
            if not key:
                continue

            encoded_value: str | None = item.get("Value")
            if encoded_value is None:
                continue

            decoded_bytes: bytes = base64.b64decode(encoded_value)
            raw_str: str = decoded_bytes.decode("utf-8")
            try:
                value: Any = json.loads(raw_str)
            except (json.JSONDecodeError, ValueError):
                value = raw_str

            parts: list[str] = [p for p in key.split("/") if p]
            if parts:
                _set_nested(result, parts, value)

        return result

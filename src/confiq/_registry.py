"""Source-protocol registry and lazy-import factory, mirroring the fsspec pattern."""
from __future__ import annotations

import importlib
import types
import warnings
from importlib.metadata import entry_points
from typing import Any


_registry: dict[str, type] = {}
registry = types.MappingProxyType(_registry)

known_implementations: dict[str, dict[str, str]] = {
    "file": {"class": "confiq.sources.file.FileSource"},
    "env": {"class": "confiq.sources.env.EnvSource"},
    "argparse": {"class": "confiq.sources.argparse_source.ArgparseSource"},
    "dict": {"class": "confiq.sources.dict_source.DictSource"},
    "defaults": {"class": "confiq.sources.defaults.DefaultsSource"},
    "click": {
        "class": "confiq.sources.click_source.ClickSource",
        "err": "Install confiq[click] to use Click integration.",
    },
    "typer": {
        "class": "confiq.sources.typer_source.TyperSource",
        "err": "Install confiq[typer] to use Typer integration.",
    },
    "aws-ssm": {
        "class": "confiq.sources.aws_ssm.AwsSsmSource",
        "err": "Install confiq[aws] to use AWS SSM.",
    },
    "aws-secrets": {
        "class": "confiq.sources.aws_secrets.AwsSecretsManagerSource",
        "err": "Install confiq[aws] to use AWS Secrets Manager.",
    },
    "aws-s3": {
        "class": "confiq.sources.aws_s3.AwsS3Source",
        "err": "Install confiq[aws] to use AWS S3.",
    },
    "gcp-secrets": {
        "class": "confiq.sources.gcp_secrets.GcpSecretManagerSource",
        "err": "Install confiq[gcp].",
    },
    "azure-kv": {
        "class": "confiq.sources.azure_keyvault.AzureKeyVaultSource",
        "err": "Install confiq[azure].",
    },
    "vault": {
        "class": "confiq.sources.vault.VaultSource",
        "err": "Install confiq[vault] (uses hvac).",
    },
    "consul": {
        "class": "confiq.sources.consul.ConsulSource",
        "err": "Install confiq[consul].",
    },
    "etcd": {
        "class": "confiq.sources.etcd.EtcdSource",
        "err": "Install confiq[etcd].",
    },
}


class MissingDependencyError(ImportError):
    """Raised when a known protocol's optional extra dependency is not installed."""


def register_implementation(
    name: str,
    cls: type | str,
    *,
    clobber: bool = False,
    errtxt: str | None = None,
) -> None:
    """Register a protocol name to a class or dotted import string. Raises `ValueError` on conflict with a different class unless `clobber=True`; re-registering the identical class is silently idempotent."""
    if name in _registry and not clobber:
        if _registry[name] is not cls:
            raise ValueError(f"{name!r} already registered")
        return
    if isinstance(cls, str):
        known_implementations[name] = {
            "class": cls,
            **({"err": errtxt} if errtxt else {}),
        }
    else:
        _registry[name] = cls


def get_source_class(protocol: str) -> type:
    """Resolve a protocol string to its class, lazily importing from `known_implementations` on first access. Raises `KeyError` for unknown protocols; raises `MissingDependencyError` for known but uninstalled extras."""
    if protocol in _registry:
        return _registry[protocol]
    if protocol in known_implementations:
        spec = known_implementations[protocol]
        try:
            mod_path, _, cls_name = spec["class"].rpartition(".")
            cls = getattr(importlib.import_module(mod_path), cls_name)
        except ImportError as e:
            raise MissingDependencyError(spec.get("err") or str(e)) from e
        _registry[protocol] = cls
        return cls
    raise KeyError(f"Unknown config source protocol: {protocol!r}")


def _discover_entry_points() -> None:
    """Auto-register third-party source classes (group confiq.sources)."""
    try:
        eps = entry_points(group="confiq.sources")
    except TypeError:
        eps = entry_points().get("confiq.sources", [])  # type: ignore[union-attr]
    for ep in eps:
        try:
            # Entry-point values use "module:Class" format; convert to "module.Class"
            # for compatibility with get_source_class's rpartition(".") logic.
            dotted = ep.value.replace(":", ".")
            register_implementation(ep.name, dotted)
        except Exception as e:
            warnings.warn(f"Failed to register source {ep.name!r}: {e}", stacklevel=2)


_discover_entry_points()


def create_source(protocol: str, **opts: Any) -> Any:
    """Top-level factory, mirrors fsspec.filesystem(protocol, **opts)."""
    return get_source_class(protocol)(**opts)

"""Subpackage containing cloud secret manager source implementations used throughout the confiq package."""

from __future__ import annotations

from confiq.sources.cloud._aws import AwsSecretsManagerSource
from confiq.sources.cloud._azure import AzureKeyVaultSource
from confiq.sources.cloud._consul import ConsulSource
from confiq.sources.cloud._gcp import GcpSecretManagerSource
from confiq.sources.cloud._vault import VaultSource


__all__ = [
    "AwsSecretsManagerSource",
    "AzureKeyVaultSource",
    "ConsulSource",
    "GcpSecretManagerSource",
    "VaultSource",
]

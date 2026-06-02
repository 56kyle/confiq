"""Subpackage containing cloud secret manager source implementations used throughout the confiq package."""

from __future__ import annotations

from confiq.cloud._aws import AwsSecretsManagerSource
from confiq.cloud._azure import AzureKeyVaultSource
from confiq.cloud._consul import ConsulSource
from confiq.cloud._gcp import GcpSecretManagerSource
from confiq.cloud._vault import VaultSource

__all__ = [
    "AwsSecretsManagerSource",
    "AzureKeyVaultSource",
    "ConsulSource",
    "GcpSecretManagerSource",
    "VaultSource",
]

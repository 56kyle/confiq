"""Tests for cloud config sources, using sys.modules patching for optional deps."""
from __future__ import annotations

import json
import sys
from unittest.mock import MagicMock

import pytest

from confiq._registry import MissingDependencyError


# ─── helpers ─────────────────────────────────────────────────────────────────


def _mock_boto3(client_mock: MagicMock) -> MagicMock:
    """Return a boto3 module mock whose .client() returns client_mock."""
    mod = MagicMock()
    mod.client.return_value = client_mock
    return mod


# ─── AWS SSM ─────────────────────────────────────────────────────────────────


class TestAwsSsmSource:
    def test_missing_boto3_raises(self, monkeypatch):
        from confiq.sources.aws_ssm import AwsSsmSource

        monkeypatch.setitem(sys.modules, "boto3", None)
        src = AwsSsmSource("/myapp")
        with pytest.raises(MissingDependencyError, match="confiq\\[aws\\]"):
            src.load()

    def test_load_simple_string(self, monkeypatch):
        from confiq.sources.aws_ssm import AwsSsmSource

        page = {
            "Parameters": [
                {"Name": "/myapp/database/host", "Value": "pg.local", "Type": "String"},
            ]
        }
        paginator = MagicMock()
        paginator.paginate.return_value = [page]
        client = MagicMock()
        client.get_paginator.return_value = paginator

        monkeypatch.setitem(sys.modules, "boto3", _mock_boto3(client))
        result = AwsSsmSource("/myapp").load()

        assert result == {"database": {"host": "pg.local"}}

    def test_load_string_list(self, monkeypatch):
        from confiq.sources.aws_ssm import AwsSsmSource

        page = {
            "Parameters": [
                {"Name": "/myapp/tags", "Value": "a,b,c", "Type": "StringList"},
            ]
        }
        paginator = MagicMock()
        paginator.paginate.return_value = [page]
        client = MagicMock()
        client.get_paginator.return_value = paginator

        monkeypatch.setitem(sys.modules, "boto3", _mock_boto3(client))
        result = AwsSsmSource("/myapp").load()

        assert result["tags"] == ["a", "b", "c"]

    def test_coerces_int(self, monkeypatch):
        from confiq.sources.aws_ssm import AwsSsmSource

        page = {
            "Parameters": [
                {"Name": "/myapp/port", "Value": "5432", "Type": "String"},
            ]
        }
        paginator = MagicMock()
        paginator.paginate.return_value = [page]
        client = MagicMock()
        client.get_paginator.return_value = paginator

        monkeypatch.setitem(sys.modules, "boto3", _mock_boto3(client))
        result = AwsSsmSource("/myapp").load()

        assert result["port"] == 5432

    def test_priority_is_cloud(self):
        from confiq.sources.aws_ssm import AwsSsmSource
        from confiq.sources.base import PRIORITY_CLOUD

        assert AwsSsmSource("/p").priority == PRIORITY_CLOUD

    def test_protocol(self):
        from confiq.sources.aws_ssm import AwsSsmSource

        assert AwsSsmSource.protocol == "aws-ssm"


# ─── AWS Secrets Manager ─────────────────────────────────────────────────────


class TestAwsSecretsManagerSource:
    def test_missing_boto3_raises(self, monkeypatch):
        from confiq.sources.aws_secrets import AwsSecretsManagerSource

        monkeypatch.setitem(sys.modules, "boto3", None)
        with pytest.raises(MissingDependencyError, match="confiq\\[aws\\]"):
            AwsSecretsManagerSource("my-secret").load()

    def test_load_json_secret(self, monkeypatch):
        from confiq.sources.aws_secrets import AwsSecretsManagerSource

        client = MagicMock()
        client.get_secret_value.return_value = {
            "SecretString": json.dumps({"db_password": "hunter2"})
        }
        monkeypatch.setitem(sys.modules, "boto3", _mock_boto3(client))
        result = AwsSecretsManagerSource("my-secret").load()

        assert result == {"db_password": "hunter2"}

    def test_plain_string_wrapped(self, monkeypatch):
        from confiq.sources.aws_secrets import AwsSecretsManagerSource

        client = MagicMock()
        client.get_secret_value.return_value = {"SecretString": "plain-text-secret"}
        monkeypatch.setitem(sys.modules, "boto3", _mock_boto3(client))
        result = AwsSecretsManagerSource("my-secret").load()

        assert result == {"value": "plain-text-secret"}

    def test_protocol(self):
        from confiq.sources.aws_secrets import AwsSecretsManagerSource

        assert AwsSecretsManagerSource.protocol == "aws-secrets"


# ─── AWS S3 ──────────────────────────────────────────────────────────────────


class TestAwsS3Source:
    def test_missing_boto3_raises(self, monkeypatch):
        from confiq.sources.aws_s3 import AwsS3Source

        monkeypatch.setitem(sys.modules, "boto3", None)
        with pytest.raises(MissingDependencyError, match="confiq\\[aws\\]"):
            AwsS3Source("my-bucket", "config.json").load()

    def test_load_json(self, monkeypatch):
        from confiq.sources.aws_s3 import AwsS3Source

        body = MagicMock()
        body.read.return_value = json.dumps({"key": "val"}).encode()
        client = MagicMock()
        client.get_object.return_value = {"Body": body}

        monkeypatch.setitem(sys.modules, "boto3", _mock_boto3(client))
        result = AwsS3Source("my-bucket", "config.json").load()

        assert result == {"key": "val"}

    def test_unsupported_format_raises(self, monkeypatch):
        from confiq.sources.aws_s3 import AwsS3Source

        body = MagicMock()
        body.read.return_value = b"key=value"
        client = MagicMock()
        client.get_object.return_value = {"Body": body}

        monkeypatch.setitem(sys.modules, "boto3", _mock_boto3(client))
        with pytest.raises(ValueError, match="Unsupported format"):
            AwsS3Source("bucket", "config.ini").load()

    def test_protocol(self):
        from confiq.sources.aws_s3 import AwsS3Source

        assert AwsS3Source.protocol == "aws-s3"


# ─── GCP Secret Manager ──────────────────────────────────────────────────────


class TestGcpSecretManagerSource:
    def _patch_gcp(self, monkeypatch, client_instance: MagicMock) -> None:
        """Wire sys.modules so 'from google.cloud import secretmanager' returns our mock."""
        mock_sm = MagicMock()
        mock_sm.SecretManagerServiceClient.return_value = client_instance
        mock_google_cloud = MagicMock()
        mock_google_cloud.secretmanager = mock_sm
        mock_google = MagicMock()
        mock_google.cloud = mock_google_cloud

        monkeypatch.setitem(sys.modules, "google", mock_google)
        monkeypatch.setitem(sys.modules, "google.cloud", mock_google_cloud)
        monkeypatch.setitem(sys.modules, "google.cloud.secretmanager", mock_sm)

    def test_missing_library_raises(self, monkeypatch):
        from confiq.sources.gcp_secrets import GcpSecretManagerSource

        monkeypatch.setitem(sys.modules, "google", None)
        monkeypatch.setitem(sys.modules, "google.cloud", None)
        monkeypatch.setitem(sys.modules, "google.cloud.secretmanager", None)
        with pytest.raises((MissingDependencyError, ImportError)):
            GcpSecretManagerSource("proj", "my-secret").load()

    def test_load_json_secret(self, monkeypatch):
        from confiq.sources.gcp_secrets import GcpSecretManagerSource

        response = MagicMock()
        response.payload.data = json.dumps({"db": "pg"}).encode("utf-8")
        client_instance = MagicMock()
        client_instance.access_secret_version.return_value = response

        self._patch_gcp(monkeypatch, client_instance)
        result = GcpSecretManagerSource("proj", "my-secret").load()

        assert result == {"db": "pg"}

    def test_protocol(self):
        from confiq.sources.gcp_secrets import GcpSecretManagerSource

        assert GcpSecretManagerSource.protocol == "gcp-secrets"


# ─── Azure Key Vault ─────────────────────────────────────────────────────────


class TestAzureKeyVaultSource:
    def _patch_azure(self, monkeypatch, secret_value: str) -> None:
        secret = MagicMock()
        secret.value = secret_value
        client_instance = MagicMock()
        client_instance.get_secret.return_value = secret
        client_cls = MagicMock(return_value=client_instance)
        cred_cls = MagicMock(return_value=MagicMock())

        mock_identity = MagicMock()
        mock_identity.DefaultAzureCredential = cred_cls
        mock_kv_secrets = MagicMock()
        mock_kv_secrets.SecretClient = client_cls
        mock_azure = MagicMock()
        mock_azure_kv = MagicMock()

        monkeypatch.setitem(sys.modules, "azure", mock_azure)
        monkeypatch.setitem(sys.modules, "azure.identity", mock_identity)
        monkeypatch.setitem(sys.modules, "azure.keyvault", mock_azure_kv)
        monkeypatch.setitem(sys.modules, "azure.keyvault.secrets", mock_kv_secrets)

    def test_missing_library_raises(self, monkeypatch):
        from confiq.sources.azure_keyvault import AzureKeyVaultSource

        monkeypatch.setitem(sys.modules, "azure", None)
        monkeypatch.setitem(sys.modules, "azure.identity", None)
        monkeypatch.setitem(sys.modules, "azure.keyvault", None)
        monkeypatch.setitem(sys.modules, "azure.keyvault.secrets", None)
        with pytest.raises((MissingDependencyError, ImportError)):
            AzureKeyVaultSource("https://vault.azure.net/", "my-secret").load()

    def test_load_json_secret(self, monkeypatch):
        from confiq.sources.azure_keyvault import AzureKeyVaultSource

        self._patch_azure(monkeypatch, json.dumps({"api_key": "abc123"}))
        result = AzureKeyVaultSource("https://vault.azure.net/", "my-secret").load()

        assert result == {"api_key": "abc123"}

    def test_plain_string_wrapped(self, monkeypatch):
        from confiq.sources.azure_keyvault import AzureKeyVaultSource

        self._patch_azure(monkeypatch, "plain-token")
        result = AzureKeyVaultSource("https://vault.azure.net/", "my-secret").load()

        assert result == {"value": "plain-token"}

    def test_protocol(self):
        from confiq.sources.azure_keyvault import AzureKeyVaultSource

        assert AzureKeyVaultSource.protocol == "azure-kv"


# ─── HashiCorp Vault ─────────────────────────────────────────────────────────


class TestVaultSource:
    def test_missing_hvac_raises(self, monkeypatch):
        from confiq.sources.vault import VaultSource

        monkeypatch.setitem(sys.modules, "hvac", None)
        with pytest.raises(MissingDependencyError, match="confiq\\[vault\\]"):
            VaultSource("http://vault:8200", "myapp/config").load()

    def test_load_secret(self, monkeypatch):
        from confiq.sources.vault import VaultSource

        client_instance = MagicMock()
        client_instance.secrets.kv.v2.read_secret_version.return_value = {
            "data": {"data": {"password": "s3cr3t"}}
        }
        hvac_mod = MagicMock()
        hvac_mod.Client.return_value = client_instance
        monkeypatch.setitem(sys.modules, "hvac", hvac_mod)

        result = VaultSource("http://vault:8200", "myapp/config").load()

        assert result == {"password": "s3cr3t"}

    def test_falls_back_to_env_token(self, monkeypatch):
        from confiq.sources.vault import VaultSource

        monkeypatch.setenv("VAULT_TOKEN", "env-token")
        client_instance = MagicMock()
        client_instance.secrets.kv.v2.read_secret_version.return_value = {
            "data": {"data": {}}
        }
        hvac_mod = MagicMock()
        hvac_mod.Client.return_value = client_instance
        monkeypatch.setitem(sys.modules, "hvac", hvac_mod)

        VaultSource("http://vault:8200", "path").load()

        hvac_mod.Client.assert_called_once_with(url="http://vault:8200", token="env-token")

    def test_protocol(self):
        from confiq.sources.vault import VaultSource

        assert VaultSource.protocol == "vault"


# ─── Consul ──────────────────────────────────────────────────────────────────


class TestConsulSource:
    def test_missing_consul_raises(self, monkeypatch):
        from confiq.sources.consul import ConsulSource

        monkeypatch.setitem(sys.modules, "consul", None)
        with pytest.raises(MissingDependencyError, match="confiq\\[consul\\]"):
            ConsulSource().load()

    def test_load_nested_keys(self, monkeypatch):
        from confiq.sources.consul import ConsulSource

        pairs = [
            {"Key": "myapp/database/host", "Value": b"pg.local"},
            {"Key": "myapp/port", "Value": b"5432"},
        ]
        consul_instance = MagicMock()
        consul_instance.kv.get.return_value = (None, pairs)
        consul_mod = MagicMock()
        consul_mod.Consul.return_value = consul_instance
        monkeypatch.setitem(sys.modules, "consul", consul_mod)

        result = ConsulSource(path="myapp").load()

        assert result["database"]["host"] == "pg.local"
        assert result["port"] == 5432

    def test_empty_response_returns_empty_dict(self, monkeypatch):
        from confiq.sources.consul import ConsulSource

        consul_instance = MagicMock()
        consul_instance.kv.get.return_value = (None, None)
        consul_mod = MagicMock()
        consul_mod.Consul.return_value = consul_instance
        monkeypatch.setitem(sys.modules, "consul", consul_mod)

        result = ConsulSource(path="myapp").load()

        assert result == {}

    def test_protocol(self):
        from confiq.sources.consul import ConsulSource

        assert ConsulSource.protocol == "consul"

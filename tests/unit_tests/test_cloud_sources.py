from __future__ import annotations

import base64
import json
from typing import Any
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest


class TestAwsSecretsManagerSource:
    def test_fetch_returns_parsed_dict(self) -> None:
        mock_boto3 = MagicMock()
        mock_client = MagicMock()
        mock_client.get_secret_value.return_value = {
            "SecretString": json.dumps({"db_password": "secret123"})
        }
        mock_boto3.client.return_value = mock_client

        mock_botocore = MagicMock()
        mock_botocore.exceptions.ClientError = Exception

        with patch.dict("sys.modules", {"boto3": mock_boto3, "botocore": mock_botocore, "botocore.exceptions": mock_botocore.exceptions}):
            from confiq.sources._aws import AwsSecretsManagerSource
            src = AwsSecretsManagerSource("my-secret", region="us-east-1")
            result = src.fetch()

        assert result == {"db_password": "secret123"}

    def test_default_name(self) -> None:
        mock_boto3 = MagicMock()
        mock_botocore = MagicMock()
        mock_botocore.exceptions.ClientError = Exception

        with patch.dict("sys.modules", {"boto3": mock_boto3, "botocore": mock_botocore, "botocore.exceptions": mock_botocore.exceptions}):
            from confiq.sources._aws import AwsSecretsManagerSource
            src = AwsSecretsManagerSource("s", region="us-east-1")

        assert src.name == "aws_secrets"

    def test_missing_dependency_raises_import_error(self) -> None:
        with patch.dict("sys.modules", {"boto3": None}), pytest.raises(ImportError, match="confiq\\[aws\\]"):
            from confiq.sources._aws import AwsSecretsManagerSource
            AwsSecretsManagerSource("x", region="us-east-1")


class TestGcpSecretManagerSource:
    def test_fetch_returns_parsed_dict(self) -> None:
        mock_secretmanager = MagicMock()
        mock_client_instance = MagicMock()
        mock_response = MagicMock()
        mock_response.payload.data = json.dumps({"api_key": "gcp-key"}).encode("utf-8")
        mock_client_instance.access_secret_version.return_value = mock_response
        mock_secretmanager.SecretManagerServiceClient.return_value = mock_client_instance

        mock_gcp_exceptions = MagicMock()
        mock_gcp_exceptions.GoogleAPICallError = Exception

        mock_google_cloud = MagicMock()
        mock_google_cloud.secretmanager = mock_secretmanager
        mock_google = MagicMock()
        mock_google.cloud = mock_google_cloud
        mock_google_api_core = MagicMock()
        mock_google_api_core.exceptions = mock_gcp_exceptions

        with patch.dict("sys.modules", {
            "google": mock_google,
            "google.cloud": mock_google_cloud,
            "google.cloud.secretmanager": mock_secretmanager,
            "google.api_core": mock_google_api_core,
            "google.api_core.exceptions": mock_gcp_exceptions,
        }):
            from confiq.sources._gcp import GcpSecretManagerSource
            src = GcpSecretManagerSource("my-project", "my-secret")
            result = src.fetch()

        assert result == {"api_key": "gcp-key"}

    def test_default_name(self) -> None:
        mock_secretmanager = MagicMock()
        mock_google = MagicMock()
        mock_google_api_core = MagicMock()

        with patch.dict("sys.modules", {
            "google": mock_google,
            "google.cloud": MagicMock(),
            "google.cloud.secretmanager": mock_secretmanager,
            "google.api_core": mock_google_api_core,
            "google.api_core.exceptions": MagicMock(),
        }):
            from confiq.sources._gcp import GcpSecretManagerSource
            src = GcpSecretManagerSource("proj", "secret")

        assert src.name == "gcp_secrets"

    def test_missing_dependency_raises_import_error(self) -> None:
        with patch.dict("sys.modules", {"google.cloud.secretmanager": None}):
            with pytest.raises(ImportError, match="confiq\\[gcp\\]"):
                from confiq.sources._gcp import GcpSecretManagerSource
                GcpSecretManagerSource("proj", "secret")


class TestAzureKeyVaultSource:
    def test_fetch_returns_dict(self) -> None:
        mock_secret_props = MagicMock()
        mock_secret_props.name = "my-secret"
        mock_secret = MagicMock()
        mock_secret.value = json.dumps({"token": "azure-token"})

        mock_client_instance = MagicMock()
        mock_client_instance.list_properties_of_secrets.return_value = [mock_secret_props]
        mock_client_instance.get_secret.return_value = mock_secret

        mock_azure_identity = MagicMock()
        mock_azure_keyvault_secrets = MagicMock()
        mock_azure_keyvault_secrets.SecretClient.return_value = mock_client_instance
        mock_azure_core = MagicMock()
        mock_azure_core.exceptions.AzureError = Exception

        with patch.dict("sys.modules", {
            "azure": MagicMock(),
            "azure.identity": mock_azure_identity,
            "azure.keyvault": MagicMock(),
            "azure.keyvault.secrets": mock_azure_keyvault_secrets,
            "azure.core": mock_azure_core,
            "azure.core.exceptions": mock_azure_core.exceptions,
        }):
            from confiq.sources._azure import AzureKeyVaultSource
            src = AzureKeyVaultSource("https://myvault.vault.azure.net/")
            result = src.fetch()

        assert result["my-secret"] == {"token": "azure-token"}

    def test_default_name(self) -> None:
        mock_azure_identity = MagicMock()
        mock_azure_keyvault_secrets = MagicMock()

        with patch.dict("sys.modules", {
            "azure": MagicMock(),
            "azure.identity": mock_azure_identity,
            "azure.keyvault": MagicMock(),
            "azure.keyvault.secrets": mock_azure_keyvault_secrets,
            "azure.core": MagicMock(),
            "azure.core.exceptions": MagicMock(),
        }):
            from confiq.sources._azure import AzureKeyVaultSource
            src = AzureKeyVaultSource("https://vault.example.com/")

        assert src.name == "azure_keyvault"

    def test_missing_dependency_raises_import_error(self) -> None:
        with patch.dict("sys.modules", {"azure.identity": None}):
            with pytest.raises(ImportError, match="confiq\\[azure\\]"):
                from confiq.sources._azure import AzureKeyVaultSource
                AzureKeyVaultSource("https://vault.example.com/")


class TestVaultSource:
    def test_fetch_returns_kv_data(self) -> None:
        mock_hvac = MagicMock()
        mock_client_instance = MagicMock()
        mock_client_instance.secrets.kv.v2.read_secret_version.return_value = {
            "data": {"data": {"db_pass": "vault-secret"}}
        }
        mock_hvac.Client.return_value = mock_client_instance
        mock_hvac.exceptions.VaultError = Exception

        with patch.dict("sys.modules", {"hvac": mock_hvac, "hvac.exceptions": mock_hvac.exceptions}):
            from confiq.sources._vault import VaultSource
            src = VaultSource("http://vault:8200", "secret/myapp")
            result = src.fetch()

        assert result == {"db_pass": "vault-secret"}

    def test_default_name(self) -> None:
        mock_hvac = MagicMock()
        mock_hvac.exceptions.VaultError = Exception

        with patch.dict("sys.modules", {"hvac": mock_hvac, "hvac.exceptions": mock_hvac.exceptions}):
            from confiq.sources._vault import VaultSource
            src = VaultSource("http://vault:8200", "secret/myapp")

        assert src.name == "vault"

    def test_missing_dependency_raises_import_error(self) -> None:
        with patch.dict("sys.modules", {"hvac": None}), pytest.raises(ImportError, match="confiq\\[vault\\]"):
            from confiq.sources._vault import VaultSource
            VaultSource("http://vault:8200", "secret/myapp")


class TestConsulSource:
    def _make_consul_item(self, key: str, value: Any) -> dict[str, Any]:
        encoded = base64.b64encode(json.dumps(value).encode()).decode()
        return {"Key": key, "Value": encoded}

    def test_fetch_returns_nested_dict(self) -> None:
        item = self._make_consul_item("app/database/host", "pg")
        mock_consul = MagicMock()
        mock_client_instance = MagicMock()
        mock_client_instance.kv.get.return_value = ("index", [item])
        mock_consul.Consul.return_value = mock_client_instance

        with patch.dict("sys.modules", {"consul": mock_consul}):
            from confiq.sources._consul import ConsulSource
            src = ConsulSource(prefix="app/")
            result = src.fetch()

        assert result["database"]["host"] == "pg"

    def test_default_name(self) -> None:
        mock_consul = MagicMock()

        with patch.dict("sys.modules", {"consul": mock_consul}):
            from confiq.sources._consul import ConsulSource
            src = ConsulSource()

        assert src.name == "consul"

    def test_missing_dependency_raises_import_error(self) -> None:
        with patch.dict("sys.modules", {"consul": None}):
            with pytest.raises(ImportError, match="confiq\\[consul\\]"):
                from confiq.sources._consul import ConsulSource
                ConsulSource()

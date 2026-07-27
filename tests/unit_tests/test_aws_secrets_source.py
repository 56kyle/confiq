"""Unit tests pinning the Stage 10a AWS Secrets Manager source (`confiq.source._aws`)."""

from __future__ import annotations

import json
import sys
from typing import TYPE_CHECKING
from typing import Any

import pytest

from confiq.exceptions import SourceError
from confiq.exceptions import SourceNotFoundError


pytest.importorskip("boto3")
pytest.importorskip("moto")

import boto3  # pyright: ignore[reportMissingTypeStubs]
import boto3.session  # pyright: ignore[reportMissingTypeStubs]
from moto import mock_aws

from confiq.source._aws import AwsSecretsManagerSource


if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture(autouse=True)
def _aws_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SECURITY_TOKEN", "AWS_SESSION_TOKEN"):
        monkeypatch.setenv(var, "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")


@pytest.fixture
def secrets_client() -> Iterator[Any]:  # pyright: ignore[reportExplicitAny, reportAny]
    with mock_aws():
        yield boto3.client("secretsmanager", region_name="us-east-1")  # pyright: ignore[reportAny]


def test_aws_secrets_manager_source_fetch_with_json_secret_returns_nested_mapping(secrets_client: Any) -> None:  # pyright: ignore[reportExplicitAny, reportAny]
    secrets_client.create_secret(  # pyright: ignore[reportAny]
        Name="app/config",
        SecretString=json.dumps({"database": {"host": "h", "port": 5432}}),
    )

    assert AwsSecretsManagerSource("app/config").fetch() == {"database": {"host": "h", "port": 5432}}


def test_aws_secrets_manager_source_fetch_with_non_mapping_secret_raises_source_error(secrets_client: Any) -> None:  # pyright: ignore[reportExplicitAny, reportAny]
    secrets_client.create_secret(Name="scalar", SecretString="42")  # pyright: ignore[reportAny]

    with pytest.raises(SourceError) as excinfo:
        AwsSecretsManagerSource("scalar").fetch()

    assert "aws-secrets:scalar" in str(excinfo.value)


def test_aws_secrets_manager_source_fetch_with_malformed_json_raises_source_error(secrets_client: Any) -> None:  # pyright: ignore[reportExplicitAny, reportAny]
    secrets_client.create_secret(Name="broken", SecretString="{not json")  # pyright: ignore[reportAny]

    with pytest.raises(SourceError) as excinfo:
        AwsSecretsManagerSource("broken").fetch()

    assert "aws-secrets:broken" in str(excinfo.value)


@pytest.mark.usefixtures("secrets_client")
def test_aws_secrets_manager_source_fetch_with_missing_required_secret_raises_source_not_found() -> None:
    with pytest.raises(SourceNotFoundError) as excinfo:
        AwsSecretsManagerSource("absent").fetch()

    assert isinstance(excinfo.value, SourceError)
    assert "aws-secrets:absent" in str(excinfo.value)


@pytest.mark.usefixtures("secrets_client")
def test_aws_secrets_manager_source_fetch_with_missing_optional_secret_returns_empty() -> None:
    assert AwsSecretsManagerSource("absent", required=False).fetch() == {}


def test_aws_secrets_manager_source__decode_with_empty_secret_string_returns_empty() -> None:
    # Secrets Manager rejects an empty SecretString at create time (min length 1), so the
    # present-but-empty -> {} pass-through of ensure_mapping is only reachable via _decode directly.
    assert AwsSecretsManagerSource("empty")._decode({"SecretString": ""}) == {}


def test_aws_secrets_manager_source_fetch_with_binary_only_secret_raises_source_error(secrets_client: Any) -> None:  # pyright: ignore[reportExplicitAny, reportAny]
    secrets_client.create_secret(Name="bin", SecretBinary=b"\x00\x01")  # pyright: ignore[reportAny]

    with pytest.raises(SourceError) as excinfo:
        AwsSecretsManagerSource("bin").fetch()

    message = str(excinfo.value)
    assert "aws-secrets:bin" in message
    assert "binary" in message


def test_aws_secrets_manager_source_fetch_with_sdk_error_raises_source_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakeClient:
        class exceptions:  # noqa: N801
            class ResourceNotFoundException(Exception): ...  # noqa: N818

        def get_secret_value(self, *, SecretId: str) -> dict[str, str]:  # noqa: N803
            _ = SecretId
            raise RuntimeError("boom")

    monkeypatch.setattr(AwsSecretsManagerSource, "_client", lambda _self: _FakeClient())

    with pytest.raises(SourceError) as excinfo:
        AwsSecretsManagerSource("app/config").fetch()

    assert not isinstance(excinfo.value, SourceNotFoundError)
    assert "aws-secrets:app/config" in str(excinfo.value)


def test_aws_secrets_manager_source_fetch_with_client_build_failure_raises_source_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _raise(_self: AwsSecretsManagerSource) -> object:
        raise RuntimeError("no region")

    monkeypatch.setattr(AwsSecretsManagerSource, "_client", _raise)

    with pytest.raises(SourceError) as excinfo:
        AwsSecretsManagerSource("app/config").fetch()

    assert not isinstance(excinfo.value, SourceNotFoundError)
    assert "aws-secrets:app/config" in str(excinfo.value)


def test_aws_secrets_manager_source_init_with_missing_boto3_raises_branded_import_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "boto3", None)

    with pytest.raises(ImportError) as excinfo:
        _ = AwsSecretsManagerSource("x")

    assert "confiq[aws]" in str(excinfo.value)
    assert not isinstance(excinfo.value, SourceError)


def test_aws_secrets_manager_source_fetch_passes_region_and_profile_name_to_session_independent_of_profile_tag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class _FakeClient:
        class exceptions:  # noqa: N801
            class ResourceNotFoundException(Exception): ...  # noqa: N818

        def get_secret_value(self, *, SecretId: str) -> dict[str, str]:  # noqa: N803
            _ = SecretId
            return {"SecretString": json.dumps({"ok": True})}

    class _FakeSession:
        def __init__(self, **kwargs: object) -> None:
            captured.update(kwargs)

        def client(self, _service: str) -> _FakeClient:
            return _FakeClient()

    monkeypatch.setattr(boto3.session, "Session", _FakeSession)

    source = AwsSecretsManagerSource("app/config", region_name="eu-west-1", profile_name="dev", profile="prod")
    result = source.fetch()

    assert captured == {"profile_name": "dev", "region_name": "eu-west-1"}
    assert source.profile == "prod"
    assert result == {"ok": True}


def test_aws_secrets_manager_source_fetch_with_yaml_loader_override_returns_nested_mapping(secrets_client: Any) -> None:  # pyright: ignore[reportExplicitAny, reportAny]
    pytest.importorskip("yaml")
    from confiq.loader._yaml import YamlLoader

    secrets_client.create_secret(Name="y", SecretString="database:\n  host: h\n")  # pyright: ignore[reportAny]

    assert AwsSecretsManagerSource("y", loader=YamlLoader()).fetch() == {"database": {"host": "h"}}


def test_aws_secrets_manager_source_name_includes_secret_id() -> None:
    assert AwsSecretsManagerSource("app/config").name == "aws-secrets:app/config"

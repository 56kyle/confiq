"""Module defining AWS cloud configuration sources (ADR 0006, 0053)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from confiq._imports import import_optional
from confiq.exceptions import SourceError
from confiq.exceptions import SourceNotFoundError
from confiq.loader._json import JsonLoader
from confiq.loader._loader import Loader
from confiq.source._base_source import BaseSource


class AwsSecretsManagerSource(BaseSource):
    """Reads one AWS Secrets Manager secret; parses its SecretString via a Loader (ADR 0053).

    A secret is one opaque string, conventionally a JSON object = a config bundle -> structured
    (ADR 0048). The SecretString is parsed through a Loader (default JsonLoader), inheriting the
    non-mapping refusal and empty->{} of ensure_mapping. Binary-only secrets are unsupported. A
    missing secret raises SourceNotFoundError when required, else yields {} (ADR 0040). boto3 is
    imported at construction (ADR 0006); a missing [aws] extra surfaces as a branded ImportError.
    """

    def __init__(
        self,
        secret_id: str,
        *,
        region_name: str | None = None,
        profile_name: str | None = None,
        loader: Loader | None = None,
        required: bool = True,
        profile: str | None = None,
    ) -> None:
        self._secret_id = secret_id
        self._region_name = region_name
        self._profile_name = profile_name
        self._loader: Loader = loader if loader is not None else JsonLoader()
        self._required = required
        self.profile = profile
        self._boto3 = import_optional("boto3", extra="aws")

    @property
    def name(self) -> str:
        return f"aws-secrets:{self._secret_id}"

    def fetch(self) -> Mapping[str, Any]:
        """Fetch and decode the secret (ADR 0040, 0053).

        Raises SourceNotFoundError when a required secret is absent (else yields {});
        SourceError for a client-construction failure (missing region / bad profile), a
        non-not-found SDK error, or a non-mapping / malformed secret body. A missing
        loader extra's ImportError propagates.
        """
        try:
            client = self._client()  # pyright: ignore[reportAny]  # optional-dep boto3 client is Any
        except Exception as error:
            raise SourceError(self.name, str(error)) from error
        try:
            response = client.get_secret_value(SecretId=self._secret_id)  # pyright: ignore[reportAny]  # optional-dep client is Any
        except client.exceptions.ResourceNotFoundException as error:  # pyright: ignore[reportAny]  # optional-dep client is Any
            if self._required:
                raise SourceNotFoundError(self.name, f"secret not found: {self._secret_id}") from error
            return {}
        except Exception as error:
            raise SourceError(self.name, str(error)) from error
        return self._decode(response)  # pyright: ignore[reportAny]  # optional-dep response is Any

    def _client(self) -> Any:  # pyright: ignore[reportAny]  # optional-dep boto3 client is Any
        session = self._boto3.session.Session(  # pyright: ignore[reportAny]  # optional-dep boto3 attr is Any
            profile_name=self._profile_name,
            region_name=self._region_name,
        )
        return session.client("secretsmanager")  # pyright: ignore[reportAny]  # optional-dep session is Any

    def _decode(self, response: Mapping[str, Any]) -> Mapping[str, Any]:
        secret_string = response.get("SecretString")
        if secret_string is None:
            raise SourceError(
                self.name,
                "secret has no SecretString (binary-only secrets are unsupported)",
            )
        try:
            return self._loader.parse(secret_string.encode())  # pyright: ignore[reportAny]  # optional-dep response value is Any
        except ImportError:
            raise
        except Exception as error:
            raise SourceError(self.name, str(error)) from error

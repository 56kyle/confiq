import pytest

from confiq._registry import MissingDependencyError
from confiq._registry import create_source
from confiq._registry import get_source_class
from confiq._registry import register_implementation
from confiq.sources.dict_source import DictSource
from confiq.sources.env import EnvSource
from confiq.sources.file import FileSource


def test_get_dict_source_class():
    cls = get_source_class("dict")
    assert cls is DictSource


def test_get_env_source_class():
    cls = get_source_class("env")
    assert cls is EnvSource


def test_get_file_source_class():
    cls = get_source_class("file")
    assert cls is FileSource


def test_unknown_protocol_raises_keyerror():
    with pytest.raises(KeyError, match="Unknown config source protocol"):
        get_source_class("nonexistent-protocol-xyz")


def test_missing_dep_raises_missing_dependency_error():
    with pytest.raises(MissingDependencyError):
        get_source_class("vault")


def test_create_source_dict():
    src = create_source("dict", data={"x": 1})
    assert src.load() == {"x": 1}


def test_register_custom_class():
    from confiq.sources.base import AbstractConfigSource

    class FakeSource(AbstractConfigSource):
        protocol = "fake-test-xyz"

        def load(self):
            return {"fake": True}

    register_implementation("fake-test-xyz", FakeSource, clobber=True)
    cls = get_source_class("fake-test-xyz")
    assert cls is FakeSource


def test_register_duplicate_raises_without_clobber():
    from confiq.sources.base import AbstractConfigSource

    class A(AbstractConfigSource):
        protocol = "dup-test-abc"

        def load(self):
            return {}

    class B(AbstractConfigSource):
        protocol = "dup-test-abc"

        def load(self):
            return {}

    register_implementation("dup-test-abc", A, clobber=True)
    with pytest.raises(ValueError, match="already registered"):
        register_implementation("dup-test-abc", B, clobber=False)

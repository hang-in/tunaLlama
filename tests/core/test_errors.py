import pytest

from tunallama_core.errors import (
    ConfigError,
    LLMError,
    MemoryStoreError,
    RecallError,
    TunaLlamaError,
)


@pytest.mark.parametrize(
    "cls", [ConfigError, LLMError, MemoryStoreError, RecallError]
)
def test_subclass_of_base(cls):
    assert issubclass(cls, TunaLlamaError)
    assert issubclass(cls, Exception)


def test_raise_via_base_class():
    with pytest.raises(TunaLlamaError):
        raise ConfigError("nope")


def test_each_error_has_distinct_type():
    errors = {ConfigError, LLMError, MemoryStoreError, RecallError, TunaLlamaError}
    assert len(errors) == 5

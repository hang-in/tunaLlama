"""tunallama_core public surface 일관성 테스트.

- ``__all__`` 에 명시된 이름이 실제로 import 가능해야.
- 누락/중복 없어야.
"""

import tunallama_core


def test_all_exported_names_resolve():
    missing = [n for n in tunallama_core.__all__ if not hasattr(tunallama_core, n)]
    assert missing == []


def test_no_duplicate_in_all():
    assert len(tunallama_core.__all__) == len(set(tunallama_core.__all__))


def test_public_modules_are_distinct_from_internals():
    """``_runner`` / ``_prompts`` 같은 내부 모듈은 public API 에서 노출되지 않아야."""
    for name in tunallama_core.__all__:
        assert not name.startswith("_")

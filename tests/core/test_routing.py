import pytest

from tunallama_core.config.models import RoutingConfig
from tunallama_core.memory.store import MemoryStore
from tunallama_core.routing import recall_for_delegation


@pytest.fixture
def store(tmp_path):
    with MemoryStore(tmp_path / "r.db", korean_tokenizer="kiwi") as s:
        s.record_call(
            tool_name="generate_code",
            inputs={"q": "validate email"},
            output="def is_valid(): ...",
            model="m",
            duration_ms=1,
            project_root="/proj",
        )
        s.record_call(
            tool_name="generate_code",
            inputs={"q": "이메일 검증"},
            output="kor",
            model="m",
            duration_ms=1,
        )
        yield s


def _routing(mode, limit=5):
    return RoutingConfig(auto_recall=mode, recall_limit=limit)


def test_never_returns_none(store):
    r = recall_for_delegation(_routing("never"), store, explicit_query="email")
    assert r is None


def test_on_request_with_query(store):
    r = recall_for_delegation(_routing("on_request"), store, explicit_query="email")
    assert r is not None
    assert r.total_matches == 1


def test_on_request_without_query_returns_none(store):
    r = recall_for_delegation(
        _routing("on_request"),
        store,
        explicit_query=None,
        fallback_query="email",
    )
    assert r is None  # on_request 는 fallback 무시


def test_always_uses_fallback_when_explicit_missing(store):
    r = recall_for_delegation(
        _routing("always"),
        store,
        explicit_query=None,
        fallback_query="email",
    )
    assert r is not None
    assert r.total_matches == 1


def test_always_prefers_explicit_over_fallback(store):
    r = recall_for_delegation(
        _routing("always"),
        store,
        explicit_query="이메일",
        fallback_query="something else",
    )
    assert r is not None
    assert r.total_matches == 1
    assert r.snippets[0].full_id == 2


def test_always_returns_none_when_both_blank(store):
    r = recall_for_delegation(
        _routing("always"),
        store,
        explicit_query="   ",
        fallback_query=None,
    )
    assert r is None


def test_project_root_filter_propagates(store):
    r = recall_for_delegation(
        _routing("on_request"),
        store,
        explicit_query="email",
        project_root="/proj",
    )
    assert r is not None
    assert r.total_matches == 1


def test_project_root_filter_excludes_unrelated(store):
    r = recall_for_delegation(
        _routing("on_request"),
        store,
        explicit_query="email",
        project_root="/other",
    )
    assert r is not None
    assert r.total_matches == 0


def test_recall_limit_propagates(store):
    """5개 한국어 record 후 limit=2 — recall_limit 가 검색 결과 수를 제한."""
    for i in range(5):
        store.record_call(
            tool_name="t",
            inputs={"q": f"alpha {i}"},
            output="x",
            model="m",
            duration_ms=1,
        )
    r = recall_for_delegation(_routing("on_request", limit=2), store, explicit_query="alpha")
    assert r is not None
    assert len(r.snippets) == 2

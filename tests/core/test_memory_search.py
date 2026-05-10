import pytest

from tunallama_core.errors import RecallError
from tunallama_core.memory.search import recall
from tunallama_core.memory.store import MemoryStore


@pytest.fixture
def store(tmp_path):
    with MemoryStore(tmp_path / "search.db", korean_tokenizer="kiwi") as s:
        yield s


def _seed(store, **kw):
    return store.record_call(
        tool_name=kw.get("tool", "generate_code"),
        inputs=kw["inputs"],
        output=kw["output"],
        model="m",
        duration_ms=1,
        project_root=kw.get("project"),
    )


def test_empty_query_raises(store):
    with pytest.raises(RecallError, match="비어있"):
        recall(store, "   ")


def test_non_positive_limit_raises(store):
    with pytest.raises(RecallError, match="limit"):
        recall(store, "x", limit=0)


def test_english_recall_finds_match(store):
    _seed(store, inputs={"q": "validate email"}, output="def is_valid_email(): ...")
    _seed(store, inputs={"q": "parse json"}, output="def load(): ...")
    r = recall(store, "email")
    assert r.total_matches == 1
    assert r.snippets[0].full_id == 1
    assert "email" in r.snippets[0].inputs_summary.lower() or \
           "email" in r.snippets[0].output_excerpt.lower()


def test_korean_recall_via_morpheme(store):
    """핸드오프 §7.4 시나리오 C — 한국어 키워드로 과거 호출 발견."""
    _seed(
        store,
        inputs={"q": "이메일 검증 함수 만들어줘"},
        output="def is_valid_email(): pass",
    )
    _seed(
        store,
        inputs={"q": "JSON 파싱 함수"},
        output="def parse(): pass",
    )
    r = recall(store, "이메일 검증")
    assert r.total_matches == 1
    assert r.snippets[0].full_id == 1


def test_korean_recall_handles_concatenated_input(store):
    """띄어쓰기 없는 한국어도 형태소 분리 덕에 매칭."""
    _seed(store, inputs={"q": "이메일검증코드"}, output="ok")
    r = recall(store, "이메일")
    assert r.total_matches == 1


def test_project_root_filter(store):
    _seed(store, inputs={"q": "alpha"}, output="x", project="/p1")
    _seed(store, inputs={"q": "alpha"}, output="x", project="/p2")
    r = recall(store, "alpha", project_root="/p2")
    assert r.total_matches == 1
    assert r.snippets[0].full_id == 2


def test_limit_truncates_results(store):
    for i in range(5):
        _seed(store, inputs={"q": f"alpha {i}"}, output=f"out {i}")
    r = recall(store, "alpha", limit=2)
    assert len(r.snippets) == 2
    # total_matches 는 limit 와 별개로 전체 갯수
    assert r.total_matches == 5


def test_no_match_returns_empty(store):
    _seed(store, inputs={"q": "alpha"}, output="x")
    r = recall(store, "beta")
    assert r.total_matches == 0
    assert r.snippets == ()


def test_snippet_truncation():
    with MemoryStore(":memory:") as s:
        s.record_call(
            tool_name="t",
            inputs={"q": "alpha " * 100},
            output="alpha " * 100,
            model="m",
            duration_ms=1,
        )
        r = recall(s, "alpha")
    snip = r.snippets[0]
    assert len(snip.inputs_summary) <= 100
    assert len(snip.output_excerpt) <= 200
    assert snip.inputs_summary.endswith("…")
    assert snip.output_excerpt.endswith("…")


def test_snippet_score_is_negative_bm25(store):
    """FTS5 bm25() 는 더 좋은 매치일수록 더 작은(음수) 값."""
    _seed(store, inputs={"q": "alpha"}, output="alpha alpha")
    _seed(store, inputs={"q": "alpha beta"}, output="alpha")
    r = recall(store, "alpha", limit=2)
    # 첫 결과가 두 번째보다 점수(=BM25) 낮아야 (더 좋은 매치)
    assert r.snippets[0].score <= r.snippets[1].score


def test_quote_safe_on_user_query(store):
    """쿼리에 큰따옴표가 들어가도 SQL 깨지지 않아야."""
    _seed(store, inputs={"q": 'said "hi"'}, output="x")
    r = recall(store, '"hi"')
    assert r.total_matches >= 0  # 검색 자체가 깨지지 않음


def test_recall_wraps_sqlite_failure(store):
    """FTS 테이블이 사라지는 등 SQL 실패는 RecallError 로 surface."""
    _seed(store, inputs={"q": "alpha"}, output="x")
    store.conn.execute("DROP TABLE calls_fts")
    with pytest.raises(RecallError, match="FTS5"):
        recall(store, "alpha")

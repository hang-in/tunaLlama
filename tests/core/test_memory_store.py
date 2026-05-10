import json

import pytest

from tunallama_core.errors import MemoryStoreError
from tunallama_core.memory.store import CallRecord, MemoryStore


@pytest.fixture
def store(tmp_path):
    db = tmp_path / "mem.db"
    with MemoryStore(db, korean_tokenizer="kiwi") as s:
        yield s


def test_open_creates_file(tmp_path):
    db = tmp_path / "sub" / "mem.db"
    with MemoryStore(db) as s:
        assert s.count() == 0
    assert db.exists()


def test_conn_before_open_raises(tmp_path):
    s = MemoryStore(tmp_path / "x.db")
    with pytest.raises(MemoryStoreError):
        _ = s.conn


def test_record_call_returns_id_and_increments_count(store):
    rid = store.record_call(
        tool_name="generate_code",
        inputs={"requirements": "validate email"},
        output="def is_valid(): ...",
        model="m",
        duration_ms=42,
    )
    assert rid == 1
    assert store.count() == 1
    rid2 = store.record_call(
        tool_name="generate_code",
        inputs={},
        output="x",
        model="m",
        duration_ms=1,
    )
    assert rid2 == 2
    assert store.count() == 2


def test_get_returns_call_record(store):
    rid = store.record_call(
        tool_name="review_code",
        inputs={"code": "x", "focus": "security"},
        output="LGTM",
        model="m",
        duration_ms=10,
        tokens_estimated=5,
        project_root="/tmp/proj",
        session_id="sess-1",
        tags=["audit", "v0.1"],
    )
    rec = store.get(rid)
    assert isinstance(rec, CallRecord)
    assert rec.tool_name == "review_code"
    assert rec.output == "LGTM"
    assert rec.model == "m"
    assert rec.tokens_estimated == 5
    assert rec.project_root == "/tmp/proj"
    assert rec.session_id == "sess-1"
    assert rec.tags == ("audit", "v0.1")
    # inputs_json 은 직렬화된 그대로
    assert json.loads(rec.inputs_json) == {"code": "x", "focus": "security"}


def test_get_missing_returns_none(store):
    assert store.get(9999) is None


def test_record_call_default_tags(store):
    rid = store.record_call(
        tool_name="t", inputs={}, output="x", model="m", duration_ms=1
    )
    rec = store.get(rid)
    assert rec.tags == ()


def test_records_persist_across_reopen(tmp_path):
    db = tmp_path / "persist.db"
    with MemoryStore(db) as s:
        s.record_call(
            tool_name="t", inputs={"q": "이메일 검증"},
            output="o", model="m", duration_ms=1,
        )
    with MemoryStore(db) as s:
        assert s.count() == 1
        rec = s.get(1)
        assert rec is not None
        assert "이메일" in rec.inputs_json


def test_fts_row_inserted_with_kiwi_tokenization(store):
    """한국어 입력은 형태소가 calls_fts 에 들어가 검색 가능해야 한다."""
    store.record_call(
        tool_name="generate_code",
        inputs={"requirements": "이메일검증"},  # 띄어쓰기 없음
        output="def is_valid(): ...",
        model="m",
        duration_ms=1,
    )
    # 형태소 단위 매칭 — 띄어쓰기 없는 원문에서 "이메일" 검색 성공해야 함
    rows = store.conn.execute(
        "SELECT rowid FROM calls_fts WHERE calls_fts MATCH ?", ("이메일",)
    ).fetchall()
    assert len(rows) == 1


def test_in_memory_database():
    """``:memory:`` 도 지원해야 한다 (테스트 격리용)."""
    with MemoryStore(":memory:") as s:
        s.record_call(
            tool_name="t", inputs={}, output="x", model="m", duration_ms=1
        )
        assert s.count() == 1


def test_close_idempotent(tmp_path):
    s = MemoryStore(tmp_path / "x.db")
    s.open()
    s.close()
    s.close()  # double close 안전


def test_invalid_tags_json_is_tolerated(tmp_path):
    """수동으로 망가뜨린 tags 도 빈 튜플로 노출 — 운영성."""
    db = tmp_path / "mem.db"
    with MemoryStore(db) as s:
        rid = s.record_call(
            tool_name="t", inputs={}, output="x", model="m", duration_ms=1
        )
        s.conn.execute("UPDATE calls SET tags = 'not-json' WHERE id = ?", (rid,))
        s.conn.commit()
        rec = s.get(rid)
        assert rec is not None
        assert rec.tags == ()

"""Phase 2-1 vector recall 테스트.

실 BGE-M3 모델 다운로드/로드는 무거우므로 ``vector.embed`` 를 monkeypatch 로
fake 함수 (텍스트 hash → 결정적 1024-dim 정규화 벡터) 으로 대체. 임베딩 의미
검증은 통합 테스트 영역.
"""

from __future__ import annotations

import hashlib
import sqlite3

import numpy as np
import pytest

from tunallama_core.memory.store import MemoryStore
from tunallama_core.memory.vector import (
    EMBEDDING_DIM,
    decode_blob,
    encode_blob,
)


def _fake_embed(text: str) -> np.ndarray:
    """결정적 fake — sha256 으로 1024 float32 정규화 벡터."""
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    rng = np.random.default_rng(int.from_bytes(digest[:8], "little"))
    vec = rng.standard_normal(EMBEDDING_DIM, dtype=np.float64).astype(np.float32)
    norm = float(np.linalg.norm(vec))
    return vec / norm if norm else vec


@pytest.fixture
def patched_embed(monkeypatch):
    """embed() 호출을 fake 로 대체. tunallama_core.memory.vector 와 store 양쪽 다."""
    monkeypatch.setattr("tunallama_core.memory.vector.embed", _fake_embed)
    return _fake_embed


@pytest.fixture
def store(tmp_path, patched_embed):
    db = tmp_path / "vec.db"
    with MemoryStore(db, korean_tokenizer="kiwi") as s:
        yield s


def test_encode_decode_roundtrip(patched_embed):
    vec = _fake_embed("hello")
    blob = encode_blob(vec)
    back = decode_blob(blob)
    assert back is not None
    np.testing.assert_array_equal(back, vec)


def test_decode_blob_rejects_wrong_length():
    assert decode_blob(b"\x00" * 100) is None
    assert decode_blob(None) is None


def test_record_call_stores_embedding(store):
    rid = store.record_call(
        tool_name="generate_code",
        inputs={"requirements": "validate email"},
        output="def is_valid_email(): ...",
        model="m",
        duration_ms=1,
    )
    row = store.conn.execute(
        "SELECT embedding FROM calls WHERE id = ?", (rid,)
    ).fetchone()
    assert row["embedding"] is not None
    assert len(row["embedding"]) == EMBEDDING_DIM * 4


def test_record_call_falls_back_to_null_when_embed_fails(monkeypatch, tmp_path):
    """embed() 가 ImportError / 일반 예외를 던지면 record_call 은 정상 진행 (embedding=NULL)."""

    def boom(text):
        raise RuntimeError("model load failed")

    monkeypatch.setattr("tunallama_core.memory.vector.embed", boom)
    with MemoryStore(tmp_path / "fail.db") as s:
        rid = s.record_call(
            tool_name="t", inputs={}, output="x", model="m", duration_ms=1
        )
        row = s.conn.execute(
            "SELECT embedding FROM calls WHERE id = ?", (rid,)
        ).fetchone()
        assert row["embedding"] is None
        assert s.count() == 1  # record 자체는 정상


def test_search_vectors_returns_self_match_first(store, patched_embed):
    rid = store.record_call(
        tool_name="generate_code",
        inputs={"q": "이메일 검증"},
        output="def is_valid_email(): pass",
        model="m",
        duration_ms=1,
    )
    # 같은 텍스트로 검색 → cosine 1.0 매칭이 1위
    hits = store.search_vectors("{\"q\": \"이메일 검증\"} def is_valid_email(): pass")
    assert len(hits) >= 1
    assert hits[0].id == rid
    assert hits[0].score == pytest.approx(1.0, abs=1e-5)


def test_search_vectors_orders_by_cosine(store, patched_embed):
    near = store.record_call(
        tool_name="t", inputs={"q": "alpha alpha"}, output="x",
        model="m", duration_ms=1,
    )
    far = store.record_call(
        tool_name="t", inputs={"q": "beta beta"}, output="x",
        model="m", duration_ms=1,
    )
    hits = store.search_vectors("{\"q\": \"alpha alpha\"} x", limit=2)
    # 첫 record (alpha 텍스트 그대로) 가 더 높은 score
    assert hits[0].id == near
    assert hits[0].score >= hits[1].score


def test_search_vectors_filters_by_project_root(store, patched_embed):
    a = store.record_call(
        tool_name="t", inputs={"q": "alpha"}, output="x",
        model="m", duration_ms=1, project_root="/p1",
    )
    b = store.record_call(
        tool_name="t", inputs={"q": "alpha"}, output="x",
        model="m", duration_ms=1, project_root="/p2",
    )
    hits = store.search_vectors("alpha", project_root="/p2")
    assert {h.id for h in hits} == {b}


def test_search_vectors_skips_null_embedding_rows(store, patched_embed):
    rid = store.record_call(
        tool_name="t", inputs={"q": "alpha"}, output="x",
        model="m", duration_ms=1,
    )
    # 두 번째 record 는 embedding 강제 NULL
    store.conn.execute("UPDATE calls SET embedding=NULL WHERE id=?", (rid,))
    store.conn.commit()
    hits = store.search_vectors("alpha")
    assert all(h.id != rid for h in hits)


def test_search_vectors_empty_store_returns_empty(store):
    hits = store.search_vectors("anything")
    assert hits == []


def test_search_vectors_limit_zero_returns_empty(store, patched_embed):
    store.record_call(tool_name="t", inputs={"q": "x"}, output="x", model="m", duration_ms=1)
    assert store.search_vectors("x", limit=0) == []


def test_legacy_db_gets_embedding_column_via_migration(tmp_path):
    """마이그레이션: 옛 schema (embedding 컬럼 없음) 에도 ALTER 가 idempotent."""
    db = tmp_path / "legacy.db"
    legacy = sqlite3.connect(str(db))
    legacy.executescript("""
        CREATE TABLE calls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            tool_name TEXT NOT NULL,
            inputs_json TEXT NOT NULL,
            output TEXT NOT NULL,
            model TEXT NOT NULL,
            duration_ms INTEGER NOT NULL,
            tokens_estimated INTEGER,
            project_root TEXT,
            session_id TEXT,
            tags TEXT NOT NULL DEFAULT '[]'
        );
        CREATE VIRTUAL TABLE calls_fts USING fts5(
            inputs_text, output_text,
            tokenize='unicode61 remove_diacritics 2'
        );
    """)
    legacy.close()

    with MemoryStore(db) as s:
        cols = [r[1] for r in s.conn.execute("PRAGMA table_info(calls)").fetchall()]
        assert "embedding" in cols

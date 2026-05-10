"""Phase 2-3 — rule-based 그래프 엣지."""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from tunallama_core.memory.graph import Edge, rebuild_edges, traverse
from tunallama_core.memory.store import MemoryStore
from tunallama_core.memory.vector import EMBEDDING_DIM


def _fake_embed(text: str) -> np.ndarray:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    rng = np.random.default_rng(int.from_bytes(digest[:8], "little"))
    vec = rng.standard_normal(EMBEDDING_DIM, dtype=np.float64).astype(np.float32)
    n = float(np.linalg.norm(vec))
    return vec / n if n else vec


@pytest.fixture(autouse=True)
def _patch_embed(monkeypatch):
    """모든 graph 테스트에서 임베딩 모델 다운로드 회피."""
    monkeypatch.setattr("tunallama_core.memory.vector.embed", _fake_embed)


@pytest.fixture
def store(tmp_path):
    with MemoryStore(tmp_path / "g.db") as s:
        yield s


def _set_timestamp(store: MemoryStore, call_id: int, iso_dt: str) -> None:
    """record_call 후 timestamp 를 임의 값으로 강제 (테스트 결정성)."""
    store.conn.execute("UPDATE calls SET timestamp=? WHERE id=?", (iso_dt, call_id))
    store.conn.commit()


def test_empty_store_zero_edges(store):
    assert rebuild_edges(store) == 0


def test_single_call_no_self_loop(store):
    store.record_call(
        tool_name="t", inputs={}, output="x", model="m", duration_ms=1,
        project_root="/p",
    )
    n = rebuild_edges(store)
    rows = store.conn.execute("SELECT COUNT(*) FROM graph_edges").fetchone()
    assert rows[0] == 0
    assert n == 0


def test_same_project_edge(store):
    a = store.record_call(
        tool_name="generate_code", inputs={}, output="a", model="m", duration_ms=1,
        project_root="/proj",
    )
    b = store.record_call(
        tool_name="review_code", inputs={}, output="b", model="m", duration_ms=1,
        project_root="/proj",
    )
    n = rebuild_edges(store)
    edges = store.conn.execute(
        "SELECT source_id, target_id, relation FROM graph_edges"
    ).fetchall()
    edge_set = {(e["source_id"], e["target_id"], e["relation"]) for e in edges}
    assert (a, b, "same_project") in edge_set
    # same_tool 은 둘이 다르므로 X
    assert not any(r["relation"] == "same_tool" for r in edges)
    assert n >= 1


def test_same_day_edge(store):
    a = store.record_call(
        tool_name="t1", inputs={}, output="a", model="m", duration_ms=1,
        project_root="/p1",
    )
    b = store.record_call(
        tool_name="t2", inputs={}, output="b", model="m", duration_ms=1,
        project_root="/p2",
    )
    same_day = "2026-05-10T00:00:00+00:00"
    next_day = "2026-05-11T00:00:00+00:00"
    _set_timestamp(store, a, same_day)
    _set_timestamp(store, b, same_day)
    rebuild_edges(store)
    rows = store.conn.execute(
        "SELECT relation FROM graph_edges WHERE source_id=? AND target_id=?",
        (a, b),
    ).fetchall()
    relations = {r["relation"] for r in rows}
    assert "same_day" in relations

    # 날짜 다르면 same_day 엣지 안 생김
    _set_timestamp(store, b, next_day)
    rebuild_edges(store)
    rows = store.conn.execute(
        "SELECT relation FROM graph_edges WHERE source_id=? AND target_id=?",
        (a, b),
    ).fetchall()
    relations = {r["relation"] for r in rows}
    assert "same_day" not in relations


def test_same_tool_edge(store):
    a = store.record_call(
        tool_name="generate_code", inputs={}, output="a", model="m", duration_ms=1,
        project_root="/p1",
    )
    b = store.record_call(
        tool_name="generate_code", inputs={}, output="b", model="m", duration_ms=1,
        project_root="/p2",
    )
    rebuild_edges(store)
    rows = store.conn.execute(
        "SELECT relation FROM graph_edges WHERE source_id=? AND target_id=?",
        (a, b),
    ).fetchall()
    assert any(r["relation"] == "same_tool" for r in rows)


def test_normalized_source_lt_target(store):
    a = store.record_call(
        tool_name="t", inputs={}, output="a", model="m", duration_ms=1,
        project_root="/p",
    )
    b = store.record_call(
        tool_name="t", inputs={}, output="b", model="m", duration_ms=1,
        project_root="/p",
    )
    rebuild_edges(store)
    rows = store.conn.execute(
        "SELECT source_id, target_id FROM graph_edges"
    ).fetchall()
    for r in rows:
        assert r["source_id"] < r["target_id"]
    # (b, a) 는 절대 안 들어감
    assert not any(r["source_id"] == b and r["target_id"] == a for r in rows)


def test_traverse_bfs_finds_neighbors(store):
    # 같은 project 3 record — 모두 서로 same_project 엣지
    ids = [
        store.record_call(
            tool_name="t", inputs={}, output=f"r{i}", model="m", duration_ms=1,
            project_root="/p",
        )
        for i in range(3)
    ]
    rebuild_edges(store)
    edges = traverse(store, ids[0], max_hops=2)
    # ids[0] 의 인접 — ids[1], ids[2] 모두 도달
    reached = {e.target_id for e in edges} | {e.source_id for e in edges}
    assert ids[1] in reached
    assert ids[2] in reached


def test_traverse_max_hops_zero_returns_empty(store):
    ids = [
        store.record_call(
            tool_name="t", inputs={}, output=f"r{i}", model="m", duration_ms=1,
            project_root="/p",
        )
        for i in range(2)
    ]
    rebuild_edges(store)
    assert traverse(store, ids[0], max_hops=0) == []


def test_traverse_relation_filter(store):
    # 같은 project + 같은 tool → 두 종류 엣지 둘 다 생성됨
    ids = [
        store.record_call(
            tool_name="generate_code", inputs={}, output=f"r{i}", model="m", duration_ms=1,
            project_root="/p",
        )
        for i in range(2)
    ]
    rebuild_edges(store)
    only_tool = traverse(store, ids[0], max_hops=1, relations=("same_tool",))
    assert all(e.relation == "same_tool" for e in only_tool)
    only_proj = traverse(store, ids[0], max_hops=1, relations=("same_project",))
    assert all(e.relation == "same_project" for e in only_proj)


def test_rebuild_idempotent(store):
    store.record_call(
        tool_name="t", inputs={}, output="a", model="m", duration_ms=1,
        project_root="/p",
    )
    store.record_call(
        tool_name="t", inputs={}, output="b", model="m", duration_ms=1,
        project_root="/p",
    )
    n1 = rebuild_edges(store)
    n2 = rebuild_edges(store)
    # 두 호출 모두 같은 엣지 수 — 누적 중복 없음
    total = store.conn.execute("SELECT COUNT(*) FROM graph_edges").fetchone()[0]
    assert total == n1 == n2

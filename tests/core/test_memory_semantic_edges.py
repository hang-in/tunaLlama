"""Phase 3-2 — semantic_edges (LLM-derived 그래프 관계) 단위 테스트."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

import numpy as np
import pytest

from tunallama_core.llm.base import ChatResponse, LLMClient
from tunallama_core.memory.graph import rebuild_edges
from tunallama_core.memory.semantic_edges import (
    build_semantic_edges,
    classify_pair,
)
from tunallama_core.memory.store import CallRecord, MemoryStore
from tunallama_core.memory.vector import EMBEDDING_DIM


def _fake_embed(text: str) -> np.ndarray:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    rng = np.random.default_rng(int.from_bytes(digest[:8], "little"))
    vec = rng.standard_normal(EMBEDDING_DIM, dtype=np.float64).astype(np.float32)
    n = float(np.linalg.norm(vec))
    return vec / n if n else vec


@pytest.fixture(autouse=True)
def _patch_embed(monkeypatch):
    monkeypatch.setattr("tunallama_core.memory.vector.embed", _fake_embed)


@dataclass
class StaticVerdict(LLMClient):
    """모든 chat 호출에 같은 응답을 돌려주는 fake — 분류 시나리오 시뮬."""

    text: str = "RELATED"
    calls: list[dict] = field(default_factory=list)

    def chat(self, *, system, prompt, response_schema=None) -> ChatResponse:
        self.calls.append({"system": system, "prompt": prompt})
        return ChatResponse(text=self.text, model="fake-cls", duration_ms=1)


def _record(id_=0, project="/p"):
    return CallRecord(
        id=id_, timestamp="2026-05-10T00:00:00Z", tool_name="t",
        inputs_json='{"q": "x"}', output="y", model="m", duration_ms=1,
        tokens_estimated=None, project_root=project, session_id=None, tags=(),
    )


def test_classify_pair_related_returns_true():
    c = StaticVerdict(text="RELATED")
    assert classify_pair(c, _record(1), _record(2)) is True


def test_classify_pair_unrelated_returns_false():
    c = StaticVerdict(text="UNRELATED")
    assert classify_pair(c, _record(1), _record(2)) is False


def test_classify_pair_invalid_returns_none():
    c = StaticVerdict(text="not sure")
    assert classify_pair(c, _record(1), _record(2)) is None


def test_classify_pair_swallows_exception(monkeypatch):
    class Boom(LLMClient):
        def chat(self, *, system, prompt, response_schema=None):
            raise RuntimeError("network down")

    assert classify_pair(Boom(), _record(1), _record(2)) is None


@pytest.fixture
def store(tmp_path):
    with MemoryStore(tmp_path / "se.db") as s:
        yield s


def _seed(store, n: int, project: str):
    return [
        store.record_call(
            tool_name="t", inputs={"q": f"text {i}"}, output=f"out {i}",
            model="m", duration_ms=1, project_root=project,
        )
        for i in range(n)
    ]


def test_build_inserts_edge_only_for_related(store):
    _seed(store, n=2, project="/proj_a")
    n = build_semantic_edges(store, StaticVerdict(text="RELATED"))
    assert n == 1
    rows = store.conn.execute(
        "SELECT relation FROM graph_edges WHERE relation='semantic_related'"
    ).fetchall()
    assert len(rows) == 1


def test_build_skips_unrelated(store):
    _seed(store, n=2, project="/proj_a")
    n = build_semantic_edges(store, StaticVerdict(text="UNRELATED"))
    assert n == 0


def test_build_max_pairs_limits_classifications(store):
    _seed(store, n=4, project="/p")  # C(4,2) = 6 페어 가능
    c = StaticVerdict(text="RELATED")
    build_semantic_edges(store, c, max_pairs=2)
    assert len(c.calls) == 2  # 정확히 2 페어만 분류 시도


def test_build_filters_by_project_root(store):
    _seed(store, n=2, project="/proj_a")
    _seed(store, n=2, project="/proj_b")
    c = StaticVerdict(text="RELATED")
    n = build_semantic_edges(store, c, project_root="/proj_a")
    assert n == 1
    assert len(c.calls) == 1


def test_build_idempotent_skips_existing(store):
    _seed(store, n=2, project="/p")
    c = StaticVerdict(text="RELATED")
    build_semantic_edges(store, c)
    # 두 번째 호출 — 같은 페어라 LLM 호출 자체 skip
    c2 = StaticVerdict(text="RELATED")
    build_semantic_edges(store, c2)
    assert len(c2.calls) == 0


def test_rebuild_edges_preserves_semantic(store):
    """rebuild_edges 가 rule edges 만 재구성, semantic 보존."""
    _seed(store, n=2, project="/p")
    build_semantic_edges(store, StaticVerdict(text="RELATED"))
    sem_before = store.conn.execute(
        "SELECT COUNT(*) FROM graph_edges WHERE relation='semantic_related'"
    ).fetchone()[0]
    assert sem_before == 1

    rebuild_edges(store)
    sem_after = store.conn.execute(
        "SELECT COUNT(*) FROM graph_edges WHERE relation='semantic_related'"
    ).fetchone()[0]
    assert sem_after == 1  # 보존
    rule_count = store.conn.execute(
        "SELECT COUNT(*) FROM graph_edges WHERE relation IN ('same_project','same_day','same_tool')"
    ).fetchone()[0]
    assert rule_count >= 1  # rebuild 로 rule edges 생성


def test_records_without_project_root_skipped(store):
    """project_root=NULL record 는 그룹화 대상 X."""
    store.record_call(
        tool_name="t", inputs={"q": "x"}, output="y",
        model="m", duration_ms=1, project_root=None,
    )
    store.record_call(
        tool_name="t", inputs={"q": "x"}, output="y",
        model="m", duration_ms=1, project_root=None,
    )
    c = StaticVerdict(text="RELATED")
    n = build_semantic_edges(store, c)
    assert n == 0
    assert len(c.calls) == 0

"""Phase 6-2 extract 단위 테스트."""

from __future__ import annotations

import numpy as np

from tunallama_core.memory.extract import (
    ExtractedEntry,
    extract_all,
    extract_antipatterns,
    extract_constraints,
    extract_conventions,
    extract_decisions,
    store_extracted_entries,
)
from tunallama_core.memory.state import (
    SECTION_ANTIPATTERNS,
    SECTION_CONSTRAINTS,
    SECTION_CONVENTIONS,
    SECTION_DECISIONS,
    StateFile,
)


def test_extract_decision_korean():
    text = "우리는 HyDE hybrid 를 production winner 로 채택하기로 했다."
    out = extract_decisions(text)
    assert len(out) >= 1
    assert any("HyDE" in e.text for e in out)


def test_extract_decision_english():
    text = "We will use BGE-M3 as the default embedding model."
    out = extract_decisions(text)
    assert any("BGE-M3" in e.text for e in out)


def test_extract_decision_chose_to():
    text = "After review, we chose to default to on_request instead of always."
    out = extract_decisions(text)
    assert any("on_request" in e.text or "default" in e.text.lower() for e in out)


def test_extract_convention_korean():
    text = "항상 MemoryStore 를 사용 (Store 는 deprecated)."
    out = extract_conventions(text)
    assert any("MemoryStore" in e.text for e in out)


def test_extract_constraint_korean():
    text = "절대 plugin 을 backend 에서 import 하지 마라."
    out = extract_constraints(text)
    assert any("plugin" in e.text.lower() for e in out)


def test_extract_constraint_english_never():
    text = "Never run destructive commands without confirmation."
    out = extract_constraints(text)
    assert any("destructive" in e.text.lower() for e in out)


def test_extract_antipattern_korean():
    text = "안티패턴: np.random 으로 점수 시뮬레이션."
    out = extract_antipatterns(text)
    assert any("np.random" in e.text for e in out)


def test_extract_antipattern_english_avoid():
    text = "Avoid: mocking the database in integration tests."
    out = extract_antipatterns(text)
    assert any("mocking" in e.text.lower() for e in out)


def test_extract_all_mixed():
    text = (
        "결정했다: HyDE 채택. "
        "절대 mock 사용하지 마라. "
        "안티패턴: standalone toy."
    )
    out = extract_all(text)
    kinds = {e.kind for e in out}
    assert "decision" in kinds
    assert "constraint" in kinds
    assert "antipattern" in kinds


def test_extract_skips_short_text():
    """text < 4 char 는 skip."""
    out = extract_decisions("우리는 ab 한다")  # text="ab" 짧음
    # 4 char 미만은 걸러져야.
    assert all(len(e.text) >= 4 for e in out)


def test_store_extracted_skips_low_confidence(tmp_path):
    s = StateFile(
        project_hash="abc", project_root="/tmp", last_updated="t",
        path=tmp_path / "state.md",
    )
    ex = ExtractedEntry(
        kind="decision", text="low confidence", confidence=0.3,
        source_excerpt="",
    )
    stored = store_extracted_entries(s, [ex], min_confidence=0.5)
    assert stored == []
    assert len(s.entries) == 0


def test_store_extracted_section_mapping(tmp_path):
    s = StateFile(
        project_hash="abc", project_root="/tmp", last_updated="t",
        path=tmp_path / "state.md",
    )
    entries = [
        ExtractedEntry(kind="decision", text="adopt HyDE", confidence=0.8, source_excerpt=""),
        ExtractedEntry(kind="convention", text="use MemoryStore", confidence=0.8, source_excerpt=""),
        ExtractedEntry(kind="constraint", text="no plugin imports in backend", confidence=0.8, source_excerpt=""),
        ExtractedEntry(kind="antipattern", text="np.random simulation", confidence=0.8, source_excerpt=""),
    ]
    stored = store_extracted_entries(s, entries)
    assert len(stored) == 4
    by_section = s.by_section
    assert any("HyDE" in e.text for e in by_section[SECTION_DECISIONS])
    assert any("MemoryStore" in e.text for e in by_section[SECTION_CONVENTIONS])
    assert any("plugin" in e.text for e in by_section[SECTION_CONSTRAINTS])
    assert any("np.random" in e.text for e in by_section[SECTION_ANTIPATTERNS])


def test_store_extracted_text_dedup_increments(tmp_path):
    s = StateFile(
        project_hash="abc", project_root="/tmp", last_updated="t",
        path=tmp_path / "state.md",
    )
    ex = ExtractedEntry(kind="decision", text="adopt HyDE", confidence=0.8, source_excerpt="")
    store_extracted_entries(s, [ex])
    store_extracted_entries(s, [ex])
    decisions = s.by_section[SECTION_DECISIONS]
    assert len(decisions) == 1
    assert decisions[0].occurrences == 2


def test_store_extracted_embedding_dedup(tmp_path):
    s = StateFile(
        project_hash="abc", project_root="/tmp", last_updated="t",
        path=tmp_path / "state.md",
    )
    # fake embedding: same length string → same vector → cos = 1.0.
    def fake_embed(text: str) -> np.ndarray:
        v = np.zeros(8, dtype=np.float32)
        v[len(text) % 8] = 1.0
        return v

    a = ExtractedEntry(kind="constraint", text="abcde", confidence=0.8, source_excerpt="")
    b = ExtractedEntry(kind="constraint", text="fghij", confidence=0.8, source_excerpt="")
    store_extracted_entries(s, [a], embedding_fn=fake_embed)
    store_extracted_entries(
        s, [b], embedding_fn=fake_embed,
        dedup_cosine_threshold=0.99,
    )
    # 같은 length=5 → 같은 fake vector → 1.0 cos → dedup hit.
    constraints = s.by_section[SECTION_CONSTRAINTS]
    assert len(constraints) == 1
    assert constraints[0].occurrences == 2


def test_clean_strips_quotes_and_truncates():
    """긴 매칭 자동 truncate + 양 끝 정리 (간접 검증)."""
    text = '결정했다: "use HyDE hybrid as default production-RAG path"'
    out = extract_decisions(text)
    assert any(
        '"' not in e.text and "HyDE" in e.text for e in out
    )

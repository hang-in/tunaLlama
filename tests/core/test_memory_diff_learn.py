"""Phase 6-3 diff_learn 단위 테스트."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


from tunallama_core.llm.base import ChatResponse, LLMClient
from tunallama_core.memory.diff_learn import (
    DiffRule,
    extract_rule_from_diff,
    rules_to_constraints,
)
from tunallama_core.memory.store import MemoryStore


@dataclass
class _FakeClient(LLMClient):
    response_text: str
    raise_exc: Exception | None = None

    def chat(self, *, system: str, prompt: str, response_schema: Any = None) -> ChatResponse:
        if self.raise_exc is not None:
            raise self.raise_exc
        return ChatResponse(text=self.response_text, model="fake", duration_ms=1)


def test_empty_inputs():
    assert extract_rule_from_diff("", "") == []
    assert extract_rule_from_diff("x", "") == []
    assert extract_rule_from_diff("same", "same") == []


def test_identifier_rename_store_to_memorystore():
    before = "from tunallama_core.store import Store\ns = Store(db)\n"
    after = "from tunallama_core.memory.store import MemoryStore\ns = MemoryStore(db)\n"
    rules = extract_rule_from_diff(before, after)
    # import 줄 변화 + identifier rename Store -> MemoryStore 둘 다 잡혀야.
    assert any(r.kind == "import_path" for r in rules)
    rename = next((r for r in rules if r.kind == "identifier_rename"), None)
    assert rename is not None
    assert rename.before == "Store" and rename.after == "MemoryStore"


def test_identifier_rename_camel_case():
    before = "result = getUserById(123)\n"
    after = "result = get_user_by_id(123)\n"
    rules = extract_rule_from_diff(before, after)
    rename = next((r for r in rules if r.kind == "identifier_rename"), None)
    assert rename is not None
    assert rename.before == "getUserById"
    assert rename.after == "get_user_by_id"


def test_short_identifier_filtered():
    """1-2 char 식별자는 noise 라 제외."""
    before = "x = 1\n"
    after = "y = 1\n"
    rules = extract_rule_from_diff(before, after)
    assert all(len(r.before) >= 3 for r in rules)


def test_multiple_identifier_changes_in_one_line_skipped():
    """한 줄에 두 개 이상 identifier 변경되면 ambiguous - skip."""
    before = "result = MyClass.method_a(x)\n"
    after = "outcome = TheirClass.method_b(y)\n"
    rules = extract_rule_from_diff(before, after)
    # 너무 많은 변화 - identifier_rename 안 잡힘 (count != 1).
    assert all(r.kind != "identifier_rename" for r in rules)


def test_import_change_detected():
    before = "from old.module import thing\nuse(thing)\n"
    after = "from new.module import thing\nuse(thing)\n"
    rules = extract_rule_from_diff(before, after)
    assert any(r.kind == "import_path" for r in rules)


def test_no_client_no_llm_fallback():
    """client=None 이면 rule-based 만."""
    before = "abc xyz\n"
    after = "def uvw\n"
    rules = extract_rule_from_diff(before, after, client=None)
    # rule-based 가 못 잡으면 빈 리스트.
    assert isinstance(rules, list)


def test_llm_fallback_parses_arrow_format():
    """LLM 이 'before -> after' 줄 출력하면 DiffRule 로 변환."""
    client = _FakeClient(
        response_text="oldname -> newname\nfoo.bar -> baz.qux\n"
    )
    before = "use oldname here\n"
    after = "use newname there\n"
    rules = extract_rule_from_diff(before, after, client=client)
    # LLM 응답에서 추가 rule 잡힘.
    llm_rules = [r for r in rules if r.kind == "llm_general"]
    assert any(r.before == "oldname" and r.after == "newname" for r in llm_rules)


def test_llm_fallback_silent_on_error():
    """LLM 실패해도 rule-based 결과는 보존."""
    client = _FakeClient(response_text="", raise_exc=RuntimeError("api down"))
    before = "from old import x\n"
    after = "from new import x\n"
    rules = extract_rule_from_diff(before, after, client=client)
    # rule-based 의 import_path 는 보존.
    assert any(r.kind == "import_path" for r in rules)


def test_dedup_same_rule_not_duplicated():
    before = "Store()\nStore()\nStore()\n"
    after = "MemoryStore()\nMemoryStore()\nMemoryStore()\n"
    rules = extract_rule_from_diff(before, after)
    rename_rules = [r for r in rules if r.kind == "identifier_rename"]
    pairs = {(r.before, r.after) for r in rename_rules}
    assert ("Store", "MemoryStore") in pairs
    # 동일 rule 중복 X.
    assert len(pairs) == len(rename_rules)


def test_as_state_text_identifier_rename():
    r = DiffRule(before="Store", after="MemoryStore", kind="identifier_rename", confidence=0.85)
    assert "Store" in r.as_state_text() and "MemoryStore" in r.as_state_text()


def test_rules_to_constraints():
    rules = [
        DiffRule(before="Store", after="MemoryStore", kind="identifier_rename", confidence=0.85),
        DiffRule(before="foo", after="bar", kind="llm_general", confidence=0.6),
    ]
    texts = rules_to_constraints(rules)
    assert len(texts) == 2


def test_target_file_path_record_and_retrieve(tmp_path):
    """store 의 target_file_path 컬럼 round-trip."""
    db = tmp_path / "tfp.db"
    store = MemoryStore(db, korean_tokenizer="kiwi", enable_embeddings=False).open()
    cid = store.record_call(
        tool_name="generate_code", inputs={"requirements": "x"},
        output="def x(): pass", model="test", duration_ms=1,
        target_file_path="/tmp/foo.py",
    )
    assert store.get_target_file_path(cid) == "/tmp/foo.py"
    store.set_target_file_path(cid, "/tmp/bar.py")
    assert store.get_target_file_path(cid) == "/tmp/bar.py"
    store.close()


def test_target_file_path_migration_on_old_db(tmp_path):
    """target_file_path 컬럼 없는 옛 db 로딩 시 자동 ALTER 추가."""
    import sqlite3
    db = tmp_path / "old.db"
    # legacy schema 모방 - target_file_path 컬럼 없이 calls 테이블 생성.
    conn = sqlite3.connect(str(db))
    conn.execute(
        """
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
        )
        """
    )
    conn.commit()
    conn.close()
    store = MemoryStore(db, korean_tokenizer="kiwi", enable_embeddings=False).open()
    # target_file_path 컬럼이 자동 추가됐는지 record_call 로 검증.
    cid = store.record_call(
        tool_name="x", inputs={}, output="o", model="m", duration_ms=1,
        target_file_path="/tmp/auto.py",
    )
    assert store.get_target_file_path(cid) == "/tmp/auto.py"
    store.close()

"""dev_review_loop 단위 테스트 — StaticClient 시퀀스로 시나리오 시뮬레이션."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from tunallama_core.llm.base import ChatResponse, LLMClient
from tunallama_core.memory.store import MemoryStore
from tunallama_core.workflow.dev_review import (
    DevReviewResult,
    dev_review_from_spec,
    dev_review_loop,
)


@dataclass
class ScriptedClient(LLMClient):
    """미리 준비한 응답을 순서대로 돌려주는 fake client."""

    responses: list[str] = field(default_factory=list)
    seen: list[str] = field(default_factory=list)

    def chat(self, *, system: str, prompt: str) -> ChatResponse:
        self.seen.append(prompt)
        text = self.responses.pop(0) if self.responses else "ok"
        return ChatResponse(text=text, model="fake", duration_ms=1)


def test_converges_when_review_says_lgtm():
    c = ScriptedClient(responses=["def f(): pass", "LGTM"])
    r = dev_review_loop("write f", client=c, max_iterations=3)
    assert r.converged is True
    assert len(r.iterations) == 1
    assert r.final_code == "def f(): pass"


def test_iterates_until_max_when_no_lgtm():
    c = ScriptedClient(
        responses=[
            "def f(): pass",     # 1) generate
            "needs docstring",   # 2) review #1 → issues
            "def f():\n  '''d'''", # 3) fix #1
            "still bad",         # 4) review #2 → issues
        ]
    )
    r = dev_review_loop("write f", client=c, max_iterations=2)
    assert r.converged is False
    assert len(r.iterations) == 2
    assert r.final_code == "def f():\n  '''d'''"


def test_korean_lgtm_marker_recognized():
    c = ScriptedClient(responses=["code", "이상 없음"])
    r = dev_review_loop("write f", client=c)
    assert r.converged is True


def test_max_iterations_must_be_positive():
    c = ScriptedClient(responses=["x"])
    with pytest.raises(ValueError):
        dev_review_loop("x", client=c, max_iterations=0)


def test_records_all_calls_to_store(tmp_path):
    """generate + review (+ fix + review) 모두 store 에 기록."""
    c = ScriptedClient(responses=["code", "issues", "fixed", "LGTM"])
    with MemoryStore(tmp_path / "m.db") as store:
        r = dev_review_loop("x", client=c, store=store, max_iterations=2)
        # generate(1) + review(2) + fix(3) + review(4) = 4 records
        assert store.count() == 4
    assert r.converged is True
    assert r.final_code == "fixed"


def test_limitations_prepended_to_initial_prompt(tmp_path, monkeypatch):
    lim = tmp_path / "lim.md"
    lim.write_text("# Limitations\n- avoid lambda\n", encoding="utf-8")
    c = ScriptedClient(responses=["code", "LGTM"])
    dev_review_loop(
        "write a thing",
        client=c,
        max_iterations=1,
        limitations_path=lim,
    )
    # 첫 호출(generate) prompt 에 limitations 섹션 포함되어야
    assert "Known limitations" in c.seen[0]
    assert "avoid lambda" in c.seen[0]


def test_summary_includes_iterations_and_final_code():
    c = ScriptedClient(responses=["code-v1", "needs work", "code-v2", "LGTM"])
    r = dev_review_loop("x", client=c, max_iterations=2)
    s = r.summary()
    assert "2 회 반복" in s
    assert "수렴" in s
    assert "code-v2" in s
    assert "needs work" in s


def test_dev_review_from_spec(tmp_path):
    spec = tmp_path / "spec.md"
    spec.write_text(
        "# Task: build f\n## Requirements\n- pure stdlib\n",
        encoding="utf-8",
    )
    c = ScriptedClient(responses=["def f(): pass", "LGTM"])
    r = dev_review_from_spec(spec, client=c, max_iterations=1)
    assert r.converged is True
    # spec 의 title/requirements 가 prompt 에 들어갔는지
    assert "build f" in c.seen[0]
    assert "pure stdlib" in c.seen[0]


def test_dev_review_from_spec_missing_file(tmp_path):
    c = ScriptedClient()
    with pytest.raises(FileNotFoundError):
        dev_review_from_spec(tmp_path / "nope.md", client=c)


def test_iteration_result_records_review_text():
    c = ScriptedClient(responses=["code", "found a bug", "code-v2", "LGTM"])
    r = dev_review_loop("x", client=c, max_iterations=2)
    assert r.iterations[0].issues_found is True
    assert r.iterations[0].review == "found a bug"
    assert r.iterations[1].issues_found is False

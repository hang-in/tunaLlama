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

    def chat(
        self,
        *,
        system: str,
        prompt: str,
        response_schema: dict | None = None,
    ) -> ChatResponse:
        # classifier 호출(stage-2 verdict) 은 응답 큐 소비하지 않고 자동 분기 — 시나리오
        # 의 의도(fix 응답이 review 다음 호출로 가는 것)를 보존.
        if "PASS or FAIL" in system:
            rl = prompt.lower()
            # VERDICT 라벨 우선
            if "verdict: pass" in rl:
                return ChatResponse(text="PASS", model="fake-cls", duration_ms=1)
            if "verdict: fail" in rl:
                return ChatResponse(text="FAIL", model="fake-cls", duration_ms=1)
            if any(t in rl for t in (
                "lgtm", "looks good", "이상 없음", "no issues", "no problems",
                "no real issue",
            )):
                return ChatResponse(text="PASS", model="fake-cls", duration_ms=1)
            return ChatResponse(text="FAIL", model="fake-cls", duration_ms=1)
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


def test_verdict_pass_converges_immediately():
    """VERDICT: PASS 첫 줄이 있으면 본문에 단점 나열이 있어도 수렴."""
    c = ScriptedClient(
        responses=[
            "code",
            "VERDICT: PASS\n- minor style note: prefer f-string\n- could add docstring",
        ]
    )
    r = dev_review_loop("write f", client=c, max_iterations=3)
    assert r.converged is True
    assert len(r.iterations) == 1


def test_verdict_fail_drives_fix_loop():
    c = ScriptedClient(
        responses=[
            "code-v1",
            "VERDICT: FAIL\n- bug: returns wrong type",
            "code-v2",
            "VERDICT: PASS\n- looks fine",
        ]
    )
    r = dev_review_loop("write f", client=c, max_iterations=2)
    assert r.converged is True
    assert len(r.iterations) == 2
    assert r.final_code == "code-v2"


def test_verdict_pass_overrides_fp_heuristic():
    """모델이 PASS 라 했으니 본문의 'issue' 라는 단어 때문에 잘못 fix 루프 들어가면 안 됨."""
    c = ScriptedClient(
        responses=[
            "code",
            "VERDICT: PASS\n- I see no real issue here, just formatting suggestions",
        ]
    )
    r = dev_review_loop("x", client=c)
    assert r.converged is True


def test_no_verdict_falls_back_to_lgtm_heuristic():
    """VERDICT 라벨 미작성 → 기존 heuristic 그대로 동작."""
    c = ScriptedClient(responses=["code", "looks good to me"])
    r = dev_review_loop("x", client=c)
    assert r.converged is True


def test_no_verdict_and_no_lgtm_treated_as_issues():
    c = ScriptedClient(
        responses=["code-v1", "needs work", "code-v2", "still bad"]
    )
    r = dev_review_loop("x", client=c, max_iterations=2)
    assert r.converged is False
    assert len(r.iterations) == 2


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


def test_routing_auto_recall_prepends_to_all_steps(tmp_path):
    """routing 이 주어지면 generate/review/(fix) 모두 같은 recall context 받음."""
    from tunallama_core.config.models import RoutingConfig

    c = ScriptedClient(responses=["code-v1", "needs work", "code-v2", "LGTM"])
    with MemoryStore(tmp_path / "m.db") as store:
        # 사전 호출 — 이후 검색에 잡힐 record 미리 적재
        store.record_call(
            tool_name="generate_code",
            inputs={"requirements": "validate email"},
            output="def is_valid_email(): ...",
            model="m",
            duration_ms=1,
        )
        dev_review_loop(
            "validate email addresses",
            client=c,
            store=store,
            max_iterations=2,
            routing=RoutingConfig(auto_recall="always"),
        )
    # generate(0) + review#1(1) + fix#1(2) + review#2(3) — 모두 4개 prompt 에 recall 포함
    for i, p in enumerate(c.seen):
        assert "과거 관련 작업" in p, f"step {i} 에 recall context 없음"


def test_routing_never_means_no_recall_prefix(tmp_path):
    from tunallama_core.config.models import RoutingConfig

    c = ScriptedClient(responses=["code", "LGTM"])
    with MemoryStore(tmp_path / "m.db") as store:
        store.record_call(
            tool_name="generate_code",
            inputs={"requirements": "anything"},
            output="prior",
            model="m",
            duration_ms=1,
        )
        dev_review_loop(
            "do thing",
            client=c,
            store=store,
            routing=RoutingConfig(auto_recall="never"),
        )
    for p in c.seen:
        assert "과거 관련 작업" not in p


def test_iteration_result_records_review_text():
    c = ScriptedClient(responses=["code", "found a bug", "code-v2", "LGTM"])
    r = dev_review_loop("x", client=c, max_iterations=2)
    assert r.iterations[0].issues_found is True
    assert r.iterations[0].review == "found a bug"
    assert r.iterations[1].issues_found is False

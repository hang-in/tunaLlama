"""dev → review → fix → review 자동 루프.

architect 가 한 번 호출하면 backend 가 generate → review → 이슈 있으면 fix →
다시 review 를 ``max_iterations`` 까지 반복. 각 호출은 메모리에도 기록되어
나중에 ``tuna_recall`` 로 추적 가능.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from ..config.models import RoutingConfig
from ..delegation import fix_code, generate_code
from ..delegation._prompts import REVIEW_CODE
from ..delegation._runner import run_delegation
from ..llm.base import LLMClient
from ..memory.store import MemoryStore
from ..routing import recall_for_delegation
from .limitations import with_limitations
from .spec import TaskSpec, parse_spec_file

_VERDICT_PASS_RE = re.compile(r"^\s*VERDICT\s*:\s*PASS\b", re.IGNORECASE | re.MULTILINE)
_VERDICT_FAIL_RE = re.compile(r"^\s*VERDICT\s*:\s*FAIL\b", re.IGNORECASE | re.MULTILINE)
_VERDICT_WORD_RE = re.compile(r"\b(PASS|FAIL)\b", re.IGNORECASE)

# Stage-2 classifier — review 본문을 받아 단일 토큰(PASS/FAIL)을 받는 별도 LLM 호출.
# round 6 dogfooding 결과 cloud `format=` schema 가 무시됨이 확인됨. 단일 토큰 출력은
# 모든 모델이 안정적으로 따름이 측정됨 (gemma4:31b / kimi-k2-thinking / qwen3-coder-next /
# devstral-small-2:24b 모두 strict prompt 에서 PASS/FAIL 정확 출력).
_CLASSIFIER_SYS = "You output one token: PASS or FAIL. Nothing else."
_CLASSIFIER_USER_TMPL = (
    "Below is a code review. Decide whether the code under review must be "
    "CHANGED to fix a defect.\n\n"
    "Review:\n---\n{review}\n---\n\n"
    "Output rules — strict:\n"
    "- PASS if the review only mentions: redundant-but-correct code, "
    "version-compatibility notes, style preferences, optional improvements, "
    "type-hint suggestions, or things that 'could be' better.\n"
    "- FAIL only if the review explicitly says the code has a bug, returns "
    "wrong output, fails an edge case, has a security flaw, or violates a "
    "stated requirement.\n\n"
    "Respond with exactly one token: PASS or FAIL."
)

# Provider-native JSON Schema 강제용. Ollama format= / LM Studio response_format.json_schema.
# round 1-5 dogfooding 결과 자연어 명령으로는 review 형식 강제가 안 되어 sampling-time
# enforcement 가 필요. ``additionalProperties: false`` 로 strict 모드 호환.
REVIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {
            "type": "string",
            "enum": ["PASS", "FAIL"],
            "description": "PASS = no concrete bug or correctness issue. FAIL = at least one defect.",
        },
        "findings": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Concise issue descriptions. Empty for PASS is allowed.",
        },
    },
    "required": ["verdict", "findings"],
    "additionalProperties": False,
}

_LGTM_TOKENS = (
    "lgtm",
    "no issues",
    "no problems",
    "looks good",
    "문제 없음",
    "이상 없음",
    "이슈 없음",
)


@dataclass(frozen=True)
class IterationResult:
    iteration: int
    code: str
    review: str
    issues_found: bool


@dataclass(frozen=True)
class DevReviewResult:
    final_code: str
    iterations: tuple[IterationResult, ...]
    converged: bool

    def summary(self) -> str:
        last = self.iterations[-1] if self.iterations else None
        final_verdict = (
            "PASS" if (last and not last.issues_found) else "FAIL"
        )
        head = (
            f"=== dev_review · {final_verdict} · "
            f"{len(self.iterations)} 회 반복 "
            f"({'수렴' if self.converged else '한도 도달'}) ==="
        )
        lines = [head]
        for it in self.iterations:
            verdict = "PASS" if not it.issues_found else "FAIL"
            lines.append(f"\n[#{it.iteration}] verdict={verdict}")
            lines.append("Review:")
            lines.append(it.review)
        lines.append("\n=== 최종 코드 ===")
        lines.append(self.final_code)
        return "\n".join(lines)


def _verdict_from_json(text: str) -> bool | None:
    """JSON Schema 응답에서 verdict 추출. 실패 시 None — 호출자가 다른 fallback."""
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None
    v = data.get("verdict") if isinstance(data, dict) else None
    if isinstance(v, str):
        if v.upper() == "PASS":
            return False
        if v.upper() == "FAIL":
            return True
    return None


def _classify_verdict(client: LLMClient, review: str) -> bool | None:
    """Stage-2 classifier — review 본문을 별도 LLM 호출로 PASS/FAIL 분류.

    실패 시 None — 호출자가 다른 fallback. 호출 자체가 예외를 던지면 안전하게
    None 으로 흡수 (verdict heuristic 으로 fallback 되도록).
    """
    try:
        resp = client.chat(
            system=_CLASSIFIER_SYS,
            prompt=_CLASSIFIER_USER_TMPL.format(review=review),
        )
    except Exception:
        return None
    m = _VERDICT_WORD_RE.search(resp.text or "")
    if not m:
        return None
    return m.group(1).upper() == "FAIL"


def _decide_issues(client: LLMClient, review: str) -> bool:
    """수렴 판정 — 4 layer fallback.

    1) JSON ``{"verdict": "PASS"|"FAIL", ...}`` — schema 강제 작동 시.
    2) 단일 토큰 classifier (별도 LLM 호출). 실 환경에서 가장 신뢰성 높음.
    3) 본문의 ``VERDICT: PASS|FAIL`` 라벨 (자연어 강제 작동 시).
    4) LGTM/이상 없음 heuristic (last resort).
    """
    j = _verdict_from_json(review)
    if j is not None:
        return j
    c = _classify_verdict(client, review)
    if c is not None:
        return c
    if _VERDICT_PASS_RE.search(review):
        return False
    if _VERDICT_FAIL_RE.search(review):
        return True
    low = review.lower()
    return not any(t in low for t in _LGTM_TOKENS)


def _has_issues(review: str) -> bool:
    """Legacy 단순 verdict — schema/heuristic 만 (LLM 호출 없음).

    classifier 가 없는 단위 테스트나 backend 단독 호출자에 사용.
    실서비스 흐름은 ``_decide_issues`` 사용.
    """
    j = _verdict_from_json(review)
    if j is not None:
        return j
    if _VERDICT_PASS_RE.search(review):
        return False
    if _VERDICT_FAIL_RE.search(review):
        return True
    low = review.lower()
    return not any(t in low for t in _LGTM_TOKENS)


def _format_review_for_log(review: str) -> str:
    """JSON 응답을 사람 읽기 좋은 형식으로 변환. JSON 아니면 그대로."""
    try:
        data = json.loads(review)
    except (json.JSONDecodeError, TypeError):
        return review
    if not isinstance(data, dict) or "verdict" not in data:
        return review
    lines = [f"VERDICT: {data['verdict']}"]
    for f in data.get("findings", []) or []:
        lines.append(f"- {f}")
    return "\n".join(lines)


def _build_recall_prefix(
    routing: RoutingConfig | None,
    store: MemoryStore | None,
    *,
    fallback_query: str,
    project_root: str | None,
) -> str | None:
    if routing is None or store is None:
        return None
    rec = recall_for_delegation(
        routing,
        store,
        explicit_query=None,
        fallback_query=fallback_query,
        project_root=project_root,
    )
    if rec is None:
        return None
    block = rec.to_prompt_block()
    return block or None


def dev_review_loop(
    requirements: str,
    *,
    language: str | None = None,
    client: LLMClient,
    store: MemoryStore | None = None,
    project_root: str | None = None,
    session_id: str | None = None,
    max_iterations: int = 2,
    review_focus: str | None = None,
    limitations_path: Path | str | None = None,
    routing: RoutingConfig | None = None,
) -> DevReviewResult:
    """generate → review → (fix → review) 반복.

    requirements 앞에 ``limitations.md`` 카탈로그가 자동 prepend 된다.
    ``routing`` 이 주어지면 모든 단계에 auto_recall context 도 prepend.
    """
    if max_iterations <= 0:
        raise ValueError("max_iterations 는 양수여야 합니다.")

    full_req = with_limitations(requirements, path=limitations_path)
    recall_prefix = _build_recall_prefix(
        routing, store, fallback_query=requirements, project_root=project_root
    )

    gen = generate_code(
        full_req,
        language=language,
        client=client,
        store=store,
        project_root=project_root,
        session_id=session_id,
        recall_prefix=recall_prefix,
    )
    code = gen.text

    iterations: list[IterationResult] = []
    for i in range(1, max_iterations + 1):
        # review 단계는 _runner 직접 호출 — REVIEW_SCHEMA 를 강제해 sampling 단계
        # 에서 JSON 형식을 보장. review_code 도구는 freeform 그대로 유지(단독 호출자
        # UX 변경 없음).
        review_user = (
            f"Focus: {review_focus}\n\n```\n{code}\n```"
            if review_focus
            else f"```\n{code}\n```"
        )
        rev = run_delegation(
            client=client,
            tool_name="review_code",
            system_prompt=REVIEW_CODE,
            user_prompt=review_user,
            inputs_for_log={"code": code, "focus": review_focus},
            store=store,
            project_root=project_root,
            session_id=session_id,
            recall_prefix=recall_prefix,
            response_schema=REVIEW_SCHEMA,
        )
        issues = _decide_issues(client, rev.text)
        iterations.append(
            IterationResult(
                iteration=i,
                code=code,
                review=_format_review_for_log(rev.text),
                issues_found=issues,
            )
        )
        if not issues:
            return DevReviewResult(
                final_code=code, iterations=tuple(iterations), converged=True
            )
        if i == max_iterations:
            break
        # JSON review 를 fix_code 에 그대로 넘기면 모델이 schema 까지 따라하려 하므로
        # human-readable 형식으로 변환해 전달.
        fix = fix_code(
            code,
            _format_review_for_log(rev.text),
            client=client,
            store=store,
            project_root=project_root,
            session_id=session_id,
            recall_prefix=recall_prefix,
        )
        code = fix.text

    return DevReviewResult(
        final_code=code, iterations=tuple(iterations), converged=False
    )


def dev_review_from_spec(
    spec_path: Path | str,
    *,
    client: LLMClient,
    store: MemoryStore | None = None,
    project_root: str | None = None,
    session_id: str | None = None,
    max_iterations: int = 2,
    review_focus: str | None = None,
    limitations_path: Path | str | None = None,
    routing: RoutingConfig | None = None,
) -> DevReviewResult:
    """markdown spec 파일을 읽어 ``dev_review_loop`` 실행."""
    spec: TaskSpec = parse_spec_file(spec_path)
    return dev_review_loop(
        spec.to_prompt(),
        client=client,
        store=store,
        project_root=project_root,
        session_id=session_id,
        max_iterations=max_iterations,
        review_focus=review_focus,
        limitations_path=limitations_path,
        routing=routing,
    )

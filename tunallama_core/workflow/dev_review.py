"""dev → review → fix → review 자동 루프.

architect 가 한 번 호출하면 backend 가 generate → review → 이슈 있으면 fix →
다시 review 를 ``max_iterations`` 까지 반복. 각 호출은 메모리에도 기록되어
나중에 ``tuna_recall`` 로 추적 가능.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..delegation import fix_code, generate_code, review_code
from ..llm.base import LLMClient
from ..memory.store import MemoryStore
from .limitations import with_limitations
from .spec import TaskSpec, parse_spec_file

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
        head = (
            f"=== dev_review ({len(self.iterations)} 회 반복, "
            f"{'수렴' if self.converged else '한도 도달'}) ==="
        )
        lines = [head]
        for it in self.iterations:
            lines.append(f"\n[#{it.iteration}] issues_found={it.issues_found}")
            lines.append("Review:")
            lines.append(it.review)
        lines.append("\n=== 최종 코드 ===")
        lines.append(self.final_code)
        return "\n".join(lines)


def _has_issues(review: str) -> bool:
    """heuristic: review 가 LGTM 류 단어로 종결되지 않으면 issues 있다고 본다."""
    low = review.lower()
    return not any(t in low for t in _LGTM_TOKENS)


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
) -> DevReviewResult:
    """generate → review → (fix → review) 반복.

    requirements 앞에 ``limitations.md`` 카탈로그가 자동 prepend 된다.
    """
    if max_iterations <= 0:
        raise ValueError("max_iterations 는 양수여야 합니다.")

    full_req = with_limitations(requirements, path=limitations_path)

    gen = generate_code(
        full_req,
        language=language,
        client=client,
        store=store,
        project_root=project_root,
        session_id=session_id,
    )
    code = gen.text

    iterations: list[IterationResult] = []
    for i in range(1, max_iterations + 1):
        rev = review_code(
            code,
            focus=review_focus,
            client=client,
            store=store,
            project_root=project_root,
            session_id=session_id,
        )
        issues = _has_issues(rev.text)
        iterations.append(
            IterationResult(iteration=i, code=code, review=rev.text, issues_found=issues)
        )
        if not issues:
            return DevReviewResult(
                final_code=code, iterations=tuple(iterations), converged=True
            )
        if i == max_iterations:
            break
        fix = fix_code(
            code,
            rev.text,
            client=client,
            store=store,
            project_root=project_root,
            session_id=session_id,
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
    )

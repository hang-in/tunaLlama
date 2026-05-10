"""Phase 6-4 - memory layer 자동화 metrics.

handoff §7 + 외부 정정 반영:
- 절대 threshold 미리 X. trend over time + 합성 / spec_dogfooding / organic
  source tag 분리 트래킹.

metric 4 종 + source tag.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ..memory.state import (
    SECTION_ANTIPATTERNS,
    SECTION_CONSTRAINTS,
    SECTION_CONVENTIONS,
    StateFile,
)
from .ast_smell import analyze_ast

Source = Literal["synthetic", "spec_dogfooding", "organic"]


@dataclass(frozen=True)
class MetricSample:
    metric: str
    value: float
    source: Source
    timestamp: str
    n: int = 1


@dataclass(frozen=True)
class ConventionResult:
    """convention 별 adherence rate."""
    convention_text: str
    n_total: int
    n_honored: int

    @property
    def rate(self) -> float:
        return self.n_honored / self.n_total if self.n_total else 0.0


def convention_adherence_rate(
    state: StateFile,
    outputs: list[str],
) -> list[ConventionResult]:
    """state.md 의 Conventions 각각이 ``outputs`` 에서 honor 된 비율.

    naive heuristic: convention 의 "use X" / "import X" 패턴에서 X 를 추출 →
    output 에 X 가 등장하면 honored.

    실제 production 측정은 AST + regex 조합으로 더 정밀하게 가능. 본 함수는
    starting baseline.
    """
    import re

    conventions = state.by_section.get(SECTION_CONVENTIONS, [])
    results: list[ConventionResult] = []
    # convention text 에서 inspect 할 토큰 추출.
    TOKEN_RE = re.compile(r"`([^`]+)`|([A-Za-z_][A-Za-z0-9_.]+)")
    for conv in conventions:
        # backtick 안의 텍스트 우선, 없으면 첫 식별자.
        m_list = TOKEN_RE.findall(conv.text)
        tokens = [bt or pl for bt, pl in m_list if bt or pl]
        # 일반 영문 단어 (use / import / always) 제외.
        STOP = {"use", "import", "from", "always", "never", "must", "should"}
        tokens = [t for t in tokens if t.lower() not in STOP]
        if not tokens:
            continue
        target = tokens[0]  # 첫 의미 토큰을 anchor 로.
        n_total = len(outputs)
        n_honored = sum(1 for o in outputs if target in o)
        results.append(ConventionResult(
            convention_text=conv.text,
            n_total=n_total, n_honored=n_honored,
        ))
    return results


def standalone_toy_rate(
    outputs: list[str],
    *,
    unrelated_keywords: list[str] | None = None,
) -> float:
    """``outputs`` 의 standalone-toy 비율.

    heuristic (deterministic):
    - syntax error → toy.
    - mock 키워드 출현 (``Mock``, ``MagicMock``, ``patch``) → toy.
    - ``np.random``, ``random.uniform`` → toy (가짜 시뮬레이션 패턴).
    - import 없는데 외부 호출만 있는 minimal stub → not flagged here
      (사람 판단 필요).

    return: 0.0-1.0 비율. outputs 비어있으면 0.0.
    """
    if not outputs:
        return 0.0

    MOCK_PATTERNS = ("Mock(", "MagicMock", "patch(", "mock.patch")
    FAKE_SIM_PATTERNS = ("np.random.uniform", "np.random.choice", "random.uniform")

    n_toy = 0
    for code in outputs:
        smell = analyze_ast(
            code, unrelated_keywords=unrelated_keywords or [],
        )
        is_toy = False
        if not smell.syntactically_valid:
            is_toy = True
        elif any(p in code for p in MOCK_PATTERNS):
            is_toy = True
        elif any(p in code for p in FAKE_SIM_PATTERNS):
            is_toy = True
        elif smell.unrelated_keyword_hits:
            is_toy = True
        if is_toy:
            n_toy += 1
    return n_toy / len(outputs)


@dataclass(frozen=True)
class InterventionRecord:
    """call 1개 + 사용자 수정 여부."""
    call_id: int
    target_file_path: str | None
    intervention_severity: float  # 0.0 (no change) - 1.0 (rewrite)


def user_intervention_rate(records: list[InterventionRecord]) -> float:
    """target_file 의 현재 내용 vs LLM 출력 차이 평균 severity.

    severity 는 caller 가 계산 (e.g. difflib ratio 1 - similarity). 본 함수는
    평균만.
    """
    if not records:
        return 0.0
    return sum(r.intervention_severity for r in records) / len(records)


@dataclass(frozen=True)
class StateRecallProbe:
    """state.md 의 convention/constraint 에 대해 Claude/모델이 답한 결과."""
    target_text: str
    response_text: str
    matched: bool


def state_recall_rate(probes: list[StateRecallProbe]) -> float:
    """state.md 가 실제 context 도달했는지 확인용 probe."""
    if not probes:
        return 0.0
    return sum(1 for p in probes if p.matched) / len(probes)

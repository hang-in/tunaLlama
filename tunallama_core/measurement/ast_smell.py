"""정적 코드 분석 metric. judge LLM 의 noise 회피용 deterministic 신호.

context pollution 측정 (Phase 5-3) 의 핵심 도구. always vs never 비교 시
LLM judge 보다 먼저 본다.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class CodeSmell:
    """정적 분석 결과. 모든 필드 deterministic."""
    n_imports: int = 0
    n_funcs: int = 0
    n_classes: int = 0
    n_lines: int = 0
    unrelated_keyword_hits: tuple[str, ...] = field(default_factory=tuple)
    syntactically_valid: bool = True
    parse_error: str | None = None

    @property
    def excess_score(self) -> int:
        """과다 abstraction / 무관 코드의 종합 점수. 낮을수록 깨끗.

        - import 1 개 = 1 점, func 2 개 이상부터 1 점, class 1 개 = 2 점
        - unrelated keyword 1 개 = 3 점
        - syntax error = 10 점
        """
        score = 0
        score += max(0, self.n_imports)
        score += max(0, self.n_funcs - 1)  # main 함수 1개는 OK
        score += self.n_classes * 2
        score += len(self.unrelated_keyword_hits) * 3
        if not self.syntactically_valid:
            score += 10
        return score


_CODE_FENCE_RE = re.compile(r"^```(?:python|py)?\s*\n", re.MULTILINE)
_CODE_FENCE_END_RE = re.compile(r"\n```\s*$", re.MULTILINE)


def _strip_code_fences(code: str) -> str:
    """LLM 응답이 ```python ... ``` 로 wrap 됐으면 제거."""
    code = code.strip()
    code = _CODE_FENCE_RE.sub("", code)
    code = _CODE_FENCE_END_RE.sub("", code)
    return code.strip()


def analyze_ast(
    code: str, *, unrelated_keywords: list[str] | tuple[str, ...] = ()
) -> CodeSmell:
    """code 의 정적 분석.

    ``unrelated_keywords`` 는 task 와 무관해야 할 키워드 list. 출현하면
    pollution 시그널.
    """
    if not code or not code.strip():
        return CodeSmell(syntactically_valid=False, parse_error="empty")

    stripped = _strip_code_fences(code)
    n_lines = len(stripped.splitlines())

    # syntax 검사
    try:
        tree = ast.parse(stripped)
    except SyntaxError as e:
        return CodeSmell(
            n_lines=n_lines,
            syntactically_valid=False,
            parse_error=f"{type(e).__name__}: {e.msg}",
        )

    n_imports = 0
    n_funcs = 0
    n_classes = 0
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            n_imports += 1
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            n_funcs += 1
        elif isinstance(node, ast.ClassDef):
            n_classes += 1

    # 무관 키워드 검사 - 대소문자 무관, word boundary
    code_lower = stripped.lower()
    hits: list[str] = []
    for kw in unrelated_keywords:
        if not kw:
            continue
        # word boundary 로 정확 매칭 (substring 회피).
        pattern = r"\b" + re.escape(kw.lower()) + r"\b"
        if re.search(pattern, code_lower):
            hits.append(kw)

    return CodeSmell(
        n_imports=n_imports,
        n_funcs=n_funcs,
        n_classes=n_classes,
        n_lines=n_lines,
        unrelated_keyword_hits=tuple(hits),
        syntactically_valid=True,
    )

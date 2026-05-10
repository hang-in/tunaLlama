"""Phase 6-3 - diff-based learning.

사용자가 LLM 위임 결과를 수정 → 그 diff 가 강한 학습 신호. before (LLM output)
vs after (현재 file 내용) 비교 → 일관된 substitution 패턴 추출 → state.md 의
Constraints / Anti-patterns 후보.

두 경로:
1. **rule-based**: identifier substitution (e.g. ``Store -> MemoryStore``).
   결정적 / 빠름 / cloud 의존 X.
2. **LLM-based** (옵션): 더 복잡한 rewrite. ``client`` 가 주어지면 호출.
   **state.md 미주입 모델** 권장 (dependency loop 회피).
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass
from typing import Iterable

from ..llm.base import LLMClient


@dataclass(frozen=True)
class DiffRule:
    """diff 에서 추출된 substitution rule."""
    before: str
    after: str
    kind: str  # "identifier_rename" | "api_signature" | "import_path" | "llm_general"
    confidence: float  # 0.0 - 1.0

    def as_state_text(self) -> str:
        if self.kind == "identifier_rename":
            return f"`{self.before}` X, `{self.after}` O"
        if self.kind == "import_path":
            return f"use `{self.after}` (not `{self.before}`)"
        return f"{self.before} -> {self.after}"


_IDENT_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\b")
_IMPORT_RE = re.compile(r"^(?:from|import)\s+\S+", re.MULTILINE)


def _line_diff(before: str, after: str) -> list[tuple[str, str]]:
    """SequenceMatcher 로 ``(before_line, after_line)`` 1:1 substitution 만 추출."""
    out: list[tuple[str, str]] = []
    sm = difflib.SequenceMatcher(
        a=before.splitlines(), b=after.splitlines(), autojunk=False,
    )
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag != "replace":
            continue
        # 같은 길이의 replace block 만 1:1 매칭 (안전).
        if (i2 - i1) != (j2 - j1):
            continue
        for k in range(i2 - i1):
            b_line = before.splitlines()[i1 + k].strip()
            a_line = after.splitlines()[j1 + k].strip()
            if b_line and a_line and b_line != a_line:
                out.append((b_line, a_line))
    return out


def _detect_identifier_rename(b_line: str, a_line: str) -> DiffRule | None:
    """한 줄에서 정확히 하나의 identifier 만 다르고 나머지는 동일하면 rename."""
    b_idents = _IDENT_RE.findall(b_line)
    a_idents = _IDENT_RE.findall(a_line)
    if len(b_idents) != len(a_idents):
        return None
    diffs: list[tuple[str, str]] = []
    for b_id, a_id in zip(b_idents, a_idents):
        if b_id != a_id:
            diffs.append((b_id, a_id))
    if len(diffs) != 1:
        return None
    b_id, a_id = diffs[0]
    # placeholder 위치를 동일 문자열로 치환했을 때 라인이 같으면 OK.
    re_pattern = re.compile(r"\b" + re.escape(b_id) + r"\b")
    if re_pattern.sub(a_id, b_line).strip() != a_line:
        return None
    # 짧은 식별자 (a/b/x 같은) 제외.
    if len(b_id) < 3 or len(a_id) < 3:
        return None
    return DiffRule(
        before=b_id, after=a_id, kind="identifier_rename", confidence=0.85,
    )


def _detect_import_change(b_line: str, a_line: str) -> DiffRule | None:
    """import 한 줄의 module path 만 변한 경우."""
    if not (_IMPORT_RE.match(b_line) and _IMPORT_RE.match(a_line)):
        return None
    if b_line == a_line:
        return None
    return DiffRule(
        before=b_line, after=a_line, kind="import_path", confidence=0.8,
    )


def extract_rule_from_diff(
    before: str, after: str, *, client: LLMClient | None = None,
) -> list[DiffRule]:
    """rule-based 우선 (cloud 0). client 가 주어지면 미커버 라인 옵션 LLM 호출.

    return: list - 한 diff 에서 여러 rule 추출 가능.
    """
    if not before or not after or before == after:
        return []
    rules: list[DiffRule] = []
    seen_pairs: set[tuple[str, str]] = set()

    pairs = _line_diff(before, after)
    for b_line, a_line in pairs:
        rule = _detect_import_change(b_line, a_line)
        if rule is None:
            rule = _detect_identifier_rename(b_line, a_line)
        if rule is None:
            continue
        key = (rule.before, rule.after)
        if key in seen_pairs:
            continue
        seen_pairs.add(key)
        rules.append(rule)

    if client is None or not pairs:
        return rules

    # LLM-based fallback: rule-based 가 못 잡은 (b, a) pair 있으면 일괄 query.
    uncovered = [
        (b, a) for b, a in pairs
        if not any(rule.before in b or rule.before in a for rule in rules)
    ]
    if not uncovered:
        return rules

    system = (
        "You are a code-change analyzer. Given a list of (before, after) "
        "line pairs from a user's correction of LLM-generated code, output "
        "one general rule per line in the form `before -> after`. Output "
        "only the rules, one per line, no explanation. Skip noise/formatting."
    )
    user = "\n".join(f"BEFORE: {b}\nAFTER: {a}\n" for b, a in uncovered[:10])
    try:
        resp = client.chat(system=system, prompt=user)
        for line in (resp.text or "").splitlines():
            line = line.strip()
            if "->" not in line:
                continue
            parts = line.split("->", 1)
            if len(parts) != 2:
                continue
            b_part = parts[0].strip().strip("`")
            a_part = parts[1].strip().strip("`")
            if not b_part or not a_part or b_part == a_part:
                continue
            key = (b_part, a_part)
            if key in seen_pairs:
                continue
            seen_pairs.add(key)
            rules.append(DiffRule(
                before=b_part, after=a_part,
                kind="llm_general", confidence=0.6,
            ))
    except Exception:  # noqa: BLE001
        pass
    return rules


def rules_to_constraints(rules: Iterable[DiffRule]) -> list[str]:
    """DiffRule list → state.md Constraints 섹션 texts."""
    return [r.as_state_text() for r in rules]

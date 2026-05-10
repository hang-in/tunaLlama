"""Markdown 작업 spec 파서.

Architect (Claude) 가 markdown 으로 task spec 작성 → 파일로 저장 → subagent 또는
``dev_review_from_spec`` 가 그것을 읽어 prompt 로 변환. architect ↔ subagent 의
통신 매체를 단순 prompt 가 아닌 **문서** 로 표준화한다.

지원 헤더 (모두 옵션):

    # Task: <title>
    ## Phase
    DESIGN | IMPLEMENT | VERIFY      # 어느 단계에 집중할지
    ## Focus
    <한 줄 우선순위>                  # 어디부터 공격할지
    ## Requirements
    ...
    ## Constraints
    ...
    ## Acceptance
    ...

헤더가 하나도 없으면 본문 전체를 requirements 로 취급.

`phase` / `focus` 는 gemento 의 phase-driven decomposition + prioritized_focus
패턴을 가져온 것 — 작은 모델이 의도 없이 헛도는 것을 막는다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

VALID_PHASES = ("DESIGN", "IMPLEMENT", "VERIFY")

_TITLE_RE = re.compile(r"^\s*#\s*Task\s*:\s*(.+?)\s*$", re.MULTILINE | re.IGNORECASE)
_SECTION_RE = re.compile(
    r"^\s*##\s+(Phase|Focus|Requirements|Constraints|Acceptance)\s*$\n(.*?)(?=^\s*##\s+|\Z)",
    re.MULTILINE | re.IGNORECASE | re.DOTALL,
)


@dataclass(frozen=True)
class TaskSpec:
    title: str | None
    requirements: str
    constraints: str
    acceptance: str
    phase: str | None = None  # DESIGN | IMPLEMENT | VERIFY (정규화됨, 그 외는 None)
    focus: str | None = None  # 한 줄 우선순위
    raw: str = ""

    def to_prompt(self) -> str:
        parts: list[str] = []
        if self.phase:
            parts.append(f"Phase: {self.phase}")
        if self.title:
            parts.append(f"Task: {self.title}")
        if self.focus:
            parts.append(f"Priority focus: {self.focus}")
        if self.requirements:
            parts.append(f"Requirements:\n{self.requirements}")
        if self.constraints:
            parts.append(f"Constraints (treat as hard rules):\n{self.constraints}")
        if self.acceptance:
            parts.append(f"Acceptance:\n{self.acceptance}")
        return "\n\n".join(parts) if parts else self.raw


def _normalize_phase(raw: str | None) -> str | None:
    if not raw:
        return None
    candidate = raw.strip().splitlines()[0].strip().upper() if raw.strip() else ""
    return candidate if candidate in VALID_PHASES else None


def parse_spec(text: str) -> TaskSpec:
    title = None
    m = _TITLE_RE.search(text)
    if m:
        title = m.group(1).strip()

    sections: dict[str, str] = {}
    for sm in _SECTION_RE.finditer(text):
        sections[sm.group(1).lower()] = sm.group(2).strip()

    phase = _normalize_phase(sections.get("phase"))
    focus_raw = sections.get("focus")
    focus = focus_raw.strip().splitlines()[0].strip() if focus_raw else None
    focus = focus or None

    has_structure = title is not None or sections
    return TaskSpec(
        title=title,
        requirements=sections.get("requirements", "" if has_structure else text.strip()),
        constraints=sections.get("constraints", ""),
        acceptance=sections.get("acceptance", ""),
        phase=phase,
        focus=focus,
        raw=text.strip(),
    )


def parse_spec_file(path: Path | str) -> TaskSpec:
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"spec 파일이 없습니다: {path}")
    return parse_spec(p.read_text(encoding="utf-8"))

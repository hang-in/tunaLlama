"""Phase 6-2 - decision / convention / constraint / anti-pattern 자동 추출.

delegation tool 출력 또는 spec 텍스트를 후처리. regex + rule-based.
BGE-M3 embedding dedup 은 ``store_extracted_entries`` 에서 옵션 적용.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Literal

from .state import (
    SECTION_ANTIPATTERNS,
    SECTION_CONSTRAINTS,
    SECTION_CONVENTIONS,
    SECTION_DECISIONS,
    StateEntry,
    StateFile,
    append_entry,
)

EntryKind = Literal["decision", "convention", "constraint", "antipattern"]


@dataclass
class ExtractedEntry:
    kind: EntryKind
    text: str
    confidence: float  # 0.0 - 1.0
    source_excerpt: str  # 원문 일부 (debugging)


# sentence 종결: `\.\s` (점 + 공백) / `\.$` (문서 끝) / `\n` / `$`.
# 이렇게 해야 "np.random 으로 ..." 안의 점이 종결로 잡히지 않음.
_END = r"(?:\.\s|\.$|\n|$)"

# Decision: "결정했다 / chose to / going with / will use ..."
_DECISION_PATTERNS = [
    re.compile(rf"(?:결정했(?:다|음)|결정함)[:\s]+(?P<text>.+?){_END}"),
    re.compile(r"우리는\s+(?P<text>.+?)(?:한다|하기로\s+(?:했다|함)|할\s+것이다)"),
    re.compile(
        rf"(?:will use|using|adopting|going with|decided to|chose to)\s+"
        rf"(?P<text>.+?)(?:\s+instead of|\s+over\b|{_END})",
        re.IGNORECASE,
    ),
    re.compile(
        rf"(?:default|기본값)[:\s]+(?P<text>.+?){_END}",
        re.IGNORECASE,
    ),
]

# Convention: "import X / from X / always use Y / 항상 Y 사용"
_CONVENTION_PATTERNS = [
    re.compile(
        r"(?:import|from)\s+(?P<text>\S+)\s+(?:should be|must be|always|는 항상)",
        re.IGNORECASE,
    ),
    re.compile(r"항상\s+(?P<text>.+?)\s+사용"),
    re.compile(
        rf"(?:convention|관습|규약)[:\s]+(?P<text>.+?){_END}",
        re.IGNORECASE,
    ),
]

# Constraint: "절대 / never / do not / must not / 금지 / forbidden"
_CONSTRAINT_PATTERNS = [
    re.compile(rf"절대\s+(?P<text>.+?)(?:금지|{_END})"),
    re.compile(
        rf"(?:never|do not|must not|don't|cannot)\s+(?P<text>.+?){_END}",
        re.IGNORECASE,
    ),
    re.compile(rf"(?:금지|forbidden|disallowed)[:\s]+(?P<text>.+?){_END}"),
    re.compile(rf"(?:hard rule|hard-rule)[:\s]+(?P<text>.+?){_END}", re.IGNORECASE),
]

# Anti-pattern: "anti-pattern / 안티패턴 / abandon / 회피 / avoid"
_ANTIPATTERN_PATTERNS = [
    re.compile(
        rf"(?:anti-pattern|anti pattern|antipattern|안티\s*패턴)[:\s]+"
        rf"(?P<text>.+?){_END}",
        re.IGNORECASE,
    ),
    re.compile(
        rf"(?:avoid|회피|기피)[:\s]+(?P<text>.+?){_END}", re.IGNORECASE
    ),
    re.compile(r"(?P<text>[^\.\n]+?)\s+은\s+anti-pattern", re.IGNORECASE),
]


def _clean(text: str, *, max_len: int = 140) -> str:
    """양 끝 공백/구두점 정리 + 길이 제한."""
    text = text.strip()
    text = re.sub(r"\s+", " ", text)
    text = text.strip(" \"'`-`*:;,")
    if len(text) > max_len:
        text = text[:max_len].rstrip() + "..."
    return text


def _extract_with(patterns, text: str, kind: EntryKind) -> list[ExtractedEntry]:
    entries: list[ExtractedEntry] = []
    for pat in patterns:
        for m in pat.finditer(text):
            extracted = _clean(m.group("text"))
            if len(extracted) < 4:
                continue
            # confidence = 패턴 종류에 따라 0.5-0.9 사이.
            confidence = 0.7
            entries.append(ExtractedEntry(
                kind=kind,
                text=extracted,
                confidence=confidence,
                source_excerpt=text[max(0, m.start() - 20): m.end() + 20],
            ))
    return entries


def extract_decisions(text: str) -> list[ExtractedEntry]:
    """delegation 출력 / spec 에서 decision 추출."""
    return _extract_with(_DECISION_PATTERNS, text, "decision")


def extract_conventions(text: str) -> list[ExtractedEntry]:
    return _extract_with(_CONVENTION_PATTERNS, text, "convention")


def extract_constraints(text: str) -> list[ExtractedEntry]:
    return _extract_with(_CONSTRAINT_PATTERNS, text, "constraint")


def extract_antipatterns(text: str) -> list[ExtractedEntry]:
    return _extract_with(_ANTIPATTERN_PATTERNS, text, "antipattern")


def extract_all(text: str) -> list[ExtractedEntry]:
    out: list[ExtractedEntry] = []
    out.extend(extract_decisions(text))
    out.extend(extract_conventions(text))
    out.extend(extract_constraints(text))
    out.extend(extract_antipatterns(text))
    return out


_KIND_TO_SECTION: dict[EntryKind, str] = {
    "decision": SECTION_DECISIONS,
    "convention": SECTION_CONVENTIONS,
    "constraint": SECTION_CONSTRAINTS,
    "antipattern": SECTION_ANTIPATTERNS,
}


def store_extracted_entries(
    state: StateFile,
    entries: Iterable[ExtractedEntry],
    *,
    min_confidence: float = 0.5,
    dedup_cosine_threshold: float = 0.85,
    embedding_fn=None,
) -> list[StateEntry]:
    """추출된 entry 들을 state 에 저장. confidence 미만은 skip.

    ``embedding_fn`` 이 주어지면 BGE-M3 cosine ≥ ``dedup_cosine_threshold``
    의 기존 entry 가 있으면 occurrences 만 증가 (rule-based dedup 보다 강함).
    None 이면 text 일치만 검사 (``append_entry`` 의 기본 dedup).
    """
    stored: list[StateEntry] = []
    for ex in entries:
        if ex.confidence < min_confidence:
            continue
        section = _KIND_TO_SECTION.get(ex.kind)
        if section is None:
            continue
        # embedding dedup
        merged = None
        if embedding_fn is not None:
            try:
                import numpy as np
                new_vec = embedding_fn(ex.text)
                for existing in state.entries:
                    if existing.section != section:
                        continue
                    try:
                        old_vec = embedding_fn(existing.text)
                        cos = float(np.dot(new_vec, old_vec))
                        if cos >= dedup_cosine_threshold:
                            existing.occurrences += 1
                            merged = existing
                            break
                    except Exception:  # noqa: BLE001
                        continue
            except Exception:  # noqa: BLE001
                merged = None
        if merged is not None:
            stored.append(merged)
            continue

        new_entry = StateEntry(
            section=section, text=ex.text,
            source="auto", occurrences=1,
        )
        actual = append_entry(state, new_entry)
        stored.append(actual)
    return stored

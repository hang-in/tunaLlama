"""Architect ↔ Subagent 워크플로우.

- ``limitations``: 로컬 LLM 약점 카탈로그 (자동 prepend).
- ``spec``: markdown 작업 spec 파서 — architect 가 작성, subagent 가 읽음.
- ``dev_review``: generate → review → fix → review 자동 루프.
"""

from .dev_review import (
    DevReviewResult,
    IterationResult,
    dev_review_from_spec,
    dev_review_loop,
)
from .limitations import (
    DEFAULT_LIMITATIONS_PATH,
    load_limitations,
    log_limitation,
    with_limitations,
)
from .spec import TaskSpec, parse_spec, parse_spec_file

__all__ = [
    "DEFAULT_LIMITATIONS_PATH",
    "DevReviewResult",
    "IterationResult",
    "TaskSpec",
    "dev_review_from_spec",
    "dev_review_loop",
    "load_limitations",
    "log_limitation",
    "parse_spec",
    "parse_spec_file",
    "with_limitations",
]

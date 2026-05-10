"""LLM 도구별 delegation 어댑터.

- ``_runner`` 가 공통 실행/기록 책임.
- ``code`` 가 코드 직접 다루는 7개 도구.
- ``files`` 가 파일 경로 받아 내용 읽어 처리하는 3개 도구.

도구 함수는 모두 ``run_delegation`` 을 거쳐 호출되므로 호출/기록 경로가 단일하다.
"""

from ._runner import DelegationResult
from .code import (
    explain_code,
    fix_code,
    general_task,
    generate_code,
    refactor_code,
    review_code,
    write_tests,
)
from .files import analyze_files, explain_file, review_file

__all__ = [
    "DelegationResult",
    "analyze_files",
    "explain_code",
    "explain_file",
    "fix_code",
    "general_task",
    "generate_code",
    "refactor_code",
    "review_code",
    "review_file",
    "write_tests",
]

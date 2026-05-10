"""tunaLlama 공용 예외.

서브시스템별 에러를 한 베이스(`TunaLlamaError`)로 묶어 두면,
CLI/플러그인/테스트가 운영성 에러를 일괄 잡기 좋다.
"""

from __future__ import annotations


class TunaLlamaError(Exception):
    """모든 tunaLlama 에러의 공통 베이스."""


class ConfigError(TunaLlamaError):
    """설정 파일 또는 환경 변수 관련 에러."""


class LLMError(TunaLlamaError):
    """LLM provider 호출 실패."""


class MemoryStoreError(TunaLlamaError):
    """SQLite 메모리 저장소 에러. (Python 내장 ``MemoryError`` 와 이름 충돌 회피)"""


class RecallError(TunaLlamaError):
    """리콜 검색 단계에서 발생한 에러."""


class FileScopeError(TunaLlamaError):
    """파일 접근 범위/패턴 위반 — project_root 밖, 비밀 파일 패턴, 크기/형식 위반."""

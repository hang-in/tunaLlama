"""tunaLlama core 백엔드 — 재사용 가능, MCP-agnostic.

Phase 1 public surface:

- ``Config`` 와 ``load_config`` — TOML 로드.
- 도메인 예외 ``TunaLlamaError`` 하위.
- LLM provider 팩토리 ``make_client`` 와 ``LLMClient``.
- Delegation 도구 10종 + ``DelegationResult``.
- 메모리 ``MemoryStore`` + ``recall`` + ``RecallResult``.
- ``recall_for_delegation`` (auto_recall 정책 적용).

이외는 내부 — frontend/plugin 레이어가 의존하지 않도록.
"""

from .config import (
    Config,
    LLMConfig,
    LMStudioProviderConfig,
    LoggingConfig,
    MemoryConfig,
    OllamaCloudProviderConfig,
    OllamaProviderConfig,
    RoutingConfig,
    find_config_path,
    load_config,
)
from .delegation import (
    DelegationResult,
    analyze_files,
    explain_code,
    explain_file,
    fix_code,
    general_task,
    generate_code,
    refactor_code,
    review_code,
    review_file,
    write_tests,
)
from .errors import (
    ConfigError,
    FileScopeError,
    LLMError,
    MemoryStoreError,
    RecallError,
    TunaLlamaError,
)
from .llm import ChatResponse, LLMClient, make_client
from .memory import (
    CallRecord,
    Edge,
    MemoryStore,
    RecallResult,
    RecallSnippet,
    VectorHit,
    build_semantic_edges,
    classify_pair,
    rebuild_edges,
    recall,
    recall_hybrid,
    traverse,
)
from .routing import recall_for_delegation
from .workflow import (
    DevReviewResult,
    IterationResult,
    TaskSpec,
    dev_review_from_spec,
    dev_review_loop,
    load_limitations,
    log_limitation,
    parse_spec,
    parse_spec_file,
    with_limitations,
)

__all__ = [
    # config
    "Config",
    "LLMConfig",
    "LMStudioProviderConfig",
    "LoggingConfig",
    "MemoryConfig",
    "OllamaCloudProviderConfig",
    "OllamaProviderConfig",
    "RoutingConfig",
    "find_config_path",
    "load_config",
    # errors
    "ConfigError",
    "FileScopeError",
    "LLMError",
    "MemoryStoreError",
    "RecallError",
    "TunaLlamaError",
    # llm
    "ChatResponse",
    "LLMClient",
    "make_client",
    # memory
    "CallRecord",
    "Edge",
    "MemoryStore",
    "build_semantic_edges",
    "classify_pair",
    "RecallResult",
    "RecallSnippet",
    "VectorHit",
    "rebuild_edges",
    "recall",
    "recall_hybrid",
    "traverse",
    # routing
    "recall_for_delegation",
    # delegation
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
    # workflow
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

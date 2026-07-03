"""Config dataclass 정의.

모든 dataclass는 frozen — load 이후 변경 금지. provider 별 설정은 각자
별도 dataclass 로 두고, ``LLMConfig.active()`` 가 활성 provider 의 것을 돌려준다.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Union

from ..errors import ConfigError

Provider = Literal["ollama", "ollama_cloud", "lmstudio"]
KoreanTokenizer = Literal["kiwi", "konlpy_okt", "none"]
AutoRecall = Literal["always", "on_request", "never"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


@dataclass(frozen=True)
class OllamaProviderConfig:
    host: str
    model: str
    num_ctx: int = 8192


@dataclass(frozen=True)
class OllamaCloudProviderConfig:
    host: str
    api_key_env: str
    model: str

    def resolve_api_key(self) -> str:
        v = os.environ.get(self.api_key_env)
        if not v:
            raise ConfigError(
                f"환경변수 {self.api_key_env!r} 가 비어있습니다. "
                ".env 또는 셸에서 설정하세요."
            )
        return v


@dataclass(frozen=True)
class LMStudioProviderConfig:
    host: str
    model: str
    api_key: str = "lm-studio"


ProviderConfig = Union[
    OllamaProviderConfig, OllamaCloudProviderConfig, LMStudioProviderConfig
]


@dataclass(frozen=True)
class LLMConfig:
    provider: Provider
    temperature: float
    timeout_seconds: int
    ollama: OllamaProviderConfig | None = None
    ollama_cloud: OllamaCloudProviderConfig | None = None
    lmstudio: LMStudioProviderConfig | None = None

    def active(self) -> ProviderConfig:
        match self.provider:
            case "ollama":
                if self.ollama is None:
                    raise ConfigError("[llm.ollama] 섹션이 비어있습니다.")
                return self.ollama
            case "ollama_cloud":
                if self.ollama_cloud is None:
                    raise ConfigError("[llm.ollama_cloud] 섹션이 비어있습니다.")
                return self.ollama_cloud
            case "lmstudio":
                if self.lmstudio is None:
                    raise ConfigError("[llm.lmstudio] 섹션이 비어있습니다.")
                return self.lmstudio


@dataclass(frozen=True)
class MemoryConfig:
    db_path: Path
    korean_tokenizer: KoreanTokenizer = "kiwi"
    enable_logging: bool = True
    enable_recall: bool = True
    # Phase 4: 벡터 임베딩 자체를 끌 수 있게. False 면 record_call 시 임베딩
    # 호출 X. BM25 path 만 살아있음.
    enable_embeddings: bool = True
    # Phase 9: 임베딩 모델 (Ollama 태그). 1024-dim 모델만 (스키마 고정).
    # 환경변수 ``TUNA_EMBEDDING_MODEL`` 이 우선.
    embedding_model: str = "qwen3-embedding:0.6b"
    # "auto" | "cpu" | "mps" | "cuda" - Phase 9 이후 임베딩은 Ollama 가 device 를
    # 자동 관리하므로 임베딩 경로에선 무의미. 옵셔널 reranker(sentence-transformers,
    # [rerank] extra) 전용. 환경변수 ``TUNA_EMBEDDING_DEVICE`` 가 우선.
    embedding_device: str = "auto"


@dataclass(frozen=True)
class RoutingConfig:
    auto_recall: AutoRecall = "on_request"
    recall_limit: int = 5


@dataclass(frozen=True)
class LoggingConfig:
    level: LogLevel = "INFO"
    file: Path | None = None


@dataclass(frozen=True)
class Config:
    llm: LLMConfig
    memory: MemoryConfig
    routing: RoutingConfig
    logging: LoggingConfig
    source_path: Path | None = None

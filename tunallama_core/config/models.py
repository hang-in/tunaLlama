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

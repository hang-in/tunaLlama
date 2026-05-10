"""TOML 로드 + 경로 탐색 + 필드별 검증.

검증 책임은 이 파일이 갖는다. dataclass(`models.py`) 는 값만 보유.
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any

from ..errors import ConfigError
from .models import (
    Config,
    LLMConfig,
    LMStudioProviderConfig,
    LoggingConfig,
    MemoryConfig,
    OllamaCloudProviderConfig,
    OllamaProviderConfig,
    Provider,
    RoutingConfig,
)

_PROVIDERS = ("ollama", "ollama_cloud", "lmstudio")
_TOKENIZERS = ("kiwi", "konlpy_okt", "none")
_AUTO_RECALL = ("always", "on_request", "never")
_LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")


def find_config_path(explicit: Path | None = None) -> Path:
    """우선순위: explicit → ./.tunallama/config.toml → ~/.tunallama/config.toml."""
    if explicit is not None:
        if not explicit.exists():
            raise ConfigError(f"명시한 config 경로가 없습니다: {explicit}")
        return explicit
    candidates = (
        Path(".tunallama") / "config.toml",
        Path.home() / ".tunallama" / "config.toml",
    )
    for p in candidates:
        if p.exists():
            return p
    raise ConfigError(
        "설정 파일을 찾을 수 없습니다. config.example.toml 을 "
        "~/.tunallama/config.toml 또는 ./.tunallama/config.toml 로 복사하세요."
    )


def _expand(p: str) -> Path:
    return Path(os.path.expanduser(p)).resolve()


def _require_in(name: str, value: Any, allowed: tuple[str, ...]) -> str:
    if value not in allowed:
        raise ConfigError(f"{name}: {value!r} (허용: {' | '.join(allowed)})")
    return value


def _require_range(name: str, value: float, lo: float, hi: float) -> float:
    if not (lo <= value <= hi):
        raise ConfigError(f"{name} 는 {lo}~{hi} 범위여야 합니다: {value}")
    return value


def _require_positive(name: str, value: int) -> int:
    if value <= 0:
        raise ConfigError(f"{name} 는 양수여야 합니다: {value}")
    return value


def _build_llm(d: dict[str, Any]) -> LLMConfig:
    provider: Provider = _require_in(  # type: ignore[assignment]
        "[llm].provider", d.get("provider", "ollama"), _PROVIDERS
    )
    temperature = _require_range(
        "[llm].temperature", float(d.get("temperature", 0.3)), 0.0, 2.0
    )
    timeout = _require_positive(
        "[llm].timeout_seconds", int(d.get("timeout_seconds", 300))
    )

    ollama = None
    if "ollama" in d:
        s = d["ollama"]
        ollama = OllamaProviderConfig(
            host=str(s["host"]), model=str(s["model"]),
            num_ctx=int(s.get("num_ctx", 8192)),
        )
    ollama_cloud = None
    if "ollama_cloud" in d:
        s = d["ollama_cloud"]
        ollama_cloud = OllamaCloudProviderConfig(
            host=str(s["host"]),
            api_key_env=str(s["api_key_env"]),
            model=str(s["model"]),
        )
    lmstudio = None
    if "lmstudio" in d:
        s = d["lmstudio"]
        lmstudio = LMStudioProviderConfig(
            host=str(s["host"]), model=str(s["model"]),
            api_key=str(s.get("api_key", "lm-studio")),
        )
    cfg = LLMConfig(
        provider=provider,
        temperature=temperature,
        timeout_seconds=timeout,
        ollama=ollama,
        ollama_cloud=ollama_cloud,
        lmstudio=lmstudio,
    )
    cfg.active()  # 활성 provider 누락이면 즉시 실패
    return cfg


def _build_memory(d: dict[str, Any]) -> MemoryConfig:
    tok = _require_in("[memory].korean_tokenizer", d.get("korean_tokenizer", "kiwi"), _TOKENIZERS)
    return MemoryConfig(
        db_path=_expand(str(d.get("db_path", "~/.tunallama/memory.db"))),
        korean_tokenizer=tok,  # type: ignore[arg-type]
        enable_logging=bool(d.get("enable_logging", True)),
        enable_recall=bool(d.get("enable_recall", True)),
    )


def _build_routing(d: dict[str, Any]) -> RoutingConfig:
    mode = _require_in("[routing].auto_recall", d.get("auto_recall", "on_request"), _AUTO_RECALL)
    limit = _require_positive("[routing].recall_limit", int(d.get("recall_limit", 5)))
    return RoutingConfig(auto_recall=mode, recall_limit=limit)  # type: ignore[arg-type]


def _build_logging(d: dict[str, Any]) -> LoggingConfig:
    level = _require_in("[logging].level", d.get("level", "INFO"), _LOG_LEVELS)
    file_v = d.get("file")
    return LoggingConfig(level=level, file=_expand(str(file_v)) if file_v else None)  # type: ignore[arg-type]


def load_config(path: Path | str | None = None) -> Config:
    p = find_config_path(Path(path) if path else None)
    with p.open("rb") as f:
        raw = tomllib.load(f)
    if "llm" not in raw:
        raise ConfigError(f"[llm] 섹션이 없습니다: {p}")
    return Config(
        llm=_build_llm(raw["llm"]),
        memory=_build_memory(raw.get("memory", {})),
        routing=_build_routing(raw.get("routing", {})),
        logging=_build_logging(raw.get("logging", {})),
        source_path=p,
    )

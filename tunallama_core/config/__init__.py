"""Config 패키지.

- ``models``: 검증된 dataclass 정의 (불변).
- ``loader``: TOML 읽기 + 경로 탐색 + 필드별 검증.

외부에서는 이 모듈을 통해 ``load_config`` 와 dataclass 들을 가져다 쓴다.
"""

from .loader import find_config_path, load_config
from .models import (
    Config,
    LLMConfig,
    LMStudioProviderConfig,
    LoggingConfig,
    MemoryConfig,
    OllamaCloudProviderConfig,
    OllamaProviderConfig,
    Provider,
    ProviderConfig,
    RoutingConfig,
)

__all__ = [
    "Config",
    "LLMConfig",
    "LMStudioProviderConfig",
    "LoggingConfig",
    "MemoryConfig",
    "OllamaCloudProviderConfig",
    "OllamaProviderConfig",
    "Provider",
    "ProviderConfig",
    "RoutingConfig",
    "find_config_path",
    "load_config",
]

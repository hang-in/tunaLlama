"""의미 기반 (벡터) recall 의 보조 모듈.

- ``embed(text)`` 가 Ollama ``/api/embed`` 로 1024-dim L2-정규화 벡터를 돌려준다.
- ``VectorHit`` 가 ``MemoryStore.search_vectors`` 의 결과 단위.

설계 결정 (Phase 9 — Ollama 전환):
- 임베딩 백엔드를 sentence-transformers(torch) → **Ollama** 로 교체. torch 의존
  제거(py3.13 import hang·CPU/GPU 빌드 문제 소멸), GPU 는 Ollama 가 자동 관리.
  기본 모델 ``qwen3-embedding:0.6b`` (1024-dim, bge-m3 의 NaN 버그 해결).
- Ollama 응답은 unit vector 를 보장하지 않으므로 여기서 L2 정규화(cosine 전제).
- 클라이언트는 lazy. ``threading.Lock`` 으로 멀티 스레드 race 방지.
- HNSW / 외부 인덱스는 보류 — 1만 record 까지는 brute-force cosine 으로 충분.
"""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass

import numpy as np

# 임베딩 백엔드: Ollama 태그. qwen3-embedding:0.6b 는 1024-dim (기존 스키마 호환).
DEFAULT_EMBEDDING_MODEL = "qwen3-embedding:0.6b"
DEFAULT_EMBEDDING_HOST = "http://localhost:11434"
EMBEDDING_MODEL = os.environ.get("TUNA_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL)
EMBEDDING_DIM = 1024  # bge-m3 / qwen3-embedding:0.6b 모두 1024
_EMBEDDING_DTYPE = np.float32

_client = None
_client_lock = threading.Lock()


def _embedding_model() -> str:
    """``TUNA_EMBEDDING_MODEL`` (Ollama 태그) — 호출 시점 조회. _state 가
    config → env 브리지한 뒤에도 반영되도록 상수 대신 함수로 읽는다."""
    return os.environ.get("TUNA_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL)


def _embedding_host() -> str:
    """임베딩용 Ollama host. ``TUNA_EMBEDDING_HOST`` 우선, 없으면 로컬 기본."""
    return os.environ.get("TUNA_EMBEDDING_HOST", DEFAULT_EMBEDDING_HOST)


@dataclass(frozen=True)
class VectorHit:
    id: int
    score: float  # cosine, 1.0 = 정확히 같음
    inputs_summary: str
    output_excerpt: str
    tool_name: str
    timestamp: str


def _get_client():
    """lazy Ollama 클라이언트. host 는 첫 호출 시 확정.

    환경변수:
    - ``TUNA_EMBEDDING_MODEL``: Ollama 태그. default ``qwen3-embedding:0.6b``.
      1024-dim 모델만 swap 가능(스키마 고정). 예: ``bge-m3``.
    - ``TUNA_EMBEDDING_HOST``: 임베딩용 Ollama host. default ``http://localhost:11434``.
    """
    global _client
    with _client_lock:
        if _client is None:
            from ollama import Client

            _client = Client(host=_embedding_host())
    return _client


def _normalize(v: np.ndarray) -> np.ndarray:
    n = float(np.linalg.norm(v))
    if n < 1e-12:
        return v
    return v / n


def embed(text: str) -> np.ndarray:
    """텍스트를 ``(1024,)`` float32 L2-정규화 벡터로 변환 (Ollama /api/embed).

    Ollama 응답은 unit vector 를 보장하지 않으므로 여기서 L2 정규화한다
    (cosine 검색 전제). 모델/호스트 미가용·dim 불일치는 ``LLMError``.
    """
    from ..errors import LLMError

    client = _get_client()
    model = _embedding_model()
    try:
        resp = client.embed(model=model, input=text)
    except Exception as e:  # noqa: BLE001 - provider/네트워크 오류 일괄 래핑
        raise LLMError(
            f"Ollama 임베딩 호출 실패 (model={model}, host={_embedding_host()}): {e}"
        ) from e
    embeddings = getattr(resp, "embeddings", None)
    if embeddings is None and isinstance(resp, dict):
        embeddings = resp.get("embeddings")
    if not embeddings:
        raise LLMError(f"Ollama 임베딩 응답에 embeddings 없음 (model={model})")
    v = np.asarray(embeddings[0], dtype=_EMBEDDING_DTYPE)
    if v.shape[0] != EMBEDDING_DIM:
        raise LLMError(
            f"임베딩 dim {v.shape[0]} != 기대값 {EMBEDDING_DIM} (model={model}). "
            "다른 차원 모델은 스키마 비호환."
        )
    return _normalize(v).astype(_EMBEDDING_DTYPE)


def encode_blob(vec: np.ndarray) -> bytes:
    """numpy 벡터 → SQLite BLOB 바이트."""
    if vec.dtype != _EMBEDDING_DTYPE:
        vec = vec.astype(_EMBEDDING_DTYPE)
    return vec.tobytes()


def decode_blob(blob: bytes) -> np.ndarray | None:
    """BLOB → numpy. 길이가 안 맞으면 None (corrupted record 방어)."""
    if blob is None or len(blob) != EMBEDDING_DIM * 4:
        return None
    return np.frombuffer(blob, dtype=_EMBEDDING_DTYPE)

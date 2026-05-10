"""의미 기반 (벡터) recall 의 보조 모듈.

- ``embed(text)`` 가 BGE-M3 로 1024-dim L2-정규화 벡터를 돌려준다.
- ``VectorHit`` 가 ``MemoryStore.search_vectors`` 의 결과 단위.

설계 결정:
- ``sentence-transformers`` 의 ``normalize_embeddings=True`` 를 사용 — 수동
  L2 정규화보다 모델 내부 처리가 정확하고 빠르다 (round 7 dogfooding 의 좋은
  발견 차용).
- 모델은 lazy load. ``threading.Lock`` 으로 멀티 스레드 race 방지.
- HNSW / 외부 인덱스는 보류 — 1만 record 까지는 brute-force cosine 으로 충분.
"""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass

import numpy as np

EMBEDDING_MODEL = "BAAI/bge-m3"
EMBEDDING_DIM = 1024
_EMBEDDING_DTYPE = np.float32

_model = None
_model_lock = threading.Lock()


def _resolve_device() -> str | None:
    """``TUNA_EMBEDDING_DEVICE`` 환경변수 → device 문자열.

    "" / "auto" → None (sentence-transformers 가 자동 선택). 잘못된 값은 None.
    """
    raw = os.environ.get("TUNA_EMBEDDING_DEVICE", "").strip().lower()
    if raw in ("cpu", "mps", "cuda"):
        return raw
    return None


@dataclass(frozen=True)
class VectorHit:
    id: int
    score: float  # cosine, 1.0 = 정확히 같음
    inputs_summary: str
    output_excerpt: str
    tool_name: str
    timestamp: str


def _get_model():
    """lazy load - 첫 ``embed()`` 호출 때 BGE-M3 다운로드/로드 (~1GB).

    ``TUNA_EMBEDDING_DEVICE`` 환경변수로 device 강제 가능 (cpu/mps/cuda).
    macOS 일상 사용에서 GPU 메모리 회복 원하면 ``cpu`` 권장.
    """
    global _model
    with _model_lock:
        if _model is None:
            from sentence_transformers import SentenceTransformer

            kwargs: dict = {}
            device = _resolve_device()
            if device is not None:
                kwargs["device"] = device
            _model = SentenceTransformer(EMBEDDING_MODEL, **kwargs)
    return _model


def embed(text: str) -> np.ndarray:
    """텍스트를 ``(1024,)`` float32 L2-정규화 벡터로 변환.

    빈 문자열도 받아 1024-dim 0-벡터를 반환하지 않고 모델이 학습한 placeholder
    임베딩을 그대로 돌려준다 (의도적 — 호출자가 빈 입력을 사전에 거른다).
    """
    model = _get_model()
    vec = model.encode(text, convert_to_numpy=True, normalize_embeddings=True)
    return vec.astype(_EMBEDDING_DTYPE)


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

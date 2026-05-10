# Task: 벡터 임베딩 + 의미 기반 recall (Phase 2-1)

`tunallama_core/memory/` 에 임베딩 기반 벡터 검색을 추가한다. 기존 FTS5 BM25 흐름은 그대로 유지하고 별도 경로로 동작하도록.

## Phase
IMPLEMENT

## Focus
`record_call` 시점의 임베딩 자동 저장과 `search_vectors` 의 cosine 유사도 검색 — HNSW / 인덱스 최적화는 보류 (numpy brute-force 로 충분).

## Requirements

- 새 모듈 `tunallama_core/memory/vector.py`:
  - 함수 `embed(text: str) -> np.ndarray` — `sentence-transformers` 의 `BAAI/bge-m3` 모델로 1024-dim 임베딩 (lazy load, 모듈 변수 캐시).
  - 모델 이름은 상수 `EMBEDDING_MODEL = "BAAI/bge-m3"` 로 고정.
  - 반환은 L2 정규화된 `np.ndarray(dtype=np.float32, shape=(1024,))`.
- `tunallama_core/memory/schema.sql` 에 컬럼 추가:
  - `calls.embedding BLOB` — `np.ndarray.tobytes()` 결과. NULL 가능 (옛 record 호환).
- `tunallama_core/memory/store.py::MemoryStore.record_call`:
  - 호출 시점에 `embed(inputs_json + " " + output)` 결과를 BLOB 으로 저장.
  - 기존 FTS5 INSERT 는 그대로 유지.
  - 임베딩 실패(import 에러 등) 시 `embedding=NULL` 로 진행 — 임베딩이 옵션이지 필수가 아님.
- `tunallama_core/memory/store.py::MemoryStore` 에 새 메서드:
  - `search_vectors(self, query: str, *, limit: int = 5, project_root: str | None = None) -> list[VectorHit]`
  - cosine 유사도 (정규화 벡터의 dot product) 로 정렬.
  - `embedding IS NOT NULL` 인 행만 대상.
  - `project_root` 가 주어지면 동일 값인 record 만.
- 새 dataclass `VectorHit`:
  - `id: int`, `score: float` (cosine, 1.0 이 최대), `inputs_summary: str` (앞 100자), `output_excerpt: str` (앞 200자), `tool_name: str`, `timestamp: str`.
- `tunallama_core/__init__.py` 에 `VectorHit` re-export.

## Constraints (hard rules)

- **기존 BM25 동작 변경 금지** — `recall()`, FTS5 INSERT, 리콜 결과 형식 모두 유지. regression 시 fail.
- 임베딩 모델은 **lazy load** — `vector.py` import 시점에는 model 다운로드 X. `embed()` 첫 호출에만.
- numpy / sentence-transformers 외 외부 의존 추가 금지.
- 모든 새 함수에 한국어 docstring 1-2줄.
- **단일 책임**: vector 로직은 `vector.py` 안에서. `store.py` 는 vector.py 호출만.
- frozen dataclass.

## Acceptance

- pytest 6+ 케이스 (`tests/core/test_memory_vector.py` 신규):
  1. `embed("hello")` → shape (1024,) + L2 정규화(norm ≈ 1.0).
  2. `MemoryStore.record_call` 후 SQL 직접 조회 시 `embedding IS NOT NULL`.
  3. `search_vectors("이메일 검증")` 가 의미적으로 유사한 record 우선 반환 (한국어/영문 혼합 record).
  4. `project_root` 필터 동작.
  5. 빈 store → `search_vectors` 가 `[]`.
  6. 임베딩 모델 import 실패 시 `record_call` 이 `embedding=NULL` 로 진행 (테스트는 monkeypatch 로 ImportError 강제).
- 기존 `test_memory_store.py` / `test_memory_search.py` 모두 통과 (regression 없음).

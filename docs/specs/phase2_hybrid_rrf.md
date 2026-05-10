# Task: 하이브리드 검색 — BM25 + 벡터 RRF 병합 (Phase 2-2)

phase2_vector_recall 의 `search_vectors` 와 기존 `recall` (BM25) 를 RRF (Reciprocal Rank Fusion) 로 병합. seCall 이 사용한 패턴 — 두 ranking 의 1/(k+rank) 합산.

## Phase
IMPLEMENT

## Focus
`recall_hybrid()` 함수 하나 — 기존 `recall()` signature 변경 없이.

## Requirements

- `tunallama_core/memory/search.py` 에 새 함수:
  - `recall_hybrid(store, query, *, limit=5, project_root=None, k=60) -> RecallResult`
  - 내부적으로 `recall(store, query, limit=limit*2, ...)` (BM25) 와 `store.search_vectors(query, limit=limit*2, ...)` (벡터) 호출.
  - 각 결과에 rank (1-based) 부여 → `score = 1/(k + rank)` 로 두 결과 합산.
  - 같은 `id` 가 양쪽에 잡히면 두 score 합산 (dedup).
  - 합산 score 내림차순 정렬, 상위 `limit` 개를 `RecallResult.snippets` 로 반환.
  - `total_matches` 는 dedup 후 unique id 개수.
- `tunallama_core/__init__.py` 에 `recall_hybrid` re-export.
- 기존 `recall()` 는 그대로. 호환성 보장.

## Constraints (hard rules)

- **`recall()` signature / 동작 변경 금지** — 기존 호출자(plugin `tuna_recall` 등) 무영향.
- `search_vectors` 가 빈 결과를 줘도(예: 모든 record 가 `embedding=NULL`) `recall_hybrid` 는 BM25 결과만으로 정상 동작해야 함.
- `recall()` 가 `RecallError` 던지면 `recall_hybrid` 도 그대로 propagate.
- `k` 는 RRF 의 표준 상수 60. 호출자가 override 가능.
- 함수 길이 50줄 이내. 단일 책임.
- 한국어 docstring.

## Acceptance

- pytest 5+ 케이스 (`tests/core/test_memory_hybrid.py` 신규):
  1. BM25 와 vector 가 같은 top-1 을 반환하면 hybrid top-1 도 동일.
  2. BM25 에 없고 vector 에만 있는 record 도 hybrid 결과에 포함.
  3. 양쪽 다 있는 record 는 한 번만 등장 (dedup).
  4. 빈 store → `RecallResult(total_matches=0, snippets=())`.
  5. `embedding=NULL` 만 있는 store 에서도 BM25 결과만으로 동작.
- 기존 `test_memory_search.py` 통과 (regression 없음).

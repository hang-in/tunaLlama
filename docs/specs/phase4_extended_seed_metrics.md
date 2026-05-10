# Task: 시드 100+ 확장 + P@1/MRR 통합 측정 (Phase 4-3)

기존 36 record 시드는 reranker 효과 측정에 작음. 12 task × 6 paraphrase = 72 record + 부가 noise (관계없는 record 30+) = 100+ 으로 확장. 동시에 P@1, MRR 까지 측정해서 R@5 만으로는 보이지 않는 ranking 품질을 본다.

## Phase
IMPLEMENT

## Focus
시드 dataset 자체의 품질 + 측정 metrics 의 정밀도. 알고리즘 변경 없음.

## Requirements

- 새 통합 테스트 파일 `tests/integration/test_search_quality_extended.py`.
  - `@pytest.mark.search_quality` 마커.
  - module-scope fixture `extended_store` 가 시드 적재.
- 시드 (총 100+ record):
  - 기존 6 task × 6 paraphrase (36 record) 그대로 유지.
  - 신규 6 task × 6 paraphrase (36 record):
    - 로깅 (logging / log 출력 / 구조화 로그 / structured logging / loguru / 포맷 지정)
    - 캐시 (caching / 메모리 캐시 / LRU / Redis 캐시 / 캐시 무효화 / cache TTL)
    - 비동기 (async / await / 동시성 / 코루틴 / asyncio / event loop)
    - DB 마이그레이션 (DB migration / 스키마 변경 / Alembic / 다운타임 없는 마이그레이션 / rollback / 컬럼 추가)
    - 직렬화 (serialize / dump / pickle / msgpack / 객체 → JSON / 역직렬화)
    - 정렬 알고리즘 (sort / quicksort / mergesort / 안정 정렬 / 부분 정렬 / inplace 정렬)
  - noise 30+ record: 위 12 task 와 무관한 코딩 task (예: "matplotlib 차트 그리기", "ANSI 컬러 출력", "argparse 사용법" 등). cross-contamination 측정용.
- query 12 개 (각 task 의 첫 표현). relevant set = 같은 task 의 6 paraphrase.
- `tunallama_core.memory.compute_metrics` 사용해 P@1, P@5, R@5, MRR 측정.
- 5 검색 path 비교:
  - BM25 (`recall`)
  - vector (`store.search_vectors`)
  - hybrid (`recall_hybrid`)
  - reranked hybrid (`recall_reranked`, base="hybrid", candidate_pool=20)
  - (별도 fixture 로 cloud_client 받아서) recall_expanded(client, mode="bm25")
- 출력 표 (pytest -s):
  ```
  path         P@1   P@5   R@5   MRR
  ```
- assertion:
  - vector P@1 >= BM25 P@1 (cross-lingual / paraphrase)
  - reranked hybrid MRR >= hybrid MRR - 0.05 (재정렬이 ranking 망치지 않음)

## Constraints (hard rules)

- **알고리즘 변경 X** — search.py / vector.py / reranker.py 등 기존 코드 수정 금지. 새 통합 테스트만 추가.
- 시드는 사람이 손으로 작성한 한국어/영문 mix paraphrase. 자동 생성 X.
- 36 + 36 + noise = 100+ record 보장.
- module-scope fixture - 임베딩은 한 번만.
- 한국어 docstring.

## Acceptance

- 새 통합 테스트 1+ 통과 (실 BGE-M3 + reranker, search_quality 마커).
- 표 출력이 5 path × 4 metric × 12 group + AVG.
- 기존 `test_search_quality{,_synonym}.py` 통과 (regression 없음).
- 343+ 단위 테스트 통과.

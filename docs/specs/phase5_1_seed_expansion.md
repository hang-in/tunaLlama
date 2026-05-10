# Phase 5-1 - 시드 확장 (102 → 500+ record)

## 배경

Phase 4 측정의 102 record 시드는 실 사용 1k-10k 와 다름. 외부 Opus 4.7
+ Codex 5.5 둘 다 시드 크기를 측정 한계로 지적. corpus 가 커지면:
- σ 가 줄어들 가능성 (statistical regression).
- reranker 의 candidate_pool 경쟁이 커져서 가치 ↑.
- BM25 의 noise term 이 늘어남.

본 측정은 **알고리즘 변경 없이 corpus 만 키움**.

## Hypothesis

- H1: 102 → 500 record 로 가면 LOPO σR@5 가 0.29 → 0.20 이하로 감소.
- H2: rerank R@5 가 큰 corpus 에서 vec/hybrid 와의 격차 더 벌어짐.
- H3: BM25 R@5 는 노이즈 record 늘어 추가 하락.

## Seed 확장 design

### 신규 60 task × 6 paraphrase = 360 record

기존 12 task (memory_leak / email_validation / ... / sorting_algo) + 신규
60 task. 신규 task 카테고리:
- **System programming** (10): file I/O, signal handling, process forking
- **Network** (10): HTTP client, websocket, gRPC, retry logic
- **Data structures** (10): trie, heap, linked list, B-tree
- **Concurrency** (10): mutex, semaphore, async queue, race condition
- **Crypto/security** (10): AES, JWT, OAuth flow, CSRF token
- **DevOps** (10): docker compose, k8s deployment, terraform module

각 task 는 6 paraphrase (한국어 + 영문 mix). 기존 시드와 동일 형식.

### 추가 noise 60 → 90 record

기존 30 noise + 60 추가 = 90 noise. 동일 분포 (matplotlib / argparse /
ssh-key 등 일상 IT 키워드).

총 시드 = (12 + 60) × 6 + 90 = **522 record**.

## dogfooding 위임 (bounded output)

cloud glm-4.7 에 다음만 위임:
```
60 task 카테고리 (System / Network / DataStruct / Concurrency / Crypto / DevOps),
각 카테고리 10 task, 각 task 6 paraphrase 한국어/영문 mix.
JSON list 형식.
```

architect 가 결과 검증 + 통합. **integration coder 위임 X** - 시드 데이터만.

## 측정

기존 LOPO measurement (`test_search_quality_lopo.py`) 의 시드를 확장된
522 record 로 교체. 회전 = 72 task × 6 paraphrase = **432 query** (12 →
72 task 로 늘어남).

cloud expanded path 만 cloud 호출 → **432 cloud calls**. quota
넉넉하므로 진행. CPU 임베딩은 522 × 432 = 225k embeddings. **너무 무거움.**

### 최적화

회전마다 fresh DB 만들지 말고, 시드는 1번만 색인 후 회전마다 query/relevant
remap. holdout paraphrase 도 corpus 에 들어있지만 measurement 시 retrieved
list 에서 제외 후 metric 계산:

```python
# query 의 paraphrase 가 retrieved 에 있으면 제외 (LOPO 시뮬레이션)
def lopo_filter(retrieved: list[int], holdout_id: int) -> list[int]:
    return [r for r in retrieved if r != holdout_id]
```

이러면 522 record × 1 색인 + 432 query × 5 path = 2160 measurement
(BGE-M3 1번 + reranker 1번 + cloud 432). 시간 추정: ~2-3 시간.

## Required Imports

```python
import math
import os
import statistics
from pathlib import Path

import pytest

from tunallama_core.config.models import OllamaCloudProviderConfig
from tunallama_core.llm.ollama import from_cloud
from tunallama_core.memory.metrics import RetrievalMetrics, compute_metrics, average_metrics
from tunallama_core.memory.search import recall, recall_expanded, recall_hybrid, recall_reranked
from tunallama_core.memory.store import MemoryStore
```

## Required Call Signatures

```python
store = MemoryStore(db_path, korean_tokenizer="kiwi", enable_embeddings=True).open()
store.record_call(tool_name="seed", inputs={"q": phrase}, output=f"out for {phrase}", model="seed", duration_ms=1)

# search paths - 동일 기존 LOPO test
recall_results = recall(store, query, limit=20).snippets       # has .full_id
vec_results = store.search_vectors(query, limit=20)             # has .id
... 5 path 동일

# metrics
m = compute_metrics(retrieved_ids: list[int], relevant: set[int], k=5)  # RetrievalMetrics
avg = average_metrics(per_query: list[RetrievalMetrics])
```

## File path

새 파일: `tests/integration/test_search_quality_lopo_500.py`. 기존
LOPO test 와 분리.

## Forbidden Patterns

- 기존 test 함수 수정 X (별 파일).
- mock store / hardcoded data X.
- 검색 알고리즘 변경 X (측정만).
- `from tunallama_core.store import Store` 등 잘못된 import X (실제 모듈은
  `tunallama_core.memory.store.MemoryStore`).

## Acceptance

- 522 record 시드 색인 1회.
- 432 query × 5 path × 4 metric 측정.
- per-path P@1, R@5, MRR, NDCG@5 + σP@1, σR@5.
- 102 record LOPO 와 비교 표 (dogfooding-log 에 추가).

## Constraints

- 알고리즘 변경 X.
- pytest mark `search_quality` 필수.
- cloud timeout 600 초 + retry 3 회 (Phase 4-4 패턴 그대로).

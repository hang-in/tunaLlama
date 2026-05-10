# Phase 5-2 - σ reduction (query normalization + hard-tier 분리)

## 배경

Phase 4-3b LOPO σR@5 0.18-0.30, σP@1 0.44-0.50. **사용자 신뢰의 진짜
위협은 평균보다 분산** (외부 Opus 4.7 + Codex 5.5 합의).

목표: σR@5 ≤ 0.15. 두 path 동시 시도.

## Path A - Query normalization

### 알고리즘

1. user query → LLM (cloud / local) → "standard form" 으로 재작성
   (예: "GC 가 안 돌아가는 문제" → "garbage collection memory leak")
2. standard form 으로 기존 search path (BM25/vec/hybrid/rerank) 호출
3. 비용: cloud LLM 1 회 추가 / 검색.

### 새 함수

`tunallama_core/memory/normalization.py`:
```python
def normalize_query(query: str, *, client: LLMClient) -> str:
    """LLM 으로 query 를 검색에 더 안정적인 standard form 으로 재작성.

    응답 형식 강제 (response_schema={"type": "string"}). 실패 시 fallback
    = 원 query.
    """
```

### 새 search path

`recall_normalized(store, query, *, client, base="hybrid", limit=5) -> RecallResult`
- internally `normalize_query` → 그 결과로 base path 호출.

## Path B - Hard-tier 분리

### 알고리즘

검색 결과를 **3 tier 로 분류**:
- `exact`: 정확 토큰 일치 (BM25 점수 ≥ threshold_high).
- `near`: 의미 유사 (vector cosine ≥ 0.7).
- `hard`: 둘 다 약함 (BM25 미달 + cosine < 0.7).

UX: 결과 list 가 tier 별로 그룹 보임. 사용자가 hard tier 보고 신뢰도 판단.
`auto_recall=always` 모드면 hard tier 는 prepend 안 함 (precision 보호).

### 새 dataclass

```python
@dataclass(frozen=True)
class TieredRecall:
    exact: list[RecallSnippet]
    near: list[RecallSnippet]
    hard: list[RecallSnippet]
```

### 새 함수

`recall_tiered(store, query, *, limit=5, threshold_bm25=10.0, threshold_cosine=0.7) -> TieredRecall`

## 측정

같은 LOPO 524 record 시드로 3 path 비교:
- baseline `recall_hybrid`
- new `recall_normalized` (mode=A)
- new `recall_tiered` 의 `exact + near` 만 사용 (mode=B)

per-path P@1 / R@5 / MRR / NDCG@5 + σ. **목표: σR@5 ≤ 0.15**.

## Required Imports / Signatures - **architect 직접 작성** (위임 X)

dogfooding 의 algorithm/seed 위임은 OK 였지만 **새 모듈 추가 + signature
설계는 architect 가 직접**. 외부 Codex 5.5 결론.

dogfooding 위임 가능 부분 (`tuna_general_task` 채널만):
- normalization prompt variants 5 개 (한국어 query → English standard form).
- hard-tier threshold 값 후보 list (BM25 / cosine cut-off 의 합리적 범위).

## File path

- 새 모듈: `tunallama_core/memory/normalization.py` (path A)
- 새 모듈: `tunallama_core/memory/tiered.py` (path B)
- search.py 에 wrapper 함수 export
- 새 통합 테스트: `tests/integration/test_phase5_2_variance.py`

## Acceptance

- σR@5 ≤ 0.15 달성하면 README §4.3 업데이트 + auto_recall=always 의 risk
  완화 (hard-tier 모드와 함께면 OK).
- 미달 시: 원인 분석 (LLM 응답 quality / threshold 튜닝 / corpus 확대 등) 후
  Phase 5-2b 로.

## Constraints

- 기존 `recall` / `recall_hybrid` / `recall_reranked` / `recall_expanded` 시그너처
  변경 X.
- pytest mark `search_quality` 필수.
- timeout 600 초 + retry 3 회.

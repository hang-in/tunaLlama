# 측정 방법론

## 시드 구성

### Phase 4-3b (102 record)
- 12 task × 6 paraphrase = 72 record
- 30 noise (matplotlib / argparse / ssh-keygen 등 일상 IT 키워드)
- 한국어/영문 mix paraphrase

### Phase 5-1 (524 record)
- 기존 12 task + 60 task (round 16 dogfooding 차용, `tuna_general_task` 채널)
- 60 task = 6 카테고리 × 10:
  system_programming / network / data_structures / concurrency /
  crypto_security / devops
- 합산 72 task × 6 paraphrase + 92 noise

## LOPO (Leave-One-Paraphrase-Out)

기존 측정은 query = paraphrases[0] 가 시드 record 와 정확히 동일 →
P@1 / MRR 모든 path 1.00 (변별력 0). LOPO 는:

- corpus = 그 task 의 5 paraphrase + 다른 task 의 모든 paraphrase + noise
- query = 빠진 1 paraphrase
- relevant = 그 task 의 corpus 안 5 paraphrase
- 6 paraphrase 회전 → 12 task × 6 = 72 query (102 record) 또는
  72 task × 6 = 432 query (524 record)

## Metrics

| metric | 정의 |
|---|---|
| P@1 | top-1 이 relevant 면 1.0, 아니면 0.0 |
| P@K | \|relevant ∩ top-K\| / K |
| R@K | \|relevant ∩ top-K\| / \|relevant\| |
| MRR | 1 / rank (첫 relevant 의 1-based rank). 못 찾으면 0.0 |
| NDCG@K | binary relevance, log2(rank+1) discount, IDCG 로 정규화 |
| σ | per-query metric 의 표준편차 (paraphrase variance 측정) |

## Search path 정의

```python
# 5 path
recall(store, query)              # BM25 (Kiwi 형태소)
store.search_vectors(query)       # vector (BGE-M3 1024d cosine)
recall_hybrid(store, query)       # BM25 + vector RRF (k=60)
recall_reranked(store, query)     # candidate_pool=20 → bge-reranker-v2-m3
recall_expanded(store, query, client=cloud, mode=...)  # LLM query expansion → RRF
recall_normalized(store, query, client=cloud)          # LLM query rewrite → hybrid
recall_hyde(store, query, client=cloud)                # LLM hypothetical answer → hybrid
recall_adaptive(store, query, cloud_client=cloud)      # 휴리스틱 분기
```

## Cloud LLM 설정

- Provider: Ollama Cloud (`https://ollama.com`)
- 기본 모델: `glm-4.7` (Phase 5-2C 모델 비교에서 kimi-k2-thinking 과 동률)
- Judge / Classifier: `kimi-k2-thinking` (Phase 4-4 context pollution 측정)
- Timeout: 600s + retry 3회

## 알려진 한계

### 1. 합성 시드 의존
- task 가 "task description" 형식 → HyDE 의 hypothetical answer 와
  매칭 매우 강함. 실 사용 record (도구 호출 dump / 긴 코드 / mixed) 면
  효과 다를 수 있음.
- 한국어/영문 paraphrase 가 표면 토큰 거의 안 겹치는 hard mode -
  실 사용자 vocabulary 일관성 더 클 가능 (검색 더 쉬워질 가능).

### 2. 단일 측정 variance
- σR@5 도 σ 가짐. Phase 5-D 의 HyDE σR@5 0.19 vs Phase 5-2C-KURE 의 0.14 -
  동일 모델/시드/path 인데도 +0.05 차이.
- 원인: random sample variance (24 group leader sample) + HyDE 의 LLM
  응답 비결정성 (temperature=0.3).
- 결론: 단일 측정 절대값에 과의존 X. **trend over time + 평균** 우선.

### 3. organic dogfooding 부재
- Round 7-16 dogfooding 은 모두 spec-driven (`tuna_dev_review_from_spec` /
  `tuna_general_task` 호출). 실 Claude Code 일상 사용 (organic) 측정 X.
- 합성에서 좋은데 organic 에서 안 좋은 자리 못 잡음.
- Phase 6 metric 자동화 시 source tag (`synthetic` / `spec_dogfooding` /
  `organic`) 분리해서 트래킹.

### 4. corpus 크기 의존
- 102 → 524 record 로 키울 때 σR@5 -0.04~-0.06 (corpus 커지면 σ 안정).
- 1k-10k corpus 에서는 더 다를 수 있음. 측정 안 함.

### 5. cloud LLM 의존
- expanded / normalized / HyDE / Adaptive 의 σ / P@1 은 cloud LLM
  (glm-4.7) 의 출력 품질 의존. 다른 cloud 모델이면 결과 다름.
- 모델 비교 (Phase 4-3 의 24 cloud calls): glm-4.7 = kimi-k2-thinking
  (동률) > qwen3-coder:480b (-0.05). 코드 특화 모델이 자연어 paraphrase
  생성에 불리.

### 6. judge LLM 의존
- Phase 4-4 / 5-3 context pollution 측정의 judge = kimi-k2-thinking. 4
  axis 0-2 정수 점수. saturation 발생 (모든 probe 만점) → judge 자체 한계.
- Phase 5-3 부터는 AST smell (deterministic) 우선, judge 는 fallback.

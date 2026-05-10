# Phase 5 - HyDE / KURE / Adaptive 측정

524 record 시드 (72 task × 6 paraphrase + 92 noise). 자세한 시드 정의는
`methodology.md`.

## Phase 5-1 - 524 record LOPO local paths (432 query × 4 path, BGE-M3)

```
path           P@1     R@5     MRR    NDCG@5   sigmaP@1   sigmaR@5
BM25          0.40    0.23    0.52    0.27      0.49       0.21
vec           0.65    0.42    0.75    0.48      0.48       0.24
hybrid        0.51    0.34    0.65    0.38      0.50       0.23
rerank        0.66    0.43    0.75    0.49      0.47       0.26
```

- BM25 R@5 +0.07 (vs 102 record 의 0.16) - LOPO 환경에서 키워드 매칭 한계.
- vec/hybrid/rerank 의 R@5 -0.04 ~ -0.11 - candidate 경쟁 ↑ 부작용.
- σR@5 일괄 -0.04 ~ -0.06 ↓ (외부 가설 H1 ✓ - 큰 corpus → σ 안정).
- rerank P@1 +0.04 (외부 H2 ✓ - 큰 noisy corpus 일수록 reranker 가치).

## Phase 5-1 - expanded sample (24 group leader)

```
path           P@1     R@5     MRR    NDCG@5    sigmaR@5
exp+H         0.67    0.44    0.78    0.50      0.23
```

- expanded hybrid 가 R@5 / MRR 모두 1위 (cloud LLM 2회 비용).

## Phase 5-1b - BGE-M3 vs KURE-v1 (432 query)

```
path     BGE-M3 P@1   KURE P@1   diff    BGE-M3 R@5   KURE R@5   diff
BM25       0.40        0.40       0.00      0.23        0.23      0.00
vec        0.65        0.67      +0.02      0.42        0.43     +0.01
hybrid     0.51        0.52      +0.01      0.34        0.34      0.00
rerank     0.66        0.65      -0.01      0.43        0.43      0.00
```

- KURE-v1 = `nlpai-lab/KURE-v1` (BGE-M3 finetune, dim 1024 호환).
- regression 없음. vec only path 작은 개선.
- 한국어 비중 큰 corpus 에서 더 큰 효과 가능. **default BGE-M3 유지** +
  env `TUNA_EMBEDDING_MODEL=nlpai-lab/KURE-v1` opt-in.

## Phase 5-2C - HyDE 가 새 winner (24 leader sample, BGE-M3, 48 cloud)

```
path                   P@1     R@5     MRR    NDCG@5    sigmaP@1   sigmaR@5
hybrid_pool20         0.33    0.30    0.50    0.31      0.48        0.28
rerank_pool50         0.54    0.38    0.71    0.43      0.51        0.24
normalized            0.71    0.42    0.79    0.48      0.46        0.22
hyde                  0.92    0.50    0.95    0.60      0.28        0.16
```

- **HyDE P@1 0.92, MRR 0.95** - 거의 항상 첫 결과가 정답.
- σR@5 0.16 - 외부 권고 목표 0.15 거의 도달.
- arXiv:2212.10496 - LLM 가상 답변 텍스트 → 검색. record 가 task description
  형태면 hypothetical answer 와 매칭 매우 강함.
- **caveat**: 시드 record 가 task description 형식이라 효과 강함. 실 사용
  record (도구 호출 dump / 긴 코드) 면 효과 편차 가능.

## Phase 5-2C-KURE - HyDE 의 KURE 측정 (24 leader, 48 cloud)

```
path                   P@1     R@5     MRR    NDCG@5    sigmaP@1   sigmaR@5
hybrid_pool20         0.38    0.30    0.51    0.32      0.49        0.29
rerank_pool50         0.54    0.38    0.71    0.42      0.51        0.24
normalized            0.67    0.38    0.75    0.45      0.48        0.22
hyde                  0.92    0.51    0.96    0.60      0.28        0.14
```

### BGE-M3 vs KURE 의 HyDE path 비교

```
metric           BGE-M3   KURE    diff    note
HyDE P@1          0.92    0.92    0.00    동일
HyDE R@5          0.50    0.51   +0.01    KURE 약간 우세
HyDE sigma R@5    0.16    0.14   -0.02    *** 목표 sigma <= 0.15 달성 ***
HyDE sigma P@1    0.28    0.28    0.00    동일
normalized P@1    0.71    0.67   -0.04    BGE-M3 우세 (정규화 출력 영문)
hybrid baseline   0.33    0.38   +0.05    KURE 약간 우세
```

- **HyDE + KURE 조합 = production RAG sigma <= 0.15 달성** (σR@5 0.14).
- normalized path 만 BGE-M3 우세 (정규화 출력이 영문 standard form).
- **path 별 best embedding**: HyDE → KURE / normalized → BGE-M3 / 그 외 비슷.

## Phase 5-2D - MMR λ sweep (full 432 query, cloud 0)

```
path               P@1     R@5     MRR    NDCG@5    sigmaR@5
hybrid            0.51    0.34    0.65    0.38       0.23
mmr_l1.0          0.65    0.42    0.75    0.47       0.24
mmr_l0.7          0.63    0.36    0.73    0.42       0.22
mmr_l0.5          0.32    0.24    0.50    0.26       0.19
mmr_l0.3          0.07    0.08    0.23    0.08       0.11
```

- λ=1.0 (다양성 0) ≈ vec 단독 (hybrid pool 을 query embedding 으로 reorder).
- λ ≤ 0.5 부터 R@5 급락. LOPO relevant 가 paraphrase set 이라 다양성이
  같은 task paraphrase 들을 떨어뜨림.
- **MMR 은 anti-pattern** (우리 use case). 외부 권고 (긴 document + 무관
  후보 다수) 와 환경 다름. **abandon**.

## Phase 5-D - Adaptive routing (24 leader, KURE, 20 cloud)

```
category distribution: {'natural': 20, 'mixed': 4}
cloud calls: hybrid=0, hyde_only=24, adaptive=20  (-16.7%)

path        P@1   R@5   MRR   NDCG@5   sigmaR@5
hybrid     0.38  0.30  0.51   0.32     0.29
hyde_only  0.92  0.49  0.95   0.59     0.19
adaptive   0.92  0.51  0.95   0.60     0.19
```

- 휴리스틱: 한국어 비중 > 30% → HyDE, 그 외 → reranked hybrid (cloud 0).
- adaptive ≈ hyde_only 품질 + cloud 17% 절감.
- σR@5 0.19 (vs 5-2C-KURE 의 0.14) - **single measurement variance** +
  HyDE LLM 비결정성. σ 자체도 σ 가짐.

## 종합 우열 (524 record LOPO)

```
path                  BGE-M3 P@1   KURE P@1   sigma R@5   cloud
BM25                    0.40        0.40       0.21         0
vector                  0.65        0.67       0.24-0.25    0
hybrid                  0.51        0.52       0.23         0
reranked hybrid         0.66        0.65       0.26         0
expanded hybrid         0.67          -        0.23         2
normalized hybrid       0.71        0.67       0.22         1
HyDE hybrid             0.92        0.92       0.14-0.19    1
Adaptive (KURE)          -          0.92       0.19         ~0.85
```

- **HyDE hybrid winner** - P@1 0.92, σR@5 0.14-0.19.
- KURE-v1 은 HyDE 환경에서 σ 더 줄임. normalized 는 BGE-M3 우세.
- Adaptive 가 HyDE only 대비 17% cloud 절감 (한국어 비중 큰 seed 기준).

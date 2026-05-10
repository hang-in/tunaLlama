# Phase 4 - 검색 품질 측정

102 record 시드 (12 task × 6 paraphrase + 30 noise). 자세한 시드 정의는
`methodology.md`.

## Phase 4-3 paraphrase variance (12 × 6 = 72 query / path)

```
path           P@1     P@5     R@5     MRR    sigmaP@1   sigmaR@5
BM25          1.00    0.73    0.29    1.00     0.00       0.14
vec           1.00    0.61    0.51    1.00     0.00       0.21
hybrid        1.00    0.60    0.50    1.00     0.00       0.20
rerank        1.00    0.65    0.54    1.00     0.00       0.22
exp+B         1.00    0.74    0.45    1.00     0.00       0.23
```

- **self-match**: query = paraphrases[0] 가 record 와 정확 동일 → P@1 / MRR
  모든 path 1.00 (변별력 0).
- σR@5 0.14-0.23 큼 - query 표현이 검색 품질의 dominant 변수.
- exp+B (expanded BM25, cloud LLM 1회) 가 BM25 baseline 0.16 → 0.45 로 R@5
  +0.29 향상.

## Phase 4-3 expanded path × 3 모델 (24 cloud calls)

```
model                        P@1     P@5     R@5     MRR
glm-4.7                     1.00    0.75    0.62    1.00
kimi-k2-thinking            1.00    0.75    0.62    1.00
qwen3-coder:480b            1.00    0.68    0.57    1.00
```

- glm-4.7 = kimi-k2-thinking 동률.
- **qwen3-coder:480b -0.05 ~ -0.07**. 코드 특화 모델이 자연어 paraphrase
  생성에 불리. query expansion 에는 일반 reasoning 모델 권장.

## Phase 4-3b LOPO (72 query, query 와 record 분리)

corpus = 그 task 의 5 paraphrase + 다른 task 의 모든 paraphrase + 30
noise. query = 빠진 1 paraphrase.

```
path           P@1     R@5     MRR    NDCG@5   sigmaP@1   sigmaR@5
BM25          0.38    0.16    0.44    0.21      0.49       0.18
vec           0.65    0.46    0.74    0.51      0.48       0.29
hybrid        0.51    0.45    0.67    0.47      0.50       0.27
rerank        0.62    0.51    0.74    0.54      0.49       0.30
exp+H         0.74    0.52    0.81    0.57      0.44       0.29
```

- **P@1 변별력 회복**: 0.38-0.74 로 path 우열 명확.
- exp+H 가 모든 metric 1위. MRR 0.81 = 평균 첫 relevant rank 1.23.
- σ 큼 - query 표현 따라 hit/miss 강하게 분리.

## Phase 4-4 컨텍스트 오염 A/B (5 probe × 2 mode × 3 run = 30 generate)

```
mode          corr   focus   minim   smell   total
never         2.00    2.00    2.00    2.00    8.00
always        2.00    2.00    2.00    2.00    8.00
```

- 모든 axis / probe / mode 만점 일괄 (variance 0).
- artifacts 분석: never 와 always 의 코드 line/char/imports 정확히 동일
  (avg 8 lines, 197 chars).
- **cloud LLM (glm-4.7) 이 무관 recall prefix 자동 무시** - context
  pollution risk 우려보다 작음. 단 always 의 positive 효과도 없음.
- **5 probe (gcd/vowels/mean/fizzbuzz/deep_merge) 가 too narrow** - 단일
  함수 task 라 recall 효과 거의 없음. cross-task probe 필요 (Phase 5-3).

## Phase 5-3 cross-task adversarial (6 probe × 2 mode × 3 run = 36 generate)

mode "always_adv" = 의도적으로 spec 무관한 recall prefix prepend (e.g.
GCD task 에 password_hashing record).

```
mode              n   valid   kw_hit%   excess
never            18    1.00     0.0%     0.11
always_adv       18    1.00     0.0%     0.00
```

- per-probe kw_hit always_adv **0%** - cloud LLM 이 의도적 무관 prefix
  도 강하게 무시.
- excess_score (AST smell): never 0.11 → always_adv 0.00 (오히려 더 깨끗).
- Phase 4-4 + 5-3 합의: **auto_recall=always 의 risk 가 우려보다 작음**
  + positive 효과도 거의 없음 → 자동 prepend 자체에 큰 가치 없음.
- 결론: recall 의 가치는 prepend 가 아닌 **사용자 명시 호출 surface**.

# Phase 5-D / 5-E - rerank pool sweep + corpus scaling (524 → 984)

524 record 환경의 결과 (`phase5-hyde-kure.md`) 가 corpus 키울 때 어떻게
변하는지, 그리고 rerank `candidate_pool` 파라미터가 실효 있는지 측정.

## Phase 5-D - rerank candidate_pool sweep (524 record, 432 query, cloud 0)

```
pool   P@1   R@5   MRR  NDCG@5  sigmaP@1  sigmaR@5
20    0.66  0.43  0.75   0.49   0.47      0.26
50    0.66  0.44  0.76   0.49   0.47      0.26
100   0.67  0.43  0.76   0.49   0.47      0.26
```

- **finding**: pool >20 효과 미미 (P@1/R@5 +/-0.01).
- 이유: 524 record 환경에서 paraphrase 5 개가 top-20 안에 거의 다 들어와
  pool 확장이 candidate 추가 효과 없음.
- **default candidate_pool=20 유지**. 50/100 으로 늘려도 cross-encoder
  추론 비용만 증가하고 품질 향상 없음.

## Phase 5-E - 984 record LOPO local paths (792 query x 4 path, cloud 0)

```
path           P@1     R@5     MRR    NDCG@5   sigmaP@1   sigmaR@5
BM25          0.53    0.31    0.62    0.36      0.50       0.25
vec           0.75    0.55    0.82    0.60      0.43       0.30
hybrid        0.63    0.42    0.73    0.47      0.48       0.27
rerank        0.77    0.59    0.83    0.63      0.42       0.31
```

seed 구성: 132 task x 6 paraphrase + 192 noise = 984 record
(기존 72 task + NEW_GROUPS_60_v2 60 task 합본 - mobile_dev, web_frontend,
backend_api, ml_inference, observability, data_pipeline 도메인).
색인 1회 + LOPO 으로 paraphrase holdout 5 개 relevant set.

### vs Phase 5-1 (524 record) 비교

```
path         524 P@1   984 P@1    delta   524 R@5   984 R@5    delta
BM25          0.40      0.53      +0.13    0.23      0.31      +0.08
vec           0.65      0.75      +0.10    0.42      0.55      +0.13
hybrid        0.51      0.63      +0.12    0.34      0.42      +0.08
rerank        0.66      0.77      +0.11    0.43      0.59      +0.16
```

**핵심 findings**:

1. **corpus 1.88배 키울 때 모든 path P@1 +0.10~0.13 / R@5 +0.08~0.16 향상**.
   특히 dense+cross-encoder (vec/rerank) 가 향상폭 큼.
2. **rerank R@5 0.59 (524 의 0.43 대비 +0.16)** - 더 많은 paraphrase 가
   noise 와 경쟁해도 cross-encoder 가 보존하는 폭이 큼.
3. **BM25 만 P@1 +0.13 향상에 비해 R@5 +0.08 작은 폭**. BM25 는 top-1
   에 정답 박는 능력은 늘지만 R@5 (paraphrase recall) 는 약함.
4. **vec P@1 0.75 / rerank P@1 0.77** - cloud 0 path 에서 P@1 0.8 직전.

### sigma 가설 검증

외부 권고 가설: sigma 가 1/sqrt(N) 비례 → 524 -> 984 면 sigma x 0.73x.
실측 결과:

```
metric          524     984      ratio    expected
sigma R@5 (rr)  0.26    0.31     1.19x    0.73x
sigma P@1 (rr)  0.47    0.42     0.89x    0.73x
```

- **sigma ~ 1/sqrt(N) 가설 거짓**. sigma R@5 오히려 증가 (0.26 -> 0.31).
- 원인 가설: NEW_GROUPS_60_v2 가 추가됐는데 도메인 어휘 (mobile_dev /
  observability / data_pipeline) 가 기존 72 task 보다 더 specific terms 를
  포함. **harder group 추가가 corpus 효과 상쇄**.
- sigma 감소는 corpus 크기뿐 아니라 group 난이도 분포에 의존.

### Per-domain breakdown (구상)

mobile_dev / web_frontend / backend_api 같은 도메인별 sigma 분해는 sample
size 작아 (6 paraphrase x 10 task = 60 query / domain) 추가 측정 필요.
LOPO 1k 의 holdout 별 dump 가 있어야 가능.

## 종합 - cloud 0 path 새 베이스라인 (984 record)

```
                    P@1     R@5     MRR    NDCG@5    cloud
BM25               0.53    0.31    0.62    0.36       0
vec                0.75    0.55    0.82    0.60       0
hybrid             0.63    0.42    0.73    0.47       0
rerank             0.77    0.59    0.83    0.63       0
```

- **rerank P@1 0.77** - cloud 0 path 의 최강.
- HyDE 측정 (P@1 0.92) 는 24 leader sample 이라 직접 비교 X. 1k full LOPO
  에서 HyDE 재측정은 별도 작업 (cloud 호출 792 회 부담).

## 다음 단계 후보

- HyDE / KURE / Adaptive path 1k 측정 (cloud 호출 비용 큰 별 단계).
- per-domain sigma 분해 (NEW_GROUPS_60_v2 도메인별 R@5 측정).
- 더 큰 corpus (2k, 5k) 에서 sigma 안정성 vs 도메인 난이도 분리.

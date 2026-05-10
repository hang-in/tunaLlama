# Dogfooding 로그

tunaLlama 자체를 tunaLlama 로 검증한 기록. Phase 2 부터의 작업 흐름은
`docs/specs/<name>.md` 작성 → `tuna_dev_review_from_spec` 호출 → 결과 검증 →
약점은 `~/.tunallama/limitations.md` 에 기록 (다음 호출에 자동 prepend) +
이 파일에도 사례별로 기록.

`limitations.md` 는 모델용, 이 파일은 개발자용.

---

## Phase 3 결과 측정 — 2026-05-10

### Synonym seed (Phase 3-1) — 36 record × 6 query × P@5/R@5

```
group                   BM25 P  BM25 R   vec P   vec R   hyb P   hyb R
----------------------------------------------------------------------
memory_leak               1.00    0.17    0.60    0.50    0.60    0.50
email_validation          1.00    0.17    0.80    0.67    0.80    0.67
file_compression          1.00    0.17    1.00    0.83    1.00    0.83
json_parsing              0.80    0.67    0.80    0.67    0.80    0.67
password_hashing          1.00    0.17    0.80    0.67    0.80    0.67
rate_limit                0.50    0.17    0.80    0.67    0.80    0.67
----------------------------------------------------------------------
AVG                       0.88    0.25    0.80    0.67    0.80    0.67
```

- ✓ **vector R@5 (0.67) >> BM25 R@5 (0.25)** — paraphrase 시드에서 의미
  매칭 **2.7배 우세** 정량 검증.
- BM25: P=0.88 (정확), R=0.25 (놓치는 게 많음).
- hybrid = vector — 두 환경(키워드/paraphrase) 모두 vector 와 동일.

### Phase 2 + 3 검색 품질 종합

| 시나리오 | BM25 | vector | hybrid | expanded BM25 |
|---|---|---|---|---|
| 키워드 일치 (Phase 2) | P=1.00 ✓ | P=0.67 | = vector | - |
| paraphrase (Phase 3-1) | R=0.25 | R=0.67 ✓ | = vector | **R=0.50** (2x BM25) |

**의사결정**: 일상 메모리 검색은 BM25(Kiwi) 만으로 충분. 다양한 표현으로 같은
task 검색 시 vector / hybrid 또는 LLM-augmented `recall_expanded`. 모두
backend 에 살아있고 사용자가 호출 시점에 선택.

### Query expansion 측정 디테일 (Phase 3.5)

```
group                     BM25     vec    hyb   exp+B   exp+H
--------------------------------------------------------------
memory_leak               0.17    0.50    0.50    0.17    0.50
email_validation          0.17    0.67    0.67    0.17    0.67
file_compression          0.17    0.83    0.83    0.50    0.83
json_parsing              0.67    0.67    0.67    0.67    0.67
password_hashing          0.17    0.67    0.67    0.83    0.67
rate_limit                0.17    0.67    0.67    0.67    0.67
--------------------------------------------------------------
AVG                       0.25    0.67    0.67    0.50    0.67
```

- query 별 편차 큼 - memory_leak / email_validation 은 expansion 효과 X,
  password_hashing 은 0.17 -> 0.83 까지.
- 실 cloud LLM (glm-4.7) 호출 - 측정 12 회 (6 query × 2 mode) 에 ~12 분.
- 호출당 ~1초가 아니라 평균 60-110 초 - cloud 응답 지연 큼. 실 사용에서는
  비용/지연 trade-off 고려해 `mode="bm25"` (paraphrase 약점 공략) 만 권장.

### Cross-encoder reranker 측정 (Phase 3.6)

`BAAI/bge-reranker-v2-m3` (~600MB) 도입. 1차 hybrid candidate_pool=20 → reranker.

```
group                     BM25     vec     hyb   rer+H   rer+B
--------------------------------------------------------------
memory_leak               0.17    0.50    0.50    0.50    0.17
email_validation          0.17    0.67    0.67    0.83    0.17
file_compression          0.17    0.83    0.83    0.83    0.17
json_parsing              0.67    0.67    0.67    0.67    0.67
password_hashing          0.17    0.67    0.67    0.67    0.17
rate_limit                0.17    0.67    0.67    0.67    0.17
--------------------------------------------------------------
AVG                       0.25    0.67    0.67    0.69    0.25
```

- rer+H R@5 = 0.69 vs hybrid 0.67 - **+0.02, 거의 noise 수준**.
- rer+B = 0.25 - 1차 BM25 의 R 한계 그대로 (1차에 못 잡힌 record 는 reranker 도 못 살림).
- email_validation 만 0.67→0.83 - 재정렬이 도움 된 유일한 케이스.

**원인 추정**:
- 시드 36 record 작음. reranker 의 진가는 큰 noisy corpus.
- paraphrase 가 명확해 bi-encoder candidate_pool=20 에 정답 6 개 다 들어감 → 재정렬 여지 X.
- R@5 보다 P@1 / MRR 에 reranker 효과 더 큼 - 우리 측정 안 함.

**검색 품질 한계 인정 + 가이드**:
- `auto_recall = "always"` 비권장. 기본값 `on_request` 유지.
- README 에 검색 품질 한계 경고 명시 (4.3 섹션).
- 코드는 모두 활성화 유지 (graceful degrade) - 사용자가 큰 corpus 에서 옵션 사용.
- precision-aware 측정 (P@1, MRR) + 더 큰 시드는 Phase 4 후보.

## Phase 4 결과 측정 - 2026-05-10

### 102 record 시드 (12 task × 6 paraphrase + 30 noise) - leader-only baseline

```
path           P@1     P@5     R@5     MRR
BM25          1.00    0.64    0.26    1.00
vec           1.00    0.65    0.54    1.00
hybrid        1.00    0.62    0.51    1.00
rerank        1.00    0.70    0.58    1.00
exp+B         1.00    0.67    0.42    1.00
```

- leader query (paraphrases[0]) 가 시드 record 와 정확히 동일 → **P@1/MRR
  =1.00 일괄, 변별력 0**.
- R@5 만 변별력. rerank > vec > hybrid > exp+B (mode=bm25) > BM25.
- 36 record (Phase 3) 와 비교: vec 0.67 → 0.51, rerank 0.69 → 0.58 - corpus
  커지면서 candidate 경쟁 증가. 정상 패턴.

### Paraphrase variance (12 × 6 = 72 query / path, 약 1시간)

```
path           P@1     P@5     R@5     MRR    σP@1    σR@5
BM25          1.00    0.73    0.29    1.00    0.00    0.14
vec           1.00    0.61    0.51    1.00    0.00    0.21
hybrid        1.00    0.60    0.50    1.00    0.00    0.20
rerank        1.00    0.65    0.54    1.00    0.00    0.22
exp+B         1.00    0.74    0.45    1.00    0.00    0.23
```

- σR@5 0.14-0.23 - query 표현마다 R@5 0.30-0.75 범위 흔들림.
- P@5 와 R@5 우위 path 가 다름:
  - P@5: exp+B (0.74) > BM25 (0.73) > rerank (0.65) > vec (0.61) > hybrid (0.60).
  - R@5: rerank (0.54) > vec (0.51) > hybrid (0.50) > exp+B (0.45) > BM25 (0.29).
- self-match 로 P@1 변별력 0 - 다음 측정은 query 를 시드에 없는 표현으로
  분리해서 ranking 측정 필요.

### Expanded path × 3 모델 비교 (12 group × leader, mode=hybrid, 약 20분)

```
model                        P@1     P@5     R@5     MRR
glm-4.7                     1.00    0.75    0.62    1.00
kimi-k2-thinking            1.00    0.75    0.62    1.00
qwen3-coder:480b            1.00    0.68    0.57    1.00
```

- **glm-4.7 ≡ kimi-k2-thinking** - 소수점 둘째 자리까지 동일.
- **qwen3-coder:480b 가 약함** (-0.07/-0.05). 코드 특화 모델이 자연어
  paraphrase 생성에 불리. query expansion 에는 일반 reasoning 모델 권장.
- mode=hybrid 의 expanded R@5 = 0.62 - **vec/rerank 도 능가**. hybrid 베이스
  expansion 이 P@5 / R@5 둘 다 최강.

### 의사결정

| 케이스 | 권장 path |
|---|---|
| 키워드 일치 (Phase 2 시드) | BM25 (P=1.00) |
| 가벼운 paraphrase (사용자 vocabulary 일정) | rerank/vec (cloud 호출 0) |
| 강한 paraphrase + cloud 가용 | **expanded hybrid** (R@5 0.62, P@5 0.75) |
| 자동 컨텍스트 주입 (`auto_recall=always`) | 비권장 - R@5 0.5 면 절반 noise |

### 측정 자체의 한계

- self-match 로 P@1/MRR 변별력 0. query 와 record 분리 필요.
- 시드 102 record 는 실 사용 1k-10k corpus 와 다름.
- 한 group 6 paraphrase 가 표면 토큰 거의 안 겹치는 hard mode - 일상 사용
  분포보다 가혹함.

---

## Phase 5-2 결과 - σ reduction (variance 잡기)

### Path A - normalized (LLM query 정규화 + hybrid, 24 group sample, 39분 55초)

```
path                   P@1     R@5     MRR    NDCG@5    σP@1    σR@5   σNDCG
hybrid_baseline       0.33    0.30    0.50      0.31    0.48    0.28    0.29
normalized            0.71    0.42    0.79      0.49    0.46    0.22    0.24
σR@5 reduction = -0.06 (개선)
```

- **P@1 +0.38 (0.33 → 0.71)** = 거대한 ranking 개선.
- σR@5 -0.06, σNDCG -0.05.
- LLM 으로 query 를 standard English form 으로 재작성 → 검색 path 가 표면
  토큰에 덜 의존, σ 안정.
- **expanded path 의 P@1 0.67 보다 높음** (524 record). cloud LLM 1 회만
  쓰고도 expanded (2 회) 이김. **production RAG 의 가성비 winner**.

### Path B - tiered threshold sweep (cloud 0, 432 query × 3 preset, 2분 52초)

```
preset                 P@1     R@5     MRR    NDCG@5    σP@1    σR@5   σNDCG   avg_n
relax (default)       0.51    0.32    0.64      0.37    0.50    0.23    0.25    12.5
medium                0.51    0.27    0.61      0.33    0.50    0.21    0.25     7.5
strict                0.50    0.26    0.59      0.31    0.50    0.22    0.25     7.2
```

- σR@5 0.21-0.23 거의 동일 (-0.02 미만). **filter 효과 X**.
- strict 일수록 R@5 ↓ (true relevant false negative).
- **결론**: tiered threshold 만으로는 σ 못 잡음. UX 분리 (사용자에게 신뢰도
  표시) 가치는 남으나, σ reduction 의 진짜 winner 는 path A.

## Phase 5-3 결과 - cross-task pollution (architect 직접, 31분 19초)

```
mode              n   valid   kw_hit%    excess
never            18    1.00      0.0%      0.11
always_adv       18    1.00      0.0%      0.00
```

6 probe (all isolated function) × 2 mode × 3 run = 36 generate_code + AST smell.
mode "always_adv" = 의도적으로 spec 무관한 recall prefix prepend (e.g. GCD
task 에 password_hashing record).

- **per-probe kw_hit always_adv 0%** - cloud LLM (glm-4.7) 이 무관 prefix
  강하게 무시. instruction-following spec 우선.
- excess_score: never 0.11 → always_adv 0.00 (오히려 always 가 약간 깨끗).
- Phase 4-4 (toy probe saturate) + Phase 5-3 (kw 0%) 합의: **cloud LLM 의
  무관 컨텍스트 자동 필터링이 강하다**. context pollution risk 가 우려보다 작음.
- 단 recall prefix 의 positive 효과도 없음 - **"recall 가치는 prepend 가
  아니라 사용자 명시 호출 surface"** 결론 강화.

## Phase 5-1 결과 - 524 record LOPO (architect 직접, 23분 54초)

102 → 524 record 시드 (12 기존 + 60 round 16 dogfooding 차용 + 92 noise).

```
=== local paths (432 query / path) ===
path           P@1     R@5     MRR    NDCG@5    σP@1    σR@5   σNDCG
BM25          0.40    0.23    0.52      0.27    0.49    0.21    0.24
vec           0.65    0.42    0.75      0.48    0.48    0.24    0.27
hybrid        0.51    0.34    0.65      0.38    0.50    0.23    0.26
rerank        0.66    0.43    0.75      0.49    0.47    0.26    0.28

=== expanded sample (24 group leader) ===
exp+H         0.67    0.44    0.78      0.50    0.48    0.23    0.24
```

### 102 vs 524 record 비교 (외부 가설 검증)

| metric | 102 | 524 | diff | hypothesis |
|---|---:|---:|---:|---|
| σR@5 vec | 0.29 | 0.24 | -0.05 | **H1 ✓** corpus 커지면 σ 감소 |
| σR@5 exp+H | 0.29 | 0.23 | -0.06 | **H1 ✓** |
| σR@5 rerank | 0.30 | 0.26 | -0.04 | **H1 ✓** |
| rerank P@1 | 0.62 | 0.66 | +0.04 | **H2 ✓** rerank 가치 ↑ |
| exp+H P@1 | 0.74 | 0.67 | -0.07 | candidate 경쟁 ↑ |
| R@5 vec/hyb/rer | - | - | -0.04 ~ -0.11 | distractor 늘어남 (정상) |

### 의미

- **σ 감소** = 외부 Opus 4.7 의 핵심 가설 정량 확인. 524 record 만 가도
  σR@5 < 0.25 도달. 1k+ corpus 면 더 안정될 가능성.
- **rerank 의 진가는 큰 corpus**. 102 record 환경에선 미미했지만 524 환경
  에서 P@1 +0.04. Codex 5.5 의 "큰 noisy corpus 일수록 reranker 가치" 일치.
- **expanded path 의 R@5 0.44** - 524 환경에서도 path 1위. cloud LLM 비용
  받아들이면 production-grade 검색 품질 가능.
- **R@5 일괄 하락** - candidate_pool=20 한도가 발목. Phase 5-2b 후보:
  candidate_pool=50 으로 확대.

## Phase 4-3b LOPO 측정 결과 - 2026-05-10 (architect 직접, 1시간 16분)

LOPO (leave-one-paraphrase-out) - 72 query (12 task × 6 회전).

```
path           P@1     R@5     MRR    NDCG@5    σP@1    σR@5   σNDCG
BM25          0.38    0.16    0.44      0.21    0.49    0.18    0.22
vec           0.65    0.46    0.74      0.51    0.48    0.29    0.31
hybrid        0.51    0.45    0.67      0.47    0.50    0.27    0.29
rerank        0.62    0.51    0.74      0.54    0.49    0.30    0.31
exp+H         0.74    0.52    0.81      0.57    0.44    0.29    0.30
```

- **P@1 변별력 회복 ✓**. 이전 self-match (모든 path 1.00) → 0.38-0.74 로 분리.
- **expanded hybrid 가 모든 metric 1위** - P@1 0.74, MRR 0.81, NDCG@5 0.57, R@5 0.52.
- MRR 0.81 = 평균 첫 relevant rank 1.23. exp+H 검색은 **거의 항상 첫 결과에 정답**.
- BM25 R@5 0.16 - LOPO 환경 (key paraphrase 누락) 에서 키워드 매칭 한계 명확.
- σP@1 0.44-0.50 - binary metric 최대 σ. query 마다 hit/miss 강하게 분리.

### Phase 4-3 paraphrase variance 와 비교

| 시드 / measurement | BM25 P@1 | vec P@1 | exp P@1 | exp R@5 |
|---|---:|---:|---:|---:|
| 102 record + paraphrases[0] | 1.00 | 1.00 | 1.00 | 0.45 (mode=bm25) |
| 102 record + 6 paraphrase | 1.00 | 1.00 | 1.00 | 0.62 (hybrid) |
| **LOPO (corpus 5 + 빠진 1)** | **0.38** | **0.65** | **0.74** | **0.52** |

**LOPO 가 진짜 ranking 측정**. 이전 측정은 self-match 라 P@1/MRR 죽은 메트릭.

## Phase 4-4 측정 결과 - 2026-05-10 (54분, 30 generate + 30 judge)

```
mode          corr   focus   minim   smell   total
never         2.00    2.00    2.00    2.00    8.00
always        2.00    2.00    2.00    2.00    8.00
```

**모든 axis / probe / mode 가 만점 일괄, 변별력 0**. artifacts 분석:
- never 와 always 의 코드 line/char/imports 모두 정확히 동일 (avg 8 lines, 197
  chars, 0 imports).
- always 가 recall prefix prepend 됐는데도 결과 코드 100% 동일 → 모델이 toy
  probe 환경에서 recall prefix 무시.
- judge comment 빈 문자열 - kimi-k2-thinking 이 schema comment 채우지 않음
  (cloud schema 강제 한계 재확인).

**해석** (외부 Codex 5.5 사전 경고 정량 검증):
- "5 probe (gcd/vowels/mean/fizzbuzz/deep_merge) 가 too narrow, 다 isolated
  function. recall 효과는 cross-task 에서 진짜 드러남" - 그대로 실현.
- 측정 자체로는 "**always 가 toy 환경 코드 품질 명백히 안 망가뜨림**" 약한
  positive signal.
- 결정적 증거 X. cross-task probe + AST smell + paired design 으로 다음
  iteration 필요 (memory `project_phase4_followups.md`).

## Round 16 - 2026-05-10 · Phase 5-1 시드 합성 · glm-4.7 · `tuna_general_task` 채널

- 위임 도구 변경: `tuna_dev_review_from_spec` (spec→generate→review)
  → `tuna_general_task` (catch-all). round 7-15 의 standalone-toy 패턴은
  **dev_review 흐름 자체가 코드 작성 모드 강제**한 결과로 추정.
- 위임 내용: 60 task × 6 paraphrase + 60 noise. 출력 형식 명시 + Forbidden
  Patterns (함수/import/pytest/f-string fake) 강조.
- 결과: ✓ **첫 차용 가능 dogfooding**. NEW_GROUPS_60 = 60 list, 각 6
  paraphrase 한국어/영문 mix. NOISE_60 = 60 string. **함수 정의 / pytest /
  f-string fake 0**.
- 사소한 결함: noise 마지막 부분에 git commit/push/pull/merge 등 9 개 git
  키워드 중복. architect 통합 시 일부 다양화 또는 그대로 두기.
- 결론: dogfooding 의 진짜 통증은 spec 형식이 아니라 **위임 채널**. spec
  형식 (negative limitations / positive grounding) 는 둘 다 dev_review 흐름
  안에서는 무력. catch-all 채널이 자유 출력 가능.

## Round 15 - 2026-05-10 · Phase 5-1 시드 첫 시도 · glm-4.7 · dev_review_from_spec

- spec: "list literal 만, 함수/import/pytest X" 명시. round 14 와 같이
  positive + negative grounding 모두.
- 결과: ✗ 또 standalone-toy. pytest 함수 + `is_korean()` / `is_english()`
  helper + f-string fake paraphrase ("한국어 작업 1 (v1)" 같은). 9 회 일관 패턴.
- 차용 가치: 0.
- 결정적 시그널: **bounded output 위임에도 dev_review 흐름은 코드 모드**.
  → round 16 에서 채널 변경.

## Round 14 - 2026-05-10 · Phase 4-3b (LOPO) · glm-4.7 · positive grounding 첫 시험

- spec: 외부 Opus 4.7 검토 따라 **Required Imports / Required Call Signatures
  / Forbidden Patterns** 명시 + File path 지정. 외부 검토 가설: "negative
  limitations 보다 positive 가 강함, 모델이 '하지 마라' 보다 '이걸 써라' 에
  훨씬 잘 반응".
- 결과: ✗ **가설 깨짐**. positive grounding 도 limitations.md 와 동일 패턴.
  - `from tunallama_core.memory.metrics import compute_metrics, RetrievalMetrics` 무시.
  - 새 `MetricResult` dataclass + `calculate_metrics(List[List[int]])` 시그너처.
  - `MemoryStore` 호출 0 회. 시드 0 record.
  - hardcoded test_data dict 로 ranks 배열 만든 toy.
  - "Forbidden np.random / MockSearchEngine" 명시했지만 hardcoded mock 으로 우회.
- **대조 검증**: round 7-14 = 8 번 일관 standalone-toy. spec 형식 (negative /
  positive / hybrid) 모두 효과 X.
- **결론**: Codex 5.5 의 진단이 정답. integration coder 위임 자체가 비경제적.
  dogfooding 은 **bounded output only** (알고리즘 초안 / seed 데이터 / prompt
  variants / 실패 샘플) 로 재포지셔닝 확정.
- Architect 통합: LOPO 측정은 architect 직접 작성 (다음 단계).

## Round 13 - 2026-05-10 · Phase 4-4 (context pollution A/B) · glm-4.7

- spec: 5 probe × 2 mode × 3 run = 30 회 **실 dev_review** + judge LLM 평가
  명시. acceptance "30 dev_review 호출 완료 + 모든 코드 저장".
- 결과: **np.random 으로 점수 시뮬**. dev_review 호출 0 회, judge 호출 0 회.
  - `BIAS_ALWAYS = -0.35` 매직 넘버로 always 모드만 -0.35 깎이도록 인위적 시뮬.
  - `np.clip(np.random.uniform(0.6, 0.9) + bias, 0, 1)` - 결과 미리 정해진 fake.
  - **README.md 직접 덮어쓰기** - 위험.
  - `tunallama_core` 어떤 모듈도 사용 X.
- 차용 가치: 0. 시뮬 toy 라 측정 가치 없음.
- Architect 통합: 직접 작성 - `tests/integration/test_context_pollution.py`
  (30 회 실 dev_review + judge LLM, kimi-k2-thinking).

## Round 12 - 2026-05-10 · Phase 4-3 (extended seed + 4-metric) · glm-4.7

- spec: `MemoryStore` + `compute_metrics` + 12 task × 6 paraphrase + 30 noise
  명시. acceptance 에 "우리 실 API 사용" 못 박음.
- 결과: 또 **standalone toy**.
  - `from tunallama_core.store import Store` (실: `MemoryStore`).
  - `from tunallama_core.clients import CloudClient` (모듈 자체 없음).
  - `compute_metrics` 가 dict `{'P@1': ...}` 반환 가정 (실: `RetrievalMetrics`
    dataclass).
  - `store.add(text)` 가공 API. 실: `record_call(tool_name, inputs, output, ...)`.
- 차용 가치: **시드 데이터 자체** (12 task × 6 paraphrase + 30 noise list).
  논리/구조/import 는 폐기.
- Architect 통합: `tests/integration/test_search_quality_extended.py` 직접
  작성. 102 record store fixture + 5 path × 4 metric 측정 + paraphrase variance
  측정 함수.

## Round 11 - 2026-05-10 · Phase 3-2 (semantic_edges) · glm-4.7

- spec: `LLMClient` + `MemoryStore.graph_edges` + `rebuild_edges` 변경 명시.
- 결과: **OpenAI SDK 가정** (`client.chat.completions.create(...)`),
  **MockStore 작성** - 우리 실 도구 무시. pytest 함수 6개 작성됨.
- 정직 평가: 통합 가능 코드 X. 차용: prompt 패턴, `id_a < id_b`, max_pairs.
- Architect 통합: 우리 `LLMClient.chat()`, `graph_edges` 테이블, `rebuild_edges`
  rule edges 만 삭제하도록 수정 (semantic_related 보존). 9 단위 테스트.

## Round 10 — 2026-05-10 · Phase 3-1 (synonym_seed) · glm-4.7

- spec: 18 record + recall@5 측정. 우리 실 도구 사용 명시.
- 결과: **MockSearchEngine 작성** — 우리 실 도구 우회.
- 정직 평가: 측정 가치 0. 차용: 시드 36 record, precision/recall 패턴.
- Architect 통합: 우리 `MemoryStore` + 실 BGE-M3 + 실 도구 호출.

## dogfooding 12 회 누적 결론

- **모델은 spec 의 형식 hint(pytest 함수, dataclass) 는 따르지만 우리
  코드베이스 통합(정확한 import, 실 인터페이스, schema migration) 은 거의
  매번 무시**. round 7-12 일관 패턴 - 12회째에도 동일.
- **dogfooding 의 가치는 "drop-in 코드" 가 아니라 "알고리즘/디테일 차용"**:
  prompt 패턴, blob 검증, RRF 점수 합산, `normalize_embeddings`, SQL JOIN,
  id 정규화 — 모델이 잘 발견하고 architect 가 통합.
- **limitations.md 자동 prepend 효과 측정**:
  - round 1→2: pytest 형식 미준수 → 카탈로그 추가 → pytest 함수 작성 ✓.
  - round 7+: "기존 코드 보존, 단일 책임" 안내해도 standalone toy 작성 — 한계.
- **delegation pattern 의 진짜 가치**: 코드 자동화가 아니라 **시간/토큰 절약 +
  탐색 보조**. Architect 의 검증 + 통합 단계는 필수.

## Round 1 — 2026-05-10 · iso_datetime_parser

- **모델**: `gemma4:31b` (Ollama Cloud)
- **spec**: `docs/specs/iso_datetime_parser.md` (ISO 8601 파서, 7 acceptance 케이스)
- **iterations**: max=2, 한도 도달 (수렴 안 함)
- **acceptance pytest**: 7/7 통과 (외부에서 손으로 작성 후 실행)
- **결과 코드**: `parse_iso(s)` 정확. timezone-aware 보장.

### 발견 약점

1. **Acceptance 가 "pytest N 케이스 통과" 인데도 inline `__main__` 블록만 작성**.
   pytest 함수 미작성. spec 의 acceptance 형식을 모델이 정확히 안 따름.
   → `tuna_log_limitation()` 으로 카탈로그에 기록 (round 2 에 자동 prepend).

2. **dev_review 의 verdict heuristic false positive**.
   review 가 단점 나열 (`Redundancy`, `Implicit UTC Assumption` 등) 만 해도
   LGTM 토큰이 없으면 issues 로 판정 → 불필요한 fix 루프 진입.
   codex review #3 의 권고가 실측으로 정당화됨.

---

## Round 2 — 2026-05-10 · 같은 spec, limitations.md 적재 후

- **변경사항**: round 1 의 약점이 `~/.tunallama/limitations.md` 에 추가됨.
  dev_review_loop 가 자동으로 prepend.
- **결과 코드**: ✓ **`@pytest.mark.parametrize` + `test_parse_iso_success` +
  `test_parse_iso_failure`** — pytest 함수로 정확히 작성됨.

### 검증된 가설

- **limitations 자동 prepend 가 작동**. delegation 패턴의 핵심 가치 — 같은
  실수를 반복하지 않도록 카탈로그에 누적 → 다음 호출에 모델이 인지.

### 여전한 약점

- **VERDICT 첫 줄 형식 따르지 않음**. round 1 과 동일하게 `**Focus Area:**`
  로 시작. 이때는 verdict 구조화가 코드에 없었으므로 prompt 강화 후 다시 시도.

---

## Round 3 — 2026-05-10 · _prompts.REVIEW_CODE 강화 후

- **변경사항**: `tunallama_core/delegation/_prompts.py` 의 `REVIEW_CODE` 가
  `VERDICT: PASS` / `VERDICT: FAIL` 첫 줄을 명시적으로 요구.
- **결과**: ✗ **여전히 `**Focus Area: Code Review**` 로 시작**. VERDICT 형식 무시.

### 확인된 사실

- system prompt 에서 *"Reply MUST start with one line in this exact form: ..."*
  를 강조해도 gemma4:31b 가 무시. 이전 review 패턴(markdown bullets)을 더 강하게 학습한 듯.

---

## Round 10 — 2026-05-10 · Phase 3-1 (synonym_seed) · glm-4.7

- spec: 6 task × 3 paraphrase (=18) 시드 + recall@5 측정. 우리 실 도구
  (`recall`, `search_vectors`, `recall_hybrid`) 사용 명시.
- 결과: **MockSearchEngine 작성** — 우리 실 도구를 우회하고 in-memory dict
  로 검색 시뮬레이션. dev_review 2 iteration 모두 같은 패턴. round 7-9 와
  동일 prior.
- 정직 평가: 측정 가치 0. 차용: 시드 36 record (6 task × 6 paraphrase) —
  spec 보다 풍부. precision/recall 계산 함수.
- Architect 직접 통합: 우리 `MemoryStore` + 실 BGE-M3 + 실 도구 호출 +
  assertion.

## 검색 품질 측정 — 2026-05-10

`tests/integration/test_search_quality.py` (`@pytest.mark.search_quality`).
실 BGE-M3 + 12 record 시드(한국어/영문 코딩 task 페어) + 6 query 의 precision@3.

```
query                     BM25    vector    hybrid
--------------------------------------------------
이메일 검증                    1.00      0.67      0.67
validate email            1.00      0.67      0.67
JSON 파싱                   1.00      0.67      0.67
memory leak               1.00      0.67      0.67
비밀번호 해시                   1.00      0.67      0.67
decorator pattern         1.00      0.67      0.67
--------------------------------------------------
AVG                       1.00      0.67      0.67
```

### 해석

- **BM25 P@3 = 1.00**: Kiwi 형태소 색인이 한국어 query 도 깨끗이 잡음. 영문은
  unicode61 그대로. 시드가 명확한 키워드 매칭이라 keyword-based 가 완벽.
- **vector P@3 = 0.67**: cross-lingual 페어는 잡지만 의미적 유사성으로 다른
  task 도 함께 끌어옴 (precision 희석).
- **hybrid = vector 동일**: BM25 가 100% 인 시나리오에서는 RRF 가 vector 의
  noise 만 추가 → BM25 만 못함. 자연.

### Cross-lingual 검증 (vector 의 진짜 가치)

`test_korean_query_finds_english_pair_via_vector` 통과 — `이메일 검증` 으로 검색
시 영문 `validate email address` (id=2) 가 top-3 에 등장.
`test_english_query_finds_korean_pair_via_vector` 통과 — `memory leak` 으로
검색 시 `메모리 누수 탐지` (id=5) 가 top-3 에 등장.

### 결론

- 일상 한국어/영문 메모리 검색은 **BM25(Kiwi) 만으로 충분**.
- **벡터의 가치는 cross-lingual / paraphrase / 동의어** — 시드 차원에서는
  추가 측정 필요.
- **hybrid 의 우위** 는 BM25 가 약한 시나리오에서 측정해야 — Phase 3 후보.

## Phase 2 종합 — Round 7-9 결론

3 라운드 모두 같은 패턴:
- ✓ 알고리즘 핵심은 모델이 합리적으로 작성 (RRF 점수 합산, JOIN 으로 O(N²)
  Python 회피, threading.Lock, blob 길이 검증 등 — round 7 의 좋은 발견을
  round 8/9 에 limitations.md 가 prepend 해 효과 누적).
- ✗ 우리 코드베이스 통합 부분(정확한 import 경로, RecallSnippet vs VectorHit
  타입 통합, schema migration, `MemoryStore.conn` API) 은 모델이 무시. 매번
  standalone prototype 으로 반환.
- ✗ Acceptance 의 pytest N 케이스 작성 0건 — 3 라운드 모두.

→ **dogfooding 의 가치는 "코드 그대로 통합" 이 아니라 "알고리즘 / 디테일 차용"**.
이번 작업 흐름 (Architect 가 결과 차용 + 우리 구조에 맞춰 직접 통합 + 테스트
직접 작성) 이 가장 효율적이었다. spec 단위 분할(3개) 도 검증된 선택 — 한
spec 이 한 번에 다 잡히지 않더라도 차용할 부분만 명확.

차용 내역:
- Round 7 → Phase 2-1: lazy load + threading.Lock, `normalize_embeddings=True`,
  blob 길이 검증.
- Round 8 → Phase 2-2: RRF 점수 합산 패턴 (`scores[id] += 1/(k+rank)`),
  `expanded_limit = limit * 2` 확장 풀.
- Round 9 → Phase 2-3: SQL JOIN 으로 O(N²) 처리 (Python 메모리 회피),
  `a.id < b.id` 정규화.

직접 작성:
- 정확한 모듈 분리 (vector.py, graph.py 별도)
- 우리 MemoryStore 인터페이스 / 시그너처 일치
- schema migration 코드 (ALTER TABLE 의 idempotent 처리)
- pytest 케이스 (각 spec 의 Acceptance 충족)

## Round 9 — 2026-05-10 · Phase 2-3 (graph_edges) · glm-4.7

- spec: 6+ pytest 케이스, rule edges (same_project / same_day / same_tool),
  BFS traverse, schema migration.
- 결과: 알고리즘 정확 (SQL JOIN + 재귀 CTE), Edge dataclass 정확.
- 못한 부분: pytest 케이스 0개, schema migration 누락, `MemoryStore.conn` 대신
  `Store.execute(...)` Protocol 가정.
- Architect 통합: SQL JOIN 패턴 그대로, 재귀 CTE → Python BFS 로 단순화 (cycle
  처리 명확), schema 추가 + idempotent migration.

## Round 8 — 2026-05-10 · Phase 2-2 (hybrid_rrf) · glm-4.7

- spec: 5+ pytest, RRF k=60, dedup, vector 미존재 시 BM25 fallback.
- 결과: ✓ `recall()` signature 보존 (limitations 효과), ✓ RRF 알고리즘 정확.
  ✗ `RecallSnippet.full_id` vs `VectorHit.id` 타입 불일치, ✗ `from .types import
  RecallResult` 같이 우리 모듈 구조 무시, ✗ 테스트 0개.
- Architect 통합: RRF 알고리즘 그대로, snippet_map 으로 BM25/벡터 dedup,
  VectorHit → RecallSnippet 변환 추가.

## Round 7 — 2026-05-10 · Phase 2-1 (vector_recall) · glm-4.7

- **변경사항**: model = `glm-4.7` (config.toml). spec
  `phase2_vector_recall.md` (244 줄) 으로 dogfooding.
- **결과**: ✗ **drop-in 통합 불가**. 모델이 spec Constraints 를 무시하고
  task 를 처음부터 다시 짜는 경향. MemoryStore 새로 작성, FTS5/기존 record_call
  스키마 무시, schema migration 누락, pytest 6+ 케이스 미작성.

### 잘 한 부분 (참고할 만함)

- `embed()` lazy load + `threading.Lock` self-discovered (race 방지).
- `SentenceTransformer(...).encode(..., normalize_embeddings=True)` —
  L2 normalize 의 native flag 사용 (수동 normalize 보다 정확).
- blob 길이 검증 (`len(blob) != 1024 * 4`) 으로 corrupted record 방어.

### 못 한 부분

- **단일 책임 분리** (spec: vector.py vs store.py 별도) → 한 파일.
- **기존 BM25 / FTS5 INSERT 보존** → MemoryStore 새로 작성.
- **schema migration** (calls.embedding 추가) 누락.
- **Acceptance pytest 6+** 케이스 작성 0개.
- **import 패턴** — 우리 패키지 구조 (`tunallama_core.memory.*`) 무시,
  standalone 모듈로 작성.

### 결정적 발견

`gemma4`, `kimi`, `glm-4.7` 모두 **task 처음부터 새로 짜기** prior 가 강함.
review prompt 의 markdown 형식과 같은 패턴 — 학습 데이터의 흔한 형태가 우리
spec 의 명시적 Constraints 를 압도. spec 에 "modify, do not rewrite" / 변경할
파일 경로 + 줄 범위 / 보존할 시그너처 그대로 첨부 — 이런 강한 boundary 가
없으면 모델은 standalone prototype 을 반환.

### 처리 방침

이번 라운드는 **Architect 가 부분 결과 차용 + 직접 통합** — dogfooding 결과의
좋은 디테일(thread-lock, normalize_embeddings, blob 검증) 만 가져와 우리
구조(vector.py 신규 + schema migration + store.py 수정 + 테스트)에 맞춰 작성.
사용자 의도("Phase 2 도 dogfooding 으로") 를 100% 만족하지 않으나, spec 강화
후 재호출 비용 대비 효율성 우선.

`tuna_log_limitation` 으로 약점 기록 — 다음 spec 호출에 자동 prepend.

---

## Round 6 — 2026-05-10 · JSON Schema 강제 시도, cloud 미지원 확인

- **변경사항**: `LLMClient.chat` 에 `response_schema` 옵션. Ollama 는
  `client.chat(format=schema)`, LM Studio 는
  `body["response_format"]["json_schema"]` 매핑. dev_review_loop 의 review
  단계에 `REVIEW_SCHEMA = {verdict: PASS|FAIL, findings: [str]}` 강제.
- **dogfooding 결과**: ✗ JSON 안 옴, markdown 그대로.
- **직접 검증**: ollama python SDK 로 `format=schema` + cloud 모델
  4종(`gemma4:31b`, `gpt-oss:20b`, `qwen3-coder-next`, `devstral-small-2:24b`)
  모두 schema 무시. → **Ollama Cloud 인프라 자체가 schema 강제 미지원**.
- **LM Studio strict 검증**: 로컬 `nvidia/nemotron-3-nano-4b` 가
  `response_format.strict=True` 에서 빈 응답 반환 — 모델 capability 부족.

### 결론

자연어로도, schema 로도 첫줄 형식 강제는 우리 환경에서 작동 안 함. 다음 후보는
**stage-2 classifier**: review freeform 받고, 별도 single-token 호출로
PASS/FAIL 분류. 한 단어 출력은 모든 모델이 학습된 분포에 정합.

### Stage-2 classifier prerun 측정

같은 4 cloud 모델 모두 strict prompt 에서 `PASS` 또는 `FAIL` 단일 토큰을 깨끗
하게 출력. 첫 시도에서 모든 모델이 FAIL (boundary 불명확) → "PASS = style /
version-note / preference, FAIL = bug or wrong output" 명시 prompt 로 모두
PASS 정확 출력.

→ classifier 가 cloud 환경의 verdict 신뢰성 확보 수단으로 확정.

---

## Round 5 — 2026-05-10 · kimi-k2-thinking 으로 모델 교체

- **변경사항**: `~/.tunallama/config.toml` 의 model 을 `gemma4:31b` →
  `kimi-k2-thinking` 으로 변경. plugin reload (`/reload-plugins`).
- **결과**: ✗ **여전히 `**Focus Area: Code Review**` 로 시작**.
  reasoning 변종 / 더 큰 모델로도 동일 패턴.

### 결정적 발견

- 모델 크기/reasoning 변종은 영향 X. "code review" task 의 학습된 prior
  (`**Focus Area:**` 헤더 + bullet findings) 가 너무 강해 자연어 system/user
  명령으로 이길 수 없다.
- **자연어 강제는 best-effort 가 한계**. sampling-time grammar enforcement
  (Ollama `format=<schema>` / LM Studio `response_format`) 가 본질적 해결.

→ **Phase 2 코드 변경 정당화**: JSON Schema harness 도입 (round 6 에서 측정).

---

## Round 4 — 2026-05-10 · review_code user prompt 끝에 reminder 추가

- **변경사항**: `tunallama_core/delegation/code.py::review_code` 가 user prompt
  끝에 한 줄 reminder 추가:
  ```
  REMINDER: Your reply MUST start with `VERDICT: PASS` or `VERDICT: FAIL`...
  ```
- **결과**: ✗ **여전히 무시**. 본문 분석은 정상이나 첫 줄 형식 강제는 작동 안 함.

### 결론

`gemma4:31b` 는 system 첫줄 + user 끝줄 둘 다 강조해도 첫 줄 verdict 라벨을
일관되게 출력하지 않는다. instruction-following 한계.

---

## 누적 약점 / 향후 우선순위

| 순위 | 약점 | 시도한 mitigation | 상태 | 다음 |
|---|---|---|---|---|
| 1 | spec acceptance 형식 (pytest 명시) 미준수 | limitations.md 등록 | ✅ 해결 (R2) | — |
| 2 | dev_review verdict heuristic false positive | VERDICT 첫줄 강제 (R3, R4) | ⚠ gemma4:31b 비호환 | two-stage verdict OR 다른 모델 |
| 3 | Python 3.11+ 의존 noting (review 단점 나열) | — | 사소 (실제 PASS 수준) | — |

### Phase 2 후보 우선순위 (재정렬)

1. **two-stage verdict** — review_code 의 freeform 본문 + 별도 short prompt 로
   classifier 단계 추가. classifier 입력: review text. 출력: `PASS|FAIL` only.
   small-model 친화 (단일 단어 출력).
2. 또는 **다른 cloud 모델 시험** — `qwen3-coder-next` / `qwen3-coder:480b` /
   `kimi-k2.6` 등에서 VERDICT 형식 따르는지. dogfooding round 5+ 로 측정.
3. **벡터 임베딩 + RRF** (seCall 패턴) — 여전히 가치 있지만 verdict 문제보다 후순위.

향후 dogfooding 추가 시 이 파일에 라운드 단위로 append.

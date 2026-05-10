# Phase 5 - Production RAG Roadmap

## 배경

Phase 4 측정 종료 시점 (2026-05-10) 의 자리:
- **R@5 0.52 (LOPO, exp+H)** vs RAG 표준 0.8+ → **gap ~0.3**.
- **σR@5 0.18-0.30** → query 표현이 검색 품질 dominant 변수.
- **σP@1 0.44-0.50** → query 마다 hit/miss 강하게 분리.
- **Phase 4-4 context pollution 변별력 0** (toy probe saturation).
- **delegation 토큰 절약은 미측정** - 정성적 가치만 주장.

목표: **production RAG 시스템 합격선** (`R@5 ≥ 0.8`, `σR@5 ≤ 0.15`,
`auto_recall=always` 가 코드 품질에 + 또는 0 효과 검증).

## 4 단계

### Phase 5-1: 시드 확장 (102 → 500+ record)

가장 작은 변경. 알고리즘 X, 측정 환경만 키움.
- corpus 크기가 σ / R@5 에 어떤 영향 미치는지.
- 큰 corpus 에서 reranker 가 더 가치 (bi-encoder candidate 경쟁 ↑).
- LOPO measurement 재실행 - 102 vs 500 record 표 비교.

dogfooding 위임: "60 task description × 6 paraphrase 합성" (bounded seed
data generation).

### Phase 5-2: σ reduction

방법 후보 + 우선순위:
1. **Query normalization**: LLM 으로 query → standard form 변환 후 검색.
   외부 Opus 4.7 권고. cloud LLM 1 호출 추가.
2. **Hard-tier 분리**: corpus 에 없는 expression 은 별도 tier 로 보고.
   user 에게 confidence 표시. 알고리즘 X, UX 변경.
3. **Reranker 강화**: `bge-reranker-v2-gemma` (~2GB) 시도. CPU/GPU 부담 ↑.

**우선 1 + 2 동시**. 3 은 알고리즘 변경 큼, 별 phase.

dogfooding 위임: "Korean/English mix query 의 normalization prompt
variants 5 개 작성" (bounded prompt variant generation).

### Phase 5-3: cross-task probe Phase 4-4 재측정

외부 Codex 5.5 권고:
- isolated function (gcd 등) → cross-task continuation 추가.
- recall prefix artifact 항상 저장.
- judge 보다 deterministic AST smell + unit test 우선.
- paired design (같은 probe/run 에서 always vs never 비교).
- adversarial set: "irrelevant but tempting" memory 의도 삽입.

dogfooding 위임: "cross-task probe 시나리오 3 종 + AST smell 후보 메트릭
list" (bounded design exploration).

### Phase 5-4: delegation token measurement

방법:
- 같은 task N 회 양쪽 실행:
  - mode A: 네이티브 Claude (메인 conversation 에서 직접 코드 작성)
  - mode B: 플러그인 (`tuna_dev_review` 위임)
- 각 모드의 메인 conversation 토큰 사용량 비교.
- task 분류: small (10 lines) / medium (50 lines) / large (200+ lines).
- delegation 의 break-even 라인 수 측정.

dogfooding 위임 X (측정 자체가 dogfooding 토큰 비교).

## v0.2.0 vs v0.3.0 분리

- **v0.2.0** (현재 - 보류 중): Phase 4 끝까지 + 솔직한 한계 명시 release.
  외부 검토 합의 메시지 (`coding memory` 포지셔닝).
- **v0.3.0**: Phase 5-1, 5-2, 5-3, 5-4 다 들어간 production-grade release.
  R@5 ≥ 0.8 + σ ≤ 0.15 + delegation 토큰 절약 정량.

## Constraints

- 측정 자산은 정직 보고. 실패해도 dogfooding-log + README 에 기록.
- 알고리즘 변경 (Phase 5-2 의 reranker 강화 등) 은 별 spec.
- dogfooding 은 **bounded output only** (알고리즘 초안 / seed / prompt variant
  / design exploration). integration coder 위임 X (round 7-14 패턴).

# Phase 4-4 - Context pollution A/B 측정

## 배경

`auto_recall = "always"` 옵션이 dev_review 호출에 매번 과거 메모리를 자동
prepend 하면, **무관한 과거 컨텍스트가 코드 품질을 떨어뜨릴 가능성**이 있다
(P@1 < 0.5 인 검색 품질에서는 거의 보장된 위험).

이 측정에서는 같은 작업을 두 모드로 돌려 **품질 지표 차이**를 잰다.

## Hypothesis

- H0: `always` 가 `never` 보다 유의미하게 나쁘지 않다 (recall 이 도움 < 무해).
- H1: 검색 품질이 낮은 시점에 `always` 는 **netto 마이너스** (오염 > 보강).

## 측정 design

### A. Seed
`tests/integration/test_search_quality_extended.py` 의 102 record store 를
재사용 (memory_leak / email_validation / ... 12 group + noise 30).

### B. Probe task
컨텍스트 오염이 잘 드러나는 작은 dev task 5개. spec 은 짧은 markdown.

| ID | task |
|----|------|
| P1 | 두 정수 입력받아 GCD 반환하는 Python 함수 |
| P2 | string 의 vowel 갯수 세는 함수 (영문) |
| P3 | list 의 평균 (mean) 계산 함수 |
| P4 | 1-100 fizzbuzz |
| P5 | 두 dict 깊게 머지 (deep merge) |

전부 단순/표준 - 정상이면 쉽게 정답에 도달. 컨텍스트 오염되면 **memory_leak/
hashing/rate_limit 같은 store seed 의 무관한 코드 패턴**이 섞일 수 있음.

### C. 두 모드 N 회 반복
- mode A: `auto_recall = "never"` (추가 prepend 없음)
- mode B: `auto_recall = "always"` (probe query 로 recall 5개 prepend)

각 probe × 각 mode × **3 회 반복** (모델 비결정성 완충) = 5 × 2 × 3 = **30 dev_review 호출**.
모델은 `glm-4.7` 단일 (그룹 변수 줄임).

### D. 평가 - LLM-as-judge

생성된 코드 + spec 을 별도 reviewer 모델 (`kimi-k2-thinking`) 에 제출:

```
Spec: <P-N spec>
Generated code:
<code>

다음 4 axis 를 0-2 정수로 점수 (0=실패, 1=부분, 2=완벽):
- correctness: spec 의 의도 동작 일치
- focus: spec 외 무관 코드/주석 없는지 (recall pollution 측정 핵심)
- minimality: 스펙 이상의 abstraction/추가 함수 없는지
- code_smell: 불필요한 import / dead code / 잘못된 type annotation 없는지

JSON 출력만: {"correctness": ..., "focus": ..., "minimality": ..., "code_smell": ..., "comment": "<1줄>"}
```

`focus` 와 `minimality` 가 컨텍스트 오염의 핵심 시그널.

### E. 결과 표

| probe | mode | run | correctness | focus | minimality | code_smell | total |
|---|---|---|---|---|---|---|---|

집계: per-mode AVG ± stddev. 차이를 dogfooding-log + README "Search quality"
세션에 정직 추가.

## Acceptance

- 30 dev_review 호출 완료 + 모든 코드 저장 (artifacts).
- Per-mode AVG 표.
- README 에 "auto_recall=always 사용 시 검증 결과" 섹션 추가.
- 만약 `always` 가 `never` 보다 focus/minimality 평균이 ≥ 0.3 낮으면, README 에
  **경고 문구 강화**.

## 비-Acceptance (해선 안 됨)

- 검색 알고리즘 변경 (이번 측정은 algorithm 고정).
- new mode 추가.
- artifacts 누락 (정직 보고 위해 raw output 다 보존).

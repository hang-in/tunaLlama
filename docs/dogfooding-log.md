# Dogfooding 로그

tunaLlama 자체를 tunaLlama 로 검증한 기록. Phase 2 부터의 작업 흐름은
`docs/specs/<name>.md` 작성 → `tuna_dev_review_from_spec` 호출 → 결과 검증 →
약점은 `~/.tunallama/limitations.md` 에 기록 (다음 호출에 자동 prepend) +
이 파일에도 사례별로 기록.

`limitations.md` 는 모델용, 이 파일은 개발자용.

---

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

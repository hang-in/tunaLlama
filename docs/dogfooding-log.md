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

| 시나리오 | BM25 | vector | hybrid |
|---|---|---|---|
| 키워드 일치 (Phase 2) | P=1.00 ✓ | P=0.67 | = vector |
| paraphrase (Phase 3-1) | R=0.25 △ | R=0.67 ✓ | = vector |

**의사결정**: 일상 메모리 검색은 BM25(Kiwi) 만으로 충분. 다양한 표현으로 같은
task 검색 시 vector / hybrid. 둘 다 backend 에 살아있고 사용자가 호출 시점에
선택.

## Round 11 — 2026-05-10 · Phase 3-2 (semantic_edges) · glm-4.7

- spec: `LLMClient` + `MemoryStore.graph_edges` + `rebuild_edges` 변경 명시.
- 결과: **OpenAI SDK 가정** (`client.chat.completions.create(...)`),
  **MockStore 작성** — 우리 실 도구 무시. pytest 함수 6개 작성됨.
- 정직 평가: 통합 가능 코드 X. 차용: prompt 패턴, `id_a < id_b`, max_pairs.
- Architect 통합: 우리 `LLMClient.chat()`, `graph_edges` 테이블, `rebuild_edges`
  rule edges 만 삭제하도록 수정 (semantic_related 보존). 9 단위 테스트.

## Round 10 — 2026-05-10 · Phase 3-1 (synonym_seed) · glm-4.7

- spec: 18 record + recall@5 측정. 우리 실 도구 사용 명시.
- 결과: **MockSearchEngine 작성** — 우리 실 도구 우회.
- 정직 평가: 측정 가치 0. 차용: 시드 36 record, precision/recall 패턴.
- Architect 통합: 우리 `MemoryStore` + 실 BGE-M3 + 실 도구 호출.

## dogfooding 11 회 누적 결론

- **모델은 spec 의 형식 hint(pytest 함수, dataclass) 는 따르지만 우리
  코드베이스 통합(정확한 import, 실 인터페이스, schema migration) 은 거의
  매번 무시**. round 7-11 일관 패턴.
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

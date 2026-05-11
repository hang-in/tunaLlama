# Phase 7-2 - 로컬 mid-size LLM 컨텍스트 보강 효과 측정

## 배경

새 framing (사용자 2026-05-11 결정):

> 클로드코드 (Opus / Sonnet) 가 무거운 코딩 작업을 mid-size 로컬/cloud LLM
> 에 위임. 로컬 LLM 은 **컨텍스트 한계 (~32k-128k)** 가 있어 architect 가
> 위임 전 **관련 컨텍스트를 검색해 prepend** 해야 작업 가능. 검색의 진짜
> 가치는 이 시점에 있음.

지금까지 측정은 cloud LLM (glm-4.7) 기준 + sample 24 group leader 였음.
사용자의 진짜 사용 시나리오는 **로컬 27-31B mid-size 모델 + recall prefix**.
이 시나리오에서:
1. recall prefix 없으면 코드 품질 떨어지는가?
2. recall prefix 있을 때 어느 모델이 잘 활용하는가?
3. unrelated prefix (Phase 5-3 의 adversarial) 도 무시할 만큼 robust 한가?

## 모델 후보

Ollama Cloud 사용 가능 + 사용자 의도 "mid-size + 최신":

| model | size | 카테고리 |
|---|---|---|
| `gemma4:31b` | 31B | **default - 2026 출시 최신 Google** |
| `qwen3-coder-next` | ~30B 추정 | Qwen 최신 코드 특화 |
| `kimi-k2.6` | 미공개 (mid) | Moonshot 최신 |

(gemma3:27b 는 outdated 라 제외 - "사용자 의도: 굳이 오래된 모델 X")

cloud quota 약 $20 넉넉. 4 모델 × 측정 가능.

## 측정 design (Phase 5-3 변형)

### Probe (cross-task continuation, isolated 아님)

각 probe = `(prior_context, current_task)` 페어. prior_context 가 recall
prefix 로 prepend 되면 도움, 안 되면 spec 만으로 작업.

| probe | prior context (recall prefix 후보) | current task |
|---|---|---|
| P1 | "이 프로젝트는 `MemoryStore` 사용 (NOT `Store`)" | "user record 조회 함수 작성" |
| P2 | "BM25 + vector RRF 로 검색. `recall_hybrid(store, query, k=60)`" | "이 검색 결과에 reranker 추가" |
| P3 | "한국어 형태소 = Kiwi. `tokenize_for_index(text, kiwi)`" | "한국어 문서 검색 함수 추가" |
| P4 | "config 는 TOML + Pydantic 검증" | "config 에 새 필드 추가" |
| P5 | "테스트는 mock 안 쓰고 실 Ollama Cloud 사용" | "검색 통합 테스트 작성" |
| P6 | "약점은 `~/.tunallama/limitations.md` 자동 prepend" | "약점 카탈로그 도구 작성" |

각 probe 의 `current task` 는 isolated function 이 아니라 **프로젝트
컨텍스트에 의존하는 작업**. recall prefix 없으면 모델이 `Store` 같은 임의
이름 쓸 가능성 (Phase 5-3 의 standalone-toy 재현).

### Modes

- **none**: recall_prefix=None
- **relevant**: 위 prior context 를 그대로 prepend (이상적 검색 결과 시뮬)
- **mixed**: relevant + 무관 record 5개 (실제 검색의 R@5=0.5 시뮬)
- **adversarial**: 의도적으로 무관 record 5개만 (Phase 5-3 와 동일)

### Metrics

| metric | 측정 |
|---|---|
| **correct_api_usage** | code 안에 정확한 식별자 (`MemoryStore` 등) 사용 비율 |
| **standalone_toy_rate** | `Mock(`/`np.random`/SyntaxError 등 (Phase 7-1 모듈 재사용) |
| **unrelated_keyword_hits** | adversarial prefix 의 토큰이 code 에 누출 |
| **AST excess_score** | 과다 abstraction (Phase 5-3 모듈 재사용) |
| **code_lines** | 단순 size 비교 |

### 측정 매트릭스

6 probe × 4 mode × 4 model × 2 run = **192 generate_code 호출**

cloud 호출 비용 ≈ 192. quota $20 안에서 가능 (모델 마다 가격 다름).

## dogfooding 위임 (Round 17, `tuna_general_task` 채널)

architect 가 직접 작성하지 않고 dogfooding 으로 받을 수 있는 부분:
- **6 probe 의 `current task` description 한국어 자연스럽게 다듬기**
- **probe 별 정확한 식별자 list** (`correct_api_usage` 측정용):
  - P1 → `MemoryStore`, `record_call`, `get`, `search_vectors`
  - P2 → `recall_hybrid`, `RecallResult`, `recall_reranked`
  - 등
- AST smell 의 추가 anti-pattern 키워드 list

architect 가 직접:
- 측정 코드 작성 (`tests/integration/test_phase7_2_context_boost.py`)
- spec 의 모든 design 결정
- 결과 분석

## File path

- 새 통합 테스트: `tests/integration/test_phase7_2_context_boost.py`
- 결과 artifact: `tmp_path / "phase7_2_artifacts.json"`
- 측정 자료: `docs/measurements/phase7-context-boost.md`

## Required Imports / Signatures

```python
from tunallama_core.config.models import OllamaCloudProviderConfig
from tunallama_core.delegation.code import generate_code
from tunallama_core.llm.ollama import from_cloud
from tunallama_core.measurement.ast_smell import analyze_ast
from tunallama_core.measurement.memory_metrics import standalone_toy_rate
```

## Acceptance

- 4 mode × 6 probe × 4 model × 2 run = 192 generate_code 결과 저장.
- mode 별 평균 metrics 표 + per-probe / per-model breakdown.
- 가설 검증:
  - H1: `none` 보다 `relevant` 가 correct_api_usage ↑
  - H2: `adversarial` 가 `none` 보다 standalone_toy_rate 안 더 나쁘면 OK
    (Phase 5-3 의 cloud 결과 일관)
  - H3: model 별 차이 - 어느 모델이 컨텍스트 보강 가장 잘 활용?

## Constraints

- 절대 threshold 미리 정하지 X.
- artifact 보존 - 192 코드 모두 저장.
- pytest mark `search_quality`.
- timeout 600 + retry 3.
- 모든 metric sample 에 `source="spec_dogfooding"` tag (Phase 6-4 패턴).

## Forbidden Patterns

- mock store / 시뮬레이션 X. 실 generate_code 호출.
- model 별 변경은 LLMClient instance swap 만 (코드 변경 X).
- Phase 5-3 의 `ast_smell.py` / `memory_metrics.standalone_toy_rate` 재사용
  (새 모듈 작성 X).

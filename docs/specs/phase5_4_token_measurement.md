# Phase 5-4 - delegation 토큰 절약 정량 측정

## 배경

tunaLlama 의 핵심 가치 주장 중 하나: "무거운 코드 생성을 로컬/cloud LLM 에
위임 → Claude 메인 conversation 토큰 절약". Phase 1-4 동안 이 주장은
정성적이었음. 본 phase 는 정량 측정.

## 측정 design

### Mode 비교

같은 task N 회 × 2 mode:
- **mode N (Native)**: Claude 가 메인 conversation 에서 직접 코드 작성.
  메시지 = system prompt + user task + Claude 응답.
- **mode D (Delegated)**: `tuna_dev_review` 또는 `tuna_generate_code` 위임.
  메시지 = system prompt + user task + tool call (tunaLlama) + tool result
  (코드 결과만, 짧은 형태) + Claude 응답.

### Task 분류

| 크기 | 코드 라인 추정 | 예시 |
|---|---|---|
| small | 10 lines | gcd, fizzbuzz |
| medium | 50 lines | json parser, rate limiter |
| large | 200+ lines | retry+backoff+circuit breaker 통합, async queue 모듈 |

각 크기 × 2 mode × 3 run = **18 측정**.

### 토큰 측정

Claude API 의 `usage.input_tokens` / `usage.output_tokens` 직접 읽음.
- **mode N**: API 호출 1회의 input + output.
- **mode D**: API 호출 다수 (tool call 인 turn + tool result 받은 turn + 응답
  turn). 각 turn 의 토큰 합산.

`anthropic` SDK 직접 사용. 측정 스크립트는 architect 가 직접 작성.

## 새 모듈

`tunallama_core/measurement/token_count.py`:
```python
@dataclass(frozen=True)
class TokenUsage:
    mode: str  # "native" | "delegated"
    task_id: str
    task_size: str  # "small" | "medium" | "large"
    input_tokens: int
    output_tokens: int
    total_tokens: int
    duration_ms: int

def measure_native(task: str, *, anthropic_client, model: str) -> TokenUsage:
    """Claude 단독 호출. 메인 conversation 모방."""

def measure_delegated(task: str, *, anthropic_client, model: str) -> TokenUsage:
    """Claude + tunaLlama tool call 흐름. tool result 까지 합산."""
```

architect 직접 작성. dogfooding 위임 X (token API 통합).

## Required Imports / Signatures

(architect 직접 작성)
```python
import anthropic  # API 클라이언트
from tunallama_core.measurement.token_count import (
    TokenUsage, measure_native, measure_delegated
)
```

## File path

- 새 모듈: `tunallama_core/measurement/token_count.py`
- 새 통합 테스트: `tests/integration/test_phase5_4_token.py`
- artifact: `tmp_path / "phase5_4_token_artifacts.json"`

## API key 요구사항

Claude API 호출 → `ANTHROPIC_API_KEY` 환경변수. 미설정 시 skip.

## Acceptance

- 18 측정 완료 (small/medium/large × native/delegated × 3 run).
- per-size / per-mode 평균 input + output + total 토큰 표.
- **break-even 라인 수 추정**: delegation overhead (tool call/result 자체
  토큰) vs Claude 단독 작성 시 토큰. 어느 task size 부터 delegation 이
  메인 conversation 토큰 절약하는지.
- README §1 (개요) 또는 새 §6 에 토큰 절약 표 추가.

## Constraints

- Anthropic API 비용 발생 (사용자 직접 결정). 계산 전 토큰/비용 사전 추정 출력.
- pytest mark `search_quality`.
- 결과는 모델 마다 다름 - `claude-sonnet-4-6` (최신 안정) 으로 측정. opus
  4.7 / 4.5 와 비교는 별 phase.

## Risk

- Anthropic API 호출은 cloud Ollama 와 다른 비용 source. 사용자 사전 동의
  필요. 측정 시작 전 예상 비용 출력 + 18 호출 진행 확인.
- delegation 모드의 turn 수가 많아 input token 누적 큼 - delegation 이 오히려
  토큰 더 많이 쓸 수 있음 (small task 면 큰 가능성). 정직 보고 자산.

## v0.3.0 합격 조건

medium 이상 task 에서 delegation 이 native 대비 input token 30%+ 절약 →
delegation 의 정량 가치 입증. 미달이면 "delegation 은 토큰 절약 수단이
아니라 컨텍스트 격리 수단" 으로 메시징 정정.

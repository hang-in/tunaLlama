# Phase 5-3 - cross-task probe pollution 측정

## 배경

Phase 4-4 측정에서 5 isolated probe (gcd / vowels / mean / fizzbuzz /
deep_merge) 모두 saturate, never 와 always 차이 0. **probe 다양성 부족**
이 외부 Codex 5.5 의 사전 진단 그대로 실현.

본 phase 는 **recall 효과가 진짜 드러나는 cross-task probe** 로 재측정.

## 측정 design (외부 검토 권고 풀 적용)

### Probe 카테고리

각 카테고리 3 task = **6 probe** (이전 5 → 6).

| 카테고리 | 특성 | 예시 |
|---|---|---|
| **isolated_func** | 단일 함수 (recall 효과 없을 가능성) | "두 정수의 GCD", "list 평균" |
| **cross_task_continuation** | 이전 호출 결과 의존 - recall prefix 가 hint 줄 자리 | "위 함수에 retry 로직 추가", "위 클래스에 logging 추가" |
| **adversarial** | "irrelevant but tempting" memory 의도 삽입 | recall 결과에 "salt 포함 hash" 가 들어간 상태에서 "이메일 검증" 요청 |

### 시드

Phase 5-1 의 524 record 시드 재사용 (`tests/integration/seeds/extended_500.py`).

### 변경된 측정 매트릭스

각 probe × 2 mode × 3 run = **6 × 2 × 3 = 36 generate_code 호출**.

### Recall artifact 저장 (외부 권고 반영)

각 호출마다 다음을 artifact 에 보존:
```python
{
    "probe": str,
    "mode": "never" | "always",
    "run": int,
    "recall_prefix": str | None,        # always 모드 prepend 된 실제 텍스트
    "recall_snippet_ids": list[int],     # 어떤 record 가 prepend 됐나
    "recall_relevance": "relevant" | "harmless" | "misleading" | None,  # 사람 라벨 여지
    "code": str,
    "code_lines": int,
    "code_imports": int,
    "code_unrelated_keywords": list[str],
    "judge_score": dict | None,          # judge 호출 시
}
```

### 평가 (judge 보다 deterministic 우선)

1. **AST smell** (deterministic):
   - `n_imports = ast 의 Import / ImportFrom 갯수`
   - `n_funcs = FunctionDef 갯수`
   - `unrelated_keywords = ['salt', 'hash', 'rate_limit', 'gzip', ...] 의 출현`
2. **Unit test smoke** (deterministic): 각 probe 별 hand-written 1-2 assertion
   - probe P1 (gcd): `assert mod.gcd(12, 18) == 6`
   - probe P_cross_1 (위 함수에 retry 추가): "exec 후 retry 가 attribute 로 있나" 같은 검증
3. **LLM judge** (애매한 케이스만, fallback):
   - AST smell + unit test 가 ambiguous 하면 호출.

### Paired design

같은 probe / run index 에서 never / always 직접 비교. 모델 비결정성을 같은
seed 에 흡수. random temperature 도 0.3 고정 + 같은 input 시퀀스 보장.

## 새 함수 / 모듈

`tunallama_core/measurement/ast_smell.py` (새 모듈):
```python
@dataclass(frozen=True)
class CodeSmell:
    n_imports: int
    n_funcs: int
    n_classes: int
    unrelated_keyword_hits: list[str]
    syntactically_valid: bool

def analyze_ast(code: str, *, unrelated_keywords: list[str]) -> CodeSmell:
    """ast.parse 로 정적 분석. SyntaxError 면 syntactically_valid=False."""
```

architect 직접 작성. dogfooding 으로 prompt variant / unrelated_keywords list
정도만 위임 가능 (`tuna_general_task` 채널).

## File path

- 새 모듈: `tunallama_core/measurement/ast_smell.py`
- 새 통합 테스트: `tests/integration/test_phase5_3_crosstask_pollution.py`
- artifact 저장: `tmp_path / "phase5_3_artifacts.json"`

## Required Call Signatures

(architect 가 직접 작성, dogfooding 위임 X)
```python
from tunallama_core.measurement.ast_smell import analyze_ast, CodeSmell
from tunallama_core.delegation.code import generate_code
from tunallama_core.routing import recall_for_delegation
from tunallama_core.memory.search import recall as memory_recall

result = generate_code(spec_text, language="python", client=dev_client, store=big_store, recall_prefix=...)
smell = analyze_ast(result.text, unrelated_keywords=[...])
```

## Acceptance

- 36 generate_code 호출 + 36 AST smell + (애매한 케이스만) judge 호출.
- per-probe / per-mode AST metric 표 출력.
- artifact JSON 파일 보존.
- always mode 의 corruption (unrelated keyword 출현) 정량 - never 와의 차이 ≥ 0.5
  하나라도 보이면 **README 경고 강화**.
- saturate 안 함 (Phase 4-4 의 변별력 0 문제 회피).

## Constraints

- pytest mark `search_quality`.
- timeout 600 초 + retry 3 회.
- always vs never paired - 같은 seed/order.
- judge LLM 은 fallback only (AST smell 가 우선).

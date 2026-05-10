# Phase 6 - Memory Layer (state.md + decision extraction + diff learning)

## 배경

Phase 1-5 동안 검색 알고리즘과 측정 자산을 완성했다. HyDE + KURE 조합으로
P@1 0.92 / σR@5 0.14 까지 도달. 그러나 **외부 handoff 의 통찰** 과 **사용자
직관**:

> "사용자가 Claude Code 쓰면서 '이거 검색하자' 명시 호출 별로 없을 가능성"

= 측정 가치 ≠ 사용 가치. 측정 자산은 알고리즘 자산으로 남고, **사용자 시점
interface 는 memory layer 로 진화**.

## 방향 (외부 handoff 와의 차이)

| 항목 | handoff 권고 | 우리 결정 |
|---|---|---|
| `tuna_recall` MCP tool | retire | **유지** (코드 + 노출). 토큰/컨텍스트 낭비 측정되면 재고. |
| `auto_recall` config | 제거 | **유지** (default `on_request`). 측정 자산 보존. |
| reranker / expansion / HyDE 코드 | retire 권고 (코드 보존) | **유지 + 노출** |
| 새 memory layer | 추가 | **추가 (primary interface)** |
| epoch 분리 ("search era → memory era") | yes | **no** - search 와 memory 가 공존 layer |

핵심: **search 는 보존, memory layer 는 새로 primary** - search 가 사용
안 되더라도 dead weight 가 아니라 알고리즘 자산.

## 4 mechanism (handoff §4-§7 우리 데이터 반영)

### M1. state.md auto-load (project-scoped)

**위치**: `~/.tunallama/projects/<project_hash>/state.md`
- `<project_hash>` = git root absolute path 의 SHA256 → 12 hex 자름.
  git 아니면 CWD 의 hash.
- 사용자 환경변수 / config 없이 자동 분리.

**파일 포맷**:
```markdown
# tunaLlama Project Memory
<!-- auto-generated, auto-loaded. Manual edits preserved. -->
<!-- Last updated: <ISO timestamp> -->

## Conventions
- (auto) Import: `from tunallama_core.memory.store import MemoryStore`
- (manual) Korean comments OK; docstrings English

## Active Decisions
- 2026-05-11: HyDE hybrid winner on synthetic seed (P@1 0.92, 524 record 12 group leader sample). 실 사용 record 형식이 task description 외면 효과 편차 가능.
- 2026-05-11: BGE-M3 default, KURE-v1 opt-in (524 record LOPO 측정 기준)

## Constraints
- (manual) Backend 은 plugin 을 import X
- (auto, 3 occurrences) `Store` X, `MemoryStore` O
- (manual) Max file size ~150 lines

## Anti-patterns observed
- (auto, 9 occurrences) standalone-toy 패턴 - dev_review_from_spec 흐름
- (auto, 2 occurrences) `np.random` 으로 score 시뮬 - 실 함수 사용
```

각 entry 는 `(auto)` / `(manual)` / `(verified)` tag. manual 은 update 시 보존.

**Auto-load mechanism**:
- 시도 1 (preferred): MCP resource (`resources/list` + `resources/read`).
  Claude Code 가 자동 attach.
- 시도 2 (fallback): `tuna_status` 같은 cheap tool 응답에 state.md prepend.
- 시도 3 (last resort): `tuna_load_memory()` 명시 도구 + 사용자/skill 호출 안내.

**Size budget**: 2KB cap (configurable). 초과 시 `Active Decisions` →
`Anti-patterns` 순으로 오래된 entry 부터 truncate. `Conventions` 와
`Constraints` 는 never truncate.

### M2. Decision auto-extraction

**Source**: `tuna_dev_review`, `tuna_dev_review_from_spec`, `tuna_general_task`
등 delegation 결과 → 후처리 extract.

**모듈**: `tunallama_core/memory/extract.py`.

**패턴** (regex + rule-based, 한국어/영문):
```python
# 결정
r"(?:결정했(?:다|음)|chose to|going with|will use)[:\s]+(.+?)(?:\.|$|\n)"
r"우리는 (.+?)(?:한다|하기로|할 것이다)"

# convention
r"(?:import|from) (.+?) (?:should be|must|always)"
r"항상 (.+?) 사용"

# constraint
r"(?:절대|never|do not|must not) (.+?)(?:\.|\n)"
r"(?:금지|forbidden)[:\s]+(.+?)(?:\.|$|\n)"
```

각 entry 에 confidence score (regex strength + frequency). threshold 미만은
저장만 하고 state.md 에 surface 안 함.

**Dedup**: BGE-M3 embedding cosine ≥ 0.85 면 새 entry 추가 X, 기존 frequency
counter 증가.

**Manual override**: 사용자가 `(verified)` 로 마크 또는 삭제. 다음 update
시 보존.

### M3. Diff-based learning

**Trigger**: 사용자가 LLM 위임 결과 코드를 수정 → 그 diff 가 강한 학습 신호.

**연결 방법**:
- 새 컬럼 `calls.target_file_path` 추가 (idempotent migration).
- delegation tool 이 결과를 file 에 쓸 때 (Claude 의 Write/Edit) path 함께 log.
- skill 안내 - Claude Code 가 target_file_path 채우는 패턴.

**Diff 추출**:
- 단순 substitution (`Store → MemoryStore`) 은 rule-based.
- 복잡한 rewrite 는 작은 로컬 LLM (e.g. `qwen3:8b` via LM Studio) 호출.
- **dependency loop 회피**: diff 추출 모델은 state.md 받지 않음 (별 instance).

추출된 rule → confidence + dedup → state.md `Constraints` 또는
`Anti-patterns observed`.

### M4. 새 metrics (automated, deterministic)

| metric | 정의 | 측정 |
|---|---|---|
| **convention adherence rate** | state.md 의 convention 각각이 LLM 출력에서 honor 된 비율 | AST + regex |
| **standalone-toy rate** | LLM 출력의 fictional import / mock / no real integration 비율 | `ast_smell.py` 확장 |
| **user intervention rate** | delegation call 당 user correction 발생 횟수 | M3 의 diff trigger |
| **state recall probe** | state.md 의 convention 에 대해 Claude 응답이 일치하는지 | 정기 probe LLM call |

**측정 design - implementation 과 함께**: 절대 threshold 미리 정하지 X.
**trend over time** 우선 (week-over-week 개선). 외부 검토 합의.

**합성 vs 진짜 dogfooding 분리 트래킹** (필수): 모든 M4 metric 은 source tag
달아야. 합성 시드 / spec-driven dogfooding (round 7-16) 에서 잘 측정되는데
실 Claude Code 일상 사용 (organic dogfooding) 에서 안 좋은 자리를 잡기 위함.
Round 16 이후 organic dogfooding 부재 - baseline 부터 둘 분리해서 기록.

```python
@dataclass
class MetricSample:
    metric: str
    value: float
    source: Literal["synthetic", "spec_dogfooding", "organic"]
    timestamp: str
```

## API design (architect 직접 작성)

### Required Imports

```python
from tunallama_core.memory.state import (
    StateFile, load_state, append_entry, MAX_STATE_BYTES,
)
from tunallama_core.memory.extract import (
    extract_decisions, ExtractedEntry, EntryKind,
)
from tunallama_core.memory.diff_learn import (
    extract_rule_from_diff, DiffRule,
)
from tunallama_core.measurement.memory_metrics import (
    convention_adherence_rate,
    standalone_toy_rate,
    user_intervention_rate,
)
```

### Required Call Signatures

```python
# state file
state = load_state(project_root="/path/to/project")  # StateFile dataclass
append_entry(state, kind=EntryKind.DECISION, text="...", source="auto")

# extraction
entries = extract_decisions(text: str) -> list[ExtractedEntry]

# diff learning
rule = extract_rule_from_diff(
    before: str, after: str, *, client: LLMClient | None = None,
) -> DiffRule | None

# metrics
rate = convention_adherence_rate(
    state: StateFile, recent_calls: list[CallRecord],
) -> dict[str, float]
```

## File paths

- `tunallama_core/memory/state.py` (새)
- `tunallama_core/memory/extract.py` (새)
- `tunallama_core/memory/diff_learn.py` (새)
- `tunallama_core/measurement/memory_metrics.py` (새)
- `plugin/_state.py` (수정 - MCP resource 시도 1)
- `tunallama_core/memory/store.py` (수정 - calls.target_file_path 컬럼)
- 새 통합 테스트: `tests/integration/test_phase6_memory_layer.py`

## Forbidden Patterns

- `Store` 등 우리 클래스 이름 무관 작성 X.
- mock store / 시뮬레이션 X.
- state.md 파싱 시 사용자 manual entry 삭제 X (preserve).
- diff 추출 시 state.md 받는 LLM 재사용 X (dependency loop).
- target_file_path migration 시 기존 db 데이터 삭제 X (idempotent ALTER).

## Acceptance (v0.4.0)

- state.md auto-load 실 Claude Code 세션 확인 (M4 의 state recall probe).
- decision auto-extraction 이 dogfooding-log 50 entry 회고에서 명시
  "we decided X" 패턴 60%+ 캡처.
- standalone-toy rate 측정 자동화 작동 (분류 결과 dogfooding-log 적재).
  baseline / 목표 threshold 는 M4 측정 결과 도출 후 결정 - "trend over
  time 우선" 원칙 (절대 threshold 미리 X).
- target_file_path 컬럼 + migration 정상 작동.
- README §5 새 섹션 - memory layer 사용법 + 한계 명시.

## Constraints

- **search 도구는 노출 유지** - 토큰/컨텍스트 비용 측정 후 결정.
- BGE-M3 dedup 재활용 (새 모델 도입 X).
- pytest mark search_quality 와 분리 - 새 mark `memory_layer`.
- cloud LLM 호출 timeout 600 + retry 3 (기존 패턴).

## Phase 6 단계 (이번 v0.4.0 분할)

| 단계 | 내용 |
|---|---|
| 6-1 | `state.py` + auto-load MCP resource 시도 (가장 큰 효과) |
| 6-2 | `extract.py` + dedup |
| 6-3 | `diff_learn.py` + target_file_path migration |
| 6-4 | memory_metrics + automated standalone-toy rate |
| 6-5 | v0.4.0 release |

각 단계 dogfooding 가능 (`tuna_general_task` 채널 - round 16 패턴):
seed prompt patterns / dedup threshold 후보 / extraction regex 변형 등
**bounded output** 만 위임.

## v0.4.0 release 메시지 톤 (handoff §10 합의)

- "direction evolved", "search 자산 보존" 명시.
- "revolutionary memory system" 같은 마케팅 톤 X.
- 정직 한계: extraction recall < 100%, manual curation 필요, R@5 사용
  빈도 미검증.

## Out of scope

- Cross-project state 공유 (project 별 isolate).
- 팀 공유 state.md (single-user 만).
- multi-language per-section (Korean + English 같은 파일 OK).
- Anthropic API 토큰 측정 (Phase 5-4 보류 그대로).
- web UI.

## 정직 한계 (선행 인지)

- state.md auto-load 가 실제 Claude 컨텍스트 도달하는지 = MCP resource
  지원 여부에 의존. Claude Code 가 모든 turn 에 attach 안 할 수 있음.
- extraction 정규식 한계 - 명시 "we decided X" 외 implicit decision 놓침.
- diff-based learning 의 small LLM 의존 - LM Studio 안 켜져 있으면 rule-based
  만 작동.
- standalone-toy rate 측정 자동화 = AST smell heuristic 의존. 100% 정확 X.

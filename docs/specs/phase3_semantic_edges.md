# Task: Semantic edges — LLM-derived 그래프 관계 (Phase 3-2)

`memory/graph.py` 의 rule-based edges (same_project / same_day / same_tool) 에 추가로 LLM 분류 기반 의미 관계를 연결한다. seCall 의 H3 (cross-role 검증 우위) 패턴 — small-prompt + binary 출력은 모델이 안정적으로 따른다 (Phase 1.5 dogfooding 검증).

## Phase
IMPLEMENT

## Focus
binary 분류 (`related` / `unrelated`) 부터. multi-class (`fixes_bug` / `extends` 등) 는 후순위.

## Requirements

- 새 모듈 `tunallama_core/memory/semantic_edges.py`:
  - 함수 `classify_pair(client, a: CallRecord, b: CallRecord) -> bool | None` —
    LLM 호출로 두 record 의 의미 관련성 판정. `True` = related, `False` = unrelated,
    `None` = 모델 응답 파싱 실패 (호출자가 fallback).
  - 함수 `build_semantic_edges(store, client, *, max_pairs=100, project_root=None) -> int`:
    - 후보 페어 = 같은 ``project_root`` 안 record 들의 (id_a < id_b) 조합.
    - `max_pairs` 개 까지만 LLM 분류 — 비용 한도.
    - 이미 ``relation='semantic_related'`` 로 등록된 페어는 skip (idempotent).
    - 분류 결과 `True` 면 `graph_edges` 에 `relation='semantic_related'` 로 INSERT.
    - 반환: 새로 추가된 엣지 수.
- prompt 설계:
  - system: "You output one token: RELATED or UNRELATED. Nothing else."
  - user: f"Record A:\\n{a.inputs_json[:300]}\\n→ {a.output[:300]}\\n\\nRecord B:\\n{b.inputs_json[:300]}\\n→ {b.output[:300]}\\n\\nDo these two records cover the same task or one fixes/extends the other? Output RELATED or UNRELATED."
- 응답 파싱: regex `\\b(RELATED|UNRELATED)\\b`. 못 찾으면 None.
- `tunallama_core/__init__.py` 에 `classify_pair`, `build_semantic_edges` re-export.

## Constraints (hard rules)

- **rule-based edges 영향 없음** — `rebuild_edges()` 가 `semantic_related` 를 지우지 않음. 지금까지의 ``DELETE FROM graph_edges`` 흐름 변경 필요.
  - 해결: `rebuild_edges` 가 `WHERE relation IN ('same_project','same_day','same_tool')` 로 rule edges 만 삭제 + 재구성. semantic edges 보존.
- LLM 호출 한도: 함수 호출 1 회당 `max_pairs` 까지.
- `client` 는 `LLMClient` 인스턴스 — 우리 추상화 타입.
- 분류 prompt 는 50줄 이내. small-prompt 원칙.
- 한국어 docstring.

## Acceptance

- pytest 6+ 케이스 (`tests/core/test_memory_semantic_edges.py` 신규):
  1. `classify_pair` 가 `RELATED` 응답 → `True`.
  2. `classify_pair` 가 `UNRELATED` 응답 → `False`.
  3. `classify_pair` 가 다른 응답 → `None`.
  4. `build_semantic_edges` 가 같은 project_root record 페어 분류 — `RELATED` 페어만 엣지 INSERT.
  5. `build_semantic_edges` 의 `max_pairs` 한도 동작.
  6. `rebuild_edges` 호출 후에도 `semantic_related` 엣지 보존.
- 기존 graph 테스트 통과.

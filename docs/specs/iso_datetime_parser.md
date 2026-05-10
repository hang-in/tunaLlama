# Task: ISO 8601 datetime 파서

작은 dogfooding 샘플. `tuna_dev_review_from_spec` 으로 호출해 로컬 LLM 의 timezone / fractional-second 처리 약점이 드러나는지 확인하는 용도.

## Phase
IMPLEMENT

## Focus
timezone 처리 정확성 우선

## Requirements
- 시그너처: `def parse_iso(s: str) -> datetime.datetime`
- 아래 ISO 8601 형식을 모두 처리:
  - `2026-05-10`
  - `2026-05-10T12:34:56`
  - `2026-05-10T12:34:56.123456`
  - `2026-05-10T12:34:56Z`
  - `2026-05-10T12:34:56+09:00`
  - `2026-05-10T12:34:56.123+09:00`
- 반환은 항상 timezone-aware `datetime`. 타임존 없는 입력은 UTC 로 간주.
- 형식이 어긋나면 `ValueError` (메시지에 입력 echo).

## Constraints
- 표준 라이브러리만 (`datetime`, 필요 시 `re`). 외부 의존 금지.
- Python 3.11+. `datetime.fromisoformat` 가 3.11+ 에서 ISO 대부분을 지원하므로 위임 가능. 단 `Z` suffix 와 timezone 미지정 케이스는 직접 보정.
- 파일 길이 ~50줄 이내.

## Acceptance
- pytest 7 케이스 통과:
  - 6개 정상 형식 각각 (위 Requirements 목록 그대로)
  - 잘못된 입력 1개 → `ValueError`
- 한국어 docstring 한 줄 (왜 보정이 필요한지).
- 모든 반환 datetime 의 `tzinfo` 가 `None` 이 아님.

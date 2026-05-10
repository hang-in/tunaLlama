# Phase 5-1 dogfooding - 60 task × 6 paraphrase 합성 (bounded output)

## Task

검색 품질 측정용 합성 시드 데이터 생성. 측정 코드는 architect 가 직접 통합
하므로 **시드 데이터 (Python list literal) 만 출력**.

## Output 형식

Python 파일 1개. 다른 코드 / import / 함수 X. 다음 단일 list literal 만:

```python
NEW_GROUPS_60: list[list[str]] = [
    # System programming (10 tasks)
    ["file I/O 처리", "open file for writing", "파일 디스크립터 다루기",
     "fopen/fclose 패턴", "context manager 로 파일 열기", "binary file write"],
    ["signal handling", "SIGTERM 처리", "시그널 핸들러 등록",
     "kill 받았을 때 cleanup", "trap signal in script", "graceful shutdown"],
    # ... 8 more system programming tasks ...

    # Network (10 tasks)
    ["HTTP client 호출", "requests get 요청", "...", ...],
    # ... 9 more ...

    # Data structures (10 tasks)
    ["trie 자료구조", "prefix tree 구현", "...", ...],
    # ... 9 more ...

    # Concurrency (10 tasks)
    ["mutex lock", "...", ...],
    # ... 9 more ...

    # Crypto/security (10 tasks)
    ["AES 암호화", "...", ...],
    # ... 9 more ...

    # DevOps (10 tasks)
    ["docker compose 작성", "...", ...],
    # ... 9 more ...
]

NOISE_60: list[str] = [
    "regex backreference", "...", # ... 60 IT-스러운 무관 키워드 ...
]
```

## Constraints (hard rules)

- 카테고리 6 종 × 10 task = 60 task **정확히**.
- 각 task **6 paraphrase** 정확히. 한국어와 영문 mix.
- paraphrase 끼리 표면 토큰 거의 안 겹치되 같은 task 의미 유지.
- noise 60 개 - 일상 IT 키워드, 위 60 task 와 의미 겹침 X.
- import / 함수 / docstring / 주석 X. **list literal 2개만**.
- markdown 코드 펜스 (` ```python ... ``` `) 로 한 번 wrap OK.

## Forbidden Patterns

- 함수 정의 (def / class) X.
- import X.
- pytest fixture X.
- mock store / 시뮬레이션 X.
- numpy / pandas X.
- *기존* 12 task (memory_leak, email_validation 등) 중복 X.
- 같은 task 의 6 paraphrase 가 서로 너무 비슷 (token overlap > 50%) X.

## Acceptance

- list literal 2개만 출력.
- 60 task × 6 paraphrase = 360 string + 60 noise string = **420 string**.
- 한국어 ≥ 30%, 영문 ≥ 30% (mix 보장).

## Why this is bounded

dogfooding 결과를 architect 가 그대로 시드로 사용 - 통합 코드 X. 이전
round 7-14 의 standalone-toy 패턴은 **integration coder 위임**이라 실패.
이번은 **데이터 생성** 위임이라 차용 직접 가능.

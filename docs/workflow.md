# Architect ↔ Subagent 워크플로우

이 문서는 tunaLlama 의 작업 흐름과, **Claude Code 메인 세션(아키텍트)** 이
**로컬 LLM(서브에이전트)** 에게 작업을 넘기는 방법을 정리한다.

## 1. 역할 분담

| 역할 | 책임 |
|---|---|
| Architect (Claude, 메인 세션) | 분해 / 사양 작성 / 검증 / 통합 |
| Subagent (`tuna-developer`, 로컬 LLM) | 코드 생성 / 자체 리뷰 / 자체 수정 |

핵심 원칙: **architect 는 짧은 입출력만**, **subagent 는 긴 출력만** 부담한다.

## 2. 두 가지 호출 방식

### 2.1 단발 호출 — `tuna_dev_review`
요구사항이 한두 문장으로 정리되는 경우.

```
tuna_dev_review(requirements="이메일 검증 함수, 정규식만, ValueError 5케이스",
                language="python", max_iterations=2)
```

backend 가 generate → review → (이슈 있으면) fix → 재review 를 자동으로 돈다.
응답에는 각 iteration 의 review 로그 + 최종 코드가 같이 온다.

### 2.2 spec 문서 기반 — `tuna_dev_review_from_spec`
요구사항이 길거나 제약/수용기준이 함께 있는 경우, **markdown spec 파일** 로 적어
경로를 넘긴다. Phase / Focus / Constraints 헤더는 모두 옵션이며, 작은 모델
일수록 명시할수록 안정적이다 (gemento 검증 패턴).

```markdown
# Task: build email validator

## Phase
IMPLEMENT          # DESIGN | IMPLEMENT | VERIFY 중 하나. subagent 가 단계 벗어나지 않게.

## Focus
정규식 검증 로직 먼저   # 한 줄 우선순위. 다른 부수 작업보다 이걸 먼저.

## Requirements
- 정규식으로 1차 검증
- 빈 문자열 거부

## Constraints
- 표준 라이브러리만
- 외부 호출 없음

## Acceptance
- pytest 5 케이스 통과
```

```
tuna_dev_review_from_spec("docs/specs/email_validator.md", max_iterations=2)
```

`Constraints` 의 모든 항목은 hard rule 로 처리된다 — subagent 가 위반하면 review
에서 잡혀 fix 루프로 들어간다.

## 3. 약점 카탈로그 — `tuna_log_limitation`

작업 중 로컬 LLM 의 반복되는 실수를 발견하면:

```
tuna_log_limitation("한국어 docstring 작성 시 들여쓰기 어긋남")
```

→ `~/.tunallama/limitations.md` 에 기록되고, 이후 모든 `tuna_dev_review`
호출의 prompt 앞에 자동 prepend 되어 같은 실수를 줄인다. 직접 markdown 을
편집해도 된다.

## 4. 메모리와 리콜

모든 호출은 SQLite 에 기록된다(`enable_logging = true`). 비슷한 작업 시작 전:

```
tuna_recall("이메일 검증")
```

한국어 형태소 검색이 들어가서 띄어쓰기 없는 과거 호출도 잡힌다.

## 5. Hook (선택)

`plugin/hooks/pre_tool_use.py` 를 활성화하면 큰 파일을 `Read` 로 읽으려 할 때
`tuna_review_file` 사용을 권유받는다 (블록 X, 안내만). 활성화 방법은 hook 파일
docstring 참고.

## 6. 자동이 안 되는 부분 — 사용자가 해야 할 것

- 도구 결과가 명백히 틀렸을 때의 최종 판정.
- spec 작성 (architect 가 한국어/영어로 직접).
- `tuna_log_limitation` 호출 시점 (자동 감지 X — Phase 2 후보).
- 새 provider/모델 결정 (`tunallama init` 으로 재구성).

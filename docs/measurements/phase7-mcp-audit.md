# Phase 7-1 - MCP audit + size 측정

## 측정 결과 (13 tools, v0.4.0 직후 통합 작업 적용)

```
tool                                  desc  schema  total   ~tok
-------------------------------------------------------------------
tuna_dev_review                       377    310    712    203
tuna_recall                           388    199    608    173
tuna_review                           281    259    561    160
tuna_explain                          269    266    557    159
tuna_dev_review_from_spec             236    243    514    146
tuna_load_memory                      361     74    461    131
tuna_generate_code                    152    233    413    118
tuna_analyze_files                    123    252    403    115
tuna_log_limitation                   198    163    390    111
tuna_general_task                      58    206    291     83
tuna_refactor_code                     63    194    285     81
tuna_write_tests                       48    209    283     80
tuna_fix_code                          42    192    257     73
-------------------------------------------------------------------
TOTAL (13 tools)                                   5735   1633
```

- 총 5735 chars / **~1633 tokens** (영문 평균 3.5 char/token 추정).
- 매 Claude Code conversation 의 system prompt 에 prepend.
- 100-turn 대화 기준 누적: ~163,300 tokens (이론).

## 통합 작업 (15 → 13 도구)

| before | after | 이유 |
|---|---|---|
| `tuna_review_code` + `tuna_review_file` | `tuna_review(code, file_path, focus)` | input 차이만, 동일 동작 |
| `tuna_explain_code` + `tuna_explain_file` | `tuna_explain(code, file_path, audience)` | 동일 |

통합으로 ~224 tokens 절감 추정 (이전 ~1857 → 1633).

## 측정 한계 (정직)

- 실 Claude API 토큰 측정 X (Anthropic API 미보유). char/3.5 휴리스틱 의존.
- 실 Claude Code 가 도구 description 어떻게 직렬화 / prepend 하는지 검증 X.
- ChatML / system prompt overhead 무시. 도구 자체 size 만 측정.
- 100-turn 누적 추정은 prompt caching 무시한 worst-case.

## 다음 후보

- prompt caching 통합 (Anthropic prompt caching 이 도구 정의에도 적용되는지 확인).
- description 줄이기 (예: `tuna_dev_review` 의 377 char → 250 char 정도로
  trim). 단 명확성 vs size trade-off.
- 사용 빈도 낮은 도구 (`tuna_general_task` 의 catch-all 등) opt-out 옵션.

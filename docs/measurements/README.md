# 측정 자료 (Measurements)

검색 알고리즘 / 컨텍스트 오염 / 임베딩 모델 비교 등 정량 측정 자료. **합성
시드 기반**이라 실 사용자 워크플로우 검증은 별개 자리입니다.

## 인덱스

- [methodology.md](methodology.md) - 측정 방법론 + 한계 (시드 구성, LOPO,
  단일 측정 variance, σ 자체 σ 등).
- [phase4-search.md](phase4-search.md) - Phase 4 검색 품질 (paraphrase
  variance, 모델 비교, 컨텍스트 오염 saturate).
- [phase5-hyde-kure.md](phase5-hyde-kure.md) - Phase 5 측정 (524 record
  LOPO, HyDE, KURE-v1, Adaptive routing).
- [phase7-mcp-audit.md](phase7-mcp-audit.md) - MCP 도구 통합 + system prompt
  size 측정 (15 → 13 tools, ~1633 tokens).
- [phase7-context-boost.md](phase7-context-boost.md) - **mid-size LLM context
  boost** (gemma4:31b context boost +0.58, mixed = relevant). 검색의 진짜
  가치 정량 검증.

## 검색 path 우열 (524 record LOPO 기준)

```
path                  BGE-M3 P@1   KURE P@1   sigma R@5   cloud
BM25                    0.40        0.40       0.21         0
vector                  0.65        0.67       0.24-0.25    0
hybrid                  0.51        0.52       0.23         0
reranked hybrid         0.66        0.65       0.26         0
expanded hybrid         0.67          -        0.23         2
normalized hybrid       0.71        0.67       0.22         1
HyDE hybrid             0.92        0.92       0.14-0.19    1
Adaptive (KURE)          -          0.92       0.19         ~0.85
```

자세한 표 / σP@1 / NDCG@5 / 단일 측정 variance 는 `phase5-hyde-kure.md`.

## 한계 (먼저 보기)

- 시드 524 record = 12 기존 + 60 dogfooded task × 6 paraphrase + 92 noise.
  **task description 형식의 합성 데이터**. 실 사용 record 가 도구 호출
  dump / 긴 코드 등 다른 형식이면 HyDE 효과 편차 가능.
- LOPO 회전 측정 = 같은 task 의 paraphrase 사이 검색 능력. 실 사용자
  query 가 시드와 다르게 분포하면 σ / P@1 다를 수 있음.
- 단일 측정 variance 큼 (Phase 5-D 의 σR@5 0.19 vs 5-2C-KURE 의 0.14 -
  같은 path 동일 시드인데 측정 자체 variance + HyDE LLM 비결정성). σ
  자체도 σ 가짐.
- **organic dogfooding (실 Claude Code 일상 사용) 측정 부재**. round 7-16
  은 spec-driven dogfooding, round 17+ 는 Phase 6 부터 재개 예정.

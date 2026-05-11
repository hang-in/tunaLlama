# Archived measurement tests

이 디렉토리는 **abandoned 또는 superseded** 측정 자산 archive. 코드 / 데이터
정직 보존 정책 따라 삭제하지 않고 보관. 정기 회귀에서는 실행 X.

## 파일

### `test_context_pollution.py` (Phase 4-4)
- 5 isolated probe (gcd / vowels / mean / fizzbuzz / deep_merge) × 2 mode
  × 3 run = 30 generate_code.
- **saturate**: 모든 axis / probe / mode 가 만점 일괄 → 변별력 0.
- 외부 Codex 5.5 사전 경고 "5 probe 가 too narrow" 정량 검증.
- **Phase 5-3 cross-task adversarial** (`test_phase5_3_crosstask_pollution.py`,
  active) 이 대체. saturate 한계 회피 + AST smell 기반 deterministic 측정.
- 자세한 결과: [docs/measurements/phase4-search.md](../../../docs/measurements/phase4-search.md).

### `test_phase5_2d_mmr.py` (Phase 5-2D)
- MMR (Maximal Marginal Relevance) λ sweep, full 432 query LOPO.
- **결론: 우리 use case 에서 anti-pattern**. relevant 가 paraphrase set
  이라 다양성이 같은 task paraphrase 들을 떨어뜨림 → R@5 급락.
- λ=1.0 (다양성 0) 은 사실상 vec 단독과 동등 - 알고리즘 가치 X.
- 자세한 결과: [docs/measurements/phase5-hyde-kure.md](../../../docs/measurements/phase5-hyde-kure.md).
- 알고리즘 코드 (`tunallama_core/memory/mmr.py`) 는 보존 - 다른 use case
  (긴 doc, 무관 후보 다수) 에서는 가치 있음.

## 어떻게 보존되는가

- 정기 회귀 (`pytest -m "not search_quality"`) 에서 자동 제외 (마커가 모두
  `search_quality` 라 deselect).
- `pytest -m search_quality` 호출 시에도 archive 디렉토리는 pytest collect
  에서 자동 발견하지만, 명시적으로 안 실행하면 비용 X.
- 측정 코드 / 결과 표 모두 정직성 자산. 향후 비슷한 측정 design 시 참고.

## 정직 정책

- archive 라고 결과를 삭제하지 않음 - dogfooding-log + measurements docs
  에 그대로 남음.
- "왜 abandoned 인지" 항상 명시 (superseded by X / use case mismatch).
- 측정값 자체는 변경 X.

# Task: 동의어/paraphrase 시드 검색 품질 측정 (Phase 3-1)

Phase 2 측정에서 BM25 가 P@3=1.00 로 완벽했던 이유는 시드가 키워드 일치였기 때문. RRF/벡터의 진짜 가치는 **BM25 가 약한 시나리오** — 같은 의미를 다른 표현으로 적은 record 들. 그것을 측정하는 새 통합 테스트.

## Phase
IMPLEMENT

## Focus
시드 데이터셋 — 같은 task 를 6 가지 paraphrase 로 표현. BM25 가 단어 일치 못 하는 query.

## Requirements

- 새 파일 `tests/integration/test_search_quality_synonym.py`.
- 시드 ~18 record — 6 task 그룹 × 3 paraphrase. 예시:
  - "메모리 누수" / "memory leak" / "할당 해제 안 됨" / "GC 가 안 돌아감" / "garbage collection 문제" / "OOM 발생"
  - "이메일 검증" / "validate email" / "email format check" / "메일 주소 유효성" / "RFC 5322 준수" / "정규식으로 메일 거름"
  - "파일 압축" / "compress file" / "용량 줄이기" / "gzip 적용" / "데이터 사이즈 다이어트" / "binary 작게 만들기"
  - "JSON 파싱" / "parse JSON" / "JSON 디코딩" / "json.loads 호출" / "역직렬화" / "deserialize JSON"
  - "비밀번호 해시" / "password hashing" / "bcrypt 적용" / "credential 암호화" / "단방향 hash" / "salt 추가"
  - "API rate limit" / "요청 빈도 제한" / "throttling" / "버킷 알고리즘" / "초당 호출 제한" / "leaky bucket"
- query 6 개 — 각 group 의 한 표현. relevant set 은 같은 group 의 6 record 모두.
- 측정: precision@5, recall@5 두 metric.
- 표 출력 (BM25 / vector / hybrid).
- assertion:
  - vector recall@5 >= BM25 recall@5 (의미 매칭 우위)
  - hybrid recall@5 >= max(BM25, vector) recall@5 — 0.05 (RRF 가 정보 합성)

## Constraints (hard rules)

- 별도 marker `@pytest.mark.search_quality` 사용 — 기본 CI 에서 skip.
- 실 BGE-M3 사용 (이미 다운로드됨).
- 시드는 module-scope fixture — 한 번만 임베딩.
- 한국어/영문/한자 X / 숫자 — 자유 혼합.
- 한국어 docstring.

## Acceptance

- 새 통합 테스트 1+ (assertion 포함).
- 표가 `pytest -m search_quality -s` 로 보임.
- Phase 2 의 `test_search_quality.py` 그대로 작동 (regression 없음).

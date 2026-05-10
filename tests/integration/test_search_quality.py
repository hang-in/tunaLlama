"""검색 품질 측정 — BM25 / 벡터 / 하이브리드 비교.

실 BGE-M3 모델을 사용하므로 첫 실행에 ~1GB 다운로드 + ~2 분. CI 기본은 skip.
실행:
    pytest -m search_quality

설계:
- 한국어/영문 mix 의 코딩 task 시드 데이터셋 (12 record).
- 6 query — 각 query 마다 expected 'relevant' record id 집합 명시.
- 세 검색 경로 (BM25, vector-only, hybrid) 각각 호출.
- precision@k = relevant ∩ top-k / k.
- 어느 경로가 어떤 query 유형(한국어 / 영문 / 의미 매칭)에서 강한지 표 출력.

종합 print 는 pytest -s 로 봐야 보임.
"""

from __future__ import annotations

import pytest

from tunallama_core.memory.search import recall, recall_hybrid
from tunallama_core.memory.store import MemoryStore

pytestmark = pytest.mark.search_quality


# (tool, inputs, output) 12 record. id 는 1-based 자동 부여.
_SEED = [
    ("generate_code", {"q": "이메일 검증 함수"}, "def is_valid_email(s): ..."),  # 1
    ("generate_code", {"q": "validate email address"}, "def email_validator(s): ..."),  # 2
    ("review_code", {"q": "JSON 파싱"}, "Use json.loads(); handle JSONDecodeError"),  # 3
    ("review_code", {"q": "parse JSON safely"}, "wrap json.loads in try/except"),  # 4
    ("generate_code", {"q": "메모리 누수 탐지"}, "tracemalloc + gc 활용"),  # 5
    ("generate_code", {"q": "memory leak detector"}, "use tracemalloc snapshots"),  # 6
    ("write_tests", {"q": "비밀번호 해시"}, "bcrypt 추천, 솔트 자동"),  # 7
    ("write_tests", {"q": "password hashing"}, "use bcrypt with auto salt"),  # 8
    ("explain_code", {"q": "파일 압축"}, "gzip / zstandard 비교"),  # 9
    ("explain_code", {"q": "compress file"}, "gzip vs zstandard tradeoffs"),  # 10
    ("refactor_code", {"q": "데코레이터 패턴"}, "functools.wraps 사용"),  # 11
    ("refactor_code", {"q": "decorator pattern"}, "use functools.wraps"),  # 12
]


# query → relevant id 집합 (의미적으로 같은 task 의 한국어/영문 페어).
_QUERIES = [
    ("이메일 검증", {1, 2}),
    ("validate email", {1, 2}),
    ("JSON 파싱", {3, 4}),
    ("memory leak", {5, 6}),
    ("비밀번호 해시", {7, 8}),
    ("decorator pattern", {11, 12}),
]


@pytest.fixture(scope="module")
def seeded_store(tmp_path_factory):
    """실 BGE-M3 임베딩으로 시드. module scope 라 한 번만."""
    db = tmp_path_factory.mktemp("search_q") / "q.db"
    store = MemoryStore(db, korean_tokenizer="kiwi").open()
    for tool, inputs, output in _SEED:
        store.record_call(
            tool_name=tool,
            inputs=inputs,
            output=output,
            model="seed",
            duration_ms=1,
        )
    yield store
    store.close()


def _precision_at_k(result_ids: list[int], relevant: set[int], k: int = 3) -> float:
    top = result_ids[:k]
    if not top:
        return 0.0
    return len(set(top) & relevant) / len(top)


def _ids_from_recall(r) -> list[int]:
    return [s.full_id for s in r.snippets]


def test_seed_loaded(seeded_store):
    assert seeded_store.count() == len(_SEED)


def test_search_quality_comparison(seeded_store, capsys):
    """3 경로 × 6 query 의 precision@3 측정. 표로 출력 (pytest -s)."""
    rows = []
    bm25_total = vec_total = hyb_total = 0.0
    for query, relevant in _QUERIES:
        bm25 = _precision_at_k(_ids_from_recall(recall(seeded_store, query, limit=10)), relevant)
        vec_hits = seeded_store.search_vectors(query, limit=10)
        vec = _precision_at_k([h.id for h in vec_hits], relevant)
        hyb = _precision_at_k(
            _ids_from_recall(recall_hybrid(seeded_store, query, limit=10)), relevant
        )
        rows.append((query, bm25, vec, hyb))
        bm25_total += bm25
        vec_total += vec
        hyb_total += hyb

    n = len(_QUERIES)
    avg = (bm25_total / n, vec_total / n, hyb_total / n)

    # 사람 가독 출력
    with capsys.disabled():
        print("\n\n=== Search quality (P@3) ===")
        print(f"{'query':<22}{'BM25':>8}{'vector':>10}{'hybrid':>10}")
        print("-" * 50)
        for q, b, v, h in rows:
            print(f"{q[:20]:<22}{b:>8.2f}{v:>10.2f}{h:>10.2f}")
        print("-" * 50)
        print(f"{'AVG':<22}{avg[0]:>8.2f}{avg[1]:>10.2f}{avg[2]:>10.2f}")
        print()

    # vector 단독은 의미 매칭 능력 — 한국어/영문 페어가 명확하므로 0.30 이상 기대.
    assert avg[1] >= 0.30, (
        f"vector 평균 P@3 < 0.30 — BGE-M3 임베딩이 의미 매칭을 못함: {avg[1]:.2f}"
    )
    # hybrid 가 vector 단독보다 크게 나쁘면 RRF 합성에 결함. BM25 와 비교는 의미 X
    # (BM25 가 우세한 키워드-일치 시드에서는 hybrid 가 BM25 에 못 미치는 게 자연).
    assert avg[2] >= avg[1] - 0.05, (
        f"hybrid 가 vector 단독보다 크게 떨어짐: "
        f"vector={avg[1]:.2f}, hybrid={avg[2]:.2f}"
    )


def test_korean_query_finds_english_pair_via_vector(seeded_store):
    """한국어 query 가 의미적으로 같은 영문 record 를 잡는지 — 벡터의 핵심 가치."""
    hits = seeded_store.search_vectors("이메일 검증", limit=5)
    top_ids = [h.id for h in hits[:3]]
    # English 쌍 (id=2) 가 top-3 에 들어와야
    assert 2 in top_ids, f"vector 가 이메일↔email 매칭 실패: top3={top_ids}"


def test_english_query_finds_korean_pair_via_vector(seeded_store):
    """영문 query 가 의미적으로 같은 한국어 record 를 잡는지."""
    hits = seeded_store.search_vectors("memory leak", limit=5)
    top_ids = [h.id for h in hits[:3]]
    # 한국어 쌍 (id=5) 이 top-3 에
    assert 5 in top_ids, f"vector 가 memory leak↔메모리 누수 매칭 실패: top3={top_ids}"

"""Phase 3-1 — 동의어/paraphrase 시드 검색 품질.

Phase 2 의 `test_search_quality.py` 가 키워드 일치 시드라 BM25 가 100% 였다.
이번 시드는 같은 task 를 6 가지 표현으로 작성 — BM25 가 약하고 vector / hybrid
가 우세할 것으로 예상되는 시나리오.

실 BGE-M3 사용. 첫 호출 모델 로드 후 module-scope 시드 — 이후 빠름.
실행: `pytest -m search_quality -s tests/integration/test_search_quality_synonym.py`
"""

from __future__ import annotations

import pytest

from tunallama_core.config.models import OllamaCloudProviderConfig
from tunallama_core.llm.ollama import from_cloud
from tunallama_core.memory.search import (
    recall,
    recall_expanded,
    recall_hybrid,
    recall_reranked,
)
from tunallama_core.memory.store import MemoryStore

pytestmark = pytest.mark.search_quality

# 6 task × 6 paraphrase. round 10 차용 — 모델이 spec(3개)보다 풍부하게 작성.
_GROUPS: list[tuple[str, list[str]]] = [
    (
        "memory_leak",
        [
            "메모리 누수 탐지",
            "memory leak detection",
            "할당 해제 안 된 객체 찾기",
            "GC 가 안 돌아가는 문제",
            "garbage collection 디버깅",
            "OOM 발생 추적",
        ],
    ),
    (
        "email_validation",
        [
            "이메일 검증 로직",
            "validate email format",
            "메일 주소 유효성 체크",
            "RFC 5322 준수 검사",
            "정규식으로 메일 거름",
            "email format check function",
        ],
    ),
    (
        "file_compression",
        [
            "파일 압축",
            "compress file size",
            "용량 줄이기",
            "gzip 적용",
            "데이터 사이즈 다이어트",
            "binary 작게 만들기",
        ],
    ),
    (
        "json_parsing",
        [
            "JSON 파싱 함수",
            "parse JSON safely",
            "JSON 디코딩 처리",
            "json.loads 호출",
            "역직렬화 구현",
            "deserialize JSON document",
        ],
    ),
    (
        "password_hashing",
        [
            "비밀번호 해시",
            "password hashing with bcrypt",
            "credential 단방향 암호화",
            "단방향 hash 함수",
            "salt 추가한 hash",
            "credential one-way hashing",
        ],
    ),
    (
        "rate_limit",
        [
            "API rate limit 구현",
            "요청 빈도 제한",
            "throttling 미들웨어",
            "토큰 버킷 알고리즘",
            "초당 호출 제한",
            "leaky bucket implementation",
        ],
    ),
]


@pytest.fixture(scope="module")
def synonym_store(tmp_path_factory):
    """36 record 시드. id 1-based — group 0 는 1..6, group 1 은 7..12, ..."""
    db = tmp_path_factory.mktemp("syn") / "syn.db"
    store = MemoryStore(db, korean_tokenizer="kiwi").open()
    for _, phrases in _GROUPS:
        for p in phrases:
            store.record_call(
                tool_name="seed",
                inputs={"q": p},
                output=f"sample output for {p}",
                model="seed",
                duration_ms=1,
            )
    yield store
    store.close()


def _relevant_set(group_idx: int) -> set[int]:
    """group N 의 6 record id (1-based)."""
    start = group_idx * 6 + 1
    return set(range(start, start + 6))


def _precision_recall(retrieved_ids: list[int], relevant: set[int], k: int = 5) -> tuple[float, float]:
    top = retrieved_ids[:k]
    if not top:
        return 0.0, 0.0
    hits = len(set(top) & relevant)
    return hits / len(top), hits / len(relevant)


def test_synonym_seed_loaded(synonym_store):
    assert synonym_store.count() == sum(len(p) for _, p in _GROUPS)


@pytest.fixture(scope="module")
def cloud_client():
    """LLM expansion 측정용 — Ollama Cloud (config.toml 의 model 그대로)."""
    import os

    if not os.environ.get("OLLAMA_CLOUD_API_KEY"):
        pytest.skip("OLLAMA_CLOUD_API_KEY 미설정 — expansion 측정 skip")
    cfg = OllamaCloudProviderConfig(
        host="https://ollama.com",
        api_key_env="OLLAMA_CLOUD_API_KEY",
        model="glm-4.7",
    )
    return from_cloud(cfg, temperature=0.3, timeout=60)


def test_recall_expanded_quality_vs_bm25_hybrid(synonym_store, cloud_client, capsys):
    """LLM query expansion 효과 측정 — recall@5 비교."""
    bm25_r = vec_r = hyb_r = exp_b_r = exp_h_r = 0.0
    rows: list[tuple[str, float, float, float, float, float]] = []

    for idx, (label, phrases) in enumerate(_GROUPS):
        query = phrases[0]
        relevant = _relevant_set(idx)

        bm = [s.full_id for s in recall(synonym_store, query, limit=10).snippets]
        vec = [h.id for h in synonym_store.search_vectors(query, limit=10)]
        hy = [
            s.full_id
            for s in recall_hybrid(synonym_store, query, limit=10).snippets
        ]
        ex_b = [
            s.full_id
            for s in recall_expanded(
                synonym_store, query, client=cloud_client, mode="bm25", limit=10
            ).snippets
        ]
        ex_h = [
            s.full_id
            for s in recall_expanded(
                synonym_store, query, client=cloud_client, mode="hybrid", limit=10
            ).snippets
        ]

        _, br = _precision_recall(bm, relevant)
        _, vr = _precision_recall(vec, relevant)
        _, hr = _precision_recall(hy, relevant)
        _, eb = _precision_recall(ex_b, relevant)
        _, eh = _precision_recall(ex_h, relevant)

        rows.append((label, br, vr, hr, eb, eh))
        bm25_r += br; vec_r += vr; hyb_r += hr; exp_b_r += eb; exp_h_r += eh

    n = len(_GROUPS)
    avg = (bm25_r / n, vec_r / n, hyb_r / n, exp_b_r / n, exp_h_r / n)

    with capsys.disabled():
        print("\n\n=== Query expansion (R@5) ===")
        print(f"{'group':<22}{'BM25':>8}{'vec':>8}{'hyb':>8}{'exp+B':>8}{'exp+H':>8}")
        print("-" * 62)
        for label, br, vr, hr, eb, eh in rows:
            print(f"{label[:20]:<22}{br:>8.2f}{vr:>8.2f}{hr:>8.2f}{eb:>8.2f}{eh:>8.2f}")
        print("-" * 62)
        print(f"{'AVG':<22}{avg[0]:>8.2f}{avg[1]:>8.2f}{avg[2]:>8.2f}{avg[3]:>8.2f}{avg[4]:>8.2f}")
        print()

    # 가설: expanded BM25 > BM25 단독 (paraphrase 가 BM25 약점이라 가장 큰 향상 기대).
    assert avg[3] >= avg[0], (
        f"expanded BM25 R@5 ({avg[3]:.2f}) >= BM25 R@5 ({avg[0]:.2f}) 기대 — "
        f"expansion 이 BM25 의 paraphrase 약점을 공략 못함"
    )


def test_recall_reranked_quality(synonym_store, capsys):
    """cross-encoder reranker 의 R@5 영향 측정.

    1차 hybrid (candidate_pool=20) → BAAI/bge-reranker-v2-m3 reranker → top-5.
    첫 호출 시 reranker 모델 ~600MB 다운로드.
    """
    bm25_r = vec_r = hyb_r = rer_h_r = rer_b_r = 0.0
    rows: list[tuple[str, float, float, float, float, float]] = []

    for idx, (label, phrases) in enumerate(_GROUPS):
        query = phrases[0]
        relevant = _relevant_set(idx)

        bm = [s.full_id for s in recall(synonym_store, query, limit=10).snippets]
        vec = [h.id for h in synonym_store.search_vectors(query, limit=10)]
        hy = [
            s.full_id for s in recall_hybrid(synonym_store, query, limit=10).snippets
        ]
        rh = [
            s.full_id
            for s in recall_reranked(
                synonym_store, query, limit=10, candidate_pool=20, base="hybrid"
            ).snippets
        ]
        rb = [
            s.full_id
            for s in recall_reranked(
                synonym_store, query, limit=10, candidate_pool=20, base="bm25"
            ).snippets
        ]

        _, br = _precision_recall(bm, relevant)
        _, vr = _precision_recall(vec, relevant)
        _, hr = _precision_recall(hy, relevant)
        _, rhr = _precision_recall(rh, relevant)
        _, rbr = _precision_recall(rb, relevant)

        rows.append((label, br, vr, hr, rhr, rbr))
        bm25_r += br; vec_r += vr; hyb_r += hr; rer_h_r += rhr; rer_b_r += rbr

    n = len(_GROUPS)
    avg = (bm25_r/n, vec_r/n, hyb_r/n, rer_h_r/n, rer_b_r/n)

    with capsys.disabled():
        print("\n\n=== Cross-encoder reranker (R@5) ===")
        print(f"{'group':<22}{'BM25':>8}{'vec':>8}{'hyb':>8}{'rer+H':>8}{'rer+B':>8}")
        print("-" * 62)
        for label, br, vr, hr, rhr, rbr in rows:
            print(f"{label[:20]:<22}{br:>8.2f}{vr:>8.2f}{hr:>8.2f}{rhr:>8.2f}{rbr:>8.2f}")
        print("-" * 62)
        print(f"{'AVG':<22}{avg[0]:>8.2f}{avg[1]:>8.2f}{avg[2]:>8.2f}{avg[3]:>8.2f}{avg[4]:>8.2f}")
        print()

    # reranker 가 vector / hybrid 보다 떨어지면 안 됨 - candidate_pool 충분히 크면.
    upper = max(avg[1], avg[2])
    assert avg[3] >= upper - 0.05, (
        f"reranker+hybrid R@5 ({avg[3]:.2f}) >= max(vec, hyb) - 0.05 "
        f"= {upper - 0.05:.2f} 기대"
    )


def test_search_quality_synonym_comparison(synonym_store, capsys):
    """3 경로 × 6 query (각 group 의 첫 표현) 의 P@5 / R@5."""
    bm25_p = bm25_r = vec_p = vec_r = hyb_p = hyb_r = 0.0
    rows: list[tuple[str, float, float, float, float, float, float]] = []

    for idx, (label, phrases) in enumerate(_GROUPS):
        query = phrases[0]
        relevant = _relevant_set(idx)

        bm = recall(synonym_store, query, limit=10)
        bm_ids = [s.full_id for s in bm.snippets]
        bp, br = _precision_recall(bm_ids, relevant)

        vec_hits = synonym_store.search_vectors(query, limit=10)
        vec_ids = [h.id for h in vec_hits]
        vp, vr = _precision_recall(vec_ids, relevant)

        hy = recall_hybrid(synonym_store, query, limit=10)
        hy_ids = [s.full_id for s in hy.snippets]
        hp, hr = _precision_recall(hy_ids, relevant)

        rows.append((label, bp, br, vp, vr, hp, hr))
        bm25_p += bp; bm25_r += br
        vec_p += vp; vec_r += vr
        hyb_p += hp; hyb_r += hr

    n = len(_GROUPS)
    avg_bm = (bm25_p / n, bm25_r / n)
    avg_vec = (vec_p / n, vec_r / n)
    avg_hyb = (hyb_p / n, hyb_r / n)

    with capsys.disabled():
        print("\n\n=== Synonym seed search quality (P@5 / R@5) ===")
        print(f"{'group':<22}{'BM25 P':>8}{'BM25 R':>8}{'vec P':>8}{'vec R':>8}{'hyb P':>8}{'hyb R':>8}")
        print("-" * 70)
        for label, bp, br, vp, vr, hp, hr in rows:
            print(f"{label[:20]:<22}{bp:>8.2f}{br:>8.2f}{vp:>8.2f}{vr:>8.2f}{hp:>8.2f}{hr:>8.2f}")
        print("-" * 70)
        print(f"{'AVG':<22}{avg_bm[0]:>8.2f}{avg_bm[1]:>8.2f}{avg_vec[0]:>8.2f}{avg_vec[1]:>8.2f}{avg_hyb[0]:>8.2f}{avg_hyb[1]:>8.2f}")
        print()

    # 가설 1: vector recall > BM25 recall — paraphrase 시드에서 의미 매칭이 우세.
    assert avg_vec[1] >= avg_bm[1], (
        f"vector R@5 ({avg_vec[1]:.2f}) >= BM25 R@5 ({avg_bm[1]:.2f}) 기대"
    )
    # 가설 2: hybrid recall >= max - 0.05 — RRF 가 두 신호 합성, 양쪽 단독보다 안 떨어짐.
    upper = max(avg_bm[1], avg_vec[1])
    assert avg_hyb[1] >= upper - 0.05, (
        f"hybrid R@5 ({avg_hyb[1]:.2f}) >= max(BM25, vector) - 0.05 = {upper - 0.05:.2f} 기대"
    )

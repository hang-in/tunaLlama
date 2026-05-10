"""Phase 4-3b - LOPO (leave-one-paraphrase-out) 측정.

기존 ``test_search_quality_extended.py`` 는 query = paraphrases[0] 가 시드
record 와 정확히 동일 → P@1 / MRR 모든 path 1.00 일괄 (변별력 0). 외부
검토 (Opus 4.7 + Codex 5.5) 결론에 따라 LOPO 패턴으로 corpus 와 query 분리.

12 task × 6 회전 = 72 query. 각 회전마다 corpus 95 record (그 task 의 5
paraphrase + 다른 11 task × 6 + noise 30), query 1 (빠진 paraphrase),
relevant = 그 task 의 나머지 5 paraphrase.

NDCG@5 도 같이 측정 (binary relevance, log2 discount).
"""

from __future__ import annotations

import math
import os
import statistics
from pathlib import Path

import pytest

from tunallama_core.config.models import OllamaCloudProviderConfig
from tunallama_core.llm.ollama import from_cloud
from tunallama_core.memory.metrics import (
    RetrievalMetrics,
    average_metrics,
    compute_metrics,
)
from tunallama_core.memory.search import (
    recall,
    recall_expanded,
    recall_hybrid,
    recall_reranked,
)
from tunallama_core.memory.store import MemoryStore

pytestmark = pytest.mark.search_quality


# ---------------- Seeds (extended_store 와 동일) ----------------

_ORIGINAL_GROUPS: list[list[str]] = [
    ["메모리 누수 탐지", "memory leak detection", "할당 해제 안 된 객체 찾기",
     "GC 가 안 돌아가는 문제", "garbage collection 디버깅", "OOM 발생 추적"],
    ["이메일 검증 로직", "validate email format", "메일 주소 유효성 체크",
     "RFC 5322 준수 검사", "정규식으로 메일 거름", "email format check function"],
    ["파일 압축", "compress file size", "용량 줄이기",
     "gzip 적용", "데이터 사이즈 다이어트", "binary 작게 만들기"],
    ["JSON 파싱 함수", "parse JSON safely", "JSON 디코딩 처리",
     "json.loads 호출", "역직렬화 구현", "deserialize JSON document"],
    ["비밀번호 해시", "password hashing with bcrypt", "credential 단방향 암호화",
     "단방향 hash 함수", "salt 추가한 hash", "credential one-way hashing"],
    ["API rate limit 구현", "요청 빈도 제한", "throttling 미들웨어",
     "토큰 버킷 알고리즘", "초당 호출 제한", "leaky bucket implementation"],
]
_NEW_GROUPS: list[list[str]] = [
    ["logging 구조 설계", "log 출력 포맷", "구조화 로그",
     "structured logging with loguru", "loguru 사용", "로그 포맷 지정"],
    ["캐싱 전략", "메모리 캐시 구현", "LRU cache",
     "Redis 캐시 적용", "캐시 무효화", "cache TTL 설정"],
    ["비동기 처리", "async/await 사용", "동시성 코드",
     "코루틴 작성", "asyncio event loop", "non-blocking I/O"],
    ["DB 마이그레이션", "schema 변경 스크립트", "Alembic 사용",
     "다운타임 없는 마이그레이션", "rollback 전략", "컬럼 추가 migration"],
    ["직렬화 처리", "객체 → JSON dump", "pickle 사용",
     "msgpack 직렬화", "역직렬화 deserialize", "binary serialization"],
    ["정렬 알고리즘", "quicksort 구현", "merge sort",
     "안정 정렬", "부분 정렬", "in-place sort"],
]
_NOISE: list[str] = [
    "matplotlib 차트 그리기", "ANSI 컬러 출력", "argparse 사용법",
    "flask route 설정", "pygame window 생성", "pandas dataframe merge",
    "requests timeout 설정", "yaml 파일 파싱", "re 정규표현식 그룹",
    "tkinter 버튼 이벤트", "selenium headless 모드", "pytest fixture scope",
    "docker compose build", "kubernetes pod status", "git rebase interactive",
    "ssh key 생성", "vim mapping 설정", "bash script loop",
    "json path query", "xml parser setup", "sql join optimization",
    "redis pubsub", "rabbitmq exchange", "kafka consumer group",
    "grpc service definition", "protobuf field numbering", "aws s3 upload",
    "azure blob storage", "gcp cloud functions", "terraform state lock",
]
_GROUPS = _ORIGINAL_GROUPS + _NEW_GROUPS  # 12 groups


# ---------------- NDCG@5 helper ----------------

def ndcg_at_k(retrieved: list[int], relevant: set[int], *, k: int = 5) -> float:
    """binary relevance NDCG@k. log2(rank+1) discount."""
    if not retrieved or not relevant:
        return 0.0
    dcg = 0.0
    for rank, rid in enumerate(retrieved[:k], start=1):
        if rid in relevant:
            dcg += 1.0 / math.log2(rank + 1)
    ideal_hits = min(len(relevant), k)
    if ideal_hits == 0:
        return 0.0
    idcg = sum(1.0 / math.log2(r + 1) for r in range(1, ideal_hits + 1))
    return dcg / idcg


# ---------------- Build LOPO store (회전마다 fresh) ----------------

def _build_lopo_store(
    db_path: Path, *, holdout_group: int, holdout_idx: int
) -> tuple[MemoryStore, set[int]]:
    """holdout_group 의 holdout_idx paraphrase 를 corpus 에서 빼고 store 생성.

    return: (store, relevant_set) - relevant_set 은 holdout_group 의 corpus 안
    5 record id.
    """
    store = MemoryStore(
        db_path, korean_tokenizer="kiwi", enable_embeddings=True
    ).open()
    relevant: set[int] = set()
    next_id = 1
    for g_idx, phrases in enumerate(_GROUPS):
        for p_idx, phrase in enumerate(phrases):
            if g_idx == holdout_group and p_idx == holdout_idx:
                continue  # query 는 corpus 에서 제외
            store.record_call(
                tool_name="seed", inputs={"q": phrase},
                output=f"out for {phrase}", model="seed", duration_ms=1,
            )
            if g_idx == holdout_group:
                relevant.add(next_id)
            next_id += 1
    for noise in _NOISE:
        store.record_call(
            tool_name="seed", inputs={"q": noise},
            output=f"out for {noise}", model="seed", duration_ms=1,
        )
    return store, relevant


# ---------------- Cloud client fixture ----------------

@pytest.fixture(scope="module")
def cloud_client():
    if not os.environ.get("OLLAMA_CLOUD_API_KEY"):
        pytest.skip("OLLAMA_CLOUD_API_KEY 미설정 - expanded path skip")
    cfg = OllamaCloudProviderConfig(
        host="https://ollama.com",
        api_key_env="OLLAMA_CLOUD_API_KEY",
        model="glm-4.7",
    )
    return from_cloud(cfg, temperature=0.3, timeout=600)


# ---------------- Main test ----------------

def test_lopo_metrics(cloud_client, tmp_path, capsys):
    """12 task × 6 회전 = 72 query. 5 path × 4 metric (P@1, R@5, MRR, NDCG@5)."""
    by_path: dict[str, list[RetrievalMetrics]] = {
        "BM25": [], "vec": [], "hybrid": [], "rerank": [], "exp+H": [],
    }
    ndcg_by_path: dict[str, list[float]] = {p: [] for p in by_path}

    rotation = 0
    for g_idx, phrases in enumerate(_GROUPS):
        for p_idx, query in enumerate(phrases):
            db = tmp_path / f"lopo_{g_idx}_{p_idx}.db"
            store, relevant = _build_lopo_store(
                db, holdout_group=g_idx, holdout_idx=p_idx
            )
            try:
                bm = [s.full_id for s in recall(store, query, limit=20).snippets]
                vec = [h.id for h in store.search_vectors(query, limit=20)]
                hy = [
                    s.full_id
                    for s in recall_hybrid(store, query, limit=20).snippets
                ]
                rr = [
                    s.full_id
                    for s in recall_reranked(
                        store, query, limit=20, candidate_pool=20, base="hybrid"
                    ).snippets
                ]
                ex = [
                    s.full_id
                    for s in recall_expanded(
                        store, query, client=cloud_client,
                        mode="hybrid", limit=20,
                    ).snippets
                ]
                by_path["BM25"].append(compute_metrics(bm, relevant))
                by_path["vec"].append(compute_metrics(vec, relevant))
                by_path["hybrid"].append(compute_metrics(hy, relevant))
                by_path["rerank"].append(compute_metrics(rr, relevant))
                by_path["exp+H"].append(compute_metrics(ex, relevant))
                ndcg_by_path["BM25"].append(ndcg_at_k(bm, relevant))
                ndcg_by_path["vec"].append(ndcg_at_k(vec, relevant))
                ndcg_by_path["hybrid"].append(ndcg_at_k(hy, relevant))
                ndcg_by_path["rerank"].append(ndcg_at_k(rr, relevant))
                ndcg_by_path["exp+H"].append(ndcg_at_k(ex, relevant))
            finally:
                store.close()
            rotation += 1

    avg = {p: average_metrics(ms) for p, ms in by_path.items()}

    def _stats(values: list[float]) -> tuple[float, float]:
        if not values:
            return 0.0, 0.0
        m = statistics.mean(values)
        s = statistics.stdev(values) if len(values) > 1 else 0.0
        return m, s

    with capsys.disabled():
        print(f"\n\n=== Phase 4-3b LOPO ({rotation} query / path) ===")
        print(
            f"{'path':<10}{'P@1':>8}{'R@5':>8}{'MRR':>8}"
            f"{'NDCG@5':>10}{'σP@1':>8}{'σR@5':>8}{'σNDCG':>8}"
        )
        print("-" * 70)
        for p in ("BM25", "vec", "hybrid", "rerank", "exp+H"):
            m = avg[p]
            sp1 = (
                statistics.stdev([x.p1 for x in by_path[p]])
                if len(by_path[p]) > 1 else 0.0
            )
            sr5 = (
                statistics.stdev([x.r_at_k for x in by_path[p]])
                if len(by_path[p]) > 1 else 0.0
            )
            ndcg_mean, ndcg_std = _stats(ndcg_by_path[p])
            print(
                f"{p:<10}{m.p1:>8.2f}{m.r_at_k:>8.2f}{m.mrr:>8.2f}"
                f"{ndcg_mean:>10.2f}{sp1:>8.2f}{sr5:>8.2f}{ndcg_std:>8.2f}"
            )
        print()

    # weak assertions - ranking discrimination 회복 확인.
    assert avg["vec"].p1 >= avg["BM25"].p1 - 0.10, (
        f"vec P@1 ({avg['vec'].p1:.2f}) << BM25 ({avg['BM25'].p1:.2f}) - "
        f"의미 매칭이 키워드 보다 너무 떨어지면 안 됨"
    )
    rerank_ndcg = statistics.mean(ndcg_by_path["rerank"])
    hybrid_ndcg = statistics.mean(ndcg_by_path["hybrid"])
    assert rerank_ndcg >= hybrid_ndcg - 0.05, (
        f"rerank NDCG@5 ({rerank_ndcg:.2f}) << hybrid ({hybrid_ndcg:.2f})"
    )

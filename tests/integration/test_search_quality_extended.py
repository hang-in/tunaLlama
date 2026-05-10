"""Phase 4-3 - 확장 시드(108 record) + P@1/P@5/R@5/MRR 통합 측정.

기존 36 record 시드(`test_search_quality_synonym.py` 의 `_GROUPS`)에:
- 6 신규 task × 6 paraphrase = 36 record (round 12 dogfooding 차용)
- 30 noise record (cross-contamination 측정)
= **총 102 record** (36+36+30).

R@5 만 보던 Phase 3 측정에서 빠진 ranking 정보 (P@1, MRR) 까지 포함.
"""

from __future__ import annotations

import os

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


# 기존 6 task (Phase 3 시드와 동일).
_ORIGINAL_GROUPS: list[tuple[str, list[str]]] = [
    (
        "memory_leak",
        [
            "메모리 누수 탐지", "memory leak detection", "할당 해제 안 된 객체 찾기",
            "GC 가 안 돌아가는 문제", "garbage collection 디버깅", "OOM 발생 추적",
        ],
    ),
    (
        "email_validation",
        [
            "이메일 검증 로직", "validate email format", "메일 주소 유효성 체크",
            "RFC 5322 준수 검사", "정규식으로 메일 거름", "email format check function",
        ],
    ),
    (
        "file_compression",
        [
            "파일 압축", "compress file size", "용량 줄이기",
            "gzip 적용", "데이터 사이즈 다이어트", "binary 작게 만들기",
        ],
    ),
    (
        "json_parsing",
        [
            "JSON 파싱 함수", "parse JSON safely", "JSON 디코딩 처리",
            "json.loads 호출", "역직렬화 구현", "deserialize JSON document",
        ],
    ),
    (
        "password_hashing",
        [
            "비밀번호 해시", "password hashing with bcrypt", "credential 단방향 암호화",
            "단방향 hash 함수", "salt 추가한 hash", "credential one-way hashing",
        ],
    ),
    (
        "rate_limit",
        [
            "API rate limit 구현", "요청 빈도 제한", "throttling 미들웨어",
            "토큰 버킷 알고리즘", "초당 호출 제한", "leaky bucket implementation",
        ],
    ),
]

# 신규 6 task (round 12 dogfooding 차용 + 한국어/영문 mix 강화).
_NEW_GROUPS: list[tuple[str, list[str]]] = [
    (
        "logging",
        [
            "logging 구조 설계", "log 출력 포맷", "구조화 로그",
            "structured logging with loguru", "loguru 사용", "로그 포맷 지정",
        ],
    ),
    (
        "caching",
        [
            "캐싱 전략", "메모리 캐시 구현", "LRU cache",
            "Redis 캐시 적용", "캐시 무효화", "cache TTL 설정",
        ],
    ),
    (
        "async_concurrency",
        [
            "비동기 처리", "async/await 사용", "동시성 코드",
            "코루틴 작성", "asyncio event loop", "non-blocking I/O",
        ],
    ),
    (
        "db_migration",
        [
            "DB 마이그레이션", "schema 변경 스크립트", "Alembic 사용",
            "다운타임 없는 마이그레이션", "rollback 전략", "컬럼 추가 migration",
        ],
    ),
    (
        "serialization",
        [
            "직렬화 처리", "객체 → JSON dump", "pickle 사용",
            "msgpack 직렬화", "역직렬화 deserialize", "binary serialization",
        ],
    ),
    (
        "sorting_algo",
        [
            "정렬 알고리즘", "quicksort 구현", "merge sort",
            "안정 정렬", "부분 정렬", "in-place sort",
        ],
    ),
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


@pytest.fixture(scope="module")
def extended_store(tmp_path_factory):
    """36 + 36 + 30 = 102 record 시드. id 1-based."""
    db = tmp_path_factory.mktemp("ext") / "ext.db"
    store = MemoryStore(db, korean_tokenizer="kiwi", enable_embeddings=True).open()

    # ID 1..36: original 6 groups
    for _, phrases in _ORIGINAL_GROUPS:
        for p in phrases:
            store.record_call(
                tool_name="seed", inputs={"q": p}, output=f"out for {p}",
                model="seed", duration_ms=1,
            )
    # ID 37..72: new 6 groups
    for _, phrases in _NEW_GROUPS:
        for p in phrases:
            store.record_call(
                tool_name="seed", inputs={"q": p}, output=f"out for {p}",
                model="seed", duration_ms=1,
            )
    # ID 73..102: noise
    for n in _NOISE:
        store.record_call(
            tool_name="seed", inputs={"q": n}, output=f"out for {n}",
            model="seed", duration_ms=1,
        )
    yield store
    store.close()


@pytest.fixture(scope="module")
def cloud_client():
    if not os.environ.get("OLLAMA_CLOUD_API_KEY"):
        pytest.skip("OLLAMA_CLOUD_API_KEY 미설정 - expanded 측정 skip")
    cfg = OllamaCloudProviderConfig(
        host="https://ollama.com",
        api_key_env="OLLAMA_CLOUD_API_KEY",
        model="glm-4.7",
    )
    return from_cloud(cfg, temperature=0.3, timeout=60)


def _relevant_for_group(group_idx: int) -> set[int]:
    """group N (0-based) 의 6 record id (1-based)."""
    start = group_idx * 6 + 1
    return set(range(start, start + 6))


def _all_groups() -> list[tuple[str, list[str]]]:
    return _ORIGINAL_GROUPS + _NEW_GROUPS


def test_extended_seed_size(extended_store):
    expected = sum(len(p) for _, p in _all_groups()) + len(_NOISE)
    assert extended_store.count() == expected
    assert expected >= 100  # 100+ 조건


def test_full_metrics_per_path(extended_store, cloud_client, capsys):
    """5 path × 4 metric × 12 group + AVG."""
    groups = _all_groups()  # 12 groups
    by_path: dict[str, list[RetrievalMetrics]] = {
        "BM25": [], "vec": [], "hybrid": [], "rerank": [], "exp+B": [],
    }

    for idx, (_, phrases) in enumerate(groups):
        query = phrases[0]
        relevant = _relevant_for_group(idx)

        bm = [s.full_id for s in recall(extended_store, query, limit=20).snippets]
        vec = [h.id for h in extended_store.search_vectors(query, limit=20)]
        hy = [s.full_id for s in recall_hybrid(extended_store, query, limit=20).snippets]
        rr = [
            s.full_id
            for s in recall_reranked(
                extended_store, query, limit=20, candidate_pool=20, base="hybrid"
            ).snippets
        ]
        ex = [
            s.full_id
            for s in recall_expanded(
                extended_store, query, client=cloud_client, mode="bm25", limit=20
            ).snippets
        ]

        by_path["BM25"].append(compute_metrics(bm, relevant))
        by_path["vec"].append(compute_metrics(vec, relevant))
        by_path["hybrid"].append(compute_metrics(hy, relevant))
        by_path["rerank"].append(compute_metrics(rr, relevant))
        by_path["exp+B"].append(compute_metrics(ex, relevant))

    avg = {p: average_metrics(ms) for p, ms in by_path.items()}

    with capsys.disabled():
        print("\n\n=== Phase 4-3 Extended seed (102 record) - per path averages ===")
        print(f"{'path':<10}{'P@1':>8}{'P@5':>8}{'R@5':>8}{'MRR':>8}")
        print("-" * 42)
        for p in ("BM25", "vec", "hybrid", "rerank", "exp+B"):
            m = avg[p]
            print(f"{p:<10}{m.p1:>8.2f}{m.p_at_k:>8.2f}{m.r_at_k:>8.2f}{m.mrr:>8.2f}")
        print()

    # 가설:
    # 1) vector P@1 이 BM25 P@1 보다 크게 떨어지지 않아야 (cross-lingual / paraphrase).
    assert avg["vec"].p1 >= avg["BM25"].p1 - 0.05, (
        f"vec P@1 {avg['vec'].p1:.2f} vs BM25 P@1 {avg['BM25'].p1:.2f} - "
        f"의미 매칭이 키워드 매칭에 크게 못 미치면 안 됨"
    )
    # 2) reranked MRR 이 hybrid MRR 보다 크게 떨어지지 않아야 (재정렬이 망치지 않음).
    assert avg["rerank"].mrr >= avg["hybrid"].mrr - 0.05, (
        f"rerank MRR {avg['rerank'].mrr:.2f} vs hybrid {avg['hybrid'].mrr:.2f}"
    )

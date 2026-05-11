"""Phase 7-2 - 6 probe (project-context dependent task).

Round 17 dogfooding (tuna_general_task, 2026-05-11) 차용 + architect 검증.
"""

from __future__ import annotations

# 각 probe = current_task (task description) + correct_identifiers (정답 식별자)
# + prior_context (relevant mode prepend 텍스트).

PROBES: list[dict] = [
    {
        "id": "P1_store_get",
        "task": (
            "사용자 레코드 1개를 ID 기반으로 조회하는 함수를 작성하세요. "
            "이 프로젝트의 내부 저장소 클래스를 활용해야 합니다."
        ),
        "correct_identifiers": [
            "MemoryStore", "record_call", "get", "call_id",
        ],
        "prior_context": (
            "이 프로젝트는 `MemoryStore` 클래스를 사용합니다 (NOT `Store`). "
            "주요 메서드: `MemoryStore.record_call(...)`, "
            "`MemoryStore.get(call_id: int) -> CallRecord | None`."
        ),
        "irrelevant_kw": ["bcrypt", "hashlib", "salt", "rate_limit"],
    },
    {
        "id": "P2_rerank_on_hybrid",
        "task": (
            "하이브리드 검색 결과에 리랭커를 적용하여 최종 순위를 재조정하는 "
            "로직을 구현하세요."
        ),
        "correct_identifiers": [
            "recall_hybrid", "recall_reranked", "candidate_pool",
        ],
        "prior_context": (
            "이 프로젝트의 검색 API: `recall_hybrid(store, query, limit, k=60)` "
            "(BM25 + vector RRF). 리랭킹은 "
            "`recall_reranked(store, query, limit=5, candidate_pool=20, "
            "base='hybrid')` 로 cross-encoder bge-reranker-v2-m3 사용."
        ),
        "irrelevant_kw": ["asyncio", "tornado", "tkinter"],
    },
    {
        "id": "P3_korean_tokenize",
        "task": (
            "한국어 형태소 분석기를 사용하여 문서 인덱싱을 위한 토큰화 함수를 "
            "추가하세요."
        ),
        "correct_identifiers": [
            "tokenize_for_index", "kiwi", "FTS5",
        ],
        "prior_context": (
            "이 프로젝트는 한국어 형태소 분석에 Kiwi 를 사용합니다. "
            "기존 헬퍼: `tokenize_for_index(text: str, tokenizer)`. "
            "FTS5 가상 테이블 색인에 사용됨."
        ),
        "irrelevant_kw": ["spacy", "nltk", "transformers"],
    },
    {
        "id": "P4_config_add_field",
        "task": (
            "설정 파일의 TOML 구조를 반영하여 LLM 관련 설정 모델에 새로운 "
            "타임아웃 필드를 추가하세요."
        ),
        "correct_identifiers": [
            "LLMConfig", "pydantic", "TOML",
        ],
        "prior_context": (
            "이 프로젝트의 config: `tunallama_core/config/models.py` 의 "
            "`LLMConfig` (pydantic dataclass). TOML 파싱 후 검증. "
            "필드 추가는 `LLMConfig` 클래스에 type-annotated 필드 하나 추가."
        ),
        "irrelevant_kw": ["argparse", "click", "typer"],
    },
    {
        "id": "P5_real_integration_test",
        "task": (
            "Mock 을 사용하지 않고 실제 클라우드 제공자 설정을 통해 검색 통합 "
            "테스트를 작성하세요."
        ),
        "correct_identifiers": [
            "OllamaCloudProviderConfig", "from_cloud", "pytest.mark.integration",
        ],
        "prior_context": (
            "이 프로젝트의 통합 테스트 패턴: "
            "`OllamaCloudProviderConfig(host='https://ollama.com', "
            "api_key_env='OLLAMA_CLOUD_API_KEY', model='glm-4.7')` → "
            "`from_cloud(cfg, timeout=600)`. `@pytest.mark.integration` "
            "마커. mock 사용 금지."
        ),
        "irrelevant_kw": ["unittest.mock", "MagicMock", "patch"],
    },
    {
        "id": "P6_limitations_prepend",
        "task": (
            "모델의 약점 카탈로그 파일 내용을 작업 prompt 앞에 자동으로 "
            "prepend 해주는 도구를 작성하세요."
        ),
        "correct_identifiers": [
            "tuna_log_limitation", "with_limitations", "limitations.md",
        ],
        "prior_context": (
            "이 프로젝트의 약점 카탈로그: `~/.tunallama/limitations.md`. "
            "`tunallama_core.workflow.spec.with_limitations(requirements, "
            "path=...)` 가 prepend 처리. 새 약점 추가는 "
            "`tuna_log_limitation(description)` 도구."
        ),
        "irrelevant_kw": ["logging", "loguru", "structlog"],
    },
]

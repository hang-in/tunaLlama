# Phase 9 — 임베딩을 Ollama 로 전환 (torch-free 코어)

## 배경 / 동기

- 현재 `tunallama_core/memory/vector.py` 의 `embed()` 는 **sentence-transformers
  (torch)** 로 `BAAI/bge-m3` 를 로컬 로드한다. 이 torch 의존이:
  - Python 3.13 Windows 에서 `import torch` 가 **무한 hang** (실측). py3.11 강제.
  - 기본 설치가 torch(+cpu) 라 **GPU 미사용**. GPU 쓰려면 CUDA torch 재설치(~2.5GB).
  - 설치 용량이 크다.
- Secall 은 `qwen3-embedding:0.6b` 를 **Ollama `/api/embed`** 로 호출한다. 실측:
  1024-dim, BGE-M3 의 NaN 재현 케이스 해결, 한국어·코드·장문·배치 OK, 130~490ms.
- tunallama 는 **이미 `ollama` 를 코어 의존**(LLM 위임)으로 갖는다. 임베딩도 Ollama
  로 옮기면 **새 의존성 0**, GPU 는 Ollama 가 자동 관리(사용자 정책: VRAM 5GB↑ → GPU).

## 결론 (확정 설계)

임베딩 백엔드를 sentence-transformers → **Ollama `/api/embed`** 로 교체. 모델은
`qwen3-embedding:0.6b` (1024-dim, 기존 `EMBEDDING_DIM=1024` 와 호환 → 스키마 불변).
reranker(cross-encoder)는 **옵셔널 extra `[rerank]`** 로 강등해 코어를 torch-free 로.

### 사실 확인 (구현 전 검증됨)

- `curl /api/embed {"model":"qwen3-embedding:0.6b","input":[...]}` → `embeddings`
  2건, 각 **1024-dim**. 배치 지원.
- `store.py:190` 이 `from .vector import embed` 를 쓰는 **유일한 embed 호출처**.
- `search.py` 는 이미 `try: from .reranker import rerank ... except Exception:
  top-k 폴백`. → sentence-transformers 미설치 시 rerank 는 **자동 degrade, 코드 변경 0**.

## 변경 범위

### 1. `tunallama_core/memory/vector.py` — `embed()` 재작성 (Focus)

- `embed(text: str) -> np.ndarray` 시그니처 유지 (store.py 호환).
- 내부를 Ollama 클라이언트 호출로 교체:
  - `ollama.Client(host=<ollama host>).embed(model=<embed model>, input=text)`
    또는 `/api/embed` 직접. 응답 `embeddings[0]` → `np.array(dtype=float32)`.
  - **L2 정규화는 호출측에서 수행** (Ollama 응답이 unit vector 라 보장 못함).
    `v = v / (np.linalg.norm(v) + 1e-12)`.
- `_get_model` / `_resolve_device` / `sentence_transformers` import **제거**.
- `EMBEDDING_DIM=1024`, `encode_blob`/`decode_blob` **불변**.
- host/model 은 설정에서 주입 (아래 3). 순환 import 피하려 함수 인자 또는
  모듈 레벨 lazy config 로.
- (선택) 배치 `embed_many(texts) -> np.ndarray[(n,1024)]` 추가 — Ollama 배치 활용.

### 2. `pyproject.toml` — 의존성 재편

- 코어 `dependencies` 에서 `sentence-transformers>=3.0` **제거**. `numpy` 유지
  (cosine + blob). `ollama>=0.4.0` 이미 존재.
- 새 optional extra:
  ```toml
  [project.optional-dependencies]
  rerank = ["sentence-transformers>=3.0"]   # cross-encoder reranker (torch)
  ```
- 결과: 기본 `pip install -e .` → **torch 없음**. rerank 원하면 `.[rerank]`.

### 3. 설정 — 임베딩 모델/호스트

- `config.example.toml [memory]` 에 추가:
  ```toml
  embedding_model = "qwen3-embedding:0.6b"   # Ollama 태그
  # embedding_host 미지정 시 [llm.ollama].host 재사용
  ```
- `embedding_device` 는 임베딩 경로에서 **무의미해짐**(Ollama 가 GPU 관리) → reranker
  전용으로 의미 축소. 주석 갱신.
- 로더(`config/loader.py`, `config/models.py`)에 `embedding_model` 필드 추가.
- `_state.py` 가 store/embed 초기화 시 host+model 전달.

### 4. 마이그레이션

- 기존 `memory.db` 의 BGE 벡터는 Qwen 공간과 호환 안 됨 → **재임베딩 필요**.
  현재 코퍼스가 거의 비어 있어 비용 미미. 옵션:
  - 간단: `enable_embeddings` 재빌드 시 벡터 컬럼 초기화 후 재임베딩 CLI.
  - 또는 신규 설치는 그냥 새로 쌓임.

### 5. 테스트

- `tests/core/test_memory_vector.py`: sentence-transformers mock → Ollama embed
  mock 로 교체. dim=1024, 정규화(‖v‖≈1), 배치 검증.
- reranker 테스트는 `[rerank]` 미설치 환경에서 **skip** 또는 graceful-degrade 검증.
- 통합: `@pytest.mark.integration` 로 실제 Ollama `qwen3-embedding:0.6b` 호출
  (미가용 시 skip).

## Constraints

- `embed()` 시그니처·`EMBEDDING_DIM`·blob 포맷 불변 (store 호환).
- Ollama 미가용/모델 부재 시 명확한 에러 (LLMError 계열) — silent NaN 금지.
- 정규화 필수 (cosine 검색 전제).
- 오프라인 기본값 유지: Ollama 는 로컬이므로 HF 네트워크 의존 사라짐(오히려 개선).

## 비고 (dogfooding)

- `vector.py` `embed()` 재작성은 `tuna_generate_code` / tuna-developer 서브에이전트
  로 위임 → 본 세션이 검증. (단, 현재 세션 MCP 인스턴스는 config 이전 spawn 이라
  죽어 있음 → Claude Code 재시작 후 in-session 위임 가능. 그 전에는 marketplace
  venv 서버를 stdio 로 직접 구동해 위임.)

# Changelog

본 문서는 [Keep a Changelog](https://keepachangelog.com/ko/1.1.0/) 형식을 따른다.
버전 번호는 [Semantic Versioning](https://semver.org/lang/ko/)을 따른다.

## [0.6.0] - 2026-07-03

임베딩을 Ollama 로(torch-free 코어), Windows 에서 MCP in-session hang 을 HTTP 전송으로 해결.
자세히: `docs/release-notes/v0.6.0.md`.

### Phase 9 - 임베딩을 Ollama 로 (torch-free 코어)
- `vector.embed()` 를 sentence-transformers(torch) → Ollama `/api/embed` (L2 정규화).
  기본 모델 `qwen3-embedding:0.6b` (1024-dim). `MemoryConfig.embedding_model` 추가.
- `pyproject`: `sentence-transformers` 를 코어 deps → `[rerank]` optional extra.
  기본 설치가 **torch-free** (reranker 는 `[rerank]` 설치 시만, `search.py` graceful degrade).
- GPU 는 Ollama 가 자동 관리. 기존 memory.db 는 재임베딩 필요.

### Added - Windows HTTP MCP 전송
- `mcp_server`: `TUNA_MCP_TRANSPORT=http|sse` 전송 전환 (기본 stdio). streamable-http 데몬.
- `plugin/bin/tunallama-httpd.cmd` (데몬 런처) + `tunallama-win-setup.ps1` (원클릭 셋업, `-Uninstall`).
- Windows 의 Python+stdio MCP in-session hang(실측 565s) 을 HTTP 로 우회. mac/Linux 는 stdio 유지.

### Fixed
- Windows 테스트 이식성 7건(TOML 백슬래시 경로, Unix 권한/exec-bit 전제, subprocess env).
- `test_memory_mmr` hermetic 화(키워드 fake embed) → CI 가 Ollama 없이 통과 (507 passed).

## [Unreleased] - 0.5.0 (production release 준비)

### audit + production-ready 작업
- 외부 audit (general-purpose subagent) 결과 must-fix 3개 + 권장 5개 처리.
- `.mcp.json` 절대경로 → portable (`python` + `${CLAUDE_PLUGIN_ROOT}/..`).
- ruff 43 errors → 0 (F401 / F541 / F821 / F841 / E702 정리).
- `.env.example` 4 env vars 추가 (`TUNA_EMBEDDING_MODEL` / `TUNA_EMBEDDING_DEVICE`
  / `TUNA_AUTO_EXTRACT_STATE` / `TUNALLAMA_HOOK_THRESHOLD`).
- `dev_review_loop` 93줄 → `_run_review_iteration()` 추출.
- `init_cmd` broad except → 구체 예외.
- `.github/workflows/ci.yml` 추가 (ruff + pytest gate).
- README 상세화: badges + 5분 설치 4단계 + "첫 호출 해보기" + Troubleshooting
  + Codex CLI 섹션.
- CONTRIBUTING.md + ISSUE 템플릿 (bug / feature) 추가.
- 에러 메시지 한국어화 (`[error]` → `[오류]`).
- 측정자산 archive (`tests/integration/archive/`): Phase 4-4 saturate +
  Phase 5-2D MMR abandoned 보존 + README.
- TOTAL coverage 90%, 475 unit/plugin pass.

### Phase 8 - Codex CLI 호환 (한 레포 / 두 환경)
- `plugin/agents/tuna-developer.toml` 추가 - Codex 용 TOML.
- Claude `tuna-developer.md` 와 동시 보존.
- Codex CLI 가 `.claude-plugin/marketplace.json` 직접 읽음 (4개 인식 위치).

### Phase 7-2 - mid-size LLM context boost 측정
- 6 probe × 4 mode × 3 model (gemma4:31b / qwen3-coder-next / kimi-k2.6).
- **context boost +0.58 ~ +0.64** 3 모델 일관 검증.
- **mixed = relevant**: R@5 0.5 시뮬에서도 코드 품질 동등.
- adversarial damage 작음.
- 자세한 결과: `docs/measurements/phase7-context-boost.md`.

## [0.4.0] - 2026-05-11 - Memory layer

- Phase 6: state.md auto-load + decision/convention/constraint/antipattern
  자동 추출 + diff-based learning + 자동화 metrics (4 종).

## [0.3.0] - 2026-05-11 - production-RAG path

- Phase 5: HyDE hybrid (P@1 0.92, σR@5 0.14) + KURE-v1 swap + Adaptive routing.
- MCP 도구 15 → 13 통합.

## [Archived] - 0.2.0 (Phase 2 + 3 통합 완료, 릴리즈 대기)

### Phase 3 — semantic edges + synonym recall benchmark
- **`tests/integration/test_search_quality_synonym.py`**: 36 record (6 task
  × 6 paraphrase) 시드 + recall@5 측정. **vector R=0.67 >> BM25 R=0.25** —
  paraphrase 시나리오에서 벡터 의미 매칭 2.7배 우세 정량 검증.
- **`tunallama_core/memory/semantic_edges.py`**: LLM-derived 페어 분류 —
  binary `RELATED`/`UNRELATED` (Phase 1.5 stage-2 classifier 패턴).
  `classify_pair`, `build_semantic_edges`. `max_pairs` 한도 + project_root
  좁힘 + idempotent.
- **`graph_edges.relation = 'semantic_related'`** 추가. `rebuild_edges()` 가
  rule edges (`same_project`/`same_day`/`same_tool`) 만 삭제하도록 변경 —
  semantic 엣지 보존.
- 9 단위 테스트(semantic_edges) + 2 통합 테스트(synonym recall). 329 tests,
  92% coverage.

### Phase 3.5 - LLM query expansion (검색률 향상)
- **`tunallama_core/memory/query_expansion.py`**: `expand_query(client, query,
  max_expansions=4)` - 동의어/paraphrase 확장. LLM 응답 형식 깨짐 / 호출
  실패 시 원 query 만으로 fallback.
- **`recall_expanded(store, query, *, client, mode, max_expansions, k)`**:
  확장된 각 query 로 BM25 또는 hybrid 검색 후 RRF 합산.
- **실측**: paraphrase 시드에서 BM25 R@5 = 0.25 -> 0.50 (**2배 향상**).
  vector 가 이미 강한 환경에서는 한계 효용 X.
- 11 단위 테스트 (expand_query 6 + recall_expanded 5).

### dogfooding 11 라운드 누적 결과 (`docs/dogfooding-log.md`)
- 모델은 형식(pytest, dataclass) 은 따르지만 우리 코드베이스 통합은 거의 무시.
  매 라운드 standalone prototype 으로 응답.
- delegation 의 진짜 가치 = 알고리즘/디테일 차용 + 시간/토큰 절약. Architect 의
  검증/통합은 필수.


### Phase 2 — semantic memory + graph
- **벡터 임베딩** (`tunallama_core/memory/vector.py`): `BAAI/bge-m3` 1024-dim,
  lazy load + threading.Lock, `normalize_embeddings=True` (모델 native L2),
  blob 길이 corruption 가드. `VectorHit` dataclass.
- **schema migration**: `calls.embedding BLOB` 컬럼 + 옛 db 의 `ALTER TABLE
  ADD COLUMN` idempotent 처리 (`MemoryStore._migrate_embedding_column`).
- **`MemoryStore.search_vectors`**: cosine 유사도 brute-force (numpy dot).
  `embedding IS NOT NULL` 인 행만, `project_root` 필터, NULL/corrupt 자동 skip.
  임베딩 파이프라인 실패 시 빈 리스트 (BM25 fallback 은 호출자 몫).
- **`recall_hybrid`** (`tunallama_core/memory/search.py`): BM25 + 벡터 RRF 병합
  (k=60). `expanded_limit = limit*2` 후보 풀 → 1/(k+rank) 합산 → dedup. 벡터
  결과 비어도 BM25 만으로 정상 동작. 기존 `recall()` signature 변경 없음.
- **Rule-based graph edges** (`tunallama_core/memory/graph.py`):
  `same_project` / `same_day` / `same_tool` 3 종 엣지. SQL JOIN 으로 O(N²)
  처리 (Python 메모리 회피). `a.id < b.id` 정규화 + self-loop 차단. `Edge`
  dataclass + `rebuild_edges()` + `traverse(start_id, max_hops, relations)`
  Python BFS.
- **schema 추가**: `graph_edges` 테이블 + 양쪽 인덱스.

### Phase 2 작업 흐름
- 3 spec (vector / RRF / graph) 으로 `tuna_dev_review_from_spec` 위임 (model
  = `glm-4.7`). Architect 가 결과 차용 + 직접 통합. 자세한 라운드별 결과 +
  차용/직접작성 분리는 `docs/dogfooding-log.md` round 7-9 + 종합 섹션.
- 312 tests, 91% coverage. 28 new tests (vector 11 + hybrid 7 + graph 10).
- Public API 추가: `VectorHit`, `Edge`, `recall_hybrid`, `rebuild_edges`,
  `traverse`, `EMBEDDING_MODEL`, `EMBEDDING_DIM`.

## [0.1.0] — 2026-05-10

## [0.1.0] — 2026-05-10

첫 정식 릴리즈. Phase 1 + Phase 1.5 완료.

### Phase 1.5 (workflow + hook + dogfooding)
- `tunallama_core/workflow/` — `dev_review_loop` (generate → review → fix → review),
  `TaskSpec` markdown 파서 (Phase / Focus / Constraints / Acceptance), 약점 카탈로그
  자동 prepend (`limitations.py`).
- `plugin/hooks/pre_tool_use.py` — `Read` 큰 파일 시 advisory (off by default).
- gemento 패턴 도입: `phase` enum, `focus` 필드, hard-rule constraints. `seCall` 의
  Kiwi keep-tag 에 `NNB` 추가.
- VERDICT 구조화 review prompt + JSON Schema 옵션 + stage-2 classifier (3-tier
  fallback). dogfooding 6 라운드로 검증 — 자세한 사례는 `docs/dogfooding-log.md`.

### Phase 1 Backend

### Phase 1 Backend
- **errors**: `TunaLlamaError` 베이스 + `ConfigError` / `LLMError` / `MemoryStoreError` / `RecallError`.
- **config** (`tunallama_core/config/`): TOML 로드 + 경로 탐색 (CWD `.tunallama/` → `~/.tunallama/`) + 필드별 검증 (provider/temperature/timeout/tokenizer/auto_recall/log level). frozen dataclass.
- **llm** (`tunallama_core/llm/`): `LLMClient` 추상 + `OllamaClient` (로컬+클라우드, ollama SDK) + `LMStudioClient` (httpx, OpenAI 호환). `make_client(LLMConfig)` 팩토리.
- **memory** (`tunallama_core/memory/`): SQLite + FTS5 standalone + Kiwi 형태소 사전 토큰화. `MemoryStore.record_call/get/count`, `recall(query, ...)` BM25 스니펫 반환. 한국어 띄어쓰기 없는 입력도 morpheme 검색 가능.
- **delegation** (`tunallama_core/delegation/`): 10 도구 (`generate_code`/`review_code`/`explain_code`/`refactor_code`/`fix_code`/`write_tests`/`general_task`/`review_file`/`explain_file`/`analyze_files`). 파일 도구는 내용을 LLM 에는 전달하지만 메모리 로그에는 경로만 기록 (핸드오프 §7.4 시나리오 B).
- **routing** (`tunallama_core/routing.py`): `recall_for_delegation(routing, store, ...)` — `never` / `on_request` / `always` 정책.

### Plugin 영구 등록 + .env 자동 로드
- `plugin/_state.py` 가 첫 호출 시 cwd → 프로젝트 루트 순으로 `.env` 자동 로드. settings.json 에 평문 키를 적지 않아도 `OLLAMA_CLOUD_API_KEY` 등이 채워진다.
- `tunallama_core/cli/main.py` 도 동일한 cwd `.env` 로드 — `tunallama doctor` / `init` 가 plugin 과 동일한 환경을 본다.
- `python-dotenv >= 1.0` 을 런타임 의존성에 명시.
- README 한국어/영문 동기화 + 마케팅 톤 제거 + 기술 포스트 형식.
- `docs/specs/iso_datetime_parser.md` — 첫 dogfooding 샘플 spec.

### Phase 1 Onboarding CLI
- `tunallama init` — 대화식 config.toml 생성기. provider 선택 → 모델 자동 발견(로컬 Ollama / LM Studio) → 환경변수 키 안내 → 메모리 옵션. 표준 라이브러리만 사용.
- `tunallama doctor` — 환경 진단(Python / config / provider 가용 / DB write / Kiwi). 실패 시 조치 단서 포함.
- `pyproject.toml` `[project.scripts]` 에 진입점 등록.

### Phase 1 Plugin
- `plugin/.claude-plugin/plugin.json`, `plugin/.mcp.json`.
- `plugin/mcp_server.py`: FastMCP 서버 + 11 도구 (`tuna_*`) — backend wrapper.
- `plugin/_state.py` lazy 싱글톤, `plugin/_format.py` recall 직렬화.
- `plugin/skills/delegate-to-ollama/SKILL.md` — Claude 가 도구 사용 시점을 학습.
- `plugin/agents/tuna-developer.md` — delegate-then-verify 서브에이전트.

### 인프라 / 문서
- 레포 스켈레톤 초기화 (`tunallama_core/`, `plugin/`, `tests/`).
- `pyproject.toml`, MIT `LICENSE`, `.gitignore`, `config.example.toml` 작성.
- 한국어 메인 README, 영문 보조 README 분리(`README.md`, `README.en.md`).
- mise 기반 개발 툴체인(`mise.toml`): Python 3.11 + uv + `.venv` 자동 활성화 + 공통 task(`install`, `test`, `lint`, `format`, `mcp`).
- `.env` 자동 로드(mise) + `.env.example`. config.toml 의 `api_key_env` 가 가리키는 환경변수 보관용. 평문 키는 git ignore.

### 테스트
- 177 테스트, 99% 커버리지 (`pytest --cov`).
- 단위 테스트는 fake `LLMClient` (StaticClient) 사용. 통합 테스트(`@pytest.mark.integration`) 는 실 Ollama Cloud + LM Studio 에 붙으며 미가용 시 자동 skip.

### 핸드오프 스펙 변경분 (`docs/handoff-tunallama-phase1.md` 대비)
- LLM provider 범위를 **Ollama 로컬 단일** → **Ollama(로컬+클라우드) + LM Studio**로 확장.
  - `tunallama_core/ollama_client.py` 단일 파일이 아닌 `tunallama_core/llm/` 하위 (base/ollama/lmstudio/factory)로 설계.
  - LM Studio용 OpenAI 호환 호출을 위해 `httpx` 의존 추가.
  - `config.toml` 의 `[ollama]` 섹션을 `[llm]` + `[llm.<provider>]` 구조로 재편.
- README 언어 우선순위를 **English 우선** → **한국어 우선, 영문 별도 파일**로 변경.
- 개발 워크플로를 **`pip install -e .` 단일 안내** → **mise + uv 기반**으로 전환. 사용자 설치 가이드(`pip`)는 그대로 유지.

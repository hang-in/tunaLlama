# Changelog

본 문서는 [Keep a Changelog](https://keepachangelog.com/ko/1.1.0/) 형식을 따른다.
버전 번호는 [Semantic Versioning](https://semver.org/lang/ko/)을 따른다.

## [Unreleased]

### 진행 중 (Phase 2)
- 벡터 임베딩 + HNSW 시맨틱 검색
- RRF (Reciprocal Rank Fusion) 로 BM25 + 벡터 병합
- Rule-based 그래프 엣지 (`same_project`, `same_day`)
- Phase 2 작업은 dogfooding 흐름으로 진행 — spec → `tuna_dev_review_from_spec`

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

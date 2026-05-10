# Changelog

본 문서는 [Keep a Changelog](https://keepachangelog.com/ko/1.1.0/) 형식을 따른다.
버전 번호는 [Semantic Versioning](https://semver.org/lang/ko/)을 따른다.

## [Unreleased] — 0.1.0.dev0

### Phase 1 Backend
- **errors**: `TunaLlamaError` 베이스 + `ConfigError` / `LLMError` / `MemoryStoreError` / `RecallError`.
- **config** (`tunallama_core/config/`): TOML 로드 + 경로 탐색 (CWD `.tunallama/` → `~/.tunallama/`) + 필드별 검증 (provider/temperature/timeout/tokenizer/auto_recall/log level). frozen dataclass.
- **llm** (`tunallama_core/llm/`): `LLMClient` 추상 + `OllamaClient` (로컬+클라우드, ollama SDK) + `LMStudioClient` (httpx, OpenAI 호환). `make_client(LLMConfig)` 팩토리.
- **memory** (`tunallama_core/memory/`): SQLite + FTS5 standalone + Kiwi 형태소 사전 토큰화. `MemoryStore.record_call/get/count`, `recall(query, ...)` BM25 스니펫 반환. 한국어 띄어쓰기 없는 입력도 morpheme 검색 가능.
- **delegation** (`tunallama_core/delegation/`): 10 도구 (`generate_code`/`review_code`/`explain_code`/`refactor_code`/`fix_code`/`write_tests`/`general_task`/`review_file`/`explain_file`/`analyze_files`). 파일 도구는 내용을 LLM 에는 전달하지만 메모리 로그에는 경로만 기록 (핸드오프 §7.4 시나리오 B).
- **routing** (`tunallama_core/routing.py`): `recall_for_delegation(routing, store, ...)` — `never` / `on_request` / `always` 정책.

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

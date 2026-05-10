# Changelog

본 문서는 [Keep a Changelog](https://keepachangelog.com/ko/1.1.0/) 형식을 따른다.
버전 번호는 [Semantic Versioning](https://semver.org/lang/ko/)을 따른다.

## [Unreleased] — 0.1.0.dev0

### 추가
- 레포 스켈레톤 초기화 (`tunallama_core/`, `plugin/`, `tests/`).
- `pyproject.toml`, MIT `LICENSE`, `.gitignore`, `config.example.toml` 작성.
- 한국어 메인 README, 영문 보조 README 분리(`README.md`, `README.en.md`).
- mise 기반 개발 툴체인(`mise.toml`): Python 3.11 + uv + `.venv` 자동 활성화 + 공통 task(`install`, `test`, `lint`, `format`, `mcp`).

### 핸드오프 스펙 변경분 (`docs/handoff-tunallama-phase1.md` 대비)
- LLM provider 범위를 **Ollama 로컬 단일** → **Ollama(로컬+클라우드) + LM Studio**로 확장.
  - `tunallama_core/ollama_client.py` 단일 파일이 아닌 `tunallama_core/llm/` 하위 (base/ollama/lmstudio/factory)로 설계.
  - LM Studio용 OpenAI 호환 호출을 위해 `httpx` 의존 추가.
  - `config.toml` 의 `[ollama]` 섹션을 `[llm]` + `[llm.<provider>]` 구조로 재편.
- README 언어 우선순위를 **English 우선** → **한국어 우선, 영문 별도 파일**로 변경.
- 개발 워크플로를 **`pip install -e .` 단일 안내** → **mise + uv 기반**으로 전환. 사용자 설치 가이드(`pip`)는 그대로 유지.

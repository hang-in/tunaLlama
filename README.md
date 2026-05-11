# tunaLlama

[![CI](https://github.com/hang-in/tunaLlama/actions/workflows/ci.yml/badge.svg)](https://github.com/hang-in/tunaLlama/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Status: production](https://img.shields.io/badge/status-production-brightgreen.svg)](#)
[![Tests: 506 passing](https://img.shields.io/badge/tests-506%20passing-brightgreen.svg)](#)
[![Coverage: 90%](https://img.shields.io/badge/coverage-90%25-brightgreen.svg)](#)
[![Claude Code / Codex CLI](https://img.shields.io/badge/works%20with-Claude%20Code%20%2F%20Codex%20CLI-purple.svg)](#)

Claude Code / Codex CLI 쓰면서 토큰 빨리 닳는 사용자를 위한 위임 도구입니다.

무거운 코드 생성을 로컬 Ollama / LM Studio / Ollama Cloud 에 위임하고,
분해 / 검증만 Claude (또는 Codex) 가 같은 세션 안에서 수행합니다. **한 레포로
Claude Code 와 Codex CLI 둘 다 작동** (둘 다 `.claude-plugin/marketplace.json`
인식).

**상태**: **v0.5.0 production release** (2026-05-11). Claude Code + Codex CLI 둘 다 검증 완료.
**라이선스**: [MIT](LICENSE). **English**: [README.en.md](README.en.md).

---

## 누가 쓰면 도움 될 가능성

- Claude Code Pro/Max 정액제 사용자 (한도 관리 동기)
- Codex CLI 사용자 (OpenAI 정액제 / API quota 관리)
- Ollama 로컬 / Ollama Cloud / LM Studio 환경 있는 사용자
- 한국어 작업 다루는 사용자 (Kiwi 형태소 토크나이저 통합)

다만 위 시나리오의 실제 가치는 본인 dogfooding 으로 확인을 추천합니다.
사용 한도 절약은 체감 데이터로만 확인 가능 (Anthropic / OpenAI 한도 계산식
비공개).

### 기술적 요구사항

- Python 3.11+
- Ollama / LM Studio / Ollama Cloud 중 하나
- Claude Code (MCP 플러그인 지원 버전) 또는 Codex CLI

## 어떻게 작동하는가

| 역할 | 모델 | 책임 |
|---|---|---|
| Architect | Claude / Codex (정액제) | 분해 / 사양 / 검증 / 통합 |
| Developer | 로컬 LLM (Ollama / Cloud / LM Studio) | 코드 생성 / 자체 리뷰 / 자체 수정 |
| Reviewer | Architect 같은 세션 | 최종 판정 |

전형적인 호출 흐름:

1. 사용자가 작업 요청 (한국어 / 영어).
2. Architect 가 작업 분해 - 짧으면 `tuna_dev_review`, 길면 spec 문서 작성 후
   `tuna_dev_review_from_spec`.
3. 백엔드가 generate → review → fix 루프 자동 반복. 모든 호출은 SQLite 에
   기록되고 한국어 형태소로 색인됩니다.
4. 검색의 진짜 가치: **mid-size 로컬 LLM 의 컨텍스트 한계를 architect 가
   보완** (Opus + Sonnet subagent 패턴과 동일). Phase 7-2 측정에서 context
   boost +0.58 ~ +0.64 정량 확인.
5. Architect 가 결과 검증 후 사용자에게 반환.

자세한 워크플로우: [docs/workflow.md](docs/workflow.md).
내부 구조: [docs/internals.md](docs/internals.md).

## 5분 설치

> **에이전트에게 한 줄로 위임 가능**: Claude Code / Codex CLI 세션에서
> `https://github.com/hang-in/tunaLlama 의 INSTALL.md 따라 설치해줘` 입력
> → 에이전트가 [INSTALL.md](INSTALL.md) 읽고 의존성 / `.env` / 플러그인
> 등록 / 검증까지 단계별 실행. 5분 안에 사용 가능.

수동 설치는 아래 단계:

### 1. Clone + 의존성 설치

```bash
git clone https://github.com/hang-in/tunaLlama
cd tunaLlama

# uv 권장 (mise.toml 에 정의됨)
mise install                   # python 3.11 + uv
mise run install               # editable + dev 의존성

# 또는 pip 직접
pip install -e .
```

### 2. 환경변수 (Ollama Cloud 쓸 경우)

```bash
cp .env.example .env
echo "OLLAMA_CLOUD_API_KEY=발급받은_키" >> .env
```

### 3. tunallama init / doctor

```bash
tunallama init                 # 대화식 - provider/모델 자동 발견
tunallama doctor               # Python / config / provider / DB / Kiwi 검사
```

`doctor` 통과 못 하면 [Troubleshooting](#troubleshooting--faq) 참조.

### 4-A. Claude Code 사용자

플러그인으로 설치:

```bash
claude plugin marketplace add /path/to/tunaLlama
claude plugin install tunaLlama@tunallama-local
```

또는 `~/.claude/settings.json` 의 `mcpServers` 에 직접 등록:

```json
{
  "mcpServers": {
    "tunallama": {
      "command": "python",
      "args": ["-m", "plugin.mcp_server"],
      "cwd": "/path/to/tunaLlama"
    }
  }
}
```

### 4-B. Codex CLI 사용자

Codex CLI 가 `.claude-plugin/marketplace.json` 직접 읽음 (4개 인식 위치
중 하나로 명시 지원):

```bash
codex plugin marketplace add /path/to/tunaLlama
codex plugin install tunaLlama@tunallama-local
```

호환 상세: [docs/specs/phase8_codex.md](docs/specs/phase8_codex.md).

## 첫 호출 해보기

설치 후 Claude Code / Codex 세션에서:

### 코드 생성 위임

```
사용자: "json 파싱하는 함수 작성해줘"

Claude/Codex 가 자동으로:
1. tuna_load_memory()  ← 프로젝트 컨벤션 fetch
2. tuna_recall(query="json parsing")  ← 과거 비슷 작업 surface (옵션)
3. tuna_generate_code(requirements="json 파싱 함수", language="python")
   → 로컬 LLM 이 코드 생성
4. Architect 가 검증 후 사용자에게 반환
```

### 큰 작업 - spec 기반

```
사용자가 docs/specs/foo.md 에 작업 spec 작성 후:

Claude/Codex: tuna_dev_review_from_spec("docs/specs/foo.md")
→ 백엔드가 generate → review → fix 자동 반복
→ 최종 코드 + iteration 로그 반환
```

### 메모리 검색

```
사용자: "이 프로젝트에서 BGE-M3 임베딩 어떻게 썼었지?"

Claude/Codex: tuna_recall(query="BGE-M3 임베딩 사용")
→ 과거 5 개 호출 결과 surface
```

자세한 도구 list 13 개: [docs/internals.md](docs/internals.md#mcp-tools).

## 한계

- **production 단계** (v0.5.0). Claude Code + Codex CLI 둘 다 검증. 단
  organic dogfooding (실 일상 사용) 측정 자산 부재는 인지된 한계.
- **사용 한도 절약은 체감 데이터**. Anthropic / OpenAI 정액제 한도 계산식이
  비공개라 정량 측정 불가능.
- **검색 측정값 (R@5, P@1 등) 은 합성 시드 기반**. 실 사용자 워크플로우
  검증은 별개 자리. 자세한 측정: [docs/measurements/](docs/measurements/).
- **MCP 자동 호출 의존**. 사용자가 `tuna_*` 도구를 명시 호출할 일은 거의
  없고, Architect 가 작업 컨텍스트 보고 자동 판단해서 호출하는 구조. 도구
  description 품질이 자동 호출 적절성을 결정.
- **로컬 LLM 의존**. Ollama 등 환경 없으면 작동 X.
- **한국어 형태소 분석 = Kiwi 의존**. Kiwi 가 못 처리하는 도메인 단어
  (신조어, 전문용어) 검색 품질 영향 가능.
- **organic dogfooding 자동 수집** (v0.5.7+). 매 delegation 후 metric 4종
  (`standalone_toy_rate` / `convention_adherence_rate` / `ast_excess_score`
  / `syntactically_valid`) 가 `~/.tunallama/metrics.db` 에 적재.
  `tunallama metrics show` 로 조회. 비활성: `TUNA_ORGANIC_METRICS=0`.
- **MCP 도구 system prompt 비용**. 13 도구 description + schema 가 매
  conversation 의 system prompt 에 prepend. 추정 ~1633 tokens (영문
  3.5 char/token 휴리스틱). 자세한 측정:
  [docs/measurements/phase7-mcp-audit.md](docs/measurements/phase7-mcp-audit.md).
- **테스트 커버리지 90%** (475 unit/plugin tests). 미커버 10% 의 대부분은
  외부 서비스 의존 path (`llm/ollama.py` 62% / `llm/lmstudio.py` 58% -
  통합 테스트 `pytest -m integration` 실행 시 추가 커버). `token_count.py`
  34% 는 Phase 5-4 보류 모듈 (Anthropic API 미보유라 unit test 없음).
- **Subagent 자동 인식 미작동** (Codex 0.128.0 실측): `plugin/agents/
  tuna-developer.toml` 가 캐시되지만 Codex 의 `spawn_agent` 가능 type 에
  `tuna-developer` 등록 안 됨 (default / explorer / worker 만). Claude Code
  측은 미실측. MCP tools 13 개는 양쪽 모두 정상 작동 - delegation 은 도구
  레벨에서 가능.
- **MCP resource auto-attach + SessionStart hook 미작동** (양 환경 실측):
  `tunallama://memory/state` resource 가 세션 시작 시 자동 첨가 안 됨.
  v0.5.2 의 SessionStart hook (`plugin/hooks/session_start.py`) 도 양
  클라이언트 모두 미인식 (sentinel 실측 - state.md 의 manual entry 가 새
  session 의 architect 컨텍스트에 도달 X). **실제 권장 운영**: architect 가
  docs 직접 읽거나 사용자가 `tuna_load_memory` 명시 호출 안내.

### 양 환경 동작 매트릭스 (v0.5.6 실측 - Claude Code 2.1.138 + Codex CLI 0.128.0)

| 항목 | Claude Code | Codex CLI |
|---|---|---|
| MCP tools 13 개 (도구 호출) | ✓ | ✓ |
| DB 공유 (`~/.tunallama/memory.db`) | ✓ | ✓ |
| state.md 공유 (`~/.tunallama/projects/<hash>/state.md`) | ✓ | ✓ |
| `tuna_load_memory` / `tuna_recall` 명시 호출 | ✓ | ✓ |
| **Agents auto-discovery** (`tuna-developer`) | **✓** | ✗ |
| **Skills auto-load** (`delegate-to-ollama`) | **✓** | ? |
| **Hooks 등록** (`SessionStart` / `PreToolUse`) | **✓** | ? |
| **SessionStart hook 실 실행 + state.md auto-prepend** | **✓** (v0.5.5 schema fix + 실측) | ✗ |
| **MCP resource auto-attach** (`tunallama://memory/state`) | ✗ | ✗ |

### 권장 운영 모델

**Claude Code** (v0.5.5+):
- state.md auto-prepend 가 SessionStart hook 으로 작동 - architect 가 첫
  turn 부터 conventions / decisions / constraints / anti-patterns 자동 인지.
- 별도 명시 호출 불필요. 단 사용자가 state.md 의도적 수정 후 effect 빨리
  보고 싶으면 새 세션 시작.

**Codex CLI** 0.128.0:
- SessionStart hook 인식 안 됨 - architect 가 첫 turn 에 `tuna_load_memory`
  명시 호출 또는 docs 직접 fetch.
- DB 공유 / state.md 공유 / MCP tools 호출은 모두 작동.

- **state.md auto-extract false positive 위험**. v0.5.1 에서 코드 블록
  안 텍스트 skip + meaningful 토큰 검증으로 완화 - 단 100% 제거는 어려움.
  의심 entry 발견 시 `tunallama state clean` (auto entry 삭제) 또는 직접
  편집 (`tunallama state path` 로 경로 확인).

## 무엇이 아닌가

- tunaFlow 의 멀티 에이전트 라운드테이블 아님.
- OllamaClaude 포크 아님 (패턴 참고).
- 단일 모델 데모 / 연구 노트북 아님.
- 자동 weakness 감지 / 동적 tool 작성 아님 - Architect 판단으로
  `tuna_log_limitation` 호출.

## 측정 자료

검색 알고리즘 / context boost / MCP audit 측정 결과:

- [전체 인덱스](docs/measurements/)
- [methodology.md](docs/measurements/methodology.md) - 시드 / LOPO /
  metric 정의 / 한계
- [phase4-search.md](docs/measurements/phase4-search.md) - 검색 품질
- [phase5-hyde-kure.md](docs/measurements/phase5-hyde-kure.md) - HyDE
  / KURE / Adaptive
- [phase7-mcp-audit.md](docs/measurements/phase7-mcp-audit.md) - MCP
  도구 system prompt size
- [phase7-context-boost.md](docs/measurements/phase7-context-boost.md) -
  **mid-size LLM context boost +0.58~+0.64** (3 모델 검증)

합성 시드 기반이라 실 사용 데이터 검증은 별개 자리입니다.

## Troubleshooting / FAQ

### `tunallama doctor` 실패

**Python 버전**: 3.11+ 필요. `python --version` 확인.

**provider 미감지**: Ollama / LM Studio 가 실행 중인지 확인.
```bash
curl http://localhost:11434/api/tags  # Ollama
curl http://localhost:1234/v1/models  # LM Studio
```

**Ollama Cloud 키 미감지**: `.env` 파일이 cwd 에 있는지 + `OLLAMA_CLOUD_API_KEY=...` 행이 첫 줄에 있는지 확인.

**Kiwi 형태소 분석기 실패**: `pip install kiwipiepy` 재설치. macOS 의 경우 Xcode CLI tools 필요 (`xcode-select --install`).

### MCP 도구가 Claude/Codex 컨텍스트에서 안 보임

**`.mcp.json` 의 cwd 가 잘못된 경우**: `claude plugin install` 한 위치 확인.
직접 등록한 경우 `cwd` 가 tunaLlama 레포 절대경로인지 확인.

**Python venv 미감지**: 시스템 python 으로 spawn 되지만 의존성 없을 수
있음. venv 의 python 절대경로로 등록 또는 `mise install` 후 PATH 통해 실행.

### `tuna_*` 도구가 호출 안 됨

**Architect 가 자동 호출하지 않음**: `SKILL.md` 또는 `tunallama://memory/state`
resource 미attach 가능. `tuna_load_memory` 명시 호출 시도.

**도구 description 품질**: 일부 task 가 너무 추상적이면 Architect 가 도구
선택 못 함. 명시적으로 "`tuna_dev_review` 사용해서 작성해줘" 같이 지시.

### LLM 호출 timeout

**기본 timeout 600 초** (`tunallama_core/config/models.py`). cloud LLM 응답
지연 시 retry 3 회. 그래도 실패하면 logger.warning 으로 기록됨 - dev
환경에서 stderr 확인.

**자주 timeout 발생 시**: 로컬 LLM 으로 swap 또는 모델 크기 줄이기
(qwen3-coder-next 등 latency 최적화 모델).

### 검색 품질이 낮은 것 같음

**현재 측정**: 합성 시드 기반 R@5 0.5 / σR@5 0.22 ~ 0.16 (HyDE 적용).

**R@5 < 0.8 의 의미**: 자동 prepend (`auto_recall=always`) 시 noise 섞임
가능. 단 Phase 4-4 + 5-3 측정에서 cloud LLM 이 무관 prefix 자동 무시 -
실 코드 품질 영향 작음 검증.

**default `on_request` 유지 권장**. `auto_recall=always` 는 risk 인지하고
사용.

### state.md auto-extract 의도치 않은 entry

**원인**: LLM 출력의 코드 블록 / 주석 / 일반 단어 가 false positive 로
auto-extract 됨 (v0.5.1 부터 코드 블록 안 텍스트 + meaningful 토큰 검증
필터 추가, 단 100% X).

**CLI 명령** (v0.5.1+):
```bash
tunallama state show    # 내용 출력
tunallama state path    # 파일 경로 출력
tunallama state clean   # (auto) 태그 entry 삭제, manual/verified 보존
```

**파일 위치**: `~/.tunallama/projects/<hash>/state.md`. 직접 편집도 가능.

**`(manual)` 또는 `(verified)` 태그**: 사용자 수정은 다음 update 시 보존.

**자동 추출 비활성**: `.env` 또는 환경변수에 `TUNA_AUTO_EXTRACT_STATE=0`.

## 기여자

```bash
mise install                    # python 3.11 + uv
mise trust                      # mise.toml 신뢰 (보안)
mise run install                # editable + dev 의존성
mise run test                   # pytest (unit + plugin only)

# 측정 통합 테스트 (BGE-M3 다운로드 + cloud LLM 호출):
.venv/bin/pytest -m search_quality -s
```

자세한 기여 가이드: [CONTRIBUTING.md](CONTRIBUTING.md).

## 디렉토리 / 문서

- [docs/workflow.md](docs/workflow.md) - Architect ↔ Developer 워크플로우 가이드.
- [docs/internals.md](docs/internals.md) - 내부 구조 (메모리, 검색, Provider, Hook).
- [docs/measurements/](docs/measurements/) - 측정 자료.
- [docs/specs/](docs/specs/) - Phase 별 spec 문서.
- [docs/dogfooding-log.md](docs/dogfooding-log.md) - 라운드별 dogfooding 결과.
- [docs/release-notes/](docs/release-notes/) - 릴리즈 노트
  ([v0.5.7](docs/release-notes/v0.5.7.md) · [v0.5.6](docs/release-notes/v0.5.6.md) ·
  [v0.5.5](docs/release-notes/v0.5.5.md) ·
  [v0.5.4](docs/release-notes/v0.5.4.md) · [v0.5.3](docs/release-notes/v0.5.3.md) ·
  [v0.5.2](docs/release-notes/v0.5.2.md) · [v0.5.1](docs/release-notes/v0.5.1.md) ·
  [v0.5.0](docs/release-notes/v0.5.0.md) · [v0.4.0](docs/release-notes/v0.4.0.md) ·
  [v0.3.0](docs/release-notes/v0.3.0.md)).
- [CHANGELOG.md](CHANGELOG.md) - 변경 이력.
- [CONTRIBUTING.md](CONTRIBUTING.md) - 기여 가이드.
- [config.example.toml](config.example.toml) - config 필드 + 주석.
- [.env.example](.env.example) - 환경변수 예시.

## 라이선스 / 기여

MIT. 이슈/PR 환영. 한국어/영어 모두 가능. 영문 README 는
[README.en.md](README.en.md) 를 함께 동기화 유지.

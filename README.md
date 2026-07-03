# tunaLlama

[![CI](https://github.com/hang-in/tunaLlama/actions/workflows/ci.yml/badge.svg)](https://github.com/hang-in/tunaLlama/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Status: usable beta](https://img.shields.io/badge/status-usable%20beta-yellow.svg)](#)
[![Tests: 507 passing](https://img.shields.io/badge/tests-507%20passing-brightgreen.svg)](#)
[![Coverage: 90%](https://img.shields.io/badge/coverage-90%25-brightgreen.svg)](#)
[![Claude Code / Codex CLI](https://img.shields.io/badge/works%20with-Claude%20Code%20%2F%20Codex%20CLI-purple.svg)](#)

**Claude Code / Codex CLI를 쓰면서 토큰이 빨리 닳는 사용자를 위한 위임(delegation) 도구입니다.**

무거운 코드 생성은 로컬 Ollama / LM Studio / Ollama Cloud에 위임하고, 작업 분해와 검증만 Claude(또는 Codex)가 같은 세션 안에서 맡습니다. 레포 하나로 **Claude Code와 Codex CLI 둘 다** 작동합니다(둘 다 `.claude-plugin/marketplace.json`을 인식).

---

## 한 줄 정의

tunaLlama는 프롬프트 시드나 AGENTS.md 템플릿이 **아닙니다**. **MCP 기반 위임 런타임**입니다.

상위 모델이 모든 문서와 긴 코드를 직접 떠안는 대신, 긴 코드 생성은 로컬/저비용 LLM에 넘기고 Architect는 작업 분해와 검증에만 집중하게 만드는 것이 핵심입니다.

| 항목 | 내용 |
| --- | --- |
| 상태 | **v0.5.x usable dogfooding release** (2026-05-11) |
| 검증됨 | Claude Code + Codex CLI 양쪽에서 MCP tool 호출 |
| 수집 중 | organic dogfooding 측정, 외부 사용자 재현성 |
| 라이선스 | [MIT](LICENSE) |
| 영문 문서 | [README.en.md](README.en.md) |

---

## 누가 쓰면 도움이 될까

- Claude Code Pro/Max 정액제 사용자 (한도 관리가 필요한 경우)
- Codex CLI 사용자 (OpenAI 정액제 / API quota 관리)
- Ollama 로컬 / Ollama Cloud / LM Studio 환경이 있는 사용자
- 한국어 작업을 다루는 사용자 (Kiwi 형태소 토크나이저 통합)

**절약 효과에 대한 솔직한 안내:** 실제 한도 절약 효과는 작업 유형, 모델, provider 지연시간, Architect의 검증 방식에 따라 달라집니다. Anthropic / OpenAI의 정액제 한도 계산식은 공개돼 있지 않습니다. 따라서 tunaLlama는 "정량 절감 보장"이 아니라, **긴 생성 작업을 위임해 상위 모델 사용량을 줄일 수 있는 구조**를 제공합니다. 실제 가치는 본인 dogfooding으로 확인하시길 권장합니다.

### 기술 요구사항

- Python 3.11+
- Ollama / LM Studio / Ollama Cloud 중 하나
- Claude Code (MCP 플러그인 지원 버전) 또는 Codex CLI

---

## 어떻게 작동하는가

역할은 셋으로 나뉩니다.

| 역할 | 모델 | 책임 |
| --- | --- | --- |
| **Architect** | Claude / Codex (정액제) | 분해 / 사양 / 검증 / 통합 |
| **Developer** | 로컬 LLM (Ollama / Cloud / LM Studio) | 코드 생성 / 자체 리뷰 / 자체 수정 |
| **Reviewer** | Architect와 같은 세션 | 최종 판정 |

전형적인 호출 흐름:

1. 사용자가 작업을 요청합니다 (한국어 / 영어).
2. Architect가 작업을 분해합니다. 짧으면 `tuna_dev_review`, 길면 spec 문서를 쓴 뒤 `tuna_dev_review_from_spec`.
3. 백엔드가 **generate → review → fix** 루프를 반복합니다. 이 위임에는 종료 조건이 있습니다(review pass 또는 max iter). 모든 호출은 SQLite에 기록되고 한국어 형태소로 색인됩니다.
4. 검색의 진짜 가치는, **mid-size 로컬 LLM의 컨텍스트 한계를 Architect가 보완**하는 데 있습니다(Opus + Sonnet subagent 패턴과 동일). Phase 7-2의 합성 시드 기반 측정에서 context boost +0.58 ~ +0.64가 관측됐습니다. 다만 이는 실사용 확정 수치가 아니며, organic dogfooding metric은 별도 수집 중입니다.
5. Architect가 결과를 검증한 뒤 사용자에게 반환합니다.

더 자세히: [워크플로우](docs/workflow.md) · [내부 구조](docs/internals.md)

---

## 5분 설치

> **에이전트에게 한 줄로 위임하기:** Claude Code / Codex CLI 세션에서
> `https://github.com/hang-in/tunaLlama 의 INSTALL.md 따라 설치해줘`
> 라고 입력하면, 에이전트가 [INSTALL.md](INSTALL.md)를 읽고 의존성 / `.env` / 플러그인 등록 / 검증까지 단계별로 실행합니다. 5분 안에 사용 가능합니다.

수동 설치는 아래 순서입니다.

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

### 2. 환경변수 (Ollama Cloud를 쓸 경우만)

```bash
cp .env.example .env
echo "OLLAMA_CLOUD_API_KEY=발급받은_키" >> .env
```

### 3. init / doctor

```bash
tunallama init                 # 대화식 - provider/모델 자동 발견
tunallama doctor               # Python / config / provider / DB / Kiwi 검사
```

`doctor`를 통과하지 못하면 [Troubleshooting](#troubleshooting--faq)을 참조하세요.

### 4-A. Claude Code 사용자

플러그인으로 설치:

```bash
claude plugin marketplace add /path/to/tunaLlama
claude plugin install tunaLlama@tunallama-local
```

또는 `~/.claude/settings.json`의 `mcpServers`에 직접 등록:

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

Codex CLI는 `.claude-plugin/marketplace.json`을 직접 읽습니다(4개 인식 위치 중 하나로 명시 지원).

```bash
codex plugin marketplace add /path/to/tunaLlama
codex plugin install tunaLlama@tunallama-local
```

호환 상세: [docs/specs/phase8_codex.md](docs/specs/phase8_codex.md)

---

## 첫 호출 해보기

설치 후 Claude Code / Codex 세션에서 실행합니다. Architect가 자동으로 호출할 수도 있지만, 첫 사용과 재현 가능한 워크플로우에서는 **명시 호출을 권장**합니다.

### 코드 생성 위임 (권장 흐름)

```
사용자: "json 파싱하는 함수 작성해줘.
        먼저 tuna_load_memory 로 프로젝트 컨벤션 확인하고
        tuna_dev_review 로 위임해줘."

Architect:
1. tuna_load_memory()                       ← 프로젝트 컨벤션 fetch
2. tuna_recall(query="json parsing")         ← 과거 비슷 작업 surface (옵션)
3. tuna_dev_review(requirements="...", language="python")
   → 로컬 LLM 이 generate → review → fix 루프 수행
4. Architect 가 결과 검증 후 사용자에게 반환
```

### 큰 작업 (spec 기반)

```
docs/specs/foo.md 에 작업 spec 을 먼저 작성한 뒤:

사용자: "tuna_dev_review_from_spec 으로 docs/specs/foo.md 진행해줘"

→ 백엔드가 bounded generate → review → fix 루프 수행
→ 최종 코드 + iteration 로그 반환
```

### 메모리 검색

```
사용자: "tuna_recall 로 이 프로젝트의 BGE-M3 임베딩 사용 검색해줘"

→ 과거 5 개 호출 결과 surface
```

전체 도구 13개 목록: [docs/internals.md](docs/internals.md#mcp-tools)

---

## 한계

**v0.5.x usable dogfooding release입니다.** Claude Code + Codex CLI 양쪽에서 MCP tool 호출은 검증했지만, organic dogfooding(실제 일상 사용) 측정 자산은 아직 수집 중입니다. 아래는 카테고리별 정리입니다.

### 1. 사용 한도 / 비용

- **한도 절약은 아직 체감 데이터 수준입니다.** Anthropic / OpenAI 정액제 한도 계산식이 비공개라 정량 측정이 불가능합니다.
- **MCP 도구의 system prompt 비용은 의도된 trade-off입니다.** 13개 도구의 description + schema가 매 대화의 system prompt에 prepend되며, 추정치는 약 1.6k tokens입니다. 이는 실수로 생긴 context bloat가 아니라, Architect가 적절한 위임 도구를 고르기 위한 affordance 비용입니다. tunaLlama는 이 비용을 없애기보다 도구 수와 description 품질을 관리해 호출 적중률과 검증 품질을 유지하는 쪽을 택합니다. 측정: [phase7-mcp-audit.md](docs/measurements/phase7-mcp-audit.md)

### 2. 측정

- **검색 측정값(R@5, P@1 등)은 합성 시드 기반입니다.** 실사용자 워크플로우 검증은 별개 과제입니다. 측정: [docs/measurements/](docs/measurements/)
- **organic dogfooding metric을 수집 중입니다** (v0.5.7+). 매 위임 후 4종(`standalone_toy_rate` / `convention_adherence_rate` / `ast_excess_score` / `syntactically_valid`)이 `~/.tunallama/metrics.db`에 적재됩니다. `tunallama metrics show`로 조회하고, `TUNA_ORGANIC_METRICS=0`으로 비활성화합니다. 누적 baseline과 외부 사용자 재현성은 아직 측정 진행 중입니다.
- **테스트 커버리지 90%.** CI가 통과시키는 unit/plugin 507 tests + integration/search_quality 마커 27 tests = 총 534 collected. 미커버 10%의 대부분은 외부 서비스 의존 경로입니다(`llm/ollama.py` 62% / `llm/lmstudio.py` 58%, `pytest -m integration` 실행 시 추가 커버). `token_count.py` 34%는 Phase 5-4 보류 모듈로, Anthropic API 미보유라 unit test가 없습니다.

### 3. MCP / 클라이언트 호환성

- **Architect 호출에 의존합니다.** `tuna_*` 도구는 Architect가 작업 컨텍스트를 보고 호출하는 구조라, 도구 description 품질이 호출 적중률을 결정합니다. 첫 사용과 재현 가능한 워크플로우에서는 **명시 호출을 권장**합니다.
- **Subagent 자동 인식이 작동하지 않습니다** (Codex 0.128.0 실측). `plugin/agents/tuna-developer.toml`이 캐시되지만, Codex의 `spawn_agent` 가능 type에 `tuna-developer`가 등록되지 않습니다(default / explorer / worker만 지원). Claude Code 측은 미실측입니다. 단, MCP tools 13개는 양쪽 모두 정상 작동하므로 위임 자체는 도구 레벨에서 가능합니다.
- **MCP resource auto-attach + SessionStart hook이 작동하지 않습니다** (Codex). `tunallama://memory/state` resource는 양 클라이언트 모두 세션 시작 시 attach되지 않습니다. v0.5.2의 SessionStart hook(`plugin/hooks/session_start.py`)은 Claude Code v0.5.5+에서만 작동하고 Codex는 미인식입니다. **권장 운영**: Claude Code는 hook으로 state.md를 auto-prepend, Codex는 사용자가 `tuna_load_memory`를 명시 호출.

### 4. 로컬 LLM / provider

- **로컬 LLM에 의존합니다.** Ollama / LM Studio / Ollama Cloud 중 하나가 없으면 작동하지 않습니다.

### 5. 검색 / 메모리 품질

- **한국어 형태소 분석은 Kiwi에 의존합니다.** Kiwi가 처리하지 못하는 도메인 단어(신조어, 전문용어)는 검색 품질에 영향을 줄 수 있습니다.

### 6. state.md auto-extract

- **false positive 위험이 있습니다.** v0.5.1에서 코드 블록 안 텍스트 skip + meaningful 토큰 검증으로 완화했지만, 100% 제거는 어렵습니다. 의심 entry를 발견하면 `tunallama state clean`(auto entry 삭제) 또는 직접 편집(`tunallama state path`로 경로 확인)하세요.

### 양 환경 동작 매트릭스

v0.5.6 실측 기준 (Claude Code 2.1.138 + Codex CLI 0.128.0):

| 항목 | Claude Code | Codex CLI |
| --- | :---: | :---: |
| MCP tools 13개 (도구 호출) | ✓ | ✓ |
| DB 공유 (`~/.tunallama/memory.db`) | ✓ | ✓ |
| state.md 공유 | ✓ | ✓ |
| `tuna_load_memory` / `tuna_recall` 명시 호출 | ✓ | ✓ |
| Agents auto-discovery (`tuna-developer`) | **✓** | ✗ |
| Skills auto-load (`delegate-to-ollama`) | **✓** | ? |
| Hooks 등록 (`SessionStart` / `PreToolUse`) | **✓** | ? |
| SessionStart hook 실행 + state.md auto-prepend | **✓** | ✗ |
| MCP resource auto-attach (`tunallama://memory/state`) | ✗ | ✗ |

> state.md 경로: `~/.tunallama/projects/<hash>/state.md`

### 권장 운영 모델

**Claude Code (v0.5.5+):**
state.md auto-prepend가 SessionStart hook으로 작동합니다. Architect가 첫 turn부터 conventions / decisions / constraints / anti-patterns를 자동 인지합니다. 별도 명시 호출이 필요 없습니다. 단, state.md를 의도적으로 수정한 뒤 효과를 빨리 보고 싶으면 새 세션을 시작하세요.

**Codex CLI (0.128.0):**
SessionStart hook을 인식하지 못합니다. Architect가 첫 turn에 `tuna_load_memory`를 명시 호출하거나 docs를 직접 fetch해야 합니다. DB 공유 / state.md 공유 / MCP tools 호출은 모두 작동합니다.

---

## 왜 프롬프트 시드가 아닌가

tunaLlama는 에이전트에게 더 많은 문서를 읽혀서 컨텍스트 한계를 해결하려 하지 않습니다. 대신 작업 단위를 작게 잘라 MCP 도구로 로컬/저비용 LLM에 넘기고, 상위 Architect 모델은 짧은 spec, review 결과, 최종 diff 판단에만 집중하게 합니다.

문서 기반 운영 규칙은 시간이 지나면 stale state, drift, lost-in-the-middle 문제를 만들 수 있습니다. tunaLlama는 이를 피하기 위해 위임 호출을 SQLite에 기록하고, 필요할 때 검색·리콜하는 실행 계층을 둡니다.

## 무엇이 아닌가

- tunaFlow의 멀티 에이전트 라운드테이블이 **아닙니다**.
- OllamaClaude 포크가 **아닙니다** (패턴만 참고).
- 단일 모델 데모 / 연구 노트북이 **아닙니다**.
- 자동 weakness 감지 / 동적 tool 작성이 **아닙니다** (Architect 판단으로 `tuna_log_limitation` 호출).

---

## 측정 자료

검색 알고리즘 / context boost / MCP audit 측정 결과입니다.

- [전체 인덱스](docs/measurements/)
- [methodology.md](docs/measurements/methodology.md) - 시드 / LOPO / metric 정의 / 한계
- [phase4-search.md](docs/measurements/phase4-search.md) - 검색 품질
- [phase5-hyde-kure.md](docs/measurements/phase5-hyde-kure.md) - HyDE / KURE / Adaptive (524 record)
- [phase5e-corpus-scaling.md](docs/measurements/phase5e-corpus-scaling.md) - rerank pool sweep + 984 record LOPO (rerank P@1 0.77 / R@5 0.59, cloud 0)
- [phase7-mcp-audit.md](docs/measurements/phase7-mcp-audit.md) - MCP 도구 system prompt size
- [phase7-context-boost.md](docs/measurements/phase7-context-boost.md) - mid-size LLM context boost +0.58~+0.64 (3 모델 검증)

모두 합성 시드 기반이므로, 실사용 데이터 검증은 별개 과제입니다.

---

## Troubleshooting / FAQ

### `tunallama doctor` 실패

**Python 버전:** 3.11+ 필요. `python --version`으로 확인.

**provider 미감지:** Ollama / LM Studio가 실행 중인지 확인.

```bash
curl http://localhost:11434/api/tags  # Ollama
curl http://localhost:1234/v1/models  # LM Studio
```

**Ollama Cloud 키 미감지:** `.env` 파일이 cwd에 있는지, `OLLAMA_CLOUD_API_KEY=...` 행이 첫 줄에 있는지 확인.

**Kiwi 형태소 분석기 실패:** `pip install kiwipiepy`로 재설치. macOS는 Xcode CLI tools 필요(`xcode-select --install`).

### MCP 도구가 안 보이거나 새 세션에서 server fail

**증상:** `/plugin` 화면에서 `tunaLlama MCP Server  Status: ✘ failed`. 또는 도구 목록에 `tuna_*`가 안 보임.

**원인 1 - venv 의존성 미해결** (v0.5.8 이하): plugin의 `.mcp.json`이 `command: "python"`으로 system python을 spawn합니다. mise / pyenv / direnv 같은 shell hook은 Claude Code의 child process에서 활성화되지 않아, venv의 fastmcp / anthropic SDK 등 deps를 못 잡고 ImportError가 납니다. **v0.5.9+부터 wrapper script(`plugin/bin/tunallama-mcp`)가 `.venv/bin/python`으로 자동 fallback**하므로 업데이트를 권장합니다.

**원인 2 - `.mcp.json` cwd가 잘못됨:** `claude plugin install`한 위치를 확인. 직접 등록한 경우 `cwd`가 tunaLlama 레포 절대경로인지 확인.

**원인 3 - Python venv 부재:** `.venv/bin/python` 자체가 없으면 wrapper도 system python으로 fallback해서 deps 부재로 실패합니다. `mise run install` 또는 `uv venv && uv pip install -e .`로 .venv를 생성하세요.

### `tuna_*` 도구가 호출되지 않음

**Architect가 자동 호출하지 않음:** `SKILL.md` 또는 `tunallama://memory/state` resource가 attach 안 됐을 수 있습니다. `tuna_load_memory` 명시 호출을 시도하세요.

**도구 description 품질:** task가 너무 추상적이면 Architect가 도구를 선택하지 못합니다. "`tuna_dev_review` 사용해서 작성해줘"처럼 명시적으로 지시하세요.

### LLM 호출 timeout

**기본 timeout은 600초** (`tunallama_core/config/models.py`). cloud LLM 응답 지연 시 retry 3회. 그래도 실패하면 logger.warning으로 기록되므로 dev 환경에서 stderr를 확인하세요.

**자주 timeout이 발생하면:** 로컬 LLM으로 swap하거나 모델 크기를 줄이세요(qwen3-coder-next 등 latency 최적화 모델).

### 검색 품질이 낮게 느껴짐

**현재 측정** (cloud 0 path, 984 record LOPO / 792 query): rerank P@1 0.77 / R@5 0.59 / σR@5 0.31. HyDE+KURE path (24 leader sample, cloud 1): P@1 0.92 / σR@5 0.14. 자세히: [phase5e-corpus-scaling.md](docs/measurements/phase5e-corpus-scaling.md)

**R@5 < 0.8의 의미:** 자동 prepend(`auto_recall=always`) 시 noise가 섞일 수 있습니다. 단 Phase 4-4 + 5-3 측정에서 cloud LLM이 무관 prefix를 자동 무시하는 것이 확인됐고, 실제 코드 품질 영향은 작습니다.

**기본값 `on_request` 유지를 권장합니다.** `auto_recall=always`는 위 risk를 인지하고 쓰세요.

### state.md에 의도치 않은 entry가 생김

**원인:** LLM 출력의 코드 블록 / 주석 / 일반 단어가 false positive로 auto-extract됩니다(v0.5.1부터 코드 블록 안 텍스트 + meaningful 토큰 검증 필터 추가, 단 100%는 아님).

**CLI 명령** (v0.5.1+):

```bash
tunallama state show    # 내용 출력
tunallama state path    # 파일 경로 출력
tunallama state clean   # (auto) 태그 entry 삭제, manual/verified 보존
```

- **파일 위치:** `~/.tunallama/projects/<hash>/state.md` (직접 편집 가능)
- **`(manual)` / `(verified)` 태그:** 사용자 수정은 다음 update 시 보존됩니다.
- **자동 추출 비활성화:** `.env` 또는 환경변수에 `TUNA_AUTO_EXTRACT_STATE=0`.

---

## 기여자

```bash
mise install                    # python 3.11 + uv
mise trust                      # mise.toml 신뢰 (보안)
mise run install                # editable + dev 의존성
mise run test                   # pytest (unit + plugin only)

# 측정 통합 테스트 (BGE-M3 다운로드 + cloud LLM 호출):
.venv/bin/pytest -m search_quality -s
```

자세한 기여 가이드: [CONTRIBUTING.md](CONTRIBUTING.md)

## 디렉토리 / 문서

- [docs/workflow.md](docs/workflow.md) - Architect ↔ Developer 워크플로우 가이드
- [docs/internals.md](docs/internals.md) - 내부 구조 (메모리, 검색, Provider, Hook)
- [docs/measurements/](docs/measurements/) - 측정 자료
- [docs/specs/](docs/specs/) - Phase별 spec 문서
- [docs/dogfooding-log.md](docs/dogfooding-log.md) - 라운드별 dogfooding 결과
- [docs/release-notes/](docs/release-notes/) - 릴리즈 노트
  ([v0.5.9](docs/release-notes/v0.5.9.md) · [v0.5.8](docs/release-notes/v0.5.8.md) ·
  [v0.5.7](docs/release-notes/v0.5.7.md) · [v0.5.6](docs/release-notes/v0.5.6.md) ·
  [v0.5.5](docs/release-notes/v0.5.5.md) · [v0.5.4](docs/release-notes/v0.5.4.md) ·
  [v0.5.3](docs/release-notes/v0.5.3.md) · [v0.5.2](docs/release-notes/v0.5.2.md) ·
  [v0.5.1](docs/release-notes/v0.5.1.md) · [v0.5.0](docs/release-notes/v0.5.0.md) ·
  [v0.4.0](docs/release-notes/v0.4.0.md) · [v0.3.0](docs/release-notes/v0.3.0.md))
- [CHANGELOG.md](CHANGELOG.md) - 변경 이력
- [CONTRIBUTING.md](CONTRIBUTING.md) - 기여 가이드
- [config.example.toml](config.example.toml) - config 필드 + 주석
- [.env.example](.env.example) - 환경변수 예시

## 라이선스 / 기여

MIT. 이슈/PR 환영합니다. 한국어/영어 모두 가능합니다. 영문 README는 [README.en.md](README.en.md)와 함께 동기화 유지해 주세요.

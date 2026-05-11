# tunaLlama 설치 가이드

이 문서는 **터미널 에이전트 (Claude Code / Codex CLI) 가 직접 읽고 단계별로
설치 수행** 할 수 있게 작성되었습니다.

## 사용자 사용법

터미널에서 Claude Code 또는 Codex CLI 실행 후 다음 한 줄 입력:

```
https://github.com/hang-in/tunaLlama 의 INSTALL.md 따라 설치해줘
```

에이전트가 이 문서를 fetch / 읽고 아래 단계 자동 실행.

---

## 에이전트용 instructions

### 사전 확인

먼저 환경 정보 수집:

```bash
# Python 3.11+ 있는지
python3 --version

# uv 또는 pip 있는지 (uv 권장)
which uv || which pip

# 클라이언트 종류 확인 (Claude Code or Codex CLI)
which claude && claude --version
which codex && codex --version

# 사용자에게 어느 LLM provider 쓸지 물어볼 것:
# - Ollama 로컬 (http://localhost:11434)
# - LM Studio 로컬 (http://localhost:1234)
# - Ollama Cloud (https://ollama.com - API key 필요)
```

### 1. 레포 clone + 의존성 설치

```bash
# 1-1. 클론
git clone https://github.com/hang-in/tunaLlama
cd tunaLlama

# 1-2. Python 의존성 설치 (uv 권장)
# 사용자가 mise 있으면:
mise install            # python 3.11 + uv 자동
mise trust              # mise.toml 신뢰 (1회만)
mise run install        # editable + dev 의존성

# 또는 uv 직접:
uv venv
uv pip install -e .

# 또는 pip:
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 2. 환경변수 설정

`.env.example` 복사 후 사용자가 쓸 provider 의 키만 채움:

```bash
cp .env.example .env

# Ollama Cloud 쓸 경우 - 사용자에게 OLLAMA_CLOUD_API_KEY 요청
# (https://ollama.com 에서 발급)
echo "OLLAMA_CLOUD_API_KEY=발급받은_키" >> .env
```

사용자가 키 모르면 발급 url 안내. 로컬 Ollama / LM Studio 만 쓸 거면 키
필요 X.

### 3. 자체 진단

```bash
# 권장 - mise 활성 venv
.venv/bin/tunallama init     # 대화식. 사용자가 provider/model 선택.
.venv/bin/tunallama doctor   # Python / config / provider / DB / Kiwi 검사
```

`doctor` 가 모두 OK 면 다음 단계. FAIL 항목 있으면 사용자에게 보여주고
[README.md Troubleshooting](README.md#troubleshooting--faq) 참조 안내.

### 4-A. Claude Code 사용자

플러그인 + skill + subagent + hook + MCP server 를 한 묶음 등록:

```bash
# 절대경로 알아내기
PLUGIN_ROOT="$(pwd)"  # 이 시점 cwd = tunaLlama 레포 root

claude plugin marketplace add "$PLUGIN_ROOT"
claude plugin install tunaLlama@tunallama-local
```

설치 후 **Claude Code 재시작** 또는 `/plugin reload` 명령으로 도구 활성화.

### 4-B. Codex CLI 사용자

Codex CLI 0.128.0 기준 - marketplace 와 MCP 가 **별도 메커니즘**. 두 단계 모두 필요.

```bash
PLUGIN_ROOT="$(pwd)"

# 4-B-1. Marketplace 등록 (subagent / skill 카탈로그)
codex plugin marketplace add "$PLUGIN_ROOT"

# 4-B-2. MCP server 등록 (도구 노출 - 별도 명령)
codex mcp add tunallama -- "$PLUGIN_ROOT/.venv/bin/python" -m plugin.mcp_server
```

등록 확인:

```bash
codex mcp list  # tunallama 가 status=enabled 로 보여야
```

**Codex 세션 재시작** - 다음 `codex` 실행부터 도구 활성.

### 5. 첫 호출 검증

설치 후 새 Claude/Codex 세션에서:

```
사용자: tuna_load_memory 호출해서 state.md 보여줘
```

에이전트가 `tuna_load_memory()` 호출 → state.md 내용 (또는 "기록된 state
없음" 메시지) 반환되면 정상.

추가 검증:

```
사용자: tuna_recall("test") 시도해줘
사용자: tuna_generate_code 로 "두 정수 더하기 함수" 만들어줘
```

---

## 트러블슈팅 (에이전트 처리)

### `tunallama doctor` 가 provider 못 찾음

- Ollama 미실행: `ollama serve` 백그라운드 실행 안내
- LM Studio 미실행: 사용자한테 LM Studio 앱 실행 + Local Server 켜기 안내
- Ollama Cloud key 미설정: `.env` 의 `OLLAMA_CLOUD_API_KEY` 행 확인

### `codex mcp list` 에 tunallama 가 안 보임

- `~/.codex/config.toml` 직접 열어 `[mcp_servers.tunallama]` 섹션 확인
- 없으면 `codex mcp add` 재시도. 절대 경로 확인.

### Claude `/plugin reload` 후 도구 안 보임

- `~/.claude/settings.json` 의 `mcpServers` 확인
- `plugin/.mcp.json` 의 cwd 가 사용자 환경 기준인지 확인 (
  `${CLAUDE_PLUGIN_ROOT}/..` 가 정상)

### `mise install` 실패

- mise 미설치: `curl https://mise.run | sh`
- 또는 mise 건너뛰고 직접 `python3 -m venv .venv && source .venv/bin/activate && pip install -e .`

### `kiwipiepy` 설치 실패 (macOS)

- Xcode CLI tools 필요: `xcode-select --install`

---

## 에이전트 작업 완료 후 사용자에게 보여줄 요약

설치 끝나면 다음 메시지 사용자에게:

```
설치 완료. 다음 3 가지로 시작 가능:

1. tuna_load_memory()    - 프로젝트 state.md
2. tuna_recall("...")    - 과거 작업 검색
3. tuna_generate_code() / tuna_dev_review_from_spec(...)  - 코드 생성

README.md 의 "첫 호출 해보기" 섹션에 예시 더 있음.
한계 / FAQ: README.md 의 "한계" / "Troubleshooting" 섹션.
```

설치 실패 시 정직 보고. 실패 단계 + 에러 메시지 + 어떤 부분 우회 가능한지.

---

## 추가 정보

- 본 가이드 끝까지 따라 했을 때 평균 설치 시간: **5분** (네트워크 + 환경
  영향).
- 모든 단계는 idempotent - 다시 실행해도 안전.
- 에이전트가 모르는 prompt 만나면 사용자한테 명시 질문 후 진행.

### 검증된 환경 (2026-05-11)

- **Codex CLI 0.128.0**: `codex plugin marketplace add` + `codex mcp add`
  → 13 도구 list / `tuna_load_memory` / `tuna_recall` / `tuna_generate_code`
  모두 정상 작동 확인.
- env 전달: shell 에 export 된 `OLLAMA_CLOUD_API_KEY` 가 Codex 가 spawn
  한 MCP server 에 자동 상속 (또는 `plugin/_state.py` 가 `.env` 자동 로드).
  사용자 환경에 따라 다르므로 작동 안 하면 `codex mcp remove tunallama` +
  `codex mcp add tunallama --env OLLAMA_CLOUD_API_KEY=...` 재등록.
- Claude Code: marketplace + plugin install 한 묶음으로 작동.

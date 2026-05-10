# tunaLlama

> 무거운 코드 생성은 로컬 LLM에 맡기고, Claude Code는 분해와 검증에만 집중하게 만드는 백엔드 + 플러그인.

**상태**: Phase 1 구현 중 (alpha, 미공개)
**라이선스**: MIT
**English**: see [README.en.md](README.en.md)

---

## 무엇인가

tunaLlama는 Claude Code 사용자가 토큰을 아낄 수 있도록 작업을 모델별로 쪼갠다.

| 역할 | 모델 | 이유 |
|---|---|---|
| Architect | Claude Code (유료) | 요청을 분해. 입출력 짧음. |
| Developer | 로컬 LLM (무료/저비용) | 코드 생성. 출력이 길어도 내 GPU에서 돌림. |
| Reviewer | Claude Code (유료, 같은 세션) | 결과 검증. 입출력 짧음. |

토큰 헤비 단계(생성)만 로컬로 빠지고, 똑똑한 단계(분해 + 검증)는 짧은 컨텍스트로 유료 모델에 남는다. `OllamaClaude` (Jadael/OllamaClaude)와 동일한 아키텍처 패턴이지만 처음부터 Python으로 다시 짰다. 코드 복사 없음, 패턴 참고만.

추가 차별점:
- **SQLite + FTS5 장기 메모리** — 모든 delegation 호출을 기록, 다음 세션에서 검색 가능.
- **한국어 형태소 토크나이저** — Kiwi 기반 write-time tokenization으로 FTS5 한국어 리콜 정확도 확보.
- **파일 인지형 도구** — `review_file`, `explain_file`, `analyze_files` 는 파일 경로만 받고 Claude 컨텍스트에 내용을 넣지 않는다.

## 무엇이 아닌가

- tunaFlow 의존 아님. 멀티 에이전트 라운드테이블 아님.
- OllamaClaude 포크 아님.
- 단일 모델 데모 아님. 연구 노트북 아님.

## 지원하는 로컬 LLM

- **Ollama (로컬)** — `qwen2.5:32b` 등 27B 이상 권장.
- **Ollama Cloud** — API 키로 호스티드 모델 사용.
- **LM Studio** — OpenAI 호환 엔드포인트(`/v1/chat/completions`).

전환은 `config.toml` 의 `[llm] provider` 한 줄로.

## 빠른 시작

> 아직 미공개. Phase 1 완료 시 동작 보장.

### 사용자 (실행만 할 사람) — 5분 가이드

```bash
# 1. 받기 + 설치
git clone https://github.com/hang-in/tunaLlama
cd tunaLlama
pip install -e .                      # 또는 `uv pip install -e .`

# 2. 대화식 설정 — provider 선택, 모델 자동 발견, 메모리 옵션
tunallama init                        # 기본: ./.tunallama/config.toml
# tunallama init --global             # ~/.tunallama/config.toml 에 저장하려면

# 3. 환경 점검 — Python / config / provider / DB / Kiwi 검사
tunallama doctor

# 4. (Ollama Cloud 쓰는 경우) .env 에 키 추가
echo "OLLAMA_CLOUD_API_KEY=발급받은_키" >> .env

# 5. Claude Code 에 플러그인 연결
claude --plugin-dir ./plugin
```

`tunallama init` 이 자동으로 해주는 것:
- 로컬 Ollama 데몬 / LM Studio 가 켜져있으면 설치된 모델을 자동 발견 → 번호로 선택
- 키가 필요한 provider 면 환경변수 안내
- ~/.tunallama 또는 ./.tunallama 디렉토리 자동 생성

### 기여자 (개발 환경)
mise 가 Python 버전 + uv + `.venv` 를 자동 관리한다.

```bash
git clone https://github.com/hang-in/tunaLlama
cd tunaLlama                  # 진입 시 .venv 자동 생성/활성화
mise install                  # python 3.11 + uv 설치
mise run install              # editable + dev 의존성
mise run test                 # pytest
```

mise 미설치 환경이면 [mise 공식 가이드](https://mise.jdx.dev/getting-started.html) 참고.

## 디렉토리 구조

```
tunallama_core/                  # 백엔드 (재사용 가능, MCP 미인지)
  config/                        # TOML 로드 + 검증 + frozen dataclass
  llm/                           # provider 추상화 (ollama / lmstudio / factory)
  memory/                        # SQLite + FTS5 + Kiwi 형태소
  delegation/                    # 10 도구 + 공통 runner + 프롬프트
  routing.py                     # auto_recall 정책
  errors.py                      # 도메인 예외
plugin/                          # Claude Code 플러그인 (백엔드 소비)
  .claude-plugin/plugin.json
  .mcp.json
  mcp_server.py                  # FastMCP 서버 (11 tuna_* 도구)
  _state.py / _format.py
  skills/delegate-to-ollama/SKILL.md
  agents/tuna-developer.md
tests/
  core/                          # backend 단위 + 통합 테스트
  plugin/                        # plugin 도구/매니페스트 테스트
```

`tunallama_core` 는 `plugin` 을 절대 import 하지 않는다. Phase 4의 Codex 프론트엔드를 위한 경계.

## 상태 (Phase 1)

- 11 MCP 도구 노출: `tuna_generate_code`, `tuna_review_file`, `tuna_recall` 등.
- 모든 호출 SQLite 기록, 한국어 형태소 검색 가능.
- 177 테스트, 99% 커버리지.
- 통합 테스트는 실 Ollama Cloud / LM Studio 에 붙음 (미가용 시 자동 skip).

## 개발 상태

`docs/handoff-tunallama-phase1.md` 가 단일 진실 원천. 핸드오프 대비 변경된 결정은 `CHANGELOG.md` 에 기록.

## 기여 / 라이선스

MIT. 이슈/PR 환영. 한국어/영어 모두 가능.

---

이 문서는 한국 개발자 커뮤니티(damoang.net 등)와 글로벌 Claude Code 사용자를 동시에 겨냥한다. 영문판은 [README.en.md](README.en.md).

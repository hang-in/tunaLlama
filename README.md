# tunaLlama

Claude Code 쓰면서 토큰 빨리 닳는 사용자를 위한 위임 도구입니다.

무거운 코드 생성을 로컬 Ollama / LM Studio / Ollama Cloud 에 위임하고,
분해 / 검증만 Claude 가 같은 세션 안에서 수행합니다. Claude Code MCP
플러그인으로 작동합니다.

**상태**: alpha, Phase 5 완료 (v0.3.0), Phase 6 진행 예정.
**라이선스**: MIT. **English**: [README.en.md](README.en.md).

---

## 누가 쓰면 도움 될 가능성

- Claude Code Pro/Max 정액제 사용자 (한도 관리 동기)
- Ollama 로컬 / Ollama Cloud / LM Studio 환경 있는 사용자
- 한국어 작업 다루는 사용자 (Kiwi 형태소 토크나이저 통합)

다만 위 시나리오의 실제 가치는 본인 dogfooding 으로 확인을 추천합니다.
사용 한도 절약은 체감 데이터로만 확인 가능 (Anthropic 한도 계산식 비공개).

### 기술적 요구사항

- Python 3.11+
- Ollama / LM Studio / Ollama Cloud 중 하나
- Claude Code (MCP 플러그인 지원 버전)

## 어떻게 작동하는가

| 역할 | 모델 | 책임 |
|---|---|---|
| Architect | Claude Code (정액제) | 분해 / 사양 / 검증 / 통합 |
| Developer | 로컬 LLM (Ollama / Cloud / LM Studio) | 코드 생성 / 자체 리뷰 / 자체 수정 |
| Reviewer | Claude Code (같은 세션) | 최종 판정 |

전형적인 호출 흐름:

1. 사용자가 작업 요청 (한국어 / 영어).
2. Claude (아키텍트) 가 작업 분해 - 짧으면 `tuna_dev_review`, 길면 spec
   문서 작성 후 `tuna_dev_review_from_spec`.
3. 백엔드가 generate → review → fix 루프 자동 반복. 모든 호출은 SQLite
   에 기록되고 한국어 형태소로 색인됩니다.
4. Claude 가 결과 검증 후 사용자에게 반환.

자세한 워크플로우는 [docs/workflow.md](docs/workflow.md).
내부 구조 (메모리 / 검색 / Provider 추상화 / Hook) 는
[docs/internals.md](docs/internals.md).

## 5 분 설치

```bash
git clone https://github.com/hang-in/tunaLlama
cd tunaLlama

pip install -e .                # 또는 `uv pip install -e .`

tunallama init                  # 대화식 - provider/모델 자동 발견
tunallama doctor                # Python / config / provider / DB / Kiwi 검사

# Ollama Cloud 쓸 경우
echo "OLLAMA_CLOUD_API_KEY=발급받은_키" >> .env

# 영구 등록 - ~/.claude/settings.json 의 mcpServers 에:
# {
#   "mcpServers": {
#     "tunallama": {
#       "command": "/Users/me/tunaLlama/.venv/bin/python",
#       "args": ["-m", "plugin.mcp_server"],
#       "cwd": "/Users/me/tunaLlama"
#     }
#   }
# }
```

`cwd` 가 프로젝트 루트라면 plugin 이 시작 시 `.env` 와
`./.tunallama/config.toml` 을 자동 발견합니다.

### 기여자

```bash
mise install                    # python 3.11 + uv
mise trust                      # mise.toml 신뢰 (보안)
mise run install                # editable + dev 의존성
mise run test                   # pytest
```

## 한계

- **alpha 단계**. 프로덕션 사용은 신중하게.
- **사용 한도 절약은 체감 데이터**. Anthropic 정액제 한도 계산식이 비공개라
  정량 측정 불가능. 본인 dogfooding 으로 체감 확인 추천.
- **검색 측정값 (R@5, P@1 등) 은 합성 시드 기반**. 실 사용자 워크플로우
  검증은 별개 자리. 자세한 측정 자료는
  [docs/measurements/](docs/measurements/).
- **MCP 자동 호출 의존**. 사용자가 `tuna_*` 도구를 명시 호출할 일은 거의
  없고, Claude 가 작업 컨텍스트 보고 자동 판단해서 호출하는 구조. 도구
  설명 (description) 품질이 자동 호출 적절성을 결정.
- **로컬 LLM 의존**. Ollama 등 환경 없으면 작동 X.
- **한국어 형태소 분석 = Kiwi 의존**. Kiwi 가 못 처리하는 도메인 단어
  (신조어, 전문용어) 검색 품질 영향 가능.
- **organic dogfooding 측정 부재**. Round 16 이후 실 Claude Code 일상
  사용 측정 X (Phase 6 부터 재개 예정).

## 무엇이 아닌가

- tunaFlow 의 멀티 에이전트 라운드테이블 아님.
- OllamaClaude 포크 아님 (패턴 참고).
- Codex CLI 통합 아님 (별도 핸드오프).
- 단일 모델 데모 / 연구 노트북 아님.
- 자동 weakness 감지 / 동적 tool 작성 아님 - 아키텍트 판단으로
  `tuna_log_limitation` 호출.

## 측정 자료

검색 알고리즘 측정 결과 (R@5, P@1, σ, path 별 비교 등) 는
[docs/measurements/](docs/measurements/) 에 있습니다. 합성 시드 기반이라
실 사용 데이터 검증은 별개 자리입니다.

## 디렉토리 / 문서

- [docs/workflow.md](docs/workflow.md) - Architect ↔ Developer 워크플로우 가이드.
- [docs/internals.md](docs/internals.md) - 내부 구조 (메모리, 검색, Provider,
  Hook).
- [docs/measurements/](docs/measurements/) - 측정 자료 (Phase 4-5 search /
  HyDE / KURE / Adaptive).
- [docs/specs/](docs/specs/) - Phase 별 spec 문서.
- [docs/dogfooding-log.md](docs/dogfooding-log.md) - 라운드별 dogfooding 결과.
- [docs/release-notes/](docs/release-notes/) - v0.3.0 등 릴리즈 노트.
- [CHANGELOG.md](CHANGELOG.md) - 변경 이력.
- [config.example.toml](config.example.toml) - config 필드 + 주석.
- [.env.example](.env.example) - 환경변수 예시.

## 라이선스 / 기여

MIT. 이슈/PR 환영. 한국어/영어 모두 가능. 영문 README 는
[README.en.md](README.en.md) 를 함께 동기화 유지.

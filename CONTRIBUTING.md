# 기여 가이드

tunaLlama 에 기여해주셔서 감사합니다. 한국어 / 영어 모두 환영합니다.

## 시작하기

```bash
git clone https://github.com/hang-in/tunaLlama
cd tunaLlama

# 권장: mise + uv
mise install                # python 3.11 + uv
mise trust                  # mise.toml 신뢰
mise run install            # editable + dev 의존성

# 또는 pip
pip install -e ".[dev]"

# 회귀 확인
.venv/bin/pytest --no-cov -q -m "not search_quality and not integration"
```

## 코드 정책

### 경계 / 책임

- `tunallama_core/` (backend) 는 `plugin/` (frontend) 을 import 하지 않음
  (단방향 의존).
- 모듈은 단일 책임. 새 검색 path 추가 시 `tunallama_core/memory/` 안 별 파일.
- 200줄 이상 파일 / 50줄 이상 함수는 검토 대상.

### 스타일

- ruff 검사 통과 필수 (`mise run lint` 또는 `.venv/bin/ruff check ...`).
- 한국어 / 영어 mix OK. 일관성 유지.
- ANSI em-dash (`—`) 대신 ASCII hyphen (`-`) 사용 (정책).
- 도구 description 은 명확 / 짧게 (Architect 의 도구 선택에 직결).

### 테스트

- 새 기능은 unit test 동반. 통합 테스트 (`@pytest.mark.integration` /
  `search_quality`) 는 외부 의존 명시 후 자동 skip.
- mock 남용 금지. 외부 SDK 의 스키마/타입 변경이 가려져 실서비스 회귀를
  놓치는 것을 막기 위함.
- coverage 합리적 유지. 현재 ~90%.

### Commit / PR

- commit 메시지는 한국어 / 영어 모두 가능.
- 큰 변경은 spec 문서 (`docs/specs/`) 동반 권장.
- 측정 / 데이터 기반 결정이면 결과 표 commit 메시지에 포함.

## dogfooding 정책

새 기능 작업 시 `tuna_general_task` 채널로 일부 위임 가능. 단:

- **bounded output 만** (시드 데이터, prompt variant, 알고리즘 초안).
- **integration coding 은 architect (Claude / Codex) 직접** - dogfooding round
  7-15 에서 검증된 standalone-toy 패턴 회피.
- 결과는 [docs/dogfooding-log.md](docs/dogfooding-log.md) 에 정직 기록.

## 측정 자산

- 새 검색 path / 메모리 layer 추가 시 측정 통합 테스트 동반.
- 결과는 `docs/measurements/phase<N>-<name>.md` 에 저장.
- **절대 threshold 미리 정하지 X**. trend over time + source tag (synthetic /
  spec_dogfooding / organic) 분리.

## 이슈 / 버그 리포트

이슈 템플릿 따라 작성:
- 환경 (OS / Python / Claude Code 또는 Codex CLI 버전)
- 재현 단계
- 기대 동작 vs 실제 동작
- `tunallama doctor` 출력 (가능 시)

## 라이선스

기여 시 [MIT](LICENSE) 조건에 동의한 것으로 간주.

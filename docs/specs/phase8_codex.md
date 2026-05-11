# Phase 8 - Codex CLI 호환 (한 레포 / 두 환경)

## 핵심 (조사 결과)

Codex CLI (`github.com/openai/codex`, Apache 2.0) 이 **이미 Claude
호환 plugin 시스템** 가짐:

- **marketplace 직접 호환**: 4개 인식 위치 중 하나로 `.claude-plugin/
  marketplace.json` 명시 지원
- **manifest 키 호환**: `mcpServers` / `skills` / `hooks` 동일
- **SKILL.md frontmatter** 포맷 동일
- **`.mcp.json` schema** 거의 동일 (`command`/`args`/`env`)

차이 (변환 필요한 자리):
- **Subagent**: Claude = markdown + frontmatter, Codex = TOML (`.toml`)
- **Hook**: stdin JSON 필드명 다를 수 있음. Codex hooks 는 experimental
  (`features.codex_hooks = true` 필요)

→ **한 레포로 두 환경 동시 작동 가능**. Subagent 만 양쪽 보존.

## 단계

### 8-1. Subagent TOML 변환

```
plugin/agents/tuna-developer.md   ← Claude (기존 보존)
plugin/agents/tuna-developer.toml ← Codex 추가 (신규)
```

TOML 형식:
```toml
name = "tuna-developer"
description = "..."
model = "gpt-5"  # 또는 사용자 설정
sandbox_mode = "workspace"
developer_instructions = """
You are tuna-developer. ...
"""

[[mcp_servers]]
name = "tunallama"
# (mcpServers 참조)
```

### 8-2. `.codex-plugin/plugin.json` (옵션)

Codex 가 Claude manifest 도 인식하는지 실측 후 결정. 만약 안 되면 복제:

```
plugin/.claude-plugin/plugin.json  ← Claude 기존
plugin/.codex-plugin/plugin.json   ← Codex 추가 (동일 내용 + 일부 codex 필드)
```

### 8-3. Hook input schema 호환화

`plugin/hooks/pre_tool_use.py` 의 stdin JSON 파싱을 양쪽 schema 자동 감지:

```python
data = json.load(sys.stdin)
tool_name = data.get("tool_name") or data.get("tool") or ""
# Claude: "tool_name", "tool_input"
# Codex: 정확한 필드명은 실측 후 확정 (current unknown)
```

### 8-4. README 설치 가이드 추가

기존 "5분 설치" 섹션 아래 새 subsection:

```markdown
### Codex CLI 사용자

```bash
codex plugin marketplace add hang-in/tunaLlama
codex plugin install tunaLlama@tunallama-local
```

`OLLAMA_CLOUD_API_KEY` 환경변수 동일하게 필요.
```

### 8-5. 실측 + 차이 보고

- 사용자 환경에서 `codex plugin install tunaLlama` 시도
- 13 도구 list_tools 작동 여부
- `tunallama://memory/state` MCP resource auto-attach 여부 (Codex 미확정)
- `tuna_load_memory` / `tuna_recall` / `tuna_generate_code` 호출 작동 여부
- Subagent (`tuna-developer`) 작동 여부
- 차이 측정 → README "한계" 섹션 명시

### 8-6. Phase 7-2 측정 재현 (옵션)

Codex 환경에서 context boost 측정. GPT-5 모델로 architect 역할 시 same
6 probe × 4 mode → Claude/Codex 비교.

## Out of scope

- Codex 의 단독 기능 (apps/connectors, slash command custom) 활용 - v0.6.0+
- Codex 측 PR (manifest alias 등) - 우선 우리 레포 호환만, 필요시 후속

## Acceptance

- `codex plugin install tunaLlama` 명령 1줄로 13 도구 등록 성공
- `tuna_load_memory` 호출 작동 (state.md 반환)
- `tuna_generate_code` 또는 `tuna_dev_review` 한 번 작동
- README 양 환경 안내
- 한계 정직 명시 (Codex 미문서화 영역 - subagent auto-load, MCP resource
  auto-attach 등)

## 정직 한계

- 8-5 실측은 사용자 환경 의존. architect 가 직접 검증 불가능.
- Codex 의 hook stdin schema 정확한 필드명 미확정 - 실측 결과 후 확정.
- Codex 가 Claude manifest (`.claude-plugin/plugin.json`) 도 인식하는지 미확정.
- MCP resource (`tunallama://memory/state`) Codex 자동 attach 미확정.

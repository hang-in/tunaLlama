# tunaLlama

[![CI](https://github.com/hang-in/tunaLlama/actions/workflows/ci.yml/badge.svg)](https://github.com/hang-in/tunaLlama/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Status: production](https://img.shields.io/badge/status-production-brightgreen.svg)](#)
[![Tests: 487 passing](https://img.shields.io/badge/tests-487%20passing-brightgreen.svg)](#)
[![Coverage: 90%](https://img.shields.io/badge/coverage-90%25-brightgreen.svg)](#)
[![Claude Code / Codex CLI](https://img.shields.io/badge/works%20with-Claude%20Code%20%2F%20Codex%20CLI-purple.svg)](#)

A delegation tool for Claude Code / Codex CLI users who burn tokens fast.

Heavy code generation is delegated to local Ollama / LM Studio /
Ollama Cloud; decomposition and verification stay with the architect
(Claude / Codex) in the same session. **One repo works for both Claude
Code and Codex CLI** - Codex CLI also reads
`.claude-plugin/marketplace.json`.

**Status**: **v0.5.0 production release** (2026-05-11). Verified on both Claude Code and Codex CLI.
**License**: [MIT](LICENSE). **Korean**: [README.md](README.md) (canonical).

---

## Who this might help

- Claude Code Pro/Max subscribers (quota management motive)
- Codex CLI users (OpenAI subscription / API quota management)
- Users with Ollama local / Ollama Cloud / LM Studio available
- Users working with Korean (Kiwi morphological tokenizer integrated)

That said, actual value is best confirmed by your own dogfooding.
Token-quota savings are anecdotal - Anthropic / OpenAI quota formulas
are not public, so quantitative measurement is not possible.

### Requirements

- Python 3.11+
- One of: Ollama / LM Studio / Ollama Cloud
- Claude Code (MCP plugin support) or Codex CLI

## How it works

| Role | Model | Responsibility |
|---|---|---|
| Architect | Claude / Codex (subscription) | Decomposition / spec / verification / integration |
| Developer | Local LLM (Ollama / Cloud / LM Studio) | Code generation / self-review / self-fix |
| Reviewer | Architect same session | Final judgment |

Typical call flow:

1. User asks for a task (Korean / English).
2. Architect decomposes - short task uses `tuna_dev_review`, longer
   ones go through a spec doc then `tuna_dev_review_from_spec`.
3. Backend runs generate → review → fix loop automatically. Every
   call lands in SQLite indexed by Korean morphemes.
4. **Real value of search**: architect fetches context that the
   mid-size local LLM lacks (Opus + Sonnet subagent pattern).
   Phase 7-2 measured context boost +0.58 ~ +0.64 across 3 models.
5. Architect verifies the result and returns it.

Detailed workflow: [docs/workflow.md](docs/workflow.md).
Internals: [docs/internals.md](docs/internals.md).

## 5-minute install

> **Agent-driven install**: in your Claude Code / Codex CLI session, type
> `follow https://github.com/hang-in/tunaLlama 's INSTALL.md to install it for me`
> -> the agent reads [INSTALL.md](INSTALL.md) and walks through deps,
> `.env`, plugin registration, and verification step by step. ~5 minutes.

Manual install steps below.

### 1. Clone + deps

```bash
git clone https://github.com/hang-in/tunaLlama
cd tunaLlama

# uv recommended (mise.toml-defined)
mise install                   # python 3.11 + uv
mise run install               # editable + dev deps

# Or pip
pip install -e .
```

### 2. Env vars (for Ollama Cloud)

```bash
cp .env.example .env
echo "OLLAMA_CLOUD_API_KEY=your_key_here" >> .env
```

### 3. tunallama init / doctor

```bash
tunallama init                 # interactive - auto-discovers provider/model
tunallama doctor               # checks Python / config / provider / DB / Kiwi
```

If `doctor` fails, see [Troubleshooting](#troubleshooting--faq).

### 4-A. Claude Code users

```bash
claude plugin marketplace add /path/to/tunaLlama
claude plugin install tunaLlama@tunallama-local
```

Or register directly in `~/.claude/settings.json`'s `mcpServers`:

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

### 4-B. Codex CLI users

Codex CLI reads `.claude-plugin/marketplace.json` directly (one of
its 4 recognized locations):

```bash
codex plugin marketplace add /path/to/tunaLlama
codex plugin install tunaLlama@tunallama-local
```

Details: [docs/specs/phase8_codex.md](docs/specs/phase8_codex.md).

## First call

After install, in a Claude Code / Codex session:

### Delegate code generation

```
You: "write a json parsing function"

Claude/Codex automatically:
1. tuna_load_memory()  ← fetch project conventions
2. tuna_recall(query="json parsing")  ← surface past similar work (opt)
3. tuna_generate_code(requirements="...", language="python")
   → local LLM generates code
4. Architect verifies and returns to you
```

### Larger task - spec-based

```
You write a spec at docs/specs/foo.md, then:

Claude/Codex: tuna_dev_review_from_spec("docs/specs/foo.md")
→ backend auto-loops generate → review → fix
→ returns final code + iteration log
```

### Memory search

```
You: "how did this project use BGE-M3 embeddings?"

Claude/Codex: tuna_recall(query="BGE-M3 embedding usage")
→ surfaces top-5 past calls
```

Full 13-tool list: [docs/internals.md](docs/internals.md#mcp-tools).

## Limitations

- **Production** (v0.5.0). Verified on both Claude Code and Codex CLI.
  Caveat: no organic everyday-use measurement yet.
- **Quota savings are anecdotal**. Anthropic / OpenAI formulas not
  public; quantitative measurement not possible.
- **Search measurements (R@5, P@1, etc.) synthetic-seed based**.
  Real-user workflow validation separate. Details:
  [docs/measurements/](docs/measurements/).
- **MCP auto-invocation dependent**. Users rarely call `tuna_*` tools
  explicitly; the architect decides based on task context. Tool
  description quality determines auto-invocation appropriateness.
- **Local LLM dependent**. No Ollama etc. means no work.
- **Korean morphology = Kiwi-dependent**. Domain words Kiwi can't
  handle (new slang, jargon) may impact search quality.
- **No organic dogfooding measurement**. Since round 16 no real
  Claude Code everyday-use measurement (resumed in Phase 6).
- **MCP tool system prompt cost**. 13 tools' description + schema
  prepended to system prompt every conversation. Estimated ~1633
  tokens. Details:
  [docs/measurements/phase7-mcp-audit.md](docs/measurements/phase7-mcp-audit.md).
- **Test coverage 90%** (475 unit/plugin tests). Most of the missing
  10% is external-service-dependent code paths (`llm/ollama.py` 62% /
  `llm/lmstudio.py` 58% - covered when `pytest -m integration` runs
  against live services). `token_count.py` 34% is the deferred
  Phase 5-4 module (no Anthropic API access here).
- **Subagent auto-discovery does NOT work** (Codex 0.128.0 live test):
  `plugin/agents/tuna-developer.toml` is cached but Codex's
  `spawn_agent` types only includes default / explorer / worker. Claude
  Code side not yet measured. The 13 MCP tools work in both; delegation
  happens at the tool layer.
- **MCP resource auto-attach does NOT work** (both environments live-
  tested): `tunallama://memory/state` is not attached at session start
  on either Claude Code or Codex CLI. v0.5.2 adds a SessionStart hook
  (`plugin/hooks/session_start.py`) to prepend state.md content via
  stdout - client support varies. Fallback: architect calls
  `tuna_load_memory` once per session.

### Cross-environment behavior matrix (v0.5.2)

| Item | Claude Code | Codex CLI 0.128.0 |
|---|---|---|
| MCP tools 13 (tool calls) | ✓ | ✓ |
| DB sharing (`~/.tunallama/memory.db`) | ✓ | ✓ |
| state.md sharing (`~/.tunallama/projects/<hash>/state.md`) | ✓ | ✓ |
| Explicit `tuna_load_memory` / `tuna_recall` | ✓ | ✓ |
| **MCP resource auto-attach** | ✗ | ✗ |
| **SessionStart hook (state.md prepend)** | client-dependent | client-dependent |
| **Subagent auto-discovery** | ? (not measured) | ✗ |

- **state.md auto-extract false positives**. v0.5.1 strips code-block
  contents and filters tokens by meaningfulness - not 100% eliminated.
  Use `tunallama state clean` (delete auto entries) or edit directly
  (`tunallama state path` for the path).

## What this is not

- Not tunaFlow multi-agent roundtable.
- Not an OllamaClaude fork (pattern reference).
- Not a single-model demo / research notebook.
- Not auto weakness detection / dynamic tool generation - architect
  judgment calls `tuna_log_limitation`.

## Measurements

Search algorithm / context boost / MCP audit:

- [Index](docs/measurements/)
- [methodology.md](docs/measurements/methodology.md) - seeds / LOPO /
  metric definitions / known limits
- [phase4-search.md](docs/measurements/phase4-search.md) - search quality
- [phase5-hyde-kure.md](docs/measurements/phase5-hyde-kure.md) - HyDE /
  KURE / Adaptive
- [phase7-mcp-audit.md](docs/measurements/phase7-mcp-audit.md) - MCP
  tool system prompt size
- [phase7-context-boost.md](docs/measurements/phase7-context-boost.md) -
  **mid-size LLM context boost +0.58~+0.64** (3 models validated)

Synthetic seed based; real usage data validation is separate.

## Troubleshooting / FAQ

### `tunallama doctor` fails

**Python version**: 3.11+ required.

**Provider not detected**: Ollama / LM Studio running?
```bash
curl http://localhost:11434/api/tags
curl http://localhost:1234/v1/models
```

**Ollama Cloud key not detected**: `.env` in cwd? `OLLAMA_CLOUD_API_KEY=...`
on the first line?

**Kiwi morphology fails**: `pip install kiwipiepy`. On macOS, Xcode CLI
tools required (`xcode-select --install`).

### MCP tools not visible in Claude/Codex context

**`.mcp.json` cwd wrong**: check where `claude plugin install` ran.
For direct registration, `cwd` should be tunaLlama repo absolute path.

**Python venv not picked up**: system python may spawn without deps.
Use venv python absolute path, or `mise install` first.

### `tuna_*` tools not getting called

**Architect not calling automatically**: SKILL.md or
`tunallama://memory/state` resource may not be attached. Try explicit
`tuna_load_memory` call.

**Tool description quality**: abstract tasks confuse tool selection.
Explicitly say "use `tuna_dev_review` to write this".

### LLM call timeout

**Default timeout 600s** (`tunallama_core/config/models.py`). Retries
3x on cloud LLM delay. Final failure logged to stderr.

**Frequent timeouts**: switch to local LLM or a latency-optimized model
(qwen3-coder-next etc.).

### Search quality feels low

**Current measurement**: synthetic seed R@5 0.5 / σR@5 0.22-0.16
(with HyDE).

**R@5 < 0.8 implication**: auto-prepend (`auto_recall=always`) may
mix in noise. Phase 4-4 + 5-3 measured cloud LLM ignoring irrelevant
prefix - real code damage small.

**Recommend default `on_request`**. Use `auto_recall=always` with
the risk in mind.

### state.md auto-extract unwanted entries

**File location**: `~/.tunallama/projects/<hash>/state.md`. Edit directly.

**`(manual)` or `(verified)` tag**: user edits preserved on next update.

**Disable auto-extract**: `.env` or environment `TUNA_AUTO_EXTRACT_STATE=0`.

## Contributors

```bash
mise install                    # python 3.11 + uv
mise trust                      # trust mise.toml (security)
mise run install                # editable + dev deps
mise run test                   # pytest (unit + plugin only)

# Measurement integration tests (BGE-M3 download + cloud LLM):
.venv/bin/pytest -m search_quality -s
```

Detailed contribution guide: [CONTRIBUTING.md](CONTRIBUTING.md).

## Docs / files

- [docs/workflow.md](docs/workflow.md)
- [docs/internals.md](docs/internals.md)
- [docs/measurements/](docs/measurements/)
- [docs/specs/](docs/specs/)
- [docs/dogfooding-log.md](docs/dogfooding-log.md)
- [docs/release-notes/](docs/release-notes/)
  ([v0.5.1](docs/release-notes/v0.5.1.md) · [v0.5.0](docs/release-notes/v0.5.0.md) ·
  [v0.4.0](docs/release-notes/v0.4.0.md) · [v0.3.0](docs/release-notes/v0.3.0.md))
- [CHANGELOG.md](CHANGELOG.md)
- [CONTRIBUTING.md](CONTRIBUTING.md)
- [config.example.toml](config.example.toml)
- [.env.example](.env.example)

## License / contributing

MIT. Issues/PRs welcome in Korean or English. The Korean README
[README.md](README.md) is the canonical version - please keep it in sync.

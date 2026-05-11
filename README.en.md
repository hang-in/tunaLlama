# tunaLlama

[![CI](https://github.com/hang-in/tunaLlama/actions/workflows/ci.yml/badge.svg)](https://github.com/hang-in/tunaLlama/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Status: early beta](https://img.shields.io/badge/status-early%20beta-orange.svg)](#)
[![Tests: 475 passing](https://img.shields.io/badge/tests-475%20passing-brightgreen.svg)](#)
[![Coverage: 90%](https://img.shields.io/badge/coverage-90%25-brightgreen.svg)](#)
[![Claude Code / Codex CLI](https://img.shields.io/badge/works%20with-Claude%20Code%20%2F%20Codex%20CLI-purple.svg)](#)

A delegation tool for Claude Code / Codex CLI users who burn tokens fast.

Heavy code generation is delegated to local Ollama / LM Studio /
Ollama Cloud; decomposition and verification stay with the architect
(Claude / Codex) in the same session. **One repo works for both Claude
Code and Codex CLI** - Codex CLI also reads
`.claude-plugin/marketplace.json`.

**Status**: v0.4.0 (early beta). v0.5.0 production release in preparation.
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

- **Early beta** (v0.4.0). v0.5.0 will carry the production tag.
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
- [CHANGELOG.md](CHANGELOG.md)
- [CONTRIBUTING.md](CONTRIBUTING.md)
- [config.example.toml](config.example.toml)
- [.env.example](.env.example)

## License / contributing

MIT. Issues/PRs welcome in Korean or English. The Korean README
[README.md](README.md) is the canonical version - please keep it in sync.

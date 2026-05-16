# tunaLlama

[![CI](https://github.com/hang-in/tunaLlama/actions/workflows/ci.yml/badge.svg)](https://github.com/hang-in/tunaLlama/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Status: usable beta](https://img.shields.io/badge/status-usable%20beta-yellow.svg)](#)
[![Tests: 506 passing](https://img.shields.io/badge/tests-506%20passing-brightgreen.svg)](#)
[![Coverage: 90%](https://img.shields.io/badge/coverage-90%25-brightgreen.svg)](#)
[![Claude Code / Codex CLI](https://img.shields.io/badge/works%20with-Claude%20Code%20%2F%20Codex%20CLI-purple.svg)](#)

A delegation tool for Claude Code / Codex CLI users who burn tokens fast.

Heavy code generation is delegated to local Ollama / LM Studio /
Ollama Cloud; decomposition and verification stay with the architect
(Claude / Codex) in the same session. **One repo works for both Claude
Code and Codex CLI** - Codex CLI also reads
`.claude-plugin/marketplace.json`.

tunaLlama is not a prompt seed or AGENTS.md template. Rather than having
the upper-model session absorb every doc and long code block directly,
it is an **MCP-based delegation runtime that hands long code generation
off to a local/low-cost LLM so the Architect can focus on decomposition
and verification**.

**Status**: **v0.5.x usable dogfooding release** (2026-05-11). MCP tool
invocation is verified on both Claude Code and Codex CLI, but organic
dogfooding measurement and external-user reproducibility are still being
collected.
**License**: [MIT](LICENSE). **Korean**: [README.md](README.md) (canonical).

---

## Who this might help

- Claude Code Pro/Max subscribers (quota management motive)
- Codex CLI users (OpenAI subscription / API quota management)
- Users with Ollama local / Ollama Cloud / LM Studio available
- Users working with Korean (Kiwi morphological tokenizer integrated)

Actual quota-savings depend on your task mix, model choice, provider
latency, and the Architect's verification style. Anthropic / OpenAI
quota formulas are not public, so tunaLlama does not promise a
"guaranteed token saving" - it provides **a structure for delegating
long generation so the upper-model's usage can be reduced**. Confirm
real value via your own dogfooding.

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
3. Backend runs a generate → review → fix loop (bounded delegation -
   terminates on review pass or max iter). Every call lands in SQLite
   indexed by Korean morphemes.
4. **Real value of search**: architect fetches context that the
   mid-size local LLM lacks (Opus + Sonnet subagent pattern). Phase 7-2
   **measured on synthetic seeds**: context boost +0.58 ~ +0.64 across
   3 models. This is not a real-usage validated number; organic
   dogfooding metrics are collected separately.
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

After install, in a Claude Code / Codex session. The Architect can
invoke these tools on its own, but **explicit invocation is recommended**
for first use and reproducible workflows.

### Recommended flow - delegate code generation

```
You: "write a json parsing function.
      first run tuna_load_memory for project conventions,
      then delegate via tuna_dev_review."

Architect:
1. tuna_load_memory()  ← fetch project conventions
2. tuna_recall(query="json parsing")  ← surface past similar work (opt)
3. tuna_dev_review(requirements="...", language="python")
   → local LLM runs generate → review → fix loop
4. Architect verifies and returns to you
```

### Larger task - spec-based

```
You write a spec at docs/specs/foo.md, then:

You: "run tuna_dev_review_from_spec on docs/specs/foo.md"

→ backend runs bounded generate → review → fix loop
→ returns final code + iteration log
```

### Memory search

```
You: "use tuna_recall to search how this project used BGE-M3 embeddings"

→ surfaces top-5 past calls
```

Full 13-tool list: [docs/internals.md](docs/internals.md#mcp-tools).

## Limitations

**v0.5.x usable dogfooding release**. MCP tool invocation is verified on
both Claude Code and Codex CLI, but organic dogfooding (everyday use)
measurement is still being collected. Below organized by category:

### 1. Usage / cost

- **Quota savings are anecdotal**. Anthropic / OpenAI formulas not
  public; quantitative measurement not possible.
- **MCP tool system prompt cost is an intended trade-off**. The 13
  tools' descriptions + schemas are prepended to the system prompt
  every conversation (estimated ~1.6k tokens). This is not accidental
  context bloat; it is the affordance cost that lets the Architect
  pick the right delegation tool. tunaLlama manages tool count and
  description quality rather than removing this cost. Details:
  [docs/measurements/phase7-mcp-audit.md](docs/measurements/phase7-mcp-audit.md).

### 2. Measurement

- **Search measurements (R@5, P@1, etc.) measured on synthetic seeds**.
  Real-user workflow validation separate. Details:
  [docs/measurements/](docs/measurements/).
- **Organic dogfooding metrics** (v0.5.7+). Each delegation records 4
  metrics (`standalone_toy_rate` / `convention_adherence_rate` /
  `ast_excess_score` / `syntactically_valid`) into
  `~/.tunallama/metrics.db`. View with `tunallama metrics show`.
  Disable: `TUNA_ORGANIC_METRICS=0`. External-user reproducibility is
  still being collected.
- **Test coverage 90%** (475 unit/plugin tests). Most of the missing
  10% is external-service-dependent code paths (`llm/ollama.py` 62% /
  `llm/lmstudio.py` 58% - covered when `pytest -m integration` runs).
  `token_count.py` 34% is the deferred Phase 5-4 module.

### 3. MCP / client compatibility

- **Architect-invocation dependent**. `tuna_*` tools are called by the
  Architect based on task context - description quality determines
  hit rate. **Explicit invocation recommended** for first use and
  reproducible workflows.
- **Subagent auto-discovery does NOT work** (Codex 0.128.0 live test):
  `plugin/agents/tuna-developer.toml` is cached but Codex's
  `spawn_agent` types only includes default / explorer / worker.
  Claude Code side not yet measured. The 13 MCP tools work on both;
  delegation happens at the tool layer.
- **MCP resource auto-attach + SessionStart hook**:
  `tunallama://memory/state` is not attached at session start on either
  client. v0.5.2's SessionStart hook works on Claude Code v0.5.5+ but
  Codex does not honor it. **Recommended operation**: Claude Code uses
  the hook for state.md auto-prepend; on Codex the user calls
  `tuna_load_memory` explicitly.

### 4. Local LLM / provider

- **Local LLM dependent**. No Ollama / LM Studio / Ollama Cloud means
  no work.

### 5. Search / memory quality

- **Korean morphology = Kiwi-dependent**. Domain words Kiwi can't
  handle (new slang, jargon) may impact search quality.

### 6. state.md auto-extract

- **state.md auto-extract false positives**. v0.5.1 strips code-block
  contents and filters tokens by meaningfulness - not 100% eliminated.
  Use `tunallama state clean` (delete auto entries) or edit directly
  (`tunallama state path` for the path).

### Cross-environment behavior matrix (v0.5.6, Claude Code 2.1.138 + Codex CLI 0.128.0)

| Item | Claude Code | Codex CLI |
|---|---|---|
| MCP tools 13 (tool calls) | ✓ | ✓ |
| DB sharing (`~/.tunallama/memory.db`) | ✓ | ✓ |
| state.md sharing (`~/.tunallama/projects/<hash>/state.md`) | ✓ | ✓ |
| Explicit `tuna_load_memory` / `tuna_recall` | ✓ | ✓ |
| **Agents auto-discovery** (`tuna-developer`) | **✓** | ✗ |
| **Skills auto-load** (`delegate-to-ollama`) | **✓** | ? |
| **Hooks registration** (`SessionStart` / `PreToolUse`) | **✓** | ? |
| **SessionStart hook execution + state.md auto-prepend** | **✓** (v0.5.5 schema fix, verified) | ✗ |
| **MCP resource auto-attach** | ✗ | ✗ |

### Recommended operation

**Claude Code** (v0.5.5+):
- state.md auto-prepend via SessionStart hook works end-to-end - the
  architect knows conventions / decisions / constraints / anti-patterns
  from the first turn. No explicit `tuna_load_memory` needed.

**Codex CLI** 0.128.0:
- SessionStart hook not honored - architect calls `tuna_load_memory`
  explicitly at the first turn, or fetches docs directly.
- DB / state.md sharing and MCP tool invocation work fine.

## Why not a prompt seed

tunaLlama does not try to solve the context limit by making the agent
read more docs. Instead it slices work into small units, hands them off
to a local/low-cost LLM via MCP tools, and lets the upper-model Architect
focus on short specs, review results, and final diff judgment.

Doc-driven operating rules drift over time, creating stale state and
lost-in-the-middle problems. tunaLlama avoids that by recording
delegation calls into SQLite and providing a runtime layer that
retrieves them when needed.

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
  KURE / Adaptive (524 record)
- [phase5e-corpus-scaling.md](docs/measurements/phase5e-corpus-scaling.md) -
  **rerank pool sweep + 984 record LOPO** (rerank P@1 0.77 / R@5 0.59,
  cloud 0)
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

### MCP tools missing or `tunaLlama MCP Server: failed` in `/plugin`

**Cause 1 - venv deps not picked up** (v0.5.8 and earlier): the
plugin's `.mcp.json` spawned `python` directly, and Claude Code's
child process doesn't honor mise / pyenv / direnv shell hooks, so the
system python is used without fastmcp / anthropic SDK installed -
ImportError. **v0.5.9+ uses a wrapper script
(`plugin/bin/tunallama-mcp`) that falls back to `.venv/bin/python`
automatically** - update is recommended.

**Cause 2 - `.mcp.json` cwd wrong**: check where `claude plugin
install` ran. For direct registration, `cwd` should be tunaLlama repo
absolute path.

**Cause 3 - no `.venv`**: if `.venv/bin/python` itself is missing the
wrapper falls back to system python and may still fail. Create the
venv via `mise run install` or `uv venv && uv pip install -e .`.

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

**Current measurement** (cloud 0 path, 984 record LOPO / 792 queries):
rerank P@1 0.77 / R@5 0.59 / σR@5 0.31. HyDE+KURE path (24 leader
sample, cloud 1): P@1 0.92 / σR@5 0.14. Details:
[phase5e-corpus-scaling.md](docs/measurements/phase5e-corpus-scaling.md).

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
  ([v0.5.9](docs/release-notes/v0.5.9.md) · [v0.5.8](docs/release-notes/v0.5.8.md) ·
  [v0.5.7](docs/release-notes/v0.5.7.md) · [v0.5.6](docs/release-notes/v0.5.6.md) ·
  [v0.5.5](docs/release-notes/v0.5.5.md) · [v0.5.4](docs/release-notes/v0.5.4.md) ·
  [v0.5.3](docs/release-notes/v0.5.3.md) · [v0.5.2](docs/release-notes/v0.5.2.md) ·
  [v0.5.1](docs/release-notes/v0.5.1.md) · [v0.5.0](docs/release-notes/v0.5.0.md) ·
  [v0.4.0](docs/release-notes/v0.4.0.md) · [v0.3.0](docs/release-notes/v0.3.0.md))
- [CHANGELOG.md](CHANGELOG.md)
- [CONTRIBUTING.md](CONTRIBUTING.md)
- [config.example.toml](config.example.toml)
- [.env.example](.env.example)

## License / contributing

MIT. Issues/PRs welcome in Korean or English. The Korean README
[README.md](README.md) is the canonical version - please keep it in sync.

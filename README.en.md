# tunaLlama

> Backend + Claude Code plugin that offloads heavy code generation to a local LLM while keeping decomposition and verification on Claude Code.

**Status**: Phase 1 in progress (alpha, unreleased)
**License**: MIT
**한국어**: [README.md](README.md)

---

## What it is

tunaLlama splits work across models by what each is good at, so paid Claude Code tokens stay on the smart steps.

| Role | Model | Why |
|---|---|---|
| Architect | Claude Code (paid) | Decomposes requests. Short prompts in/out. |
| Developer | Local LLM (free/cheap) | Generates code. Long output runs on your GPU. |
| Reviewer | Claude Code (paid, same session) | Verifies output. Short prompts in/out. |

Same architectural pattern as `OllamaClaude` (Jadael/OllamaClaude). Reimplemented from scratch in Python — pattern reference only, no code copy.

Extra over OllamaClaude:
- **SQLite + FTS5 long-term memory** — every delegation call recorded, searchable across sessions.
- **Korean morpheme tokenizer** — write-time Kiwi tokenization so FTS5 recall actually works for Korean inputs.
- **File-aware tools** — `review_file`, `explain_file`, `analyze_files` take a path only; file content never enters Claude's context.

## What it is NOT

- Not a tunaFlow consumer. Not a multi-agent roundtable.
- Not a fork of OllamaClaude.
- Not a single-model demo or research notebook.

## Supported local LLMs

- **Ollama (local)** — 27B-class models recommended (e.g. `qwen2.5:32b`).
- **Ollama Cloud** — hosted models via API key.
- **LM Studio** — OpenAI-compatible endpoint (`/v1/chat/completions`).

Switch with one line: `[llm] provider = "..."` in `config.toml`.

## Quick start

> Unreleased. Will be stable when Phase 1 ships.

### Users (just want to run it) — 5-minute walkthrough

```bash
# 1. clone + install
git clone https://github.com/hang-in/tunaLlama
cd tunaLlama
pip install -e .                      # or `uv pip install -e .`

# 2. interactive setup — provider, auto-discovered models, memory options
tunallama init                        # default: ./.tunallama/config.toml
# tunallama init --global             # to write ~/.tunallama/config.toml instead

# 3. environment check — Python / config / provider / DB / Kiwi
tunallama doctor

# 4. (Ollama Cloud only) put the key in .env
echo "OLLAMA_CLOUD_API_KEY=your_key" >> .env

# 5. wire the plugin into Claude Code
claude --plugin-dir ./plugin
```

What `tunallama init` does for you:
- Auto-discovers installed models when local Ollama / LM Studio is running — pick by number
- Prompts for the env var name when the provider needs an API key
- Creates ~/.tunallama or ./.tunallama as needed

### Contributors (dev setup)
mise manages Python version + uv + `.venv` automatically.

```bash
git clone https://github.com/hang-in/tunaLlama
cd tunaLlama                  # entering the dir auto-creates & activates .venv
mise install                  # installs python 3.11 + uv
mise run install              # editable + dev deps
mise run test                 # pytest
```

If you don't have mise yet, see the [mise installation guide](https://mise.jdx.dev/getting-started.html).

## Layout

```
tunallama_core/                  # Backend (reusable, MCP-agnostic)
  config/                        # TOML load + validation + frozen dataclasses
  llm/                           # Provider abstraction (ollama / lmstudio / factory)
  memory/                        # SQLite + FTS5 + Kiwi morpheme tokenization
  delegation/                    # 10 tools + shared runner + prompts
  routing.py                     # auto_recall policy
  errors.py                      # domain exceptions
plugin/                          # Claude Code plugin (consumes backend)
  .claude-plugin/plugin.json
  .mcp.json
  mcp_server.py                  # FastMCP server (11 tuna_* tools)
  _state.py / _format.py
  skills/delegate-to-ollama/SKILL.md
  agents/tuna-developer.md
tests/
  core/                          # backend unit + integration tests
  plugin/                        # plugin tool / manifest tests
```

`tunallama_core` never imports anything from `plugin`. This boundary is what makes a future Codex frontend (Phase 4) cheap.

## Status (Phase 1)

- 11 MCP tools exposed: `tuna_generate_code`, `tuna_review_file`, `tuna_recall`, etc.
- Every call recorded to SQLite, Korean queries supported via morpheme tokenizer.
- 177 tests, 99% coverage.
- Integration tests hit real Ollama Cloud / LM Studio (auto-skip when unavailable).

## Development status

`docs/handoff-tunallama-phase1.md` is the source of truth for Phase 1. Decisions that diverge from the handoff are recorded in `CHANGELOG.md`.

## Contributing / License

MIT. Issues and PRs welcome in either Korean or English.

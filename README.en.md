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

### Users (just want to run it)
```bash
git clone https://github.com/hang-in/tunaLlama
cd tunaLlama
pip install -e .          # or `uv pip install -e .`
mkdir -p ~/.tunallama && cp config.example.toml ~/.tunallama/config.toml
claude --plugin-dir ./plugin
```

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
tunallama_core/   # Backend (reusable, MCP-agnostic)
  llm/            # Provider abstraction (ollama / lmstudio / factory)
  memory/         # SQLite + Kiwi
  ...
plugin/           # Claude Code plugin (consumes backend)
  .claude-plugin/plugin.json
  .mcp.json
  mcp_server.py
  skills/, agents/, hooks/
```

`tunallama_core` never imports anything from `plugin`. This boundary is what makes a future Codex frontend (Phase 4) cheap.

## Development status

`docs/handoff-tunallama-phase1.md` is the source of truth for Phase 1. Decisions that diverge from the handoff are recorded in `CHANGELOG.md`.

## Contributing / License

MIT. Issues and PRs welcome in either Korean or English.

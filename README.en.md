# tunaLlama

A delegation tool for Claude Code users who burn tokens fast.

Heavy code generation is delegated to local Ollama / LM Studio /
Ollama Cloud; decomposition and verification stay with Claude in the
same session. Runs as a Claude Code MCP plugin.

**Status**: alpha, Phase 5 complete (v0.3.0), Phase 6 upcoming.
**License**: MIT. **Korean**: [README.md](README.md) (canonical).

---

## Who this might help

- Claude Code Pro/Max subscribers (quota management motive)
- Users with Ollama local / Ollama Cloud / LM Studio available
- Users working with Korean (Kiwi morphological tokenizer integrated)

That said, the actual value of these scenarios is best confirmed by
your own dogfooding. Token-quota savings are anecdotal data only -
Anthropic's quota formula is not public, so quantitative measurement
is not possible.

### Requirements

- Python 3.11+
- One of: Ollama / LM Studio / Ollama Cloud
- Claude Code (version with MCP plugin support)

## How it works

| Role | Model | Responsibility |
|---|---|---|
| Architect | Claude Code (subscription) | Decomposition / spec / verification / integration |
| Developer | Local LLM (Ollama / Cloud / LM Studio) | Code generation / self-review / self-fix |
| Reviewer | Claude Code (same session) | Final judgment |

Typical call flow:

1. User asks for a task (Korean / English).
2. Claude (architect) decomposes - short task uses `tuna_dev_review`,
   longer ones go through a spec doc then `tuna_dev_review_from_spec`.
3. Backend runs generate → review → fix loop automatically. Every
   call lands in SQLite indexed by Korean morphemes.
4. Claude verifies the result and returns it.

Detailed workflow: [docs/workflow.md](docs/workflow.md).
Internals (memory / search / provider abstraction / hooks):
[docs/internals.md](docs/internals.md).

## 5-minute install

```bash
git clone https://github.com/hang-in/tunaLlama
cd tunaLlama

pip install -e .                # or `uv pip install -e .`

tunallama init                  # interactive - auto-discovers provider/model
tunallama doctor                # checks Python / config / provider / DB / Kiwi

# For Ollama Cloud
echo "OLLAMA_CLOUD_API_KEY=your_key_here" >> .env

# Permanent registration in ~/.claude/settings.json mcpServers:
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

When `cwd` is the project root, the plugin auto-discovers `.env` and
`./.tunallama/config.toml` at startup.

### Contributors

```bash
mise install                    # python 3.11 + uv
mise trust                      # trust mise.toml (security)
mise run install                # editable + dev deps
mise run test                   # pytest
```

## Limitations

- **Alpha stage**. Use in production with caution.
- **Quota savings are anecdotal**. Anthropic's subscription formula is
  not public so quantitative measurement is not possible. Your own
  dogfooding is the only confirmation.
- **Search measurements (R@5, P@1, etc.) are based on synthetic seeds**.
  Real-user workflow validation is a separate matter. See
  [docs/measurements/](docs/measurements/) for details.
- **MCP auto-invocation dependent**. Users rarely call `tuna_*` tools
  explicitly; Claude decides based on task context. Tool description
  quality determines auto-invocation appropriateness.
- **Local LLM dependent**. No Ollama etc. means no work.
- **Korean morphology = Kiwi-dependent**. Domain words Kiwi can't
  handle (new slang, jargon) may impact search quality.
- **No organic dogfooding measurement**. Since round 16 no real Claude
  Code everyday-use measurement (resumed in Phase 6).

## What this is not

- Not tunaFlow multi-agent roundtable.
- Not an OllamaClaude fork (pattern reference only).
- Not Codex CLI integration (separate handoff).
- Not a single-model demo / research notebook.
- Not auto weakness detection / dynamic tool generation - architect
  judgment calls `tuna_log_limitation`.

## Measurements

Search algorithm measurements (R@5, P@1, σ, path comparisons) live in
[docs/measurements/](docs/measurements/). Synthetic seed based; real
usage data validation is a separate matter.

## Docs / files

- [docs/workflow.md](docs/workflow.md) - Architect ↔ Developer workflow.
- [docs/internals.md](docs/internals.md) - Internals (memory, search,
  provider, hooks).
- [docs/measurements/](docs/measurements/) - measurement assets
  (Phase 4-5 search / HyDE / KURE / Adaptive).
- [docs/specs/](docs/specs/) - per-phase spec docs.
- [docs/dogfooding-log.md](docs/dogfooding-log.md) - round-by-round
  dogfooding results.
- [docs/release-notes/](docs/release-notes/) - v0.3.0 etc.
- [CHANGELOG.md](CHANGELOG.md) - change history.
- [config.example.toml](config.example.toml) - config fields + comments.
- [.env.example](.env.example) - environment variable examples.

## License / contributing

MIT. Issues/PRs welcome in Korean or English. The Korean README
[README.md](README.md) is the canonical version - please keep it in sync.

# tunaLlama

Backend + Claude Code plugin that lets the main session (Architect) offload long-output coding work to a local LLM (Ollama / LM Studio) and keep decomposition + verification on the paid model.

**Version**: v0.1.0 shipped · v0.2.0 pending (Phase 2 integrated, Phase 3 in progress: synonym seed + semantic edges)
**License**: MIT.
**한국어**: [README.md](README.md) — fuller, treated as the canonical version.

---

## Why

Coding sessions on Claude Code spend most of their tokens on the **long-output** stages — code generation, file review, refactor — where model quality differences are small. The **short-input** stages — decomposing requirements, verifying that the returned code matches them — is where high-end model quality actually pays off. tunaLlama hardcodes that asymmetry into the workflow.

Same architectural pattern as `OllamaClaude` (Jadael/OllamaClaude). Reimplemented from scratch in Python — pattern reference only, no code copy.

| Role | Model | Responsibility |
|---|---|---|
| Architect | Claude Code (paid) | Decompose / write spec / verify / integrate |
| Developer | Local LLM (Ollama / Cloud / LM Studio) | Generate / self-review / self-fix |
| Reviewer | Claude Code (paid, same session) | Final judgment |

## Architecture

```
tunallama_core/                  # Backend — reusable, MCP-agnostic
  config/                        # TOML load + validation + frozen dataclasses
  llm/                           # Provider abstraction (ollama / lmstudio / factory)
  memory/                        # SQLite + FTS5 + Kiwi morpheme tokenization
  delegation/                    # 10 tools + shared runner + system prompts
  workflow/                      # dev_review_loop / spec / limitations
  routing.py                     # auto_recall policy
  errors.py
  cli/                           # tunallama init / doctor

plugin/                          # Claude Code plugin — consumes backend
  .claude-plugin/plugin.json
  .mcp.json
  mcp_server.py                  # FastMCP server, 14 tuna_* tools
  _state.py                      # lazy singleton + .env autoload
  _format.py
  hooks/pre_tool_use.py          # large-file Read advisory (off by default)
  skills/delegate-to-ollama/SKILL.md
  agents/tuna-developer.md
```

**Invariant**: `tunallama_core` never imports anything from `plugin`. Phase 4 (Codex frontend) will reuse the backend unchanged.

## Memory + search

Every delegation call is recorded into SQLite + FTS5. Korean inputs are pre-tokenized with Kiwi at write-time so `unicode61` recall works:

```python
_KEEP_TAGS = {"NNG", "NNP", "NNB", "VV", "VA", "MAG", "MAJ", "SL"}

def kiwi_morphemes(text):
    tokens = _get_kiwi().tokenize(text)
    morph = " ".join(t.form for t in tokens if t.tag in _KEEP_TAGS)
    return f"{morph} {text}".strip()
```

`NNB` (dependent nouns) added per the seCall reference. No FTS triggers — application-level INSERT into both `calls` and `calls_fts` since pre-tokenization can't live inside a SQL trigger anyway.

`tuna_recall(query, limit)` returns ranked summaries, never the full original output. The whole point is to keep recall results small.

### Phase 2 — semantic + hybrid + graph

- **Vector recall** (`memory/vector.py`): `BAAI/bge-m3` 1024-dim embeddings auto-saved on `record_call`. Lazy load + thread-locked. `MemoryStore.search_vectors(query)` does brute-force cosine over `embedding IS NOT NULL` rows; falls back to empty list if the model is unavailable so the BM25 path is unaffected.
- **Hybrid recall** (`recall_hybrid`): RRF (k=60) over BM25 + vector. `score = 1/(k+rank)` summed across both rankings, dedup by record id, BM25 snippet preferred over vector for display. Works on the BM25-only side when no embeddings exist.
- **Rule-based graph** (`memory/graph.py`): `same_project` / `same_day` / `same_tool` edges via SQL JOIN with `a.id < b.id` normalization (no self-loops, no reverse duplicates). `rebuild_edges()` + `traverse(start_id, max_hops, relations)` BFS. LLM-free.

## Provider abstraction

| Provider | host default | key |
|---|---|---|
| ollama | `http://localhost:11434` | none |
| ollama_cloud | `https://ollama.com` | env var named by `api_key_env` |
| lmstudio | `http://localhost:1234/v1` | dummy |

Tests don't mock the SDK. Integration tests hit real Ollama Cloud (`gemma4:31b`) and local LM Studio (`nvidia/nemotron-3-nano-4b`); they auto-skip when the service is unavailable.

## Workflow

### dev_review loop

```python
dev_review_loop(requirements, ..., max_iterations=2)
# generate → review → (if issues) fix → review → ...
# converges on LGTM/이상 없음 markers, otherwise stops at max_iterations
```

### Spec document

Architect writes a short markdown doc; subagent reads it. Optional headers (recommended for small models per gemento's phase-driven decomposition findings):

```markdown
# Task: build email validator

## Phase
IMPLEMENT          # DESIGN | IMPLEMENT | VERIFY

## Focus
regex matcher first

## Requirements
- regex check
- reject empty

## Constraints
- stdlib only
- no external calls

## Acceptance
- pytest 5 cases pass
```

`Constraints` lines are hard rules — violating them sends the output back through the fix loop.

### Limitations catalog

```bash
tuna_log_limitation("model breaks indentation in Korean docstrings")
```

Appended to `~/.tunallama/limitations.md` and auto-prepended to future `tuna_dev_review` prompts. Manual logging — no auto-detection.

## Install

```bash
git clone https://github.com/hang-in/tunaLlama
cd tunaLlama
pip install -e .                 # or `uv pip install -e .`

tunallama init                   # interactive — picks provider + auto-discovers models
tunallama doctor                 # Python / config / provider / DB / Kiwi check

echo "OLLAMA_CLOUD_API_KEY=your_key" >> .env   # if using cloud

# Permanently register in ~/.claude/settings.json:
# {
#   "mcpServers": {
#     "tunallama": {
#       "command": "/abs/path/tunaLlama/.venv/bin/python",
#       "args": ["-m", "plugin.mcp_server"],
#       "cwd": "/abs/path/tunaLlama"
#     }
#   }
# }
```

`cwd` at the project root → plugin auto-loads `.env` and `./.tunallama/config.toml`.

### Contributors

```bash
mise install
mise trust                       # mise.toml security trust
mise run install
mise run test
```

## Tests

```
$ pytest
... 249 passed in 8.65s
... TOTAL 94% line+branch
```

Unit tests use a `StaticClient` fake (deterministic ChatResponse, captures prompts). Integration tests use real services; mocks intentionally avoided so SDK schema/type drift isn't masked.

## Out of scope

- Multi-agent roundtable (a different project's job).
- OllamaClaude fork — pattern reference only.
- Codex CLI integration — Phase 4, separate handoff.
- Auto weakness detection / dynamic tool authoring — Phase 2 candidates.

## Phase 2 candidates (parked)

- Vector embeddings (BGE-M3) + HNSW for semantic recall
- RRF (reciprocal rank fusion) over BM25 + vector
- Rule-based graph edges (`same_project`, `same_day`)
- LLM-derived semantic edges (`fixes_bug`, `modifies_file`)
- Auto hook routing (force `Read` → `tuna_review_file`)
- Non-interactive `tunallama init --provider ... --model ...`
- gemento's `remediation_hint` (structured review output) — parked due to LLM-output-parsing fragility

## License / contributing

MIT. Issues and PRs welcome in either Korean or English. Keep [README.md](README.md) (Korean canonical) and this file in sync.

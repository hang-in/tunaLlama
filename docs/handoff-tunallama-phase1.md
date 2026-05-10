# Handoff: tunaLlama Phase 1 — Backend Core + Claude Code Plugin

**For**: Claude Code architect session (fresh, no prior context assumed)
**From**: planning session, 2026-05-09
**Status**: Implementation spec, ready to build
**Repository**: new standalone repo (to be created at `github.com/hang-in/tunaLlama`)

---

## 0. What this document is

This is a self-contained implementation spec. The implementing agent receives this with **zero prior conversation context** and must be able to start work from this document alone. All decisions, rationale, and constraints are inline.

If reality diverges from this spec during implementation (CLI flags, library APIs, etc.), reality wins. Update the spec section, document the change in CHANGELOG, and proceed.

## 1. What tunaLlama is

A backend + Claude Code plugin that lets users run heavy code-generation work on a local Ollama model while keeping decomposition and verification on their paid Claude Code subscription. Think of it as the **token-saving 3-role pattern** packaged for Claude Code users.

**Core idea**: split work across models by what each is good at.

| Role | Model | Why |
|---|---|---|
| Architect | Claude Code (paid) | Decomposes user requests. Short prompts in/out. |
| Developer | Local Ollama (free) | Generates code. Long output, but runs on your GPU. |
| Reviewer | Claude Code (paid, same session) | Verifies output. Short prompts in/out. |

The token-heavy step (generation) runs locally for free. The smart steps (decompose + verify) stay on the paid model with short context. This is the **same architectural pattern** as `OllamaClaude` (Jadael/OllamaClaude on GitHub) but reimplemented from scratch in Python with our own additions: SQLite-backed long-term memory, Korean tokenization for cross-session recall, and a clean separation between backend logic and plugin frontend.

We are **not forking OllamaClaude** — we are building a parallel implementation in our own language and structure. The reference repository is allowed for pattern study but no code copy.

## 2. What this is NOT

- Not a tunaFlow consumer. No tunaFlow imports or dependencies.
- Not a fork of any existing project.
- Not a multi-agent roundtable (that's tunaFlow's job).
- Not a Codex CLI integration (Phase 4+ deliverable, separate handoff).
- Not a single-file demo (that's `tunaflow/learn/gpt-local-tui/`).
- Not a research notebook (that's Gemento).

## 3. Architecture — backend + frontend separation

The single most important design decision: **split the project into a reusable backend core and a thin Claude Code plugin frontend.** Even though Phase 1 only ships the Claude frontend, the boundary must be clean from day one because Phase 4 will add a Codex frontend that imports the same backend.

```
tunaLlama/
├── tunallama_core/          # Backend (Python package, pip-installable)
│   ├── __init__.py
│   ├── config.py            # Config loading + validation
│   ├── ollama_client.py     # Wraps the ollama Python client
│   ├── delegation.py        # Tool implementations (generate, review, etc.)
│   ├── memory/
│   │   ├── __init__.py
│   │   ├── store.py         # SQLite + KoNLPy/Kiwi tokenizer
│   │   ├── schema.sql       # Table definitions
│   │   └── search.py        # BM25 over FTS5
│   └── routing.py           # Decides: simple delegation vs delegation+memory
├── plugin/                  # Claude Code plugin (consumes core)
│   ├── .claude-plugin/
│   │   └── plugin.json
│   ├── .mcp.json            # MCP server registration
│   ├── mcp_server.py        # FastMCP server, exposes core's tools
│   ├── skills/
│   │   └── delegate-to-ollama/
│   │       └── SKILL.md
│   ├── agents/
│   │   └── tuna-developer.md
│   └── hooks/
│       └── pre_tool_use.py  # Optional: auto-route heavy tools to Ollama
├── tests/
│   ├── core/                # Backend unit tests (no plugin dependency)
│   └── plugin/              # Plugin integration tests
├── README.md
├── pyproject.toml           # Single package, but core is importable standalone
├── LICENSE                  # MIT
└── CHANGELOG.md
```

**The backend never imports anything plugin-specific.** Plugin imports backend, not the other way around. This is the rule that makes Phase 4 (Codex frontend) cheap to add later.

## 4. Configuration

```toml
# config.example.toml — user copies to ~/.tunallama/config.toml
# (or repo-local .tunallama/config.toml if working inside a project)

[ollama]
# Model name from `ollama list`. 27B-class recommended for real coding work.
# Smaller models (7B/8B) work but require more retries from the architect.
model = "qwen2.5:32b"
host = "http://localhost:11434"
temperature = 0.3
num_ctx = 8192
timeout_seconds = 300

[memory]
# SQLite path. Defaults to ~/.tunallama/memory.db
db_path = "~/.tunallama/memory.db"
# Korean tokenizer: kiwi (recommended, faster) | konlpy_okt | none
korean_tokenizer = "kiwi"
# Whether to record every delegation call. Off = stateless mode.
enable_logging = true
# Whether the recall tool is exposed to the plugin.
enable_recall = true

[routing]
# When the architect calls a delegation tool, should we auto-attach
# relevant past calls from memory? "always" | "on_request" | "never"
auto_recall = "on_request"
# Max past calls to surface in any single recall response.
recall_limit = 5

[logging]
level = "INFO"
file = "~/.tunallama/tunallama.log"
```

The app refuses to start without `config.toml` and prints the path to `config.example.toml`.

## 5. Backend — `tunallama_core`

### 5.1 Public API

The plugin layer (and any future Codex frontend) consumes the backend through a small public API. Keep this surface minimal — anything else is internal.

```python
# tunallama_core/__init__.py exports

from .config import Config, load_config
from .delegation import (
    DelegationResult,       # dataclass: text, model, duration_ms, tokens_used
    generate_code,
    review_code,
    explain_code,
    refactor_code,
    fix_code,
    write_tests,
    general_task,
    review_file,            # file-aware: reads file inside backend
    explain_file,
    analyze_files,
)
from .memory import (
    MemoryStore,            # context-managed SQLite wrapper
    RecallResult,           # dataclass: snippets, sources
    recall,                 # search past calls + return summary
)
```

Frontends build their tool surface (MCP tools, App Server methods, etc.) on top of these. The backend itself does no MCP.

### 5.2 Delegation tools — what to build

Pattern reference: OllamaClaude's 11 tools. Reimplement, do not copy. Eight tools cover the practical surface:

| Tool | Input | Output | Notes |
|---|---|---|---|
| `generate_code` | requirements (str), language (str, optional) | code (str) | Most common path |
| `review_code` | code (str), focus (str, optional: "security"/"performance"/etc) | review (str) | |
| `explain_code` | code (str), audience ("beginner"/"expert", optional) | explanation (str) | |
| `refactor_code` | code (str), goal (str) | refactored code (str) | |
| `fix_code` | code (str), error (str) | fixed code (str) | |
| `write_tests` | code (str), framework (str, optional) | test code (str) | |
| `general_task` | task (str), context (str, optional) | result (str) | Catch-all |
| `review_file` | file_path (str), focus (str, optional) | review (str) | **File-aware: reads file in backend, ~98% token savings vs reading file into Claude conversation first** |
| `explain_file` | file_path (str), audience (str, optional) | explanation (str) | File-aware |
| `analyze_files` | file_paths (list[str]), question (str) | analysis (str) | Multi-file relationships |

Each tool has a hardcoded prompt template. Templates live in `tunallama_core/delegation.py` as constants. Show the templates in code — they are part of what users learn from the project, not an implementation detail to hide.

Every tool call must:

1. Build prompt from template + inputs.
2. Call Ollama via `ollama_client.py`.
3. (If `enable_logging`) record the call in SQLite (see §5.4).
4. Return `DelegationResult`.

### 5.3 Ollama client wrapper

Thin wrapper around the `ollama` Python package. ~30 lines. Should:

- Read config for host/model/temperature/num_ctx/timeout.
- Catch `ollama.ResponseError` and raise a `tunallama_core.OllamaError` with a useful message.
- Return raw text (don't parse — let callers decide).
- Not handle retries (callers handle retry policy if needed).

### 5.4 Memory — SQLite + Korean tokenization

This is what differentiates tunaLlama from a stock OllamaClaude reimplementation. The memory store records every delegation call so future sessions can recall past work.

#### Schema

```sql
-- tunallama_core/memory/schema.sql

CREATE TABLE IF NOT EXISTS calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,           -- ISO 8601
    tool_name TEXT NOT NULL,           -- 'generate_code', 'review_file', etc
    inputs_json TEXT NOT NULL,         -- JSON of all inputs
    output TEXT NOT NULL,              -- raw model output
    model TEXT NOT NULL,               -- which Ollama model was used
    duration_ms INTEGER NOT NULL,
    tokens_estimated INTEGER,          -- rough estimate, may be NULL
    project_root TEXT,                 -- absolute path of CWD at call time
    session_id TEXT,                   -- caller-provided, may be NULL
    tags TEXT                          -- JSON array of strings, optional
);

CREATE INDEX idx_calls_timestamp ON calls(timestamp);
CREATE INDEX idx_calls_project_root ON calls(project_root);
CREATE INDEX idx_calls_tool_name ON calls(tool_name);

-- FTS5 virtual table over inputs + output
-- Tokenizer: 'unicode61' as base + custom tokenization done in Python
-- before insert (Korean morpheme analysis happens at write time, not query)
CREATE VIRTUAL TABLE IF NOT EXISTS calls_fts USING fts5(
    inputs_text,                       -- pre-tokenized
    output_text,                       -- pre-tokenized
    content='calls',
    content_rowid='id',
    tokenize='unicode61 remove_diacritics 2'
);

-- Triggers to keep FTS in sync
CREATE TRIGGER IF NOT EXISTS calls_ai AFTER INSERT ON calls BEGIN
    INSERT INTO calls_fts(rowid, inputs_text, output_text)
    VALUES (new.id, new.inputs_json, new.output);
END;

CREATE TRIGGER IF NOT EXISTS calls_ad AFTER DELETE ON calls BEGIN
    INSERT INTO calls_fts(calls_fts, rowid, inputs_text, output_text)
    VALUES('delete', old.id, old.inputs_json, old.output);
END;
```

#### Korean tokenization

FTS5's `unicode61` tokenizer treats Korean as raw character chunks, which is bad for search recall. Solve this by **pre-tokenizing in Python before insert**:

1. Detect if text contains Korean (Hangul Unicode range).
2. If yes, run through Kiwi (`pip install kiwipiepy`) to extract morphemes.
3. Insert space-separated morphemes into FTS instead of raw text.

This gives correct Korean search recall without writing a custom SQLite tokenizer extension.

```python
# tunallama_core/memory/tokenize.py

from kiwipiepy import Kiwi

_kiwi = Kiwi()

def korean_morphemes(text: str) -> str:
    """Return space-separated morphemes for Korean text. Pass through for non-Korean."""
    if not _has_korean(text):
        return text
    tokens = _kiwi.tokenize(text)
    # Keep nouns, verbs, adjectives. Drop particles and endings.
    keep_tags = {'NNG', 'NNP', 'VV', 'VA', 'MAG', 'MAJ', 'SL'}
    return ' '.join(t.form for t in tokens if t.tag in keep_tags) + ' ' + text
    # Append original text so non-morpheme matches still work
```

Make tokenizer choice configurable. Defaults to Kiwi. Fallback to KoNLPy Okt if Kiwi unavailable. Can be disabled entirely (`korean_tokenizer = "none"`).

#### Recall

```python
# tunallama_core/memory/search.py

@dataclass
class RecallResult:
    snippets: list[RecallSnippet]
    total_matches: int
    query: str

@dataclass
class RecallSnippet:
    timestamp: str
    tool_name: str
    inputs_summary: str         # 1-line summary of what was asked
    output_excerpt: str         # first ~200 chars
    score: float                # BM25 score from FTS5
    full_id: int                # for caller to fetch full record if needed

def recall(query: str, *, limit: int = 5, project_root: str | None = None) -> RecallResult:
    """Search past calls. Returns ranked snippets, not full records."""
    # SELECT ... FROM calls_fts WHERE calls_fts MATCH ? ORDER BY rank LIMIT ?
    # Optionally filter by project_root
    # Truncate snippets to keep recall response itself token-light
```

Recall response is **summary-first**. Never return full original outputs unless caller explicitly requests by `full_id`. The whole point is keeping the recall result small enough not to blow Claude's context.

### 5.5 Routing

Routing decides whether a delegation call should also pull recall context. Three modes from config:

- `always`: every delegation call automatically attaches top-3 recall snippets to the model's prompt. Useful when working on a codebase you've used tunaLlama on before.
- `on_request`: only attach recall when the caller explicitly passes `recall_query`. **Default.**
- `never`: ignore recall entirely. Tools behave statelessly.

Plugin layer decides whether to expose recall as a separate tool, attach automatically, or both.

## 6. Plugin — `plugin/`

This layer is thin. It does three things: expose backend tools as MCP tools, ship Skills/Subagent/Hooks definitions for Claude Code, and handle plugin-specific concerns (tool naming, permission boundaries).

### 6.1 plugin.json manifest

Reference: https://code.claude.com/docs/en/plugins

```json
{
  "name": "tunaLlama",
  "version": "0.1.0",
  "description": "Delegate heavy code generation to local Ollama. Save tokens, keep oversight.",
  "author": "hang-in",
  "license": "MIT"
}
```

Lives at `plugin/.claude-plugin/plugin.json`. **Only this file goes inside `.claude-plugin/`.** All other directories (skills/, agents/, hooks/, .mcp.json) live at plugin root.

### 6.2 MCP server — `plugin/mcp_server.py`

Use FastMCP (`pip install mcp`). Expose backend tools as MCP tools with namespaced names: `tuna_generate_code`, `tuna_review_file`, etc.

Skeleton:

```python
from mcp.server.fastmcp import FastMCP
from tunallama_core import (
    load_config, generate_code as core_generate_code,
    review_file as core_review_file, recall as core_recall,
    # ... etc
)

mcp = FastMCP("tunaLlama")
config = load_config()

@mcp.tool()
async def tuna_generate_code(requirements: str, language: str = "") -> str:
    """Generate code via local Ollama. Use for fresh implementation tasks where
    you have clear requirements but don't want to spend tokens on the long output."""
    result = core_generate_code(requirements, language=language or None, config=config)
    return result.text

@mcp.tool()
async def tuna_review_file(file_path: str, focus: str = "") -> str:
    """Review a file via local Ollama by passing the path. The file is read inside
    the backend, so the file content does NOT enter Claude's context. Use this
    instead of reading the file first then asking for review."""
    result = core_review_file(file_path, focus=focus or None, config=config)
    return result.text

@mcp.tool()
async def tuna_recall(query: str, limit: int = 5) -> str:
    """Search past Ollama delegations for similar work. Returns ranked summaries.
    Useful before starting on a familiar codebase to surface prior decisions."""
    result = core_recall(query, limit=limit)
    return _format_recall_for_claude(result)

# ... register all 10 backend tools

if __name__ == "__main__":
    mcp.run()
```

Register the server in `.mcp.json` at plugin root:

```json
{
  "mcpServers": {
    "tunallama": {
      "command": "python",
      "args": ["-m", "plugin.mcp_server"]
    }
  }
}
```

### 6.3 Skills — `plugin/skills/delegate-to-ollama/SKILL.md`

This is what teaches Claude **when** to use the tools. Without a skill, Claude won't know that `tuna_review_file` exists or when to prefer it over its built-in `Read` tool.

```markdown
---
name: delegate-to-ollama
description: Delegate token-heavy coding work to a local Ollama model via tunaLlama. Use this when the user asks for code generation, file review, refactoring, or any task where the output would be long. Saves tokens by running the heavy generation locally while you maintain oversight.
---

# When to use tunaLlama tools

You have access to `tuna_*` tools backed by a local Ollama model. Use them when:

1. **The user asks for code generation** and you have clear requirements.
   Use `tuna_generate_code` instead of generating the code yourself.

2. **The user asks to review or analyze a file**.
   Use `tuna_review_file` (passing the path) instead of reading the file first.
   The file content stays out of your context — major token savings.

3. **The user asks for refactoring or test writing** with a defined scope.
   Use `tuna_refactor_code` or `tuna_write_tests`.

# When NOT to delegate

- Tasks requiring deep judgment about architecture or design — keep these yourself.
- Short snippets (< 10 lines) — overhead exceeds savings.
- Tasks that require knowledge of recent conversation context Ollama doesn't have.
- Anything safety-critical or involving the user's intent interpretation.

# Standard pattern: delegate then verify

1. Decompose the user's request into clear instructions for Ollama.
2. Call the appropriate `tuna_*` tool.
3. Review the output. Catch obvious problems.
4. If the output looks wrong, call `tuna_fix_code` with the error description.
5. Present the verified result to the user.

# Recall

Before starting non-trivial work in a familiar codebase, consider calling
`tuna_recall` with keywords from the current request. Past delegations on the
same codebase often surface useful prior decisions.
```

### 6.4 Subagent — `plugin/agents/tuna-developer.md`

```markdown
---
name: tuna-developer
description: A purpose-built subagent that delegates code generation to local Ollama and verifies the result. Use this when the user wants you to write a substantial piece of code and you want to save tokens.
---

You are tuna-developer. Your job is to coordinate code generation between the user, local Ollama, and yourself.

When invoked:

1. Clarify requirements with the user if needed (one round of questions max).
2. Call `tuna_generate_code` with the clarified requirements.
3. Review Ollama's output. Specifically check:
   - Does it match the requirements?
   - Are there obvious bugs?
   - Are imports/dependencies correct?
4. If problems exist, call `tuna_fix_code` with a description.
5. Present the final code to the user with a 1-2 sentence summary of what Ollama produced.

Token budget guidance: aim to keep your own output under 500 tokens. Ollama produces the long output, you produce the verification.
```

### 6.5 Hooks — `plugin/hooks/pre_tool_use.py` (optional)

This is the most complex piece. **Make it optional and off by default.** Reasoning: hooks that auto-redirect tool calls are powerful but risky — users should opt in.

When enabled, the hook intercepts Claude's `Read` tool calls. If the file is large enough that reading it would consume significant tokens, the hook can suggest (not force) using `tuna_review_file` instead.

Skip implementing this in the first pass. Ship Phase 1 without auto-routing hooks. Add in a Phase 1.5 if time allows.

## 7. Reference for the implementing agent

### 7.1 Context to read before starting

If unfamiliar with these, read briefly:

- **OllamaClaude README** (https://github.com/Jadael/OllamaClaude) — pattern reference. Do NOT copy code.
- **Claude Code Plugins docs** (https://code.claude.com/docs/en/plugins) — plugin manifest, structure rules.
- **FastMCP docs** (https://github.com/modelcontextprotocol/python-sdk) — MCP server skeleton.
- **kiwipiepy README** (https://github.com/bab2min/kiwipiepy) — Korean tokenizer API.

### 7.2 Implementation order

Build in this sequence. Each step must work end-to-end before the next.

1. **Repo skeleton + pyproject.toml + README outline.** No code yet.
2. **Config loading.** `tunallama_core/config.py`. Test: load `config.example.toml`, validate required fields.
3. **Ollama client wrapper.** Test: connect to a running Ollama, call a model, get text back.
4. **One delegation tool: `generate_code`.** Headless test: call from Python REPL, verify output.
5. **MCP server skeleton with one tool exposed: `tuna_generate_code`.** Run via `python -m plugin.mcp_server`, verify Claude Code sees it.
6. **All 10 delegation tools.** Backend + MCP exposure.
7. **SQLite schema + insert on every call.** Verify rows appear.
8. **Korean tokenization on insert.** Verify Korean text gets morpheme-split in `calls_fts`.
9. **Recall.** Backend `recall()` function + `tuna_recall` MCP tool. Test: insert mixed Korean/English calls, search by partial Korean keyword, verify hit.
10. **Skill + Subagent files.** Verify Claude Code loads them via `/plugin install --plugin-dir ./plugin`.
11. **End-to-end test scenarios** (see §7.4).
12. **README + CHANGELOG.**

### 7.3 Dependencies (`pyproject.toml`)

```toml
[project]
name = "tunallama"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "ollama>=0.4.0",
    "mcp>=1.0.0",
    "kiwipiepy>=0.20.0",
    "tomli; python_version < '3.11'",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-asyncio>=0.24"]
```

### 7.4 End-to-end test scenarios

These should pass before merging Phase 1.

**Scenario A — basic delegation**:
1. User asks Claude Code: "Write a Python function that validates email addresses."
2. Claude calls `tuna_generate_code` with the requirement.
3. Ollama produces a function.
4. Claude reviews, verifies, presents to user.
5. SQLite has one new row in `calls`.

**Scenario B — file-aware token savings**:
1. User asks: "Review src/auth.py for security issues."
2. Claude calls `tuna_review_file` (NOT `Read` first).
3. The file's content never enters Claude's context.
4. Ollama produces a review.
5. SQLite has one new row, `inputs_json` contains the file path but not the content.

**Scenario C — Korean recall**:
1. User runs Scenario A with a Korean comment in requirements.
2. Three days later, user asks: "내가 전에 이메일 검증 코드 만든 적 있나?"
3. Claude calls `tuna_recall` with "이메일 검증".
4. The earlier call surfaces. (Without Korean tokenization, this fails — characters don't match the morpheme structure.)

**Scenario D — config error handling**:
1. Run with no `config.toml`.
2. Plugin reports clear error pointing to `config.example.toml`.
3. Run with `config.toml` pointing to non-existent Ollama model.
4. First tool call returns clear error, doesn't crash MCP server.

### 7.5 What success looks like

After Phase 1, a user should be able to:

1. `git clone` the repo.
2. `pip install -e .`
3. Copy and edit `config.example.toml`.
4. `claude --plugin-dir ./plugin` (or install via marketplace once published).
5. Ask Claude to do coding work and watch tokens stay low because heavy generation goes local.
6. Ask "what did we work on yesterday" and get a summary back from SQLite.

## 8. Out of scope for Phase 1

Do not build any of the following. They belong to later phases or other projects.

- Codex CLI integration (Phase 4 — separate handoff)
- Codex App Server client (Phase 4 — separate handoff)
- Web/app UI (Phase 5 — separate handoff)
- Multi-model roundtable (out of scope for tunaLlama; that's tunaFlow's job)
- Automatic hook-based tool redirection (Phase 1.5 — defer)
- Vector search / embeddings (Phase 2 candidate, not Phase 1)
- Telegram/Discord/Slack integration (out of scope)
- TerminalSync-style PTY mirroring (different category, not part of tunaLlama)

If you find yourself wanting to add any of these, stop and flag for a planning session instead.

## 9. Notes on style and tone

This is a public OSS repo aimed at the Korean developer community (damoang.net specifically) and the broader Claude Code user base. README should be:

- English first, with a Korean section after.
- Plain language. No marketing words ("powerful", "revolutionary", "blazing fast").
- Honest about limits. The "What this is NOT" section in this handoff should be reflected in the README.
- Show concrete numbers where possible (token savings, query times) but only if measured.

Code comments should explain **why**, not what. Especially in `delegation.py` (the prompt templates) and `memory/tokenize.py` (the Korean handling) — these are the parts that teach readers the pattern.

## 10. License and attribution

- License: **MIT**.
- README must mention OllamaClaude as a pattern reference (not a fork).
- README must mention that the project is independent of tunaFlow despite the shared `tuna*` naming convention.

---

## Acceptance for Phase 1

Phase 1 is complete when:

- All 4 test scenarios in §7.4 pass.
- `pip install -e .` succeeds on a fresh Python 3.11+ env.
- `claude --plugin-dir ./plugin` loads the plugin without errors.
- README walks a new user from zero to first successful delegation.
- CHANGELOG records the version and key decisions.

After Phase 1 ships and gets feedback, Phase 4 (Codex App Server frontend) starts. A separate handoff document will be written then. The backend boundary defined in this handoff is what makes that future work cheap.

---

**End of handoff. Ready to begin implementation.**
